"""Synthetic-only SDK geometry, native decoding and response sampling checks."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rtmpose_response_features as features


def fixture():
    _, geometry = features.preprocess(np.zeros((256, 192, 3), dtype=np.uint8), [19.2, 25.6, 153.6, 204.8])
    xs, ys = np.zeros((1, 17, 384), dtype=np.float32), np.zeros((1, 17, 512), dtype=np.float32)
    xs[0, :, 20], ys[0, :, 40] = 2., 3.
    point = {"x": .5, "y": .5, "z": .1, "visibility": .9, "presence": .95}
    raw = {"RIGHT_ELBOW": dict(point), "RIGHT_WRIST": dict(point)}
    gate = {"min_visibility": .5, "min_presence": .5}
    return raw, xs, ys, geometry, gate


def build(raw, xs, ys, geometry, gate):
    return features.build_frame(raw, xs, ys, geometry, 192, 256, gate)


class PreprocessTests(unittest.TestCase):
    def test_rgb_normalization_shape_dtype_and_immutable_source(self):
        frame = np.empty((256, 192, 3), dtype=np.uint8); frame[:] = [10, 20, 30]
        saved = frame.copy(); roi = [19.2, 25.6, 153.6, 204.8]; original_roi = roi[:]
        tensor, geometry = features.preprocess(frame, roi)
        self.assertEqual(tensor.shape, (1, 3, 256, 192))
        self.assertEqual(tensor.dtype, np.float32)
        self.assertTrue(tensor.flags.c_contiguous)
        expected = (np.asarray([30, 20, 10], np.float32) - np.asarray(features.MEAN, np.float32)) / np.asarray(features.STD, np.float32)
        np.testing.assert_allclose(tensor[0, :, 128, 96], expected, rtol=0, atol=1e-6)
        np.testing.assert_array_equal(frame, saved)
        self.assertEqual(roi, original_roi)
        self.assertEqual(geometry["color_order"], "RGB")

    def test_aspect_padding_original_roi_no_clip_and_zero_border(self):
        frame = np.full((40, 60, 3), 255, dtype=np.uint8)
        tensor, geometry = features.preprocess(frame, [-100., -50., 80., 40.])
        self.assertEqual(geometry["roi_xywh"], [-100., -50., 80., 40.])
        self.assertEqual(geometry["center_xy"], [-60., -30.])
        np.testing.assert_allclose(geometry["scale_wh"], [100., 100. / .75])
        expected = -np.asarray(features.MEAN, np.float32) / np.asarray(features.STD, np.float32)
        np.testing.assert_allclose(tensor[0, :, 0, 0], expected, rtol=0, atol=1e-6)

    def test_affine_matches_rotation_zero_reference_and_roundtrips(self):
        _, geometry = features.preprocess(np.zeros((200, 300, 3), np.uint8), [20., 30., 90., 100.])
        cx, cy = geometry["center_xy"]; sw, sh = geometry["scale_wh"]
        source = np.asarray([[cx, cy], [cx, cy - sh / 2], [cx + sw / 2, cy]], np.float32)
        target = np.asarray([[96, 128], [96, 0], [192, 128]], np.float32)
        reference = cv2.getAffineTransform(source, target)
        np.testing.assert_allclose(geometry["affine_src_to_input"], reference, atol=1e-7, rtol=0)
        forward = np.vstack([geometry["affine_src_to_input"], [0, 0, 1]])
        inverse = np.vstack([geometry["affine_input_to_src"], [0, 0, 1]])
        np.testing.assert_allclose(inverse @ forward, np.eye(3), atol=1e-12, rtol=0)
        self.assertAlmostEqual(forward[0, 0], forward[1, 1])

    def test_invalid_source_and_roi_rejected(self):
        for source in (np.zeros((20, 20), np.uint8), np.zeros((20, 20, 4), np.uint8),
                       np.zeros((20, 20, 3), np.float32), np.zeros((0, 20, 3), np.uint8)):
            with self.assertRaises(ValueError): features.preprocess(source, [0, 0, 10, 10])
        for roi in ([0, 0, 0, 10], [0, 0, -1, 10], [0, 0, 10], [float("nan"), 0, 10, 10], [True, 0, 10, 10]):
            with self.assertRaises(ValueError): features.preprocess(np.zeros((20, 20, 3), np.uint8), roi)


class ResponseTests(unittest.TestCase):
    def test_native17_mapping_score_and_inverse_decoding_no_fake_fields(self):
        raw, xs, ys, geometry, gate = fixture()
        result = build(raw, xs, ys, geometry, gate)
        self.assertEqual(len(result["native_keypoints"]), 17)
        elbow = result["native_keypoints"][8]
        self.assertEqual(elbow["name"], "RIGHT_ELBOW")
        self.assertEqual(result["native_keypoints"][10]["name"], "RIGHT_WRIST")
        self.assertEqual(elbow["score"], 2.)
        np.testing.assert_allclose([elbow["x_px"], elbow["y_px"]], [10., 20.], atol=1e-12)
        self.assertFalse(any(key in elbow for key in ("visibility", "presence", "z")))
        self.assertEqual(result["roles"]["throwing_elbow"]["response_deficit"], 5.)

    def test_nearest_bin_half_up_no_softmax_and_original_gate(self):
        raw, xs, ys, geometry, gate = fixture()
        raw["RIGHT_ELBOW"].update(x=10.25 / 192, y=20.25 / 256, visibility=.01)
        xs[0, 8, 21], ys[0, 8, 41] = 1.25, -.5
        value = build(raw, xs, ys, geometry, gate)["roles"]["throwing_elbow"]
        self.assertEqual(value["bins"], [21, 41])
        self.assertAlmostEqual(value["response_deficit"], 4.25)
        self.assertTrue(value["raw_finite"])
        self.assertFalse(value["raw_gate_pass"])
        self.assertEqual(value["evidence_status"], "measured")

    def test_full_bin_outside_not_clipped_and_negative_nearest_bin(self):
        raw, xs, ys, geometry, gate = fixture()
        for x, expected in ((192., 384), (-.3, -1)):
            raw["RIGHT_ELBOW"]["x"] = x / 192
            value = build(raw, xs, ys, geometry, gate)["roles"]["throwing_elbow"]
            self.assertEqual(value["bins"][0], expected)
            self.assertIsNone(value["response_deficit"])
            self.assertEqual(value["reason"], "full_point_outside_simcc_bins")
            self.assertTrue(value["raw_finite"])

    def test_missing_or_nonfinite_full_points_and_source_overflow(self):
        for point in (None, {"x": .5, "y": .5, "visibility": float("nan"), "presence": 1.},
                      {"x": 1e308, "y": .5, "visibility": 1., "presence": 1.}):
            raw, xs, ys, geometry, gate = fixture()
            raw["RIGHT_ELBOW"] = point
            value = build(raw, xs, ys, geometry, gate)["roles"]["throwing_elbow"]
            self.assertFalse(value["raw_finite"])
            self.assertFalse(value["raw_gate_pass"])
            self.assertIsNone(value["full_xy_px"])
            self.assertIsNone(value["response_deficit"])
            self.assertEqual(value["evidence_status"], "insufficient_evidence")

    def test_nonfinite_axis_affects_only_its_joint_not_other_roles(self):
        raw, xs, ys, geometry, gate = fixture()
        xs[0, 8, 0] = float("nan")
        xs[0, 0, 0] = float("inf")
        result = build(raw, xs, ys, geometry, gate)
        self.assertIsNone(result["native_keypoints"][8]["score"])
        self.assertIsNone(result["native_keypoints"][8]["x_px"])
        self.assertEqual(result["roles"]["throwing_elbow"]["reason"], "nonfinite_native_response")
        self.assertIsNone(result["roles"]["throwing_elbow"]["response_deficit"])
        self.assertEqual(result["roles"]["throwing_wrist"]["response_deficit"], 5.)
        self.assertEqual(result["roles"]["throwing_wrist"]["evidence_status"], "measured")

    def test_nonpositive_native_score_null_xy_keeps_primary_deficit(self):
        raw, xs, ys, geometry, gate = fixture()
        xs[0, 8, :] = -3.; ys[0, 8, :] = -4.
        xs[0, 8, 20] = -1.; ys[0, 8, 40] = -2.
        result = build(raw, xs, ys, geometry, gate)
        native = result["native_keypoints"][8]
        self.assertEqual(native["score"], -2.)
        self.assertEqual(native["decode_status"], "nonpositive_score")
        self.assertIsNone(native["x_px"])
        self.assertIsNone(native["y_px"])
        self.assertEqual(result["roles"]["throwing_elbow"]["response_deficit"], 4.)
        xs[0, 8, :] = 0.; ys[0, 8, :] = 0.
        result = build(raw, xs, ys, geometry, gate)
        self.assertEqual(result["native_keypoints"][8]["score"], 0.)
        self.assertIsNone(result["native_keypoints"][8]["x_px"])
        self.assertEqual(result["roles"]["throwing_elbow"]["response_deficit"], 0.)

    def test_strict_native_shape_dtype_geometry_and_dimensions(self):
        raw, xs, ys, geometry, gate = fixture()
        for bad_x, bad_y in ((xs[:, :, :-1], ys), (xs, ys[:, :, :-1]), (xs.astype(np.float64), ys),
                              (xs.repeat(2, axis=0), ys)):
            with self.assertRaises(ValueError): build(raw, bad_x, bad_y, geometry, gate)
        for key, value in (("input_size", [256, 192]), ("simcc_split_ratio", 1),
                           ("color_order", "BGR"), ("normalize_simcc", True),
                           ("affine_input_to_src", [[1, 0], [0, 1]])):
            bad = deepcopy(geometry); bad[key] = value
            with self.assertRaises(ValueError): build(raw, xs, ys, bad, gate)
        with self.assertRaises(ValueError): features.build_frame(raw, xs, ys, geometry, 193, 256, gate)
        with self.assertRaises(ValueError): features.build_frame(raw, xs, ys, geometry, True, 256, gate)

    def test_feature_inputs_are_immutable_and_output_has_no_alias_to_raw(self):
        raw, xs, ys, geometry, gate = fixture()
        original = deepcopy((raw, geometry, gate)); original_x, original_y = xs.copy(), ys.copy()
        result = build(raw, xs, ys, geometry, gate)
        self.assertEqual((raw, geometry, gate), original)
        np.testing.assert_array_equal(xs, original_x); np.testing.assert_array_equal(ys, original_y)
        result["roles"]["throwing_elbow"]["original_point"]["x"] = 100
        self.assertEqual(raw["RIGHT_ELBOW"]["x"], .5)


if __name__ == "__main__":
    unittest.main()
