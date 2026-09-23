"""Contract, decode, environment-boundary and existing-pipeline handoff checks."""
from __future__ import annotations

import csv
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pitch_analysis.analysis.pitch import analyze_pitch
from pitch_analysis.contracts import load_input, validate_contract
from pitch_analysis.video.standardization import standardize_mp4
from pitch_analysis.video.validation import validate_mp4


def metadata(pitcher: str, pitch: str, filename: str) -> dict:
    return {
        "schema_version": "pitch-input-v1", "pitch_id": pitch,
        "pitcher": {"id": pitcher, "throws": "RIGHT"},
        "video": {"file": filename, "camera_view": "rear_centerfield_broadcast",
                  "horizontal_mirror": False, "playback_speed": 1.0,
                  "contains_single_pitch": True, "continuous_shot": True,
                  "subject_framing": "full_body"},
    }


def make_video(path: Path, fps: float = 30.0) -> None:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (96, 128))
    assert writer.isOpened()
    for index in range(12):
        image = np.full((128, 96, 3), 30 + index, np.uint8)
        writer.write(image)
    writer.release()


def fake_prepare(video, output_dir, *, video_id, throwing_side, model_path, start_second, end_second, reference_context, quality, subject_selection=None):
    """Same artifact contract as prepare_segment, with deterministic pose observations."""
    target = Path(output_dir)
    target.mkdir()
    rows = [
        {"frame": 0, "timestamp_ms": 0, "landmark": "NOSE", "x": .5, "y": .2, "z": 0, "visibility": .9, "presence": .8},
        {"frame": 2, "timestamp_ms": 67, "landmark": "NOSE", "x": .51, "y": .2, "z": 0, "visibility": .9, "presence": .8},
    ]
    with (target / "pose_raw.csv").open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    (target / "pose_raw.capture.json").write_text(json.dumps({"fps": 30, "start_frame": 0, "end_frame": 11,
                                                                     "requested_frames": 12, "processed_frames": 12, "detected_frames": 2,
                                                                     "video": str(video), "width": 96, "height": 128,
                                                                     "subject_selection": subject_selection,
                                                                     "selection_frames": [{"frame_index": frame, "status": "selected" if frame in (0, 2) else "rejected", "candidate_count": 1 if frame in (0, 2) else 0} for frame in range(12)]}), encoding="utf-8")
    (target / "events.json").write_text(json.dumps({"video_id": video_id, "throws": throwing_side,
                                                     "review_status": "needs_human_review", "events": {}}), encoding="utf-8")
    (target / "metadata.json").write_text(json.dumps({"capture": {"video": str(video)},
                                                       "reference_context": reference_context}), encoding="utf-8")
    with (target / "features.csv").open("w", encoding="utf-8", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=["frame", "throwing_knee_angle", "throwing_knee_angle_raw_observed"])
        writer.writeheader()
        writer.writerow({"frame": 0, "throwing_knee_angle": 90, "throwing_knee_angle_raw_observed": True})
        writer.writerow({"frame": 1, "throwing_knee_angle": 180, "throwing_knee_angle_raw_observed": False})
    return {"detected_frames": 2, "quality_gate_passed": False, "event_review": str(target / "events.json")}


class Phase0InputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "pitch_001.mp4"
        make_video(self.video)
        self.meta = self.root / "pitch_001.json"
        self.meta.write_text(json.dumps(metadata("pitcher_a", "pitch_001", self.video.name)), encoding="utf-8")

    def test_contract_and_local_decoding(self):
        self.assertEqual(load_input(self.video, self.meta)["pitch_id"], "pitch_001")
        report = validate_mp4(self.video)
        self.assertEqual(report["frame_count"], 12)
        self.assertEqual(len(report["timestamps_ms"]), 12)
        self.assertEqual(report["timestamps_ms"][0], 0)
        self.assertAlmostEqual(report["fps"], 30)

    def test_approximate_header_fps_uses_constant_presentation_timeline(self):
        import cv2
        import numpy as np

        class ApproximateHeaderCapture:
            index = 0

            def isOpened(self):
                return True

            def get(self, prop):
                return {
                    cv2.CAP_PROP_FPS: 30.0296915,
                    cv2.CAP_PROP_FRAME_COUNT: 12,
                    cv2.CAP_PROP_FRAME_WIDTH: 96,
                    cv2.CAP_PROP_FRAME_HEIGHT: 128,
                    cv2.CAP_PROP_ORIENTATION_META: 0,
                    cv2.CAP_PROP_SAR_NUM: 1,
                    cv2.CAP_PROP_SAR_DEN: 1,
                    cv2.CAP_PROP_FOURCC: cv2.VideoWriter_fourcc(*"mp4v"),
                    cv2.CAP_PROP_POS_MSEC: (self.index - 1) * 1000 / 30,
                }[prop]

            def read(self):
                if self.index == 12:
                    return False, None
                self.index += 1
                return True, np.zeros((128, 96, 3), np.uint8)

            def release(self):
                pass

        with patch("cv2.VideoCapture", return_value=ApproximateHeaderCapture()):
            report = validate_mp4(self.video)
        self.assertAlmostEqual(report["fps"], 30)
        self.assertAlmostEqual(report["header_fps"], 30.0296915)
        self.assertTrue(any("header_fps_approximate" in item for item in report["warnings"]))

    def test_input_rejects_source_fields_and_unsupported_claims(self):
        value = metadata("pitcher_a", "pitch_001", self.video.name)
        for alteration in (lambda p: p.update(source_url="https://example.com/video"),
                           lambda p: p["video"].update(horizontal_mirror=True),
                           lambda p: p["video"].update(camera_view="side"),
                           lambda p: p["video"].update(playback_speed=.5),
                           lambda p: p["video"].update(continuous_shot=False)):
            changed = json.loads(json.dumps(value))
            alteration(changed)
            with self.assertRaises(ValueError):
                validate_contract(changed, "pitch-input-v1")
        another = self.root / "another.mp4"
        shutil.copyfile(self.video, another)
        with self.assertRaises(ValueError):
            load_input(another, self.meta)

    def test_corrupt_and_unsupported_inputs_fail(self):
        damaged = self.root / "damaged.mp4"
        damaged.write_bytes(b"not a video")
        with self.assertRaises(ValueError):
            validate_mp4(damaged)
        with self.assertRaises(ValueError):
            validate_mp4(self.video, max_duration_seconds=.1)

    def test_native_fps_standardization(self):
        standardized = self.root / "working.mp4"
        result = standardize_mp4(self.video, standardized)
        self.assertEqual(result["frame_count"], 12)
        self.assertAlmostEqual(result["fps"], 30)
        self.assertEqual(result["codec_fourcc"].lower(), "h264")
        with self.assertRaises(FileExistsError):
            standardize_mp4(self.video, standardized)

    def test_standardized_analysis_handoff_uses_local_working_copy(self):
        model = self.root / "model.task"
        model.write_bytes(b"model fixture")
        with patch("pitch_analysis.analysis.pitch.prepare_segment", side_effect=fake_prepare) as worker:
            result = analyze_pitch(self.video, self.meta, output_root=self.root / "standardized", model_path=model, standardize=True)
        target = Path(result["output_dir"])
        self.assertEqual(Path(worker.call_args.args[0]), target / "working.mp4")
        self.assertIsNone(worker.call_args.kwargs["end_second"])
        manifest = json.loads((target / "analysis.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["provenance"]["standardization"], "h264_yuv420p_native_fps")
        self.assertTrue((target / "working_video_metadata.json").exists())
        self.assertEqual(manifest["provenance"]["analysis_video_sha256"],
                         json.loads((target / "working_video_metadata.json").read_text(encoding="utf-8"))["sha256"])

    def test_analysis_handoff_multiple_pitchers_and_no_overwrite(self):
        model = self.root / "model.task"
        model.write_bytes(b"model fixture")
        out = self.root / "results"
        with patch("pitch_analysis.analysis.pitch.prepare_segment", side_effect=fake_prepare):
            first = analyze_pitch(self.video, self.meta, output_root=out, model_path=model)
            self.assertEqual(first["status"], "quality_gate_failed")
            target = out / "pitcher_a" / "pitch_001"
            self.assertTrue((target / "events.json").exists())
            self.assertTrue((target / "pose_raw.csv").exists())
            self.assertFalse((target / "core").exists())
            keypoints = json.loads((target / "keypoints.json").read_text(encoding="utf-8"))
            self.assertEqual(len(keypoints["frames"]), 12)
            self.assertFalse(keypoints["frames"][1]["detected"])
            self.assertEqual(keypoints["frames"][0]["landmarks"][0]["confidence"], .9)
            metrics = json.loads((target / "metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(metrics["metrics"]["throwing_knee_angle"]["observed_frames"], 1)
            self.assertEqual(metrics["metrics"]["throwing_knee_angle"]["median"], 90)
            quality = json.loads((target / "keypoint_quality.json").read_text(encoding="utf-8"))
            self.assertEqual(quality["frames_with_valid_pitcher_pose"], 2)
            self.assertEqual(quality["rejected_frame_count"], 10)
            import cv2
            overlay = cv2.VideoCapture(str(target / "overlay.mp4"))
            self.assertEqual(int(overlay.get(cv2.CAP_PROP_FRAME_COUNT)), 12)
            overlay.release()
            with self.assertRaises(FileExistsError):
                analyze_pitch(self.video, self.meta, output_root=out, model_path=model)
            # Same pitch_id under a different pitcher is an independent analysis.
            other = self.root / "other.json"
            other.write_text(json.dumps(metadata("pitcher_b", "pitch_001", self.video.name)), encoding="utf-8")
            second = analyze_pitch(self.video, other, output_root=out, model_path=model)
            self.assertEqual(second["status"], "quality_gate_failed")
            self.assertTrue((out / "pitcher_b" / "pitch_001" / "analysis.json").exists())

    def test_real_mediapipe_on_synthetic_video_reports_no_pose(self):
        model = Path(__file__).resolve().parents[1] / "models" / "pose_landmarker_full.task"
        result = analyze_pitch(self.video, self.meta, output_root=self.root / "real_results", model_path=model)
        self.assertEqual(result["status"], "no_pose")
        output = self.root / "real_results" / "pitcher_a" / "pitch_001"
        self.assertFalse((output / "events.json").exists())
        self.assertEqual(len(json.loads((output / "keypoints.json").read_text(encoding="utf-8"))["frames"]), 12)
        self.assertEqual(json.loads((output / "metrics.json").read_text(encoding="utf-8"))["metrics"], {})
        self.assertEqual(len((output / "keypoints.jsonl").read_text(encoding="utf-8").splitlines()), 12)
        self.assertEqual(len((output / "processed_keypoints.jsonl").read_text(encoding="utf-8").splitlines()), 12)
        quality = json.loads((output / "keypoint_quality.json").read_text(encoding="utf-8"))
        self.assertEqual(quality["status"], "failed")
        self.assertEqual(quality["frames_with_valid_pitcher_pose"], 0)
        self.assertEqual(quality["longest_missing_pose_gap"], 12)
        self.assertEqual(json.loads((output / "review" / "human_validation_template.json").read_text(encoding="utf-8"))["review_status"], "pending")
        self.assertTrue((output / "overlay.mp4").exists())


if __name__ == "__main__":
    unittest.main()
