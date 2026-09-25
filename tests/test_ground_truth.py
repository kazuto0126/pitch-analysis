import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.ground_truth import (
    blank_ground_truth,
    create_blank_ground_truth,
    load_ground_truth,
    validate_ground_truth,
)


class GroundTruthTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "pitch_001.mp4"
        self.video.write_bytes(b"test video bytes; validation only hashes these bytes")

    def _reviewed(self):
        annotation = blank_ground_truth(self.video, "pitch_001", 10)
        annotation["annotation_status"] = "reviewed"
        annotation["provenance"]["reviewer"] = "Human reviewer A"
        annotation["provenance"]["reviewed_at_utc"] = "2026-09-25T10:00:00Z"
        labels = annotation["labels"]
        labels["pitcher_correctly_selected"] = True
        labels["identity_switch_intervals"] = []
        labels["major_pose_failure_intervals"] = [{"start_frame": 5, "end_frame": 6, "reason": "pose on batter"}]
        labels["throwing_elbow_reliability"] = [
            {"start_frame": 0, "end_frame": 4, "status": "reliable", "reason": ""},
            {"start_frame": 5, "end_frame": 6, "status": "unreliable", "reason": "arm occluded"},
            {"start_frame": 7, "end_frame": 9, "status": "uncertain", "reason": "blurred"},
        ]
        labels["lead_knee_reliability"] = [
            {"start_frame": 0, "end_frame": 9, "status": "reliable", "reason": ""}
        ]
        for frame, name in enumerate(labels["events"]):
            labels["events"][name] = {"status": "annotated", "frame_index": frame * 2, "note": ""}
        return annotation

    def test_blank_template_has_no_inferred_human_labels_and_is_hash_bound(self):
        annotation = blank_ground_truth(self.video, "pitch_001", 10)
        self.assertEqual(annotation["annotation_status"], "unreviewed")
        self.assertIsNone(annotation["provenance"]["reviewer"])
        self.assertEqual(annotation["source_video"]["sha256"], hashlib.sha256(self.video.read_bytes()).hexdigest())
        self.assertTrue(all(value is None for value in annotation["labels"].values() if not isinstance(value, dict)))
        self.assertTrue(all(value is None for value in annotation["labels"]["events"].values()))
        validate_ground_truth(annotation, source_video_path=self.video)

    def test_template_generation_never_overwrites_existing_annotation(self):
        annotation_path = create_blank_ground_truth(self.video, "pitch_001", 10, self.root / "ground_truth")
        self.assertEqual(annotation_path, self.root / "ground_truth" / "pitch_001" / "ground_truth.json")
        original = annotation_path.read_bytes()
        with self.assertRaises(FileExistsError):
            create_blank_ground_truth(self.video, "pitch_001", 10, self.root / "ground_truth")
        self.assertEqual(annotation_path.read_bytes(), original)
        self.assertEqual(load_ground_truth(annotation_path, source_video_path=self.video)["annotation_status"], "unreviewed")

    def test_fully_reviewed_annotation_can_explicitly_mark_occlusion_and_uncertainty(self):
        annotation = self._reviewed()
        validate_ground_truth(annotation, source_video_path=self.video)
        annotation["labels"]["events"]["approximate_release"] = {
            "status": "uncertain", "frame_index": None, "note": "release hidden by body"
        }
        validate_ground_truth(annotation)

    def test_reviewed_requires_provenance_and_complete_labels(self):
        annotation = self._reviewed()
        annotation["provenance"]["reviewer"] = None
        with self.assertRaisesRegex(ValueError, "reviewer"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["labels"]["identity_switch_intervals"] = None
        with self.assertRaisesRegex(ValueError, "unannotated labels"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["labels"]["throwing_elbow_reliability"].pop()
        with self.assertRaisesRegex(ValueError, "cover every frame"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["provenance"]["reviewed_at_utc"] = "2026-09-25T12:00:00+02:00"
        with self.assertRaisesRegex(ValueError, "reviewed_at_utc"):
            validate_ground_truth(annotation)

    def test_video_hash_and_filename_changes_are_rejected(self):
        annotation = self._reviewed()
        other = self.root / "pitch_001_other.mp4"
        other.write_bytes(self.video.read_bytes())
        with self.assertRaisesRegex(ValueError, "filename"):
            validate_ground_truth(annotation, source_video_path=other)
        self.video.write_bytes(b"changed video")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_ground_truth(annotation, source_video_path=self.video)

    def test_out_of_range_overlap_and_event_order_are_rejected(self):
        annotation = self._reviewed()
        annotation["labels"]["identity_switch_intervals"] = [{"start_frame": 8, "end_frame": 10, "reason": "switch"}]
        with self.assertRaisesRegex(ValueError, "outside"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["labels"]["throwing_elbow_reliability"][1]["start_frame"] = 4
        with self.assertRaisesRegex(ValueError, "overlaps"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["labels"]["events"]["approximate_release"]["frame_index"] = 1
        with self.assertRaisesRegex(ValueError, "timeline order"):
            validate_ground_truth(annotation)

    def test_unreviewed_cannot_masquerade_as_ground_truth(self):
        annotation = blank_ground_truth(self.video, "pitch_001", 10)
        annotation["labels"]["pitcher_correctly_selected"] = True
        with self.assertRaisesRegex(ValueError, "unreviewed ground truth cannot contain"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["labels"]["throwing_elbow_reliability"][1]["reason"] = " "
        with self.assertRaisesRegex(ValueError, "needs a reason"):
            validate_ground_truth(annotation)
        annotation = self._reviewed()
        annotation["labels"]["events"]["foot_plant"]["frame_index"] = None
        with self.assertRaisesRegex(ValueError, "ground-truth-v1"):
            validate_ground_truth(annotation)

    def test_partial_review_remains_distinct_from_completed_ground_truth(self):
        annotation = blank_ground_truth(self.video, "pitch_001", 10)
        annotation["annotation_status"] = "in_progress"
        annotation["provenance"]["reviewer"] = "Human reviewer A"
        annotation["labels"]["pitcher_correctly_selected"] = True
        annotation["labels"]["throwing_elbow_reliability"] = [
            {"start_frame": 0, "end_frame": 3, "status": "unreliable", "reason": "occluded"}
        ]
        validate_ground_truth(annotation)
        annotation["provenance"]["reviewed_at_utc"] = "2026-09-25T10:00:00Z"
        with self.assertRaisesRegex(ValueError, "completed review time"):
            validate_ground_truth(annotation)


if __name__ == "__main__":
    unittest.main()
