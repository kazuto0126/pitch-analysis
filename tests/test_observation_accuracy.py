"""Fixed denominator, paired comparison, coordinate and provenance assessment."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("observation_accuracy", Path(__file__).resolve().parents[1]/"scripts/assess_observation_accuracy.py")
assess = importlib.util.module_from_spec(spec)
spec.loader.exec_module(assess)


def row(state, raw, clean, human="visible"):
    return {"processed_state": state, "raw_error_px": raw, "processed_error_px": clean, "manual_state": human}


class ObservationAccuracyTests(unittest.TestCase):
    def test_missing_prediction_keeps_visible_denominator_and_is_not_zero_error(self):
        result = assess.aggregate(iter([row("observed", 10, 10), row("interpolated", 20, 25), row("missing", 100, None), row("observed", None, None, "not_observable")]))
        self.assertEqual(result["all_reference_rows"], 4)
        self.assertEqual(result["visible_reference_denominator"], 3)
        self.assertEqual(result["usable_reference_count"], 2)
        self.assertEqual(result["raw_on_full_visible_reference"]["count"], 3)
        self.assertEqual(result["same_usable_points_raw"]["mean_px"], 15)
        self.assertEqual(result["same_usable_points_clean"]["mean_px"], 17.5)
        self.assertEqual(result["by_saved_state"]["missing"]["clean_error"]["count"], 0)
        self.assertIsNone(result["by_saved_state"]["missing"]["clean_error"]["mean_px"])

    def test_nonvisible_truth_and_missing_clean_cannot_be_fabricated(self):
        for value in (row("missing", 10, 0), row("observed", 10, 10, "not_observable"), row("interpolated", 10, None)):
            with self.assertRaises(ValueError):
                assess.aggregate([value])

    def test_interpolation_compares_exact_same_points_and_retains_improvement_directions(self):
        result = assess.aggregate([row("interpolated", 10, 5), row("interpolated", 20, 28), row("missing", 1, None)])
        group = result["by_saved_state"]["interpolated"]
        self.assertEqual(group["paired_error_reduced"], 1)
        self.assertEqual(group["paired_error_increased"], 1)
        self.assertEqual(group["same_point_delta_clean_minus_raw"]["mean_px"], 1.5)
        self.assertEqual(group["same_point_raw_error"]["mean_px"], 15)

    def test_saved_width_normalization_and_outside_coordinates_are_not_clamped(self):
        self.assertEqual(assess.pixel_xy({"x": 1.2, "y": .5}, 510, 628), [612, 314])
        self.assertIsNone(assess.pixel_xy({"x": None, "y": None}, 510, 628))
        with self.assertRaises(ValueError):
            assess.pixel_xy({"x": float("nan"), "y": .5}, 510, 628)

    def test_saved_availability_provenance_is_not_manual_visibility(self):
        self.assertEqual(assess.state_of({"x": .3, "y": .4, "usable": True, "interpolated": True, "quality_valid": False}, False), "interpolated")
        self.assertEqual(assess.state_of({"x": None, "y": None, "usable": False, "interpolated": False, "quality_valid": False}, False), "missing")
        with self.assertRaises(ValueError):
            assess.state_of({"x": .3, "y": .4, "usable": True, "interpolated": False, "quality_valid": False}, True)

    def test_raw_missing_and_clean_usable_counts_are_separate(self):
        result = assess.aggregate([row("interpolated", None, 5), row("observed", 10, 10)])
        self.assertEqual(result["usable_reference_count"], 2)
        self.assertEqual(result["paired_usable_reference_count"], 1)
        self.assertEqual(result["raw_missing_on_visible_reference"], 1)
        self.assertEqual(result["same_usable_points_raw"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
