import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.ground_truth import (
    EVENT_NAMES,
    FULL_INTERVAL_LABELS,
    FULL_JOINT_LABELS,
    blank_ground_truth,
    expand_blank_review,
    load_ground_truth,
)


spec = importlib.util.spec_from_file_location(
    "import_peer_ground_truth",
    Path(__file__).resolve().parents[1] / "scripts" / "import_peer_ground_truth.py",
)
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


class PeerGroundTruthImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        repository = patch.object(importer, "REPOSITORY_ROOT", self.root)
        repository.start()
        self.addCleanup(repository.stop)
        self.video = self.root / "pitch_003.mp4"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
        self.assertTrue(writer.isOpened())
        for index in range(10):
            writer.write(np.full((64, 64, 3), index * 20, np.uint8))
        writer.release()
        self.assertEqual(importer._decoded_frame_count(self.video), 10)
        self.review = self.root / "returned_review.json"
        self.output_root = self.root / "annotations" / "phase2_peer_reviews"

    def partial(self, *, video=None, pitch_id="pitch_003"):
        payload = expand_blank_review(blank_ground_truth(video or self.video, pitch_id, 10))
        payload["annotation_status"] = "in_progress"
        payload["provenance"]["reviewer"] = "同學 A"
        payload["labels"]["events"]["approximate_release"] = {
            "status": "uncertain", "frame_index": None,
            "frame_range": {"start_frame": 5, "end_frame": 7},
            "confidence": None, "note": "球與手重疊，範圍保留。",
        }
        payload["notes"] = ["獨立人工判讀；此句原文保留。", "尚未檢查其他關節。"]
        return payload

    def completed(self):
        payload = self.partial()
        payload["annotation_status"] = "reviewed"
        payload["provenance"]["reviewed_at_utc"] = "2026-10-03T08:30:00+00:00"
        labels = payload["labels"]
        labels["pitcher_selection_review"] = {
            "status": "uncertain", "confidence": None, "note": "開始被遮住，無法确认。",
        }
        for name in FULL_INTERVAL_LABELS:
            labels[name] = []
        for name in FULL_JOINT_LABELS:
            labels[name] = [
                {"start_frame": 0, "end_frame": 4, "status": "reliable", "reason": "", "confidence": 0.8},
                {"start_frame": 5, "end_frame": 9, "status": "not_observable", "reason": "人體遮住", "confidence": None, "note": "未推測位置"},
            ]
        for frame, name in enumerate(EVENT_NAMES):
            labels["events"][name] = {
                "status": "annotated", "frame_index": frame * 2,
                "confidence": None, "note": "人工觀察",
            }
        labels["events"]["approximate_release"] = {
            "status": "uncertain", "frame_index": None,
            "frame_range": {"start_frame": 5, "end_frame": 7},
            "confidence": 0.5, "note": "無法確定單一格。",
        }
        return payload

    def write_review(self, payload, *, bom=False):
        content = json.dumps(payload, ensure_ascii=False, indent=3).encode("utf-8") + b"\r\n"
        if bom:
            content = b"\xef\xbb\xbf" + content
        self.review.write_bytes(content)
        return content

    def import_review(self, **kwargs):
        return importer.import_peer_ground_truth(
            self.review, kwargs.pop("source_video", self.video),
            review_id=kwargs.pop("review_id", "CLASSMATE_20261003"),
            output_root=kwargs.pop("output_root", self.output_root), **kwargs,
        )

    def test_full_review_preserves_bytes_provenance_uncertainty_and_canonical_files(self):
        canonical_root = self.root / "baseline" / "ground_truth"
        canonical = canonical_root / "pitch_003" / "ground_truth.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_bytes(b"existing HSU human review remains byte identical")
        prediction = self.root / "baseline" / "predictions" / "pose.json"
        prediction.parent.mkdir()
        prediction.write_bytes(b"existing prediction remains byte identical")
        before = {path: path.read_bytes() for path in (canonical, prediction, self.video)}
        payload = self.completed()
        content = self.write_review(payload, bom=True)
        with patch.object(importer, "REPOSITORY_ROOT", self.root):
            output = self.import_review()
        self.assertEqual(output, self.output_root / "CLASSMATE_20261003" / "pitch_003" / "ground_truth.json")
        self.assertEqual(output.read_bytes(), content)
        self.assertEqual(load_ground_truth(output, source_video_path=self.video), payload)
        self.assertEqual(self.review.read_bytes(), content)
        for path, original in before.items():
            self.assertEqual(path.read_bytes(), original)
        self.assertEqual(list(self.output_root.rglob("*.*")), [output])

    def test_events_supplement_keeps_in_progress_and_unreviewed_joint_nulls(self):
        video = self.root / "pitch_005.mp4"
        video.write_bytes(self.video.read_bytes())
        payload = self.partial(video=video, pitch_id="pitch_005")
        content = self.write_review(payload)
        output = self.import_review(source_video=video)
        self.assertEqual(output.read_bytes(), content)
        imported = load_ground_truth(output)
        self.assertEqual(imported["annotation_status"], "in_progress")
        self.assertIsNone(imported["provenance"]["reviewed_at_utc"])
        self.assertTrue(all(imported["labels"][name] is None for name in FULL_JOINT_LABELS))
        self.assertEqual(imported, payload)

    def test_source_hash_filename_frame_count_and_pitch_id_mismatches_are_refused(self):
        for field, value, message in (
            ("sha256", "0" * 64, "SHA-256"),
            ("filename", "other.mp4", "filename"),
            ("total_frames", 11, "decoded frames"),
            ("pitch_id", "pitch_005", "pitch_id"),
        ):
            with self.subTest(field=field):
                payload = self.partial()
                payload["source_video"][field] = value
                self.write_review(payload)
                with self.assertRaisesRegex(ValueError, message):
                    self.import_review()
                self.assertFalse(self.output_root.exists())

    def test_review_id_traversal_and_windows_devices_are_refused(self):
        self.write_review(self.partial())
        for review_id in ("", "..", "../escape", "A/escape", "A\\escape", "A:escape", "/absolute", "A ", "A.", "CON", "lpt9", "x" * 81):
            with self.subTest(review_id=review_id):
                with self.assertRaisesRegex(ValueError, "review_id"):
                    self.import_review(review_id=review_id)
        self.assertFalse(self.output_root.exists())

    def test_protected_output_roots_are_refused_without_creating_files(self):
        self.write_review(self.partial())
        with patch.object(importer, "REPOSITORY_ROOT", self.root):
            for relative in (
                "analysis_results/phase2_yamamoto_20260925_01/ground_truth",
                "analysis_results/phase2_yamamoto_20260925_01/predictions",
                "input", "data", "annotations/ground_truth", "annotations/input",
                "annotations/predictions", ".git", ".",
            ):
                with self.subTest(root=relative):
                    target = self.root / relative
                    with self.assertRaisesRegex(ValueError, "output"):
                        self.import_review(output_root=target)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["pitch_003.mp4", "returned_review.json"])

    def test_reviewed_contract_missing_labels_coverage_bounds_order_and_utc_are_refused(self):
        cases = []
        payload = self.completed()
        payload["labels"]["lead_ankle_reliability"] = None
        cases.append((payload, "unannotated"))
        payload = self.completed()
        payload["labels"]["throwing_wrist_reliability"][-1]["end_frame"] = 8
        cases.append((payload, "cover every frame"))
        payload = self.completed()
        payload["labels"]["events"]["leg_lift"]["frame_index"] = 10
        cases.append((payload, "outside"))
        payload = self.completed()
        payload["labels"]["events"]["follow_through_end"]["frame_index"] = 2
        cases.append((payload, "timeline order"))
        payload = self.completed()
        payload["provenance"]["reviewed_at_utc"] = "2026-10-03T16:30:00+08:00"
        cases.append((payload, "reviewed_at_utc"))
        payload = self.completed()
        payload["provenance"]["reviewed_at_utc"] = None
        cases.append((payload, "reviewed_at_utc"))
        for payload, message in cases:
            with self.subTest(message=message):
                self.write_review(payload)
                with self.assertRaisesRegex(ValueError, message):
                    self.import_review()
                self.assertFalse(self.output_root.exists())

    def test_profile_human_status_reviewer_and_partial_completion_time_are_required(self):
        payload = self.partial()
        del payload["review_profile"]
        self.write_review(payload)
        with self.assertRaisesRegex(ValueError, "phase2_full_review"):
            self.import_review()
        payload = expand_blank_review(blank_ground_truth(self.video, "pitch_003", 10))
        self.write_review(payload)
        with self.assertRaisesRegex(ValueError, "in_progress or reviewed"):
            self.import_review()
        payload = self.partial()
        payload["provenance"]["reviewer"] = " "
        self.write_review(payload)
        with self.assertRaisesRegex(ValueError, "reviewer"):
            self.import_review()
        payload = self.partial()
        payload["provenance"]["reviewed_at_utc"] = "2026-10-03T08:30:00Z"
        self.write_review(payload)
        with self.assertRaisesRegex(ValueError, "completed review time"):
            self.import_review()
        self.assertFalse(self.output_root.exists())

    def test_duplicate_import_and_existing_empty_destination_are_refused(self):
        content = self.write_review(self.partial())
        output = self.import_review()
        with self.assertRaises(FileExistsError):
            self.import_review()
        self.assertEqual(output.read_bytes(), content)
        empty = self.output_root / "SECOND_REVIEW" / "pitch_003"
        empty.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            self.import_review(review_id="SECOND_REVIEW")
        self.assertEqual(list(empty.iterdir()), [])

    def test_same_input_file_and_link_escape_are_refused(self):
        self.write_review(self.partial())
        folder = self.output_root / "CLASSMATE_20261003" / "pitch_003"
        folder.mkdir(parents=True)
        self.review = folder / "ground_truth.json"
        self.write_review(self.partial())
        with self.assertRaisesRegex(ValueError, "input review"):
            self.import_review()
        with patch.object(Path, "is_junction", return_value=True):
            with self.assertRaisesRegex(ValueError, "symlink or junction"):
                self.import_review(review_id="SECOND_REVIEW")

    def test_ambiguous_or_nonfinite_json_is_refused(self):
        content = self.write_review(self.partial())
        self.review.write_bytes(content.replace(b'"schema_version":', b'"schema_version": "ground-truth-v1", "schema_version":', 1))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.import_review()
        self.review.write_bytes(content.replace(b'"confidence": null', b'"confidence": NaN', 1))
        with self.assertRaisesRegex(ValueError, "non-finite"):
            self.import_review()
        self.assertFalse(self.output_root.exists())


if __name__ == "__main__":
    unittest.main()
