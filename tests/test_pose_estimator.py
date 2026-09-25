"""The capture interface keeps the established CSV contract across backends."""
from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from pitch_analysis.pose_capture import LANDMARK_NAMES, extract_pose
from pitch_analysis.pose_estimator import PoseEstimate


class FakeEstimator:
    backend_name = "fixture"

    def __init__(self, count: int, calls: list) -> None:
        self.count = count
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.calls.append("closed")

    def estimate(self, frame_bgr, timestamp_ms: int) -> PoseEstimate:
        self.calls.append((frame_bgr.shape, timestamp_ms))
        landmarks = [SimpleNamespace(x=.5, y=.5, z=0.0, visibility=.9, presence=.8)
                     for _ in LANDMARK_NAMES]
        return PoseEstimate([landmarks])


class PoseEstimatorContractTests(unittest.TestCase):
    def test_injected_backend_produces_same_raw_pose_csv_shape(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            video = folder / "fixture.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
            self.assertTrue(writer.isOpened())
            for _ in range(3):
                writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
            writer.release()

            calls = []
            def factory(_model: Path, count: int) -> FakeEstimator:
                return FakeEstimator(count, calls)

            output = folder / "pose_raw.csv"
            report = extract_pose(video, folder / "unused_model.task", output,
                                  estimator_factory=factory)
            with output.open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(report["processed_frames"], 3)
            self.assertEqual(report["detected_frames"], 3)
            self.assertEqual(len(rows), 3 * len(LANDMARK_NAMES))
            self.assertEqual(rows[0]["landmark"], "NOSE")
            self.assertEqual(rows[-1]["landmark"], "RIGHT_FOOT_INDEX")
            self.assertEqual(rows[0]["visibility"], "0.9")
            self.assertEqual(rows[0]["presence"], "0.8")
            self.assertEqual(len([entry for entry in calls if isinstance(entry, tuple)]), 3)
            self.assertEqual(calls[-1], "closed")

    def test_backend_with_wrong_landmark_count_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            video = folder / "fixture.mp4"
            writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
            self.assertTrue(writer.isOpened())
            writer.write(np.zeros((64, 64, 3), dtype=np.uint8))
            writer.release()

            class InvalidEstimator(FakeEstimator):
                def estimate(self, frame_bgr, timestamp_ms: int) -> PoseEstimate:
                    pose = super().estimate(frame_bgr, timestamp_ms).pose_landmarks[0]
                    return PoseEstimate([pose[:2]])

            with self.assertRaisesRegex(ValueError, "33 ordered landmarks"):
                extract_pose(video, folder / "unused_model.task", folder / "pose_raw.csv",
                             estimator_factory=lambda _model, count: InvalidEstimator(count, []))


if __name__ == "__main__":
    unittest.main()
