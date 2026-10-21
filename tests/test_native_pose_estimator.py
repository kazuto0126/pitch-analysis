"""Model-free checks of the live adapter's fixed SDK geometry and native data."""
from copy import deepcopy
import json
import unittest

import cv2
import numpy as np

from pitch_analysis.native_pose import NativePoseFrame, TOPOLOGIES
from pitch_analysis.native_pose_estimator import (
    NativePoseEstimate, RTMPoseNativeEstimator, decode_rtmpose_outputs,
    prepare_rtmpose_input,
)


def responses(x_index=192, y_index=256, x_score=2., y_score=3.):
    x = np.full((1, 17, 384), -1., dtype=np.float32)
    y = np.full((1, 17, 512), -1., dtype=np.float32)
    x[:, :, x_index] = x_score
    y[:, :, y_index] = y_score
    return x, y


class RecordingTransport:
    def __init__(self, outputs=None, error=None):
        self.outputs = outputs if outputs is not None else responses()
        self.error = error
        self.calls = []

    def run(self, tensor):
        self.calls.append(tensor.copy())
        if self.error is not None:
            raise self.error
        return self.outputs


class NativePoseEstimatorTests(unittest.TestCase):
    def test_official_bgr_normalization_and_contiguous_float32_nchw(self):
        # The sealed ONNX example does not reverse BGR into RGB.
        image = np.full((120, 180, 3), [10, 50, 200], dtype=np.uint8)
        tensor, geometry = prepare_rtmpose_input(image, (10, 20, 130, 100))
        self.assertEqual(tensor.shape, (1, 3, 256, 192))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertTrue(tensor.flags.c_contiguous)
        expected = (np.array([10, 50, 200]) - [123.675, 116.28, 103.53]) / [58.395, 57.12, 57.375]
        np.testing.assert_allclose(tensor[0, :, 128, 96], expected, atol=1e-7)
        self.assertEqual(geometry["sdk_geometry"]["color_order"], "BGR_unchanged")
        self.assertEqual(geometry["roi_xywh"], [10, 20, 120, 80])

    def test_known_official_scale_formula_for_wide_and_tall_nonsquare_crops(self):
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        # The independent analytic SDK formula after aspect correction is
        # input = (source - (crop origin + center)) / scale * input size + half input.
        for crop, expected_scale in (((192, 216, 768, 720), (720., 960.)),
                                     ((100, 20, 220, 620), (562.5, 750.)),
                                     ((9, 11, 110, 110), (126.25, 168.33333333333334))):
            with self.subTest(crop=crop):
                _, geometry = prepare_rtmpose_input(image, crop)
                sdk = geometry["sdk_geometry"]
                center = np.array([(crop[0] + crop[2]) / 2, (crop[1] + crop[3]) / 2])
                np.testing.assert_allclose(sdk["scale"], expected_scale)
                np.testing.assert_allclose(sdk["center_source_px"], center)
                affine = np.asarray(geometry["affine_src_to_input"])
                inverse = np.asarray(geometry["affine_input_to_src"])
                for point in (center, [crop[0], crop[1]], [crop[2], crop[3]], [350., 400.]):
                    expected = (np.asarray(point) - center) / expected_scale * [192, 256] + [96, 128]
                    projected = affine @ [*point, 1]
                    np.testing.assert_allclose(projected, expected, atol=1e-5)
                    np.testing.assert_allclose(inverse @ [*projected, 1], point, atol=1e-9)

    def test_exact_sdk_affine_tensor_uses_crop_only_and_constant_black_padding(self):
        # Outside pixels differ completely: padding must not read those people.
        rng = np.random.default_rng(184)
        first = rng.integers(0, 256, (300, 400, 3), dtype=np.uint8)
        second = 255 - first
        crop = (40, 50, 240, 170)
        second[50:170, 40:240] = first[50:170, 40:240]
        first_before = first.copy()
        tensor, geometry = prepare_rtmpose_input(first, crop)
        other_tensor, _ = prepare_rtmpose_input(second, crop)
        np.testing.assert_array_equal(tensor, other_tensor)
        np.testing.assert_array_equal(first, first_before)

        # Independent reference from official preprocess / top_down_affine:
        # crop center=(100,60), padded scale=(250,150), fixed aspect=(250,1000/3).
        warp = cv2.getAffineTransform(
            np.float32([[100, 60], [100, -65], [-25, -65]]),
            np.float32([[96, 128], [96, 32], [0, 32]]))
        expected = cv2.warpAffine(first[50:170, 40:240], warp, (192, 256), flags=cv2.INTER_LINEAR)
        expected = (expected - [123.675, 116.28, 103.53]) / [58.395, 57.12, 57.375]
        np.testing.assert_array_equal(tensor, expected.transpose(2, 0, 1)[None].astype(np.float32))
        black = (np.array([0, 0, 0]) - [123.675, 116.28, 103.53]) / [58.395, 57.12, 57.375]
        np.testing.assert_allclose(tensor[0, :, 0, 0], black, atol=1e-7)
        np.testing.assert_allclose(geometry["sdk_geometry"]["affine_crop_to_input"], warp)

    def test_decode_exact_simcc_bins_into_known_original_image_points(self):
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        _, geometry = prepare_rtmpose_input(image, (192, 216, 768, 720))
        x, y = responses(x_index=240, y_index=320, x_score=1.7, y_score=.2)
        # native input=(120,160); crop scale=(720,960), original center=(480,468).
        # This positive .2 score is deliberately below any production .5 gate.
        points = decode_rtmpose_outputs((x, y), geometry)
        self.assertEqual(len(points), 17)
        self.assertEqual([p["name"] for p in points], list(TOPOLOGIES["coco_17"]["names"]))
        for point in points:
            self.assertAlmostEqual(point["x_px"], 570.)
            self.assertAlmostEqual(point["y_px"], 588.)
            self.assertAlmostEqual(point["native_score"], .2)
            self.assertEqual(point["coordinate_state"], "model_observed")
            self.assertEqual(point["source_record"]["simcc_argmax_xy"], [240, 320])
            self.assertEqual(point["source_record"]["native_input_xy_px"], [120., 160.])
            self.assertIsNone(point["z"])
            self.assertIsNone(point["visibility"])
            self.assertIsNone(point["presence"])

    def test_no_coordinate_clipping_or_native_score_calibration(self):
        _, geometry = prepare_rtmpose_input(np.zeros((100, 100, 3), np.uint8), (0, 0, 100, 100))
        low = decode_rtmpose_outputs(responses(0, 0, 4., 3.), geometry)[0]
        self.assertAlmostEqual(low["x_px"], -12.5)
        self.assertAlmostEqual(low["y_px"], -100 / 3)
        self.assertEqual(low["native_score"], 3.)
        high = decode_rtmpose_outputs(responses(383, 511), geometry)[0]
        self.assertGreater(high["x_px"], 100)
        self.assertGreater(high["y_px"], 100)
        self.assertEqual(high["coordinate_state"], "model_observed")

    def test_nonpositive_native_response_is_missing_but_retains_real_finite_score(self):
        _, geometry = prepare_rtmpose_input(np.zeros((100, 100, 3), np.uint8), (0, 0, 100, 100))
        for score in (0., -.1):
            with self.subTest(score=score):
                point = decode_rtmpose_outputs(responses(30, 40, score, .8), geometry)[0]
                self.assertEqual(point["coordinate_state"], "missing")
                self.assertEqual(point["missing_reason"], "nonpositive_native_response")
                self.assertAlmostEqual(point["native_score"], score)
                self.assertIsNone(point["x_px"])
                self.assertIsNone(point["y_px"])
                self.assertIsNone(point["source_record"]["native_input_xy_px"])
                self.assertEqual(point["source_record"]["simcc_argmax_xy"], [30, 40])

    def test_nonfinite_response_is_joint_local_missing_and_strict_json_safe(self):
        _, geometry = prepare_rtmpose_input(np.zeros((100, 100, 3), np.uint8), (0, 0, 100, 100))
        x, y = responses()
        x[0, 0, 5] = np.nan
        y[0, 1, 5] = np.inf
        x[0, 2, 5] = -np.inf
        points = decode_rtmpose_outputs((x, y), geometry)
        json.dumps(points, allow_nan=False)
        for index in (0, 1, 2):
            self.assertEqual(points[index]["coordinate_state"], "missing")
            self.assertEqual(points[index]["missing_reason"], "nonfinite_native_response")
            self.assertIsNone(points[index]["x_px"])
            self.assertIsNone(points[index]["y_px"])
        self.assertIsNone(points[0]["native_score"])
        self.assertIsNone(points[1]["native_score"])
        self.assertEqual(points[2]["native_score"], 2.)
        self.assertEqual(points[0]["source_record"]["simcc_nonfinite_values"]["x"]["nan"], 1)
        self.assertEqual(points[1]["source_record"]["simcc_nonfinite_values"]["y"]["positive_infinity"], 1)
        self.assertEqual(points[2]["source_record"]["simcc_nonfinite_values"]["x"]["negative_infinity"], 1)
        self.assertTrue(all(p["coordinate_state"] == "model_observed" for p in points[3:]))

    def test_estimator_runs_transport_exactly_once_without_mutating_input_or_outputs(self):
        outputs = responses()
        before = [value.copy() for value in outputs]
        transport = RecordingTransport(outputs)
        estimator = RTMPoseNativeEstimator(transport, crop_xyxy=(20, 30, 90, 110))
        result = estimator.estimate(np.zeros((150, 200, 3), dtype=np.uint8))
        self.assertIsInstance(result, NativePoseEstimate)
        self.assertEqual(estimator.backend_name, "rtmpose")
        self.assertEqual(len(transport.calls), 1)
        self.assertEqual(len(result.landmarks), 17)
        for original, output in zip(before, outputs, strict=True):
            np.testing.assert_array_equal(original, output)

    def test_transport_failure_propagates_without_retry(self):
        transport = RecordingTransport(error=RuntimeError("isolated runtime stopped"))
        estimator = RTMPoseNativeEstimator(transport, crop_xyxy=(0, 0, 10, 10))
        with self.assertRaisesRegex(RuntimeError, "isolated runtime stopped"):
            estimator.estimate(np.zeros((20, 20, 3), np.uint8))
        self.assertEqual(len(transport.calls), 1)

    def test_invalid_crop_and_non_bgr_frames_never_call_transport(self):
        good = np.zeros((20, 30, 3), dtype=np.uint8)
        for crop in ((0., 0, 20, 20), (False, 0, 20, 20), (0, 0, 31, 20),
                     (-1, 0, 20, 20), (5, 0, 5, 20), (0, 0, 20), (0, 0, 20, 21)):
            with self.subTest(crop=crop), self.assertRaises(ValueError):
                prepare_rtmpose_input(good, crop)
        transport = RecordingTransport()
        estimator = RTMPoseNativeEstimator(transport, crop_xyxy=(0, 0, 10, 10))
        for image in (np.zeros((20, 30), np.uint8), np.zeros((20, 30, 4), np.uint8),
                      good.astype(float), np.zeros((0, 30, 3), np.uint8), None):
            with self.subTest(shape=getattr(image, "shape", None)), self.assertRaises(ValueError):
                estimator.estimate(image)
        self.assertEqual(transport.calls, [])

    def test_malformed_outputs_and_inverse_are_rejected_without_guessing(self):
        _, geometry = prepare_rtmpose_input(np.zeros((100, 100, 3), np.uint8), (0, 0, 100, 100))
        x, y = responses()
        for outputs in ((x,), (x[:, :16], y), (x, y[:, :, :511]),
                        (x.astype(int), y), (x[0], y)):
            with self.subTest(shapes=[v.shape for v in outputs]), self.assertRaises(ValueError):
                decode_rtmpose_outputs(outputs, geometry)
        for value in (None, [[1, 0, float("nan")], [0, 1, 0]], [[1, 0], [0, 1]]):
            bad = deepcopy(geometry)
            bad["affine_input_to_src"] = value
            with self.assertRaises(ValueError):
                decode_rtmpose_outputs((x, y), bad)

    def test_estimate_can_be_saved_as_existing_native_frame_without_false_capabilities(self):
        estimator = RTMPoseNativeEstimator(RecordingTransport(), crop_xyxy=(10, 20, 80, 90))
        estimate = estimator.estimate(np.zeros((100, 100, 3), np.uint8))
        frame = {
            "schema_version": "native-keypoints-v1", "pitch_id": "fixture",
            "backend": "rtmpose", "topology": "coco_17", "frame_index": 0,
            "timestamp_ms": 0., "source_video_sha256": "a" * 64,
            "decoded_bgr_sha256": "b" * 64, "image_size": {"width": 100, "height": 100},
            "coordinate_space": "original_image_pixels_xy", "quality_status": "not_calibrated",
            "usable_for_analysis": None, "input_geometry": estimate.input_geometry,
            "model_selection": {"method": "fixed_human_confirmed_crop"},
            "landmarks": estimate.landmarks,
        }
        wrapped = NativePoseFrame(frame)
        self.assertEqual(wrapped.to_dict()["landmarks"], estimate.landmarks)
        json.dumps(wrapped.to_dict(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
