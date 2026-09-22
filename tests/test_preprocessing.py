import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from pitch_analysis.preprocessing.naming import (
    clip_filename,
    parse_clip_range,
    parse_timestamp,
    slugify,
)
from pitch_analysis.preprocessing.motion import candidate_ranges_from_scores
from pitch_analysis.preprocessing.reid import ClipReIdentifier
from pitch_analysis.preprocessing.source import acquire_source, is_url, redact_url
from pitch_analysis.preprocessing.workflow import preprocess_video


class PreprocessingNamingTests(unittest.TestCase):
    def test_timestamp_and_range_parsing(self) -> None:
        self.assertEqual(parse_timestamp("1:02.5"), 62.5)
        self.assertEqual(parse_timestamp("01:02:03"), 3723.0)
        self.assertEqual(parse_clip_range("00:11-00:30"), (11.0, 30.0))
        with self.assertRaises(ValueError):
            parse_clip_range("30-11")

    def test_clip_name_is_deterministic_and_safe(self) -> None:
        self.assertEqual(slugify("Yu Darvish"), "yu_darvish")
        self.assertEqual(
            clip_filename("Yu Darvish", "2025", "Rear Centerfield", "abc-123", 2),
            "yu_darvish_2025_rear_centerfield_abc_123_pitch_02.mp4",
        )

    def test_motion_scores_create_separated_review_candidates(self) -> None:
        times = [float(index) for index in range(20)]
        scores = [0.01] * 20
        scores[5] = 1.0
        scores[14] = 0.8

        candidates = candidate_ranges_from_scores(
            times,
            scores,
            duration_seconds=20.0,
            pre_seconds=1.0,
            post_seconds=2.0,
            min_peak_interval_seconds=3.0,
        )

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["start_second"], 4.0)
        self.assertEqual(candidates[1]["motion_peak_second"], 14.0)


class SourceAcquisitionTests(unittest.TestCase):
    def test_url_detection_and_manifest_redaction(self) -> None:
        self.assertTrue(is_url("https://example.com/video?id=secret"))
        self.assertFalse(is_url("C:/videos/pitch.mp4"))
        self.assertEqual(
            redact_url("https://example.com/video?id=secret#part"),
            "https://example.com/video",
        )

    def test_local_source_is_not_copied_or_modified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.mp4"
            source.write_bytes(b"video-placeholder")

            result = acquire_source(source, Path(directory) / "unused")

            self.assertEqual(result["kind"], "local_file")
            self.assertEqual(Path(result["acquired_path"]), source)
            self.assertEqual(source.read_bytes(), b"video-placeholder")


class ReIdentificationTests(unittest.TestCase):
    class FakeBackend:
        def embed(self, image):
            return image

    def test_equal_reference_prototype_matches_expected_pitcher(self) -> None:
        matcher = ClipReIdentifier(self.FakeBackend(), threshold=0.5)
        matcher.register("pitcher_a", [[1.0, 0.0], [0.9, 0.1]])
        matcher.register("pitcher_b", [[0.0, 1.0]])

        result = matcher.match_embeddings(
            [
                np.array([1.0, 0.0]),
                np.array([0.8, 0.2]),
            ]
        )

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["pitcher_id"], "pitcher_a")

    def test_close_top_scores_are_ambiguous(self) -> None:
        matcher = ClipReIdentifier(
            self.FakeBackend(), threshold=0.2, ambiguity_margin=0.05
        )
        matcher.register("pitcher_a", [[1.0, 0.0]])
        matcher.register("pitcher_b", [[0.0, 1.0]])

        result = matcher.match_embeddings([np.array([1.0, 1.0])])

        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["pitcher_id"])


class PreprocessingWorkflowTests(unittest.TestCase):
    def test_workflow_writes_reviewable_clips_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job"

            def fake_acquire(_source, _output_dir, *, ffmpeg=None):
                path = Path(directory) / "downloaded.mp4"
                path.write_bytes(b"download")
                return {
                    "kind": "url",
                    "source": "https://example.com/video",
                    "acquired_path": str(path),
                    "sha256": "source-hash",
                    "remote_metadata": {"source_video_id": "video-123"},
                }

            def fake_standardize(_source, output, *, target_fps, ffmpeg=None):
                output = Path(output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"standardized")
                return {"path": str(output), "target_fps": target_fps}

            def fake_extract(_source, output, *, start_second, end_second, ffmpeg=None):
                output = Path(output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"clip")
                return {
                    "path": str(output),
                    "sha256": "clip-hash",
                    "start_second": start_second,
                    "end_second": end_second,
                    "output_probe": {"duration_seconds": end_second - start_second},
                    "review_status": "needs_human_review",
                }

            with (
                patch("pitch_analysis.preprocessing.workflow.resolve_ffmpeg", return_value="ffmpeg"),
                patch("pitch_analysis.preprocessing.workflow.acquire_source", side_effect=fake_acquire),
                patch("pitch_analysis.preprocessing.workflow.standardize_video", side_effect=fake_standardize),
                patch("pitch_analysis.preprocessing.workflow.extract_clip", side_effect=fake_extract),
            ):
                result = preprocess_video(
                    "https://example.com/video?token=secret",
                    root,
                    pitcher_id="Yu Darvish",
                    season="2025",
                    throws="RIGHT",
                    view="rear_centerfield_broadcast",
                    clip_ranges=[(11.0, 15.0), (20.0, 24.0)],
                )

            self.assertEqual(result["status"], "clips_ready_for_human_review")
            self.assertEqual(len(result["clips"]), 2)
            self.assertTrue(all(Path(clip["path"]).exists() for clip in result["clips"]))
            self.assertEqual(
                result["clips"][0]["analysis_handoff"]["command"],
                "prepare-segment",
            )
            saved = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["pitcher"]["pitcher_id"], "yu_darvish")
            self.assertEqual(saved["source"]["source"], "https://example.com/video")

    def test_workflow_refuses_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "job"
            root.mkdir()
            (root / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                preprocess_video(
                    "anything",
                    root,
                    pitcher_id="pitcher",
                    season="2026",
                    throws="RIGHT",
                    view="rear_centerfield_broadcast",
                    clip_ranges=[(0.0, 1.0)],
                )


if __name__ == "__main__":
    unittest.main()
