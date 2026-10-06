"""Public mask access must stay in bounds and preserve missing evidence."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "subject_mask_points", Path(__file__).resolve().parents[1] / "scripts/measure_subject_mask_points.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class Mask:
    image_format, channels, width, height = 9, 1, 2, 2

    def __init__(self, data=((0.0, 0.2), (0.4, 1.0))):
        self.data, self.calls = data, []

    def __getitem__(self, key):
        row, col = key
        if not (0 <= row < self.height and 0 <= col < self.width):
            raise AssertionError("Invalid native coordinate")
        self.calls.append(key)
        return self.data[row][col]

    def numpy_view(self):
        raise AssertionError("Never call the failing native array reader")


class SubjectMaskPointTests(unittest.TestCase):
    def test_fractional_point_records_real_neighbors_and_zero_is_available(self):
        mask = Mask()
        value, pixels = measure.sample_mask_point(mask, 0.5, 0.5)
        self.assertAlmostEqual(value, 0.4)
        self.assertEqual(len(mask.calls), 4)
        self.assertAlmostEqual(sum(p["weight"] for p in pixels), 1)
        self.assertEqual(measure.sample_mask_point(mask, 0, 0)[0], 0)

    def test_last_pixel_retains_edge_without_out_of_bounds_native_access(self):
        mask = Mask()
        value, pixels = measure.sample_mask_point(mask, 1.9, 1.9)
        self.assertAlmostEqual(value, 1)
        self.assertEqual(mask.calls, [(1, 1)])
        self.assertEqual(len(pixels), 1)

    def test_invalid_queries_are_rejected_before_any_native_access(self):
        mask = Mask()
        for x, y in ((-0.1, 0), (2, 0), (0, 2), (float("nan"), 0), (0, float("inf"))):
            with self.subTest(x=x, y=y), self.assertRaises(ValueError):
                measure.sample_mask_point(mask, x, y)
        self.assertEqual(mask.calls, [])

    def test_invalid_probabilities_are_missing_without_clamping(self):
        for value in (float("nan"), float("inf"), -0.1, 1.1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "invalid_mask_probability"):
                measure.sample_mask_point(Mask(((value, 0), (0, 0))), 0, 0)

    def test_candidate_count_or_source_dimensions_mismatch_is_not_guessed(self):
        mask = Mask()
        self.assertEqual(measure.selected_mask([mask], 2, 0, 2, 2),
                         (None, "mask_candidate_count_mismatch"))
        self.assertEqual(measure.selected_mask([mask], 1, None, 2, 2), (None, "no_selected_subject"))
        self.assertEqual(measure.selected_mask([mask], 1, -1, 2, 2), (None, "selected_mask_absent"))
        self.assertEqual(measure.selected_mask([mask], 1, 0, 3, 2),
                         (None, "mask_source_dimensions_mismatch"))
        mask.image_format = 1
        self.assertEqual(measure.selected_mask([mask], 1, 0, 2, 2), (None, "unexpected_pose_mask_format"))
        self.assertEqual(mask.calls, [])
