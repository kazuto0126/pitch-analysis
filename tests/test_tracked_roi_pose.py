"""Synthetic tests for fixed tracked-ROI image inputs and original-frame mapping."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

import numpy as np

from pitch_analysis.subject import PitcherSelector, Selection


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    spec = importlib.util.spec_from_file_location("measure_tracked_roi_pose", ROOT / "scripts/measure_tracked_roi_pose.py")
    measure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(measure)
finally:
    sys.path.pop(0)


def pose(x=.5, shoulder=.2, hip=.5, ankle=.8):
    result = [SimpleNamespace(x=x, y=hip, z=.3, visibility=.9, presence=.8) for _ in range(33)]
    for index in [11, 12]:
        result[index].y = shoulder
    for index in [27, 28]:
        result[index].y = ankle
    return result


class CropMappingTests(unittest.TestCase):
    def test_floor_ceil_intersection_is_exact_without_padding_or_resize(self):
        self.assertEqual(measure.crop_bounds([-2.2, 3.7, 14.4, 30.1], 20, 24), [0, 3, 13, 24])
        self.assertEqual(measure.crop_bounds([5, 6, 10, 12], 20, 24), [5, 6, 15, 18])
        for rectangle in [None, [20, 0, 1, 1], [-2, 0, 2, 1], [0, 0, 0, 4]]:
            with self.subTest(rectangle=rectangle):
                self.assertIsNone(measure.crop_bounds(rectangle, 20, 24))

    def test_malformed_or_nonfinite_crop_rectangle_is_integrity_error(self):
        for rectangle in [[0, 0, 1], [True, 0, 1, 1], [float("nan"), 0, 1, 1], [0, 0, float("inf"), 1]]:
            with self.subTest(rectangle=rectangle), self.assertRaises(ValueError):
                measure.crop_bounds(rectangle, 20, 24)

    def test_xy_affine_z_width_scale_and_confidences_are_preserved(self):
        raw = measure.serialize_candidates([pose()])
        original = copy.deepcopy(raw)
        mapped = measure.map_candidates(raw, [85, 165, 302, 600], 510, 628)
        point = mapped[0][0]
        self.assertEqual(point["x"], (85 + .5 * 217) / 510)
        self.assertEqual(point["y"], (165 + .5 * 435) / 628)
        self.assertEqual(point["z"], .3 * 217 / 510)
        self.assertEqual(point["visibility"], .9)
        self.assertEqual(point["presence"], .8)
        self.assertEqual(raw, original)

    def test_outside_crop_model_coordinates_are_preserved_without_clamping(self):
        points = pose()
        points[0].x, points[0].y, points[0].z = -1.25, 2.5, -4.2
        raw = measure.serialize_candidates([points])
        mapped = measure.map_candidates(raw, [10, 20, 30, 60], 100, 100)[0][0]
        self.assertEqual(mapped["x"], -.15)
        self.assertEqual(mapped["y"], 1.2)
        self.assertEqual(mapped["z"], -4.2 * 20 / 100)
        self.assertEqual(raw[0][0]["x"], -1.25)

    def test_original_selector_uses_global_geometry_after_mapping(self):
        crop_pose = pose(x=.95)
        self.assertIsNone(PitcherSelector().select([crop_pose]).index)
        full = measure.map_candidates(measure.serialize_candidates([crop_pose]), [200, 60, 300, 560], 510, 628)
        selected = PitcherSelector().select([[SimpleNamespace(**point) for point in full[0]]])
        self.assertEqual(selected.index, 0)
        self.assertEqual(selected.status, "selected")

    def test_nonfinite_or_wrong_cardinality_landmark_aborts(self):
        for variant in [pose()[:-1], [*pose()[:-1], SimpleNamespace(x=float("nan"), y=.1, z=.3, visibility=.9, presence=.8)]]:
            with self.assertRaises(ValueError):
                measure.serialize_candidates([variant])


class RoiFrameTests(unittest.TestCase):
    def fixture(self, rectangles=None):
        rectangles = [[2, 3, 12, 20], None, [-2, 3, 12, 20]] if rectangles is None else rectangles
        pixels = [np.arange(32 * 40 * 3, dtype=np.uint8).reshape(32, 40, 3).copy() for _ in rectangles]
        times = [index * 1000 / 30 for index in range(len(rectangles))]
        tracked = {"frames": [{"frame_index": index, "native_timestamp_ms": times[index],
                               "decoded_bgr_sha256": hashlib.sha256(pixels[index].tobytes()).hexdigest(),
                               "usable_rectangle_xywh": rectangle} for index, rectangle in enumerate(rectangles)]}
        capture = Mock()
        capture.read.side_effect = [(True, pixel) for pixel in pixels] + [(False, None)]
        capture.get.side_effect = times
        detector = Mock()
        detector.detect.return_value = SimpleNamespace(pose_landmarks=[pose()])
        selector = Mock()
        selector.select.return_value = Selection(0, "selected", "synthetic", 1, .7, .8)
        return capture, detector, selector, tracked, {"timestamps_ms": times}, {"total_frames": len(rectangles), "width": 40, "height": 32}, pixels

    def run_fixture(self, values):
        return measure.measure_frames(*values[:6], image_factory=lambda rgb: rgb)

    def test_missing_roi_calls_empty_selector_and_preserves_timeline_and_gap(self):
        values = self.fixture()
        values = (*values[:2], PitcherSelector(), *values[3:])
        report = self.run_fixture(values)
        self.assertEqual(report["inference_calls"], 2)
        self.assertEqual(len(report["frames"]), 3)
        missing = report["frames"][1]
        self.assertEqual(missing["inference_status"], "roi_unavailable")
        self.assertEqual(missing["selection"]["status"], "rejected")
        self.assertEqual(missing["selection"]["candidate_count"], 0)
        self.assertEqual(missing["crop_candidates"], [])
        self.assertEqual(missing["full_image_candidates"], [])
        self.assertIsNone(missing["crop_bounds_xyxy"])
        self.assertIsNone(missing["crop_bgr_sha256"])
        self.assertIsNone(missing["crop_shape"])

    def test_actual_crop_shape_color_pixels_and_mapped_selector_input(self):
        values = self.fixture([[2, 3, 12, 20]])
        before = values[6][0].copy()
        report = self.run_fixture(values)
        rgb = values[1].detect.call_args.args[0]
        expected_bgr = before[3:23, 2:14]
        np.testing.assert_array_equal(rgb, expected_bgr[:, :, ::-1])
        self.assertTrue(rgb.flags.c_contiguous)
        frame = report["frames"][0]
        self.assertEqual(frame["crop_shape"], [20, 12, 3])
        self.assertEqual(frame["crop_bgr_sha256"], hashlib.sha256(expected_bgr.tobytes()).hexdigest())
        self.assertEqual(frame["crop_rgb_sha256"], hashlib.sha256(rgb.tobytes()).hexdigest())
        self.assertEqual(values[2].select.call_count, 1)
        selector_point = values[2].select.call_args.args[0][0][0]
        self.assertEqual(selector_point.x, (2 + .5 * 12) / 40)
        self.assertEqual(selector_point.y, (3 + .5 * 20) / 32)
        self.assertEqual(selector_point.z, .3 * 12 / 40)
        np.testing.assert_array_equal(values[6][0], before)

    def test_partial_rectangle_keeps_original_rectangle_and_intersected_slice(self):
        values = self.fixture([[-2.2, 25.5, 12.4, 20.3]])
        frame = self.run_fixture(values)["frames"][0]
        self.assertEqual(frame["tracker_rectangle_xywh"], [-2.2, 25.5, 12.4, 20.3])
        self.assertEqual(frame["crop_bounds_xyxy"], [0, 25, 11, 32])
        self.assertEqual(frame["crop_shape"], [7, 11, 3])

    def test_source_pixel_or_pts_mismatch_aborts_before_any_inference(self):
        for key, value in [("decoded_bgr_sha256", "0" * 64), ("native_timestamp_ms", 99.)]:
            values = self.fixture()
            values[3]["frames"][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "receipt mismatch"):
                self.run_fixture(values)
            values[1].detect.assert_not_called()

    def test_detector_exception_nonfinite_and_input_mutation_abort_without_fallback(self):
        for kind in ["exception", "nonfinite", "mutation"]:
            values = self.fixture([[2, 3, 12, 20]])
            if kind == "exception":
                values[1].detect.side_effect = RuntimeError("synthetic detection error")
            elif kind == "nonfinite":
                points = pose()
                points[0].z = float("inf")
                values[1].detect.return_value = SimpleNamespace(pose_landmarks=[points])
            else:
                def mutate(rgb):
                    rgb[0, 0, 0] ^= 255
                    return SimpleNamespace(pose_landmarks=[pose()])
                values[1].detect.side_effect = mutate
            with self.subTest(kind=kind), self.assertRaises((ValueError, RuntimeError)):
                self.run_fixture(values)
            values[1].detect.assert_called_once()
            values[2].select.assert_not_called()


class RoiFreezeTests(unittest.TestCase):
    def fixture(self):
        sources = {role: {"path": role + ".json", "sha256": "receipt"} for role in measure.PRODUCER_ROLES}
        dependencies = {str(index): {"path": path, "sha256": "receipt"}
                        for index, path in enumerate(sorted(measure.DEPENDENCY_PATHS))}
        plan = {"status": "frozen_before_measurement", "producer_sources": sources,
                "producer_dependencies": dependencies, "parameters": copy.deepcopy(measure.PARAMETERS),
                "options": copy.deepcopy(measure.OPTIONS), "target": copy.deepcopy(measure.TARGET),
                "runtime": {}, "native_binding_hashes": {"binding.dll": "receipt"},
                "proposal_manifest": "proposal.json", "proposal_manifest_sha256": "receipt",
                "producer_sha256": "receipt", "evaluator_sha256": "receipt", "producer_test_sha256": "receipt"}
        proposal = {"proposed_producer_sources": sources, "proposed_producer_dependencies": dependencies,
                    "proposed_parameters": copy.deepcopy(measure.PARAMETERS), "proposed_options": copy.deepcopy(measure.OPTIONS),
                    "target": copy.deepcopy(measure.TARGET), "runtime": {}, "native_binding_hashes": plan["native_binding_hashes"]}
        return plan, proposal

    def verify(self, plan, proposal, **kwargs):
        with patch.object(measure, "runtime", return_value={}), patch.object(measure, "sha", return_value="receipt"), \
                patch.object(measure, "read", return_value=proposal), patch.object(measure, "verify_sources") as sources:
            measure.verify_execution(ROOT, plan, **kwargs)
        return sources

    def test_only_five_producer_roles_and_four_bound_dependencies_are_accepted(self):
        plan, proposal = self.fixture()
        self.assertEqual(self.verify(plan, proposal).call_count, 2)
        for key in ["manual_xy", "ground_truth", "ownership_review", "old_pose"]:
            wrong = copy.deepcopy(plan)
            wrong["producer_sources"][key] = {"path": key, "sha256": "receipt"}
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "source role"):
                self.verify(wrong, proposal)
        wrong = copy.deepcopy(plan)
        wrong["producer_dependencies"].pop(next(iter(wrong["producer_dependencies"])))
        with self.assertRaisesRegex(ValueError, "dependency"):
            self.verify(wrong, proposal)

    def test_parameter_or_model_source_change_is_rejected(self):
        plan, proposal = self.fixture()
        for key, value in [("padding", 12), ("external_resize", [256, 256]), ("map_before_selector", False), ("fallback", "full_frame")]:
            wrong = copy.deepcopy(plan)
            wrong["parameters"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.verify(wrong, proposal)
        wrong = copy.deepcopy(plan)
        wrong["producer_sources"]["model"]["path"] = "another_model.task"
        with self.assertRaisesRegex(ValueError, "differs"):
            self.verify(wrong, proposal)

    def test_evaluator_true_binds_evaluator_and_producer_tests(self):
        plan, proposal = self.fixture()
        hashed = []
        with patch.object(measure, "runtime", return_value={}), patch.object(measure, "read", return_value=proposal), \
                patch.object(measure, "verify_sources"), \
                patch.object(measure, "sha", side_effect=lambda path: hashed.append(Path(path).as_posix()) or "receipt"):
            measure.verify_execution(ROOT, plan, evaluator=True)
        self.assertTrue(any(path.endswith("scripts/evaluate_tracked_roi_pose.py") for path in hashed))
        self.assertTrue(any(path.endswith("tests/test_tracked_roi_pose.py") for path in hashed))


if __name__ == "__main__":
    unittest.main()
