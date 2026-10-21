"""Person-conditioned affine and explicit no-inference native frame semantics."""
from copy import deepcopy
import unittest

import numpy as np

from pitch_analysis.native_pose import NativePoseFrame, TOPOLOGIES
from pitch_analysis.native_pose_estimator import RTMPoseNativeEstimator, prepare_rtmpose_input
from pitch_analysis.native_pose_review import draw_native_frame
from test_native_pose_contract import make_frame


def missing_frame(reason="ambiguous_subject_boxes"):
    frame = make_frame()
    frame["backend"] = "rtmpose_person_box_onnx"
    frame["input_geometry"] = {
        "input_mode": "not_run", "roi_xywh": None, "affine_src_to_input": None,
        "affine_input_to_src": None, "sdk_geometry": None,
    }
    frame["model_selection"] = {
        "inference_mode": "live_stateless_roi", "pose_not_run": True,
        "pose_not_run_reason": reason,
        "person_box_selection": {"status": reason, "eligible_count": 2,
                                 "selected_bbox_xyxy_px": None},
    }
    for point in frame["landmarks"]:
        point.update(x_px=None, y_px=None, native_score=None, coordinate_state="missing",
                     missing_reason=reason, source_record={"pose_not_run": True})
    return frame


class PersonBoxGeometryTests(unittest.TestCase):
    def setUp(self):
        self.frame = np.full((240, 320, 3), [200, 210, 220], dtype=np.uint8)
        self.crop = [40, 50, 260, 210]
        self.frame[50:210, 40:260] = [20, 40, 60]
        self.box = [90., 70., 170., 190.]

    def test_bbox_center_and_affine_roundtrip_preserve_original_pixel_coordinates(self):
        _, geometry = prepare_rtmpose_input(self.frame, self.crop, person_bbox_xyxy=self.box)
        forward = np.asarray(geometry["affine_src_to_input"])
        inverse = np.asarray(geometry["affine_input_to_src"])
        np.testing.assert_allclose(forward @ [130, 130, 1], [96, 128], atol=1e-6)
        for point in ([90, 70], [170, 190], [130, 130], [80, 100]):
            mapped = forward @ [*point, 1]
            np.testing.assert_allclose(inverse @ [*mapped, 1], point, atol=1e-6)
        self.assertEqual(geometry["sdk_geometry"]["person_bbox_xyxy_px"], self.box)
        self.assertEqual(geometry["sdk_geometry"]["center_source_px"], [130., 130.])

    def test_bbox_padding_uses_crop_context_but_never_pixels_outside_approved_crop(self):
        changed = self.frame.copy()
        changed[:50] = 0
        changed[210:] = 255
        changed[:, :40] = 255
        changed[:, 260:] = 0
        tensor, geometry = prepare_rtmpose_input(self.frame, self.crop, person_bbox_xyxy=self.box)
        other, _ = prepare_rtmpose_input(changed, self.crop, person_bbox_xyxy=self.box)
        np.testing.assert_array_equal(tensor, other)
        # X=85 is outside the person box but inside its 1.25 affine margin.
        position = np.asarray(geometry["affine_src_to_input"]) @ [85, 130, 1]
        actual = tensor[0, :, round(position[1]), round(position[0])]
        expected = (np.array([20., 40., 60.]) - [123.675, 116.28, 103.53]) / [58.395, 57.12, 57.375]
        np.testing.assert_allclose(actual, expected, atol=1e-6)

    def test_unclamped_bbox_outside_crop_remains_recorded_and_padding_is_black(self):
        box = [30., 35., 100., 140.]
        tensor, geometry = prepare_rtmpose_input(self.frame, self.crop, person_bbox_xyxy=box)
        sdk = geometry["sdk_geometry"]
        self.assertEqual(sdk["person_bbox_xyxy_px"], box)
        self.assertFalse(sdk["person_bbox_clamped"])
        self.assertTrue(sdk["person_bbox_outside_approved_crop"])
        self.assertEqual(sdk["person_bbox_crop_intersection_xyxy_px"], [40, 50, 100., 140.])
        expected = -np.array([123.675, 116.28, 103.53]) / [58.395, 57.12, 57.375]
        np.testing.assert_allclose(tensor[0, :, 0, 0], expected, atol=1e-6)

    def test_optional_bbox_absent_preserves_original_geometry_and_tensor(self):
        old_tensor, old = prepare_rtmpose_input(self.frame, self.crop)
        none_tensor, none = prepare_rtmpose_input(self.frame, self.crop, person_bbox_xyxy=None)
        box_tensor, _ = prepare_rtmpose_input(self.frame, self.crop, person_bbox_xyxy=self.crop)
        np.testing.assert_array_equal(old_tensor, none_tensor)
        np.testing.assert_array_equal(old_tensor, box_tensor)
        self.assertEqual(old, none)
        self.assertEqual(old["sdk_geometry"]["preprocessing"], "openmmlab_sealed_onnx_example_crop_then_affine")
        self.assertNotIn("person_bbox_xyxy_px", old["sdk_geometry"])

    def test_invalid_boxes_rejected_before_transport_call(self):
        class NoCalls:
            def run(self, tensor):
                raise AssertionError("Invalid box must not call transport")
        estimator = RTMPoseNativeEstimator(NoCalls(), crop_xyxy=tuple(self.crop))
        for box in ([1, 2, 1, 3], [1, 2, 3, 2], [0, 0, 10, 10], [1, 2, 3],
                    [False, 70, 170, 190], [90, 70, np.nan, 190], [90, 70, np.inf, 190],
                    [-1e308, 70, 1e308, 190], [-1e39, 70, 1e39, 190]):
            with self.subTest(box=box), self.assertRaises(ValueError):
                estimator.estimate(self.frame, person_bbox_xyxy=box)

    def test_estimator_uses_one_call_and_decodes_selected_bbox_center(self):
        class OneCall:
            calls = 0
            def run(self, tensor):
                self.calls += 1
                self.tensor = tensor
                x, y = np.zeros((1, 17, 384), dtype=np.float32), np.zeros((1, 17, 512), dtype=np.float32)
                x[:, :, 192] = .2
                y[:, :, 256] = .3
                return x, y
        transport = OneCall()
        estimate = RTMPoseNativeEstimator(transport, crop_xyxy=tuple(self.crop)).estimate(
            self.frame, person_bbox_xyxy=self.box)
        self.assertEqual(transport.calls, 1)
        self.assertEqual(transport.tensor.shape, (1, 3, 256, 192))
        self.assertEqual(estimate.landmarks[0]["coordinate_state"], "model_observed")
        self.assertAlmostEqual(estimate.landmarks[0]["x_px"], 130)
        self.assertAlmostEqual(estimate.landmarks[0]["y_px"], 130)
        self.assertLess(estimate.landmarks[0]["native_score"], .5)


class PersonBoxNoInferenceContractTests(unittest.TestCase):
    def test_no_box_and_ambiguous_frames_keep_all17_missing_without_invented_affine(self):
        for reason in ("no_subject_box", "ambiguous_subject_boxes"):
            with self.subTest(reason=reason):
                frame = NativePoseFrame(missing_frame(reason)).to_dict()
                self.assertEqual(len(frame["landmarks"]), len(TOPOLOGIES["coco_17"]["names"]))
                self.assertTrue(all(p["coordinate_state"] == "missing" for p in frame["landmarks"]))
                self.assertIsNone(frame["input_geometry"]["affine_src_to_input"])
                self.assertIsNone(frame["usable_for_analysis"])

    def test_not_run_rejects_observed_points_fake_scores_different_reasons_and_geometry(self):
        mutations = [lambda f: f["landmarks"][0].update(x_px=1, y_px=2, coordinate_state="model_observed", missing_reason=None),
                     lambda f: f["landmarks"][0].update(native_score=.9),
                     lambda f: f["landmarks"][0].update(missing_reason="other"),
                     lambda f: f["input_geometry"].update(roi_xywh=[0, 0, 100, 200]),
                     lambda f: f["input_geometry"].update(affine_src_to_input=[[1, 0, 0], [0, 1, 0]])]
        for mutate in mutations:
            frame = missing_frame()
            mutate(frame)
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                NativePoseFrame(frame)

    def test_not_run_rejects_missing_or_false_provenance_and_wrong_backends(self):
        for mutate in (lambda f: f["model_selection"].pop("pose_not_run"),
                       lambda f: f["model_selection"].update(pose_not_run=False),
                       lambda f: f["model_selection"].update(pose_not_run=1),
                       lambda f: f["model_selection"].update(pose_not_run_reason=" "),
                       lambda f: f["model_selection"].update(inference_mode="cached_read_only"),
                       lambda f: f.update(backend="other_model")):
            frame = missing_frame()
            mutate(frame)
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                NativePoseFrame(frame)

    def test_executed_affine_cannot_claim_pose_not_run(self):
        frame = make_frame()
        frame["model_selection"]["pose_not_run"] = True
        with self.assertRaisesRegex(ValueError, "Executed"):
            NativePoseFrame(frame)

    def test_cached_mediapipe_cannot_use_not_run_geometry(self):
        frame = make_frame("mediapipe_33")
        frame["input_geometry"] = deepcopy(missing_frame()["input_geometry"])
        frame["model_selection"] = deepcopy(missing_frame()["model_selection"])
        with self.assertRaisesRegex(ValueError, "live RTMPose"):
            NativePoseFrame(frame)

    def test_overlay_visibly_marks_no_inference_without_fabricating_joint_markers(self):
        image = np.full((200, 100, 3), 100, dtype=np.uint8)
        result = draw_native_frame(image, NativePoseFrame(missing_frame()).to_dict(),
                                   source_mode="live_stateless_roi")
        np.testing.assert_array_equal(image[73:], result[73:])
        self.assertFalse(np.array_equal(image[:73], result[:73]))
        np.testing.assert_array_equal(image, np.full((200, 100, 3), 100, dtype=np.uint8))


if __name__ == "__main__":
    unittest.main()
