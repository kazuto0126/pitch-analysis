"""Countercheck source binding, abstention, anatomical comparison and GT exclusions."""
from __future__ import annotations

import copy
import hashlib
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import measure_pose_mode_countercheck as measure
    import evaluate_pose_mode_countercheck as evaluate
finally:
    sys.path.pop(0)


CONFIG = {"min_visibility": .5, "min_presence": .5}


def point(x=.5, y=.5, visibility=.9, presence=.9):
    return {"x": x, "y": y, "z": 0., "visibility": visibility, "presence": presence}


def selected(index=0):
    return {"index": index, "status": "selected" if index is not None else "rejected"}


class PoseModeCountercheckTests(unittest.TestCase):
    def test_pixel_distance_uses_both_original_dimensions(self):
        value = measure.joint_comparison(point(.2, .3), point(.3, .5), 300, 200, CONFIG)
        self.assertAlmostEqual(value["gated_distance_px"], 50.)
        self.assertAlmostEqual(value["gated_distance_image_height"], .25)
        self.assertFalse(value["subject_alignment_verified"])

    def test_finite_wrong_point_is_not_declared_correct_by_gate(self):
        value = measure.joint_comparison(point(.2, .3), point(.8, .9), 300, 200, CONFIG)
        self.assertTrue(value["image_gate_pass"])
        self.assertFalse(value["subject_alignment_verified"])
        self.assertGreater(value["gated_distance_px"], 100.)

    def test_no_selected_or_below_gate_points_remain_distinct(self):
        missing = measure.joint_comparison(point(), None, 300, 200, CONFIG)
        below = measure.joint_comparison(point(), point(visibility=.49), 300, 200, CONFIG)
        self.assertIsNone(missing["both_finite_distance_px"])
        self.assertEqual(missing["unmeasured_reasons"], ["image_selected_point_missing"])
        self.assertEqual(below["both_finite_distance_px"], 0.)
        self.assertIsNone(below["gated_distance_px"])
        self.assertEqual(below["unmeasured_reasons"], ["image_below_existing_gate"])
        self.assertTrue(measure.gate(point(visibility=.5, presence=.5), CONFIG))
        self.assertFalse(measure.gate(point(presence=.49), CONFIG))

    def test_nonfinite_has_no_numeric_disagreement(self):
        value = measure.joint_comparison(point(), point(x=float("nan")), 300, 200, CONFIG)
        self.assertIsNone(value["both_finite_distance_px"])
        self.assertEqual(value["unmeasured_reasons"], ["image_nonfinite_point"])

    def test_selected_candidate_is_independent_not_same_ordinal_as_baseline(self):
        candidates = [[point(.1)] * 33, [point(.7)] * 33]
        self.assertEqual(measure.selected_points(candidates, selected(1))["LEFT_SHOULDER"]["x"], .7)
        self.assertEqual(measure.selected_points(candidates, selected(None)), {})
        with self.assertRaises(ValueError):
            measure.selected_points(candidates, selected(2))

    def test_no_pose_frame_preserves_all_joint_denominators_and_fractional_time(self):
        frame = measure.frame_measurement(1, 33, 1000 / 30, "receipt", [], selected(None), {},
                                          {"status": "rejected"}, 300, 200, CONFIG)
        self.assertEqual(len(frame["joint_disagreement"]), 33)
        self.assertEqual(frame["native_timestamp_ms"], 1000 / 30)
        self.assertIsNone(frame["torso_median_distance_px"])
        self.assertIsNone(frame["warning_prediction"])
        self.assertEqual(frame["image_candidates"], [])

    def test_incomplete_torso_does_not_impute_summary_from_remaining_joints(self):
        before = {n: point() for n in measure.LANDMARK_NAMES}
        before.pop("LEFT_SHOULDER")
        frame = measure.frame_measurement(0, 0, 0., "receipt", [[point()] * 33], selected(), before,
                                          {"status": "selected"}, 300, 200, CONFIG)
        self.assertIsNone(frame["torso_median_distance_px"])
        self.assertEqual(frame["joint_disagreement"]["LEFT_HIP"]["gated_distance_px"], 0.)

    def test_unbound_duplicate_or_unsafe_source_plan_is_rejected(self):
        clip = {"pitch_id": "example", "total_frames": 1,
                **{role: role for role in ("video", "metadata", "video_metadata", "raw_csv", "capture", "clean_config")}}
        sources = set(clip.values()) - {1, "example"}
        sources.update(("model", "src/pitch_analysis/subject.py", "src/pitch_analysis/pose_capture.py", "src/pitch_analysis/pose_estimator.py"))
        plan = {"clips": [clip], "model_path": "model", "expected_clip_count": 1,
                "expected_total_frames": 1, "measurement_source_hashes": dict.fromkeys(sources, "hash")}
        measure.validate_plan(plan)
        broken = copy.deepcopy(plan)
        del broken["measurement_source_hashes"]["model"]
        with self.assertRaisesRegex(ValueError, "Unbound"):
            measure.validate_plan(broken)
        broken = copy.deepcopy(plan)
        broken["clips"][0]["pitch_id"] = "../source"
        with self.assertRaisesRegex(ValueError, "unsafe"):
            measure.validate_plan(broken)
        broken = copy.deepcopy(plan)
        broken["clips"] *= 2
        broken["expected_clip_count"] = 2
        with self.assertRaisesRegex(ValueError, "denominator"):
            measure.validate_plan(broken)
        broken = copy.deepcopy(plan)
        broken["measurement_source_hashes"]["ground_truth"] = "hash"
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            measure.validate_plan(broken)

    def test_original_raw_rows_cannot_silently_shift_time_or_duplicate_joint(self):
        header = "frame,timestamp_ms,landmark,x,y,z,visibility,presence\n"
        rows = "".join(f"0,0,{name},.5,.5,0,.9,.9\n" for name in measure.LANDMARK_NAMES)
        context = {"selection_frames": [{"frame_index": 0, "timestamp_ms": 0, "status": "selected"}]}
        with patch.object(Path, "open", side_effect=lambda *a, **kw: io.StringIO(header + rows)):
            self.assertEqual(len(measure.load_video_raw(Path("unused"), context, 1)[0]), 33)
        with patch.object(Path, "open", side_effect=lambda *a, **kw: io.StringIO(header + rows.replace("0,0,", "0,1,"))):
            with self.assertRaisesRegex(ValueError, "time"):
                measure.load_video_raw(Path("unused"), context, 1)
        with patch.object(Path, "open", side_effect=lambda *a, **kw: io.StringIO(header + rows + rows)):
            with self.assertRaisesRegex(ValueError, "repeated"):
                measure.load_video_raw(Path("unused"), context, 1)

    def test_hidden_and_uncertain_coordinates_are_never_scored_even_if_xy_supplied(self):
        manual = {"frames": [{"joints": [{"name": "LEFT_SHOULDER", "status": status,
                  "x_px": 50., "y_px": 50.}]} for status in ("visible", "not_observable", "uncertain")]}
        frames = [{"frame_index": i, "image_candidates": [[point()] * 33], "image_selection": selected()} for i in range(3)]
        rows = evaluate.coordinate_rows(manual, [{"LEFT_SHOULDER": point()}] * 3, frames, 100, 100, CONFIG, ["known_negative"] * 3)
        self.assertEqual(rows[0]["image_error_px"], 0.)
        self.assertIsNone(rows[1]["image_error_px"])
        self.assertIsNone(rows[2]["image_error_px"])
        self.assertEqual(evaluate.coordinate_summary(rows)["visible_reference_denominator"], 1)

    def test_common_comparison_denominator_does_not_reward_missing_predictions(self):
        rows = [{"human_status": "visible", "video_error_px": 90., "image_error_px": None,
                 "video_gate_pass": True, "image_gate_pass": False},
                {"human_status": "visible", "video_error_px": 10., "image_error_px": 9.,
                 "video_gate_pass": True, "image_gate_pass": True}]
        summary = evaluate.coordinate_summary(rows)
        self.assertEqual(summary["visible_reference_denominator"], 2)
        self.assertEqual(summary["image_finite"]["count"], 1)
        self.assertEqual(summary["common_existing_gate"]["count"], 1)
        self.assertEqual(summary["common_existing_gate"]["video"]["mean"], 10.)

    def test_uncertain_major_is_not_a_negative_and_unmeasured_remains_in_total(self):
        labels = evaluate.major_timeline([{"start_frame": 1, "end_frame": 1, "status": "uncertain"},
                                         {"start_frame": 2, "end_frame": 3, "status": "confirmed"}], 4)
        result = evaluate.compare_distributions([0., 5., None, 2.], labels)
        self.assertEqual(result["positive_total"], 2)
        self.assertEqual(result["positive_unmeasured"], 1)
        self.assertEqual(result["negative_total"], 1)
        self.assertEqual(result["excluded_labels"], {"uncertain": 1})
        self.assertEqual(result["conditional_rank_auc_higher_is_positive"], 1.)
        self.assertIsNone(evaluate.rank_auc([], [0.]))

    def test_receipt_verifier_detects_modified_disagreement(self):
        class Capture:
            def __init__(self): self.count = 0
            def read(self):
                self.count += 1
                return (True, np.zeros((2, 3, 3), np.uint8)) if self.count == 1 else (False, None)
            def get(self, _key): return 0.
        raw = [{}]
        context = {"selection_frames": [{"frame_index": 0, "timestamp_ms": 0, "status": "rejected"}]}
        pixels = np.zeros((2, 3, 3), np.uint8)
        from dataclasses import asdict
        choice = asdict(measure.PitcherSelector().select([]))
        frame = measure.frame_measurement(0, 0, 0., hashlib.sha256(pixels.tobytes()).hexdigest(), [], choice, {}, context["selection_frames"][0], 3, 2, CONFIG)
        data = {"total_frames": 1, "width": 3, "height": 2, "frames": [frame]}
        evaluate.replay_and_verify(data, raw, context, Capture(), CONFIG)
        frame["joint_disagreement"]["LEFT_HIP"]["gated_distance_px"] = 0.
        with self.assertRaisesRegex(ValueError, "does not reproduce"):
            evaluate.replay_and_verify(data, raw, context, Capture(), CONFIG)


if __name__ == "__main__":
    unittest.main()
