"""Candidate capture is optional and preserves the estimator's native values."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from pitch_analysis.pose_capture import LANDMARK_NAMES, extract_pose
from pitch_analysis.pose_estimator import PoseEstimate
from pitch_analysis.subject import Selection


def raw_pose(offset: float = 0.0) -> list:
    # Off-image X and negative Z are intentional: the sidecar must not clip them.
    return [SimpleNamespace(x=-.125 + offset + index / 40,
                            y=.2 + index / 60, z=-.3333333333333333,
                            visibility=.1234567890123456, presence=.95)
            for index in range(33)]


class SequenceEstimator:
    backend_name = "fixture"

    def __init__(self, frames: list, calls: list) -> None:
        self.frames = iter(frames)
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.calls.append("closed")

    def estimate(self, _frame_bgr, timestamp_ms: int) -> PoseEstimate:
        self.calls.append(timestamp_ms)
        return PoseEstimate(next(self.frames))


class ScriptedSelector:
    def __init__(self, selections: list[Selection]) -> None:
        self.selections = iter(selections)
        self.last_decision = None

    def select(self, poses: list) -> Selection:
        result = next(self.selections)
        self.last_decision = {"candidate_anchors": [{"candidate_index": index,
                                                      "hip_center": [.25, .5]}
                                                     for index in range(len(poses))],
                              "status": result.status}
        return result


class PoseCaptureCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.video = self.folder / "fixture.mp4"
        self.model = self.folder / "fixture.task"
        self.model.write_bytes(b"injected model fixture")
        self.output = self.folder / "pose_raw.csv"

    def make_video(self, count: int) -> None:
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"mp4v"),
                                 30, (64, 64))
        self.assertTrue(writer.isOpened())
        try:
            for _ in range(count):
                writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
        finally:
            writer.release()

    def factory(self, frames: list, calls: list, counts: list):
        def create(model_path: Path, count: int):
            self.assertEqual(model_path, self.model)
            counts.append(count)
            return SequenceEstimator(frames, calls)
        return create

    def read_trace(self) -> list[dict]:
        return [json.loads(line) for line in
                self.output.with_suffix(".candidates.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_records_all_candidates_before_rejected_and_ambiguous_frames_are_skipped(self):
        self.make_video(5)
        distractor, selected = raw_pose(.9), raw_pose()
        # A missing native presence is explicit null in the trace, not invented.
        del distractor[0].presence
        frames = [[distractor, selected], [distractor], [selected, distractor], [], [selected]]
        before = copy.deepcopy(frames)
        selections = [Selection(1, "selected", "fixture_selected", 2, .8, .9),
                      Selection(None, "rejected", "fixture_outside_roi", 1),
                      Selection(None, "ambiguous", "fixture_tie", 2),
                      Selection(None, "rejected", "fixture_no_pose", 0),
                      Selection(0, "selected", "fixture_selected", 1, .7, .8)]
        calls, counts = [], []
        selector = ScriptedSelector(selections)
        roi = (.1, .1, .7, .9)
        with patch("pitch_analysis.subject.PitcherSelector", return_value=selector) as constructor:
            report = extract_pose(self.video, self.model, self.output,
                                  subject_selection="rear_centerfield_broadcast",
                                  subject_roi=roi,
                                  estimator_factory=self.factory(frames, calls, counts))
        constructor.assert_called_once_with(subject_roi=roi)
        self.assertEqual(counts, [4])
        self.assertEqual(calls[-1], "closed")
        self.assertEqual(frames, before)
        trace = self.read_trace()
        self.assertEqual(report["processed_frames"], 5)
        self.assertEqual(report["detected_frames"], 2)
        self.assertEqual(report["candidate_trace"]["record_count"], 5)
        self.assertEqual(report["subject_roi"], list(roi))
        self.assertEqual([row["frame_index"] for row in trace], list(range(5)))
        self.assertEqual([len(row["candidates"]) for row in trace], [2, 1, 2, 0, 1])
        self.assertEqual([row["selection"]["selected_index"] for row in trace], [1, None, None, None, 0])
        self.assertEqual([row["selection"]["status"] for row in trace],
                         ["selected", "rejected", "ambiguous", "rejected", "selected"])
        self.assertEqual(trace[1]["selection"]["reason"], "fixture_outside_roi")
        self.assertEqual(trace[2]["selector_decision"]["status"], "ambiguous")
        self.assertEqual(trace[3]["selector_decision"]["candidate_anchors"], [])
        self.assertEqual(trace[0]["coordinate_system"], "original_image_normalized")
        self.assertEqual(trace[0]["candidate_index_semantics"], "frame_local")
        self.assertIsNone(trace[0]["candidates"][0]["landmarks"][0]["presence"])
        for row, original in zip(trace, frames):
            self.assertEqual(row["timestamp_ms"],
                             report["selection_frames"][row["frame_index"]]["timestamp_ms"])
            for candidate_index, pose in enumerate(original):
                saved = row["candidates"][candidate_index]
                self.assertEqual(saved["candidate_index"], candidate_index)
                self.assertEqual(len(saved["landmarks"]), 33)
                for index, point in enumerate(pose):
                    self.assertEqual(saved["landmarks"][index],
                                     {"index": index, "name": LANDMARK_NAMES[index],
                                      "x": point.x, "y": point.y, "z": point.z,
                                      "visibility": point.visibility,
                                      "presence": getattr(point, "presence", None)})
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 66)
        self.assertEqual({int(row["frame"]) for row in rows}, {0, 4})
        self.assertEqual(rows[0]["x"], str(selected[0].x))
        self.assertEqual(rows[0]["z"], str(selected[0].z))
        self.assertEqual(rows[0]["visibility"], str(selected[0].visibility))
        self.assertEqual(report["candidate_trace"]["source_video_sha256"],
                         hashlib.sha256(self.video.read_bytes()).hexdigest())
        self.assertEqual(report["candidate_trace"]["model_sha256"],
                         hashlib.sha256(self.model.read_bytes()).hexdigest())
        expected_selection_keys = {"frame_index", "timestamp_ms", "status", "reason",
                                   "candidate_count", "selected_index", "score", "mean_confidence"}
        self.assertTrue(all(set(row) == expected_selection_keys for row in report["selection_frames"]))

    def test_default_has_no_trace_or_new_report_keys_and_uses_existing_four_pose_request(self):
        self.make_video(1)
        pose = raw_pose()
        selections = [Selection(0, "selected", "fixture_selected", 1, .8, .9)]
        calls, counts = [], []
        # Default does not require a physical model when a backend is injected.
        self.model.unlink()
        with patch("pitch_analysis.subject.PitcherSelector",
                   return_value=ScriptedSelector(selections)) as constructor:
            report = extract_pose(self.video, self.model, self.output,
                                  subject_selection="rear_centerfield_broadcast",
                                  estimator_factory=self.factory([[pose]], calls, counts))
        constructor.assert_called_once_with()
        self.assertEqual(counts, [4])
        self.assertFalse(self.output.with_suffix(".candidates.jsonl").exists())
        self.assertEqual(set(report), {"video", "model", "fps", "start_frame", "end_frame",
                                       "requested_frames", "processed_frames", "detected_frames",
                                       "width", "height", "subject_selection", "selection_frames"})

    def test_enabling_trace_does_not_change_raw_csv_bytes(self):
        self.make_video(2)
        pose = raw_pose()
        baseline = self.folder / "default.csv"
        extract_pose(self.video, self.model, baseline,
                     estimator_factory=self.factory([[pose], []], [], []))
        extract_pose(self.video, self.model, self.output, record_candidates=True,
                     estimator_factory=self.factory([[pose], []], [], []))
        self.assertEqual(baseline.read_bytes(), self.output.read_bytes())

    def test_explicit_trace_also_preserves_legacy_first_pose_semantics(self):
        self.make_video(2)
        calls, counts = [], []
        report = extract_pose(self.video, self.model, self.output, record_candidates=True,
                              estimator_factory=self.factory([[raw_pose(), raw_pose(.3)], []], calls, counts))
        self.assertEqual(counts, [1])
        self.assertEqual(report["selection_frames"], [])
        self.assertEqual(report["subject_selection"], "legacy_first_pose")
        self.assertIsNone(report["subject_roi"])
        trace = self.read_trace()
        self.assertEqual(len(trace[0]["candidates"]), 2)
        self.assertEqual(trace[0]["selection"], {"selected_index": 0, "status": "selected", "reason": "legacy_first_pose"})
        self.assertIsNone(trace[0]["selector_decision"])
        self.assertEqual(trace[1]["selection"], {"selected_index": None, "status": "rejected", "reason": "no_pose_detected"})

    def test_trace_requires_hashable_source_and_model(self):
        self.make_video(1)
        self.model.unlink()
        with self.assertRaises(FileNotFoundError):
            extract_pose(self.video, self.model, self.output, record_candidates=True,
                         estimator_factory=self.factory([[raw_pose()]], [], []))
        self.assertFalse(self.output.exists())

    def test_real_roi_selector_reports_other_person_and_empty_frame_without_raw_rows(self):
        self.make_video(3)
        def spatial_pose(x):
            points = [SimpleNamespace(x=x, y=.5, z=0.0, visibility=.9, presence=.9)
                      for _ in LANDMARK_NAMES]
            for index in (11, 12):
                points[index].y = .3
            for index in (27, 28):
                points[index].y = .8
            return points
        distractor, pitcher = spatial_pose(.5), spatial_pose(.2)
        report = extract_pose(self.video, self.model, self.output,
                              subject_selection="rear_centerfield_broadcast",
                              subject_roi=(.15, .25, .3, .6),
                              estimator_factory=self.factory([[distractor, pitcher], [distractor], []], [], []))
        self.assertEqual(report["detected_frames"], 1)
        trace = self.read_trace()
        self.assertEqual(trace[0]["selection"]["selected_index"], 1)
        self.assertEqual(trace[0]["selector_decision"]["candidates"][0]["rejection_reason"], "outside_subject_roi")
        self.assertIsNone(trace[1]["selection"]["selected_index"])
        self.assertEqual(trace[1]["selector_decision"]["candidates"][0]["rejection_reason"], "outside_subject_roi")
        self.assertEqual(trace[2]["candidates"], [])
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 33)
        self.assertEqual({row["frame"] for row in rows}, {"0"})
        self.assertEqual({row["x"] for row in rows}, {"0.2"})

    def test_invalid_roi_reaches_selector_validation_before_opening_files(self):
        invalid = [(0, 0, 1), (0, 0, 1, 1, 1), (False, 0, 1, 1),
                   (0, 0, float("nan"), 1), (-.1, 0, 1, 1), (.8, 0, .2, 1)]
        for roi in invalid:
            with self.subTest(roi=roi), self.assertRaisesRegex(ValueError, "subject_roi"):
                extract_pose(self.video, self.model, self.output,
                             subject_selection="rear_centerfield_broadcast", subject_roi=roi)
        self.assertFalse(self.output.exists())

    def test_roi_without_subject_selection_is_rejected_before_opening_files(self):
        with self.assertRaisesRegex(ValueError, "subject_roi requires"):
            extract_pose(self.video, self.model, self.output, subject_roi=(.1, .1, .9, .9))
        self.assertFalse(self.output.exists())

    def test_record_candidates_requires_a_boolean(self):
        for value in (None, "false", 1, 0, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "boolean"):
                extract_pose(self.video, self.model, self.output, record_candidates=value)
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
