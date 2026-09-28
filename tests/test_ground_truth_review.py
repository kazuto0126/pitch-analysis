import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from pitch_analysis.ground_truth import FULL_JOINT_LABELS, expand_blank_review, validate_ground_truth
from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth
import test_ground_truth


spec = importlib.util.spec_from_file_location(
    "prepare_ground_truth_review", Path(__file__).resolve().parents[1] / "scripts" / "prepare_ground_truth_review.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class ExtendedReviewTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_ground_truth.GroundTruthTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def reviewed(self):
        payload = self.fixture._reviewed()
        payload["review_profile"] = "phase2_full_review"
        labels = payload["labels"]
        labels["pitcher_selection_review"] = {"status": "annotated", "confidence": .8, "note": "synthetic test"}
        labels["track_break_intervals"] = []
        labels["throwing_arm_occlusion_intervals"] = []
        for name in FULL_JOINT_LABELS:
            labels.setdefault(name, [{"start_frame": 0, "end_frame": 9, "status": "not_observable", "reason": "synthetic occlusion", "confidence": None}])
        return payload

    def test_extended_review_accepts_ranges_and_keeps_uncertainty(self):
        payload = self.reviewed()
        labels = payload["labels"]
        labels["pitcher_correctly_selected"] = None
        labels["pitcher_selection_review"] = {"status": "uncertain", "confidence": None, "note": "subject overlaps"}
        labels["events"]["approximate_release"] = {"status": "annotated", "frame_index": None,
            "frame_range": {"start_frame": 5, "end_frame": 7}, "confidence": .6, "note": "motion blur"}
        labels["events"]["preparation_start"] = {"status": "not_observable", "frame_index": None, "note": "outside clip"}
        labels["track_break_intervals"] = [{"start_frame": 2, "end_frame": 3, "status": "uncertain", "reason": "blur", "confidence": None}]
        validate_ground_truth(payload, source_video_path=self.fixture.video)
        with self.assertRaisesRegex(ValueError, "uncertainty-aware"):
            evaluate_against_ground_truth(payload, {}, {})

    def test_ranges_require_bounds_and_do_not_force_overlapping_events_apart(self):
        payload = self.reviewed()
        events = payload["labels"]["events"]
        events["leg_lift"] = {"status": "annotated", "frame_index": None, "frame_range": {"start_frame": 2, "end_frame": 5}, "note": "broad peak"}
        validate_ground_truth(payload)  # overlaps exact foot plant at 4
        for start, end in ((5, 3), (2, 10), (5, 7)):
            events["leg_lift"]["frame_range"] = {"start_frame": start, "end_frame": end}
            with self.assertRaises(ValueError):
                validate_ground_truth(payload)

    def test_confidence_and_all_six_joint_timelines_are_validated(self):
        for value in (-.1, 1.1, "high"):
            payload = self.reviewed()
            payload["labels"]["pitcher_selection_review"]["confidence"] = value
            with self.assertRaises(ValueError):
                validate_ground_truth(payload)
        payload = self.reviewed()
        payload["labels"]["throwing_wrist_reliability"][0]["end_frame"] = 8
        with self.assertRaisesRegex(ValueError, "cover every frame"):
            validate_ground_truth(payload)
        payload = self.reviewed()
        payload["labels"]["lead_hip_reliability"] = None
        with self.assertRaisesRegex(ValueError, "unannotated"):
            validate_ground_truth(payload)

    def test_blank_expansion_never_infers_or_replaces_human_labels(self):
        from pitch_analysis.ground_truth import blank_ground_truth
        blank = blank_ground_truth(self.fixture.video, "pitch_001", 10)
        saved = copy.deepcopy(blank)
        expanded = expand_blank_review(blank)
        self.assertEqual(blank, saved)
        self.assertTrue(all(value is None for name, value in expanded["labels"].items() if name != "events"))
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            expand_blank_review(self.fixture._reviewed())
        expanded["labels"]["track_break_intervals"] = []
        with self.assertRaisesRegex(ValueError, "cannot contain human labels"):
            validate_ground_truth(expanded)

    def test_frame_export_decodes_all_pairs_and_rejects_truncation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            video = root / "test.avi"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 30, (100, 100))
            self.assertTrue(writer.isOpened())
            for color in (20, 100, 200):
                writer.write(np.full((100, 100, 3), color, np.uint8))
            writer.release()
            rows = [{"frame_index": i, "timestamp_ms": i * 1000 / 30,
                     "selection_status": "selected", "model_warnings": "",
                     **{name.removesuffix("_reliability"): "missing" for name in FULL_JOINT_LABELS}}
                    for i in range(3)]
            out = root / "out"
            out.mkdir()
            helper.export_frames(video, video, out, rows)
            self.assertEqual(len(list((out / "frames").glob("*.jpg"))), 3)
            self.assertEqual(len(list((out / "contact_sheets").glob("*.jpg"))), 1)
            with self.assertRaises(FileExistsError):
                helper.export_frames(video, video, out, rows)
            short = root / "short"
            short.mkdir()
            with self.assertRaisesRegex(ValueError, "more frames"):
                helper.export_frames(video, video, short, rows[:2])

    def test_timeline_alignment_rejects_offset_or_conflicting_states(self):
        metadata = {"frame_count": 2, "timestamps_ms": [0, 33.333]}
        pose = {"total_frames": 2, "frame_indices": [0, 1], "important_joints": {"throwing_elbow": "RIGHT_ELBOW"},
                "joints": {"RIGHT_ELBOW": {"frame_states": ["observed", "missing"]}}}
        tracking = {"total_frames": 2, "frames": [{"frame_index": i, "selection_status": "selected", "warnings": []} for i in range(2)]}
        processed = [{"frame_index": i, "timestamp_ms": metadata["timestamps_ms"][i],
                      "landmarks": {"RIGHT_ELBOW": {"usable": i == 0, "interpolated": False}}} for i in range(2)]
        self.assertEqual(helper.timeline_rows(metadata, pose, tracking, processed)[1]["throwing_elbow"], "missing")
        processed[1]["frame_index"] = 2
        with self.assertRaisesRegex(ValueError, "align"):
            helper.timeline_rows(metadata, pose, tracking, processed)
        processed[1]["frame_index"] = 1
        processed[1]["landmarks"]["RIGHT_ELBOW"]["usable"] = True
        with self.assertRaisesRegex(ValueError, "differs"):
            helper.timeline_rows(metadata, pose, tracking, processed)
