"""Crop-native model predictions map back to the original image explicitly."""
from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from pitch_analysis.pose_capture import LANDMARK_NAMES, extract_pose
from pitch_analysis.pose_crop import build_input_transform, validate_input_crop
from pitch_analysis.pose_estimator import PoseEstimate


class FakeCapture:
    def __init__(self, frames):
        self.frames = frames
        self.next_frame = 0
        self.last_frame = 0
        self.released = False

    def isOpened(self):
        return True

    def get(self, prop):
        return {cv2.CAP_PROP_FPS: 30,
                cv2.CAP_PROP_FRAME_COUNT: len(self.frames),
                cv2.CAP_PROP_FRAME_WIDTH: self.frames[0].shape[1],
                cv2.CAP_PROP_FRAME_HEIGHT: self.frames[0].shape[0],
                cv2.CAP_PROP_POS_MSEC: self.last_frame * 1000 / 30}[prop]

    def set(self, prop, value):
        if prop == cv2.CAP_PROP_POS_FRAMES:
            self.next_frame = int(value)

    def read(self):
        if self.next_frame >= len(self.frames):
            return False, None
        self.last_frame = self.next_frame
        frame = self.frames[self.next_frame]
        self.next_frame += 1
        return True, frame

    def release(self):
        self.released = True


class FakeEstimator:
    backend_name = "fixture"

    def __init__(self, predictions, received):
        self.predictions = iter(predictions)
        self.received = received

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def estimate(self, frame, timestamp_ms):
        self.received.append((frame.copy(), timestamp_ms))
        return PoseEstimate(next(self.predictions))


def pose(x=.25, y=.75, z=-.4):
    return [SimpleNamespace(x=x, y=y, z=z, visibility=.9123456789012345,
                            presence=.8234567890123456) for _ in LANDMARK_NAMES]


class PoseCaptureCropTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.video = self.folder / "fixture.mp4"
        self.model = self.folder / "fixture.task"
        self.video.write_bytes(b"source fixture for fake decoder")
        self.model.write_bytes(b"model fixture for injected estimator")
        self.output = self.folder / "pose_raw.csv"
        self.image = np.arange(79 * 101 * 3, dtype=np.uint8).reshape(79, 101, 3)

    def capture(self, predictions, *, frames=None, output=None, **kwargs):
        frames = frames or [self.image] * len(predictions)
        received, counts = [], []
        source = FakeCapture(frames)
        def factory(_model, count):
            counts.append(count)
            return FakeEstimator(predictions, received)
        with patch("cv2.VideoCapture", return_value=source):
            report = extract_pose(self.video, self.model, output or self.output,
                                  estimator_factory=factory, **kwargs)
        self.assertTrue(source.released)
        return report, received, counts

    def trace(self):
        return [json.loads(line) for line in self.output.with_suffix(".candidates.jsonl")
                .read_text(encoding="utf-8").splitlines()]

    def raw_rows(self):
        with self.output.open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    def test_fractional_offset_non_square_crop_has_exact_pixels_and_inverse_mapping(self):
        original = pose()
        before = copy.deepcopy(original)
        crop = (.213, .107, .821, .809)
        report, received, counts = self.capture([[original]], input_crop=crop)
        transform = report["input_transform"]
        self.assertEqual(transform, build_input_transform(crop, 101, 79))
        self.assertEqual(transform["pixel_bounds_xyxy"], [21, 8, 83, 64])
        self.assertEqual(transform["original_image_size_px"], [101, 79])
        self.assertEqual(transform["model_input_size_px"], [62, 56])
        np.testing.assert_array_equal(received[0][0], self.image[8:64, 21:83])
        self.assertEqual(received[0][0].shape, (56, 62, 3))
        self.assertEqual(counts, [1])
        self.assertEqual(original, before)
        self.assertEqual(report["input_crop"], list(crop))
        self.assertEqual(report["candidate_trace"]["record_count"], 1)
        self.assertEqual(transform["z_scale"], 62 / 101)
        self.assertIn("not calibrated", transform["z_semantics"])
        self.assertFalse(transform["coordinate_clamping"])
        record = self.trace()[0]
        self.assertEqual(record["input_transform"], transform)
        native = record["native_candidates"][0]["landmarks"][0]
        mapped = record["candidates"][0]["landmarks"][0]
        self.assertEqual(native["x"], .25)
        self.assertEqual(native["y"], .75)
        self.assertEqual(native["z"], -.4)
        self.assertEqual(mapped["x"], (21 + .25 * 62) / 101)
        self.assertEqual(mapped["y"], (8 + .75 * 56) / 79)
        self.assertEqual(mapped["z"], -.4 * 62 / 101)
        self.assertEqual(mapped["visibility"], original[0].visibility)
        self.assertEqual(mapped["presence"], original[0].presence)
        for row, point in zip(self.raw_rows(), record["candidates"][0]["landmarks"]):
            self.assertEqual(row["landmark"], point["name"])
            for key in ("x", "y", "z", "visibility", "presence"):
                self.assertEqual(float(row[key]), point[key])

    def test_out_of_range_native_predictions_are_not_clamped_and_native_values_are_preserved(self):
        native = pose(x=-2.25, y=3.5, z=2.75)
        before = copy.deepcopy(native)
        self.capture([[native]], input_crop=(.2, .2, .7, .8))
        record = self.trace()[0]
        raw_native = record["native_candidates"][0]["landmarks"]
        mapped = record["candidates"][0]["landmarks"]
        self.assertEqual(len(raw_native), 33)
        self.assertEqual([point["index"] for point in raw_native], list(range(33)))
        for index, point in enumerate(native):
            self.assertEqual(raw_native[index], {"index": index, "name": LANDMARK_NAMES[index],
                                                **vars(point)})
        self.assertLess(mapped[0]["x"], 0)
        self.assertGreater(mapped[0]["y"], 1)
        self.assertEqual(native, before)
        self.assertEqual(mapped[0]["visibility"], raw_native[0]["visibility"])
        self.assertEqual(mapped[0]["presence"], raw_native[0]["presence"])

    def test_selector_uses_mapped_original_coordinates_not_native_crop_coordinates(self):
        image = np.zeros((80, 100, 3), dtype=np.uint8)
        native = pose(x=.8, y=(.5 - .2) / .7)
        for index in (11, 12):
            native[index].y = (.3 - .2) / .7
        for index in (27, 28):
            native[index].y = (.8 - .2) / .7
        report, _received, counts = self.capture(
            [[native]], frames=[image], input_crop=(.1, .2, .5, .9),
            subject_selection="rear_centerfield_broadcast", subject_roi=(.39, .25, .45, .6))
        self.assertEqual(counts, [4])
        self.assertEqual(report["detected_frames"], 1)
        self.assertEqual(report["selection_frames"][0]["selected_index"], 0)
        record = self.trace()[0]
        self.assertEqual(record["native_candidates"][0]["landmarks"][23]["x"], .8)
        self.assertAlmostEqual(record["selector_decision"]["candidates"][0]["hip_xy"][0], .42)
        self.assertAlmostEqual(float(self.raw_rows()[23]["x"]), .42)

    def test_empty_predictions_still_record_native_and_mapped_empty_candidates(self):
        report, received, _counts = self.capture([[], []], input_crop=(.1, .2, .8, .9))
        self.assertEqual(report["processed_frames"], 2)
        self.assertEqual(report["detected_frames"], 0)
        self.assertEqual(len(received), 2)
        self.assertEqual(self.raw_rows(), [])
        for row in self.trace():
            self.assertEqual(row["native_candidates"], [])
            self.assertEqual(row["candidates"], [])
            self.assertIsNone(row["selection"]["selected_index"])
            self.assertEqual(row["input_transform"], report["input_transform"])

    def test_ambiguous_selection_retains_every_native_and_mapped_candidate(self):
        native = [pose(x=(x - .1) / .8, y=(.5 - .2) / .7) for x in (.49, .51)]
        for candidate in native:
            for index in (11, 12):
                candidate[index].y = (.3 - .2) / .7
            for index in (27, 28):
                candidate[index].y = (.8 - .2) / .7
        before = copy.deepcopy(native)
        report, _received, _counts = self.capture(
            [native], frames=[np.zeros((80, 100, 3), dtype=np.uint8)],
            input_crop=(.1, .2, .9, .9), subject_selection="rear_centerfield_broadcast",
            subject_roi=(.3, .25, .7, .6))
        self.assertEqual(report["selection_frames"][0]["status"], "ambiguous")
        self.assertEqual(report["detected_frames"], 0)
        self.assertEqual(self.raw_rows(), [])
        record = self.trace()[0]
        self.assertEqual(len(record["native_candidates"]), 2)
        self.assertEqual(len(record["candidates"]), 2)
        self.assertIsNone(record["selection"]["selected_index"])
        self.assertEqual(native, before)
        for index, candidate in enumerate(record["native_candidates"]):
            self.assertEqual(candidate["candidate_index"], index)
            self.assertEqual(len(candidate["landmarks"]), 33)
            for point_index, point in enumerate(candidate["landmarks"]):
                self.assertEqual(point, {"index": point_index, "name": LANDMARK_NAMES[point_index],
                                         **vars(native[index][point_index])})

    def test_missing_presence_is_not_invented_by_mapping(self):
        native = pose()
        del native[0].presence
        self.capture([[native]], input_crop=(.1, .2, .8, .9))
        record = self.trace()[0]
        self.assertIsNone(record["native_candidates"][0]["landmarks"][0]["presence"])
        self.assertIsNone(record["candidates"][0]["landmarks"][0]["presence"])
        self.assertEqual(self.raw_rows()[0]["presence"], "")
        self.assertFalse(hasattr(native[0], "presence"))

    def test_absent_and_explicit_none_crop_preserve_legacy_csv_report_and_full_input(self):
        native = pose()
        baseline = self.folder / "baseline.csv"
        default_report, default_received, default_counts = self.capture([[native]], output=baseline)
        report, received, counts = self.capture([[native]], input_crop=None)
        self.assertEqual(default_report, report)
        self.assertEqual(baseline.read_bytes(), self.output.read_bytes())
        self.assertEqual(counts, default_counts)
        np.testing.assert_array_equal(received[0][0], self.image)
        np.testing.assert_array_equal(default_received[0][0], self.image)
        self.assertNotIn("input_crop", report)
        self.assertNotIn("input_transform", report)
        self.assertNotIn("candidate_trace", report)
        self.assertFalse(self.output.with_suffix(".candidates.jsonl").exists())

    def test_record_candidates_without_crop_keeps_existing_trace_shape(self):
        native = pose()
        report, received, _counts = self.capture([[native]], record_candidates=True)
        record = self.trace()[0]
        self.assertNotIn("input_crop", report)
        self.assertNotIn("input_transform", report)
        self.assertNotIn("input_transform", record)
        self.assertNotIn("native_candidates", record)
        self.assertEqual(record["candidates"][0]["landmarks"][0]["x"], native[0].x)
        np.testing.assert_array_equal(received[0][0], self.image)

    def test_invalid_bounds_are_rejected_before_opening_video_or_output(self):
        invalid = [(), (0, 0, 1), (0, 0, 1, 1, 1), (0, 0, 0, 1), (.8, 0, .2, 1),
                   (0, .7, 1, .2), (-.1, 0, 1, 1), (0, 0, 1.001, 1),
                   (False, 0, 1, 1), (0, 0, float("nan"), 1),
                   (0, 0, 1, float("inf")), "0,0,1,1", ("0", 0, 1, 1)]
        with patch("cv2.VideoCapture") as video:
            for crop in invalid:
                with self.subTest(crop=crop), self.assertRaisesRegex(ValueError, "input_crop"):
                    extract_pose(self.video, self.model, self.output, input_crop=crop)
            video.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_normalized_validation_and_pixel_rounding_support_edge_and_subpixel_crops(self):
        self.assertIsNone(validate_input_crop(None))
        self.assertEqual(validate_input_crop([0, 0, 1, 1]), (0., 0., 1., 1.))
        transform = build_input_transform((.101, .201, .102, .202), 100, 80)
        self.assertEqual(transform["pixel_bounds_xyxy"], [10, 16, 11, 17])
        self.assertEqual(transform["model_input_size_px"], [1, 1])
        self.assertEqual(build_input_transform((0, 0, 1, 1), 101, 79)["pixel_bounds_xyxy"], [0, 0, 101, 79])
        json.dumps(transform, allow_nan=False)
        for dimensions in [(0, 79), (101, 0), (-1, 79), (True, 79), (101., 79)]:
            with self.subTest(dimensions=dimensions), self.assertRaisesRegex(ValueError, "dimensions"):
                build_input_transform((0, 0, 1, 1), *dimensions)


if __name__ == "__main__":
    unittest.main()
