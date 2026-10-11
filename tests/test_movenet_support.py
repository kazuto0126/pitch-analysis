"""Geometry-support semantics and immutable offline source regressions."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import measure_movenet_support as support
finally:
    sys.path.pop(0)


TARGET = {"pitch_id": "synthetic", "total_frames": 2, "width": 100, "height": 100}
ROI = [0., 0., 80., 80.]


def raw(x=.2, y=.2, confidence=0.):
    return {name: {"x": x, "y": y, "z": 0., "visibility": confidence, "presence": confidence}
        for name in support.TORSO}


def slots(boxes=([10., 10., 30., 30.],), *, score=0.):
    output = []
    for index in range(6):
        candidate = index < len(boxes)
        xy = [20., 20.] if candidate else [90., 90.]
        box = boxes[index] if candidate else [85., 85., 99., 99.]
        output.append({"slot_index": index, "source_xy": [xy[:] for _ in support.geometry.JOINTS],
            "native_yx_score": [[0., 0., score] for _ in support.geometry.JOINTS],
            "source_box_xyxy": box[:], "native_box_ymin_xmin_ymax_xmax_score": [0., 0., 1., 1., score]})
    return output


class SupportGeometryTests(unittest.TestCase):
    def test_single_full_box_support_is_no_warning_not_correctness(self):
        value = support.frame_support(slots(), ROI, raw(), TARGET)
        self.assertEqual((value["status"], value["warning"]), ("no_warning", False))
        self.assertEqual(value["supporting_slot_indices"], [0])
        self.assertFalse(value["subject_alignment_verified"])
        self.assertIsNone(value["confirmed_major_failure"])
        self.assertEqual(len(value["slot_support_tests"]), 6)

    def test_half_open_box_lower_included_upper_excluded(self):
        for x, expected in ((.1, "no_warning"), (.3, "warning")):
            with self.subTest(x=x):
                value = support.frame_support(slots(), ROI, raw(x=x), TARGET)
                self.assertEqual(value["status"], expected)

    def test_multiple_candidates_one_support_is_enough_without_a_winner(self):
        value = support.frame_support(slots(([1., 1., 5., 5.], [10., 10., 30., 30.])), ROI, raw(), TARGET)
        self.assertEqual(value["association_status"], "ambiguous")
        self.assertEqual(value["candidate_count"], 2)
        self.assertEqual(value["status"], "no_warning")
        self.assertEqual(value["supporting_slot_indices"], [1])
        self.assertIsNone(value["association"]["descriptive_slot_index"])

    def test_warning_requires_every_candidate_to_contradict(self):
        value = support.frame_support(slots(([1., 1., 5., 5.], [30., 30., 40., 40.])), ROI, raw(), TARGET)
        self.assertEqual((value["status"], value["warning"]), ("warning", True))
        self.assertEqual(value["reason"], support.WARNING_POLICY["rule"])
        self.assertEqual(value["supporting_slot_indices"], [])

    def test_missing_and_nonfinite_raw_abstain_even_if_other_points_contradict(self):
        for point in (None, {"x": float("nan"), "y": .2, "visibility": 1., "presence": 1.},
                {"x": 1e308, "y": .2, "visibility": 1., "presence": 1.}):
            points = raw(x=.8)
            points[support.TORSO[0]] = point
            with self.subTest(point=point):
                value = support.frame_support(slots(), ROI, points, TARGET)
                self.assertEqual(value["status"], "insufficient_evidence")
                self.assertIsNone(value["warning"])
                json.dumps(value, allow_nan=False)

    def test_no_candidates_and_missing_csrt_abstain(self):
        for rectangle, values in ((ROI, slots(())), (None, slots())):
            with self.subTest(rectangle=rectangle):
                value = support.frame_support(values, rectangle, raw(), TARGET)
                self.assertEqual(value["status"], "insufficient_evidence")
                self.assertIsNone(value["warning"])
                self.assertEqual(value["candidate_count"], 0)

    def test_individual_points_in_different_boxes_cannot_be_assembled(self):
        points = raw()
        points["LEFT_HIP"]["x"] = .4
        points["RIGHT_HIP"]["x"] = .4
        value = support.frame_support(slots(([10., 10., 30., 30.], [30., 10., 50., 30.])), ROI, points, TARGET)
        self.assertEqual(value["status"], "warning")
        self.assertTrue(value["slot_support_tests"][0]["raw_torso_inside_box"]["LEFT_SHOULDER"])
        self.assertTrue(value["slot_support_tests"][1]["raw_torso_inside_box"]["LEFT_HIP"])
        self.assertFalse(any(row["contains_all_raw_torso"] for row in value["slot_support_tests"]))

    def test_zero_native_score_and_raw_confidence_have_no_cutoff(self):
        low = support.frame_support(slots(score=0.), ROI, raw(confidence=0.), TARGET)
        high = support.frame_support(slots(score=1.), ROI, raw(confidence=1.), TARGET)
        self.assertEqual(low["status"], high["status"])
        self.assertEqual(low["candidate_slot_indices"], high["candidate_slot_indices"])
        self.assertEqual(low["supporting_slot_indices"], high["supporting_slot_indices"])


class ImmutableInputTests(unittest.TestCase):
    def test_existing_outside_and_root_output_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "analysis_results" / "existing").mkdir(parents=True)
            for value in ("analysis_results/existing", "analysis_results", "elsewhere/new", "../outside"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    support.output_path(root, value)

    def test_source_mutation_after_computation_aborts_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            source = root / "source.json"
            source.write_text("sealed", encoding="utf-8")
            ref = {"path": "source.json", "sha256": support.geometry.sha(source)}
            plan = {"output_directory": "analysis_results/new", "clips": [{}]}
            path = root / "plan.json"
            path.write_text(json.dumps(plan), encoding="utf-8")
            def verify(*args):
                support.geometry.verify_ref(root, ref)
            def mutate(*args):
                source.write_text("changed", encoding="utf-8")
                return {}
            with patch.object(support, "verify_plan", side_effect=verify), \
                    patch.object(support, "measure_clip", side_effect=mutate):
                with self.assertRaisesRegex(ValueError, "Frozen source changed"):
                    support.measure(root, path)
            self.assertFalse((root / "analysis_results" / "new").exists())

    def test_ground_truth_role_and_changed_policy_fail_closed(self):
        plan = {"status": "frozen_before_support_measurement", "warning_policy": copy.deepcopy(support.WARNING_POLICY),
            "code": {name: {"path": path, "sha256": "synthetic"} for name, path in support.CODE_PATHS.items()},
            "source_frames": 2, "non_seed_frames": 1,
            "clips": [{"target": TARGET, "sources": {role: {} for role in support.SOURCE_ROLES}}]}
        plan["clips"][0]["sources"]["ground_truth"] = {}
        with patch.object(support.geometry, "verify_ref"), patch.object(support.geometry, "sha", return_value="synthetic"):
            with self.assertRaisesRegex(ValueError, "only permits"):
                support.verify_plan(ROOT, plan)
        plan["warning_policy"]["score_cutoff"] = .5
        with self.assertRaisesRegex(ValueError, "changed support warning policy"):
            support.verify_plan(ROOT, plan)


if __name__ == "__main__":
    unittest.main()
