"""Safety/ambiguity checks for experimental full-frame immutable appearance."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import io
import sys

import numpy as np

spec = importlib.util.spec_from_file_location("subject_appearance", Path(__file__).resolve().parents[1] / "scripts/measure_subject_appearance.py")
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
try:
    import evaluate_subject_appearance as evaluator
finally:
    sys.path.pop(0)


class SubjectAppearanceTests(unittest.TestCase):
    def test_source_rejects_outside_degenerate_and_out_of_image_patches(self):
        hull = [[0, 0], [19, 0], [19, 19], [0, 19]]
        self.assertEqual(measure.source_patch_rect([10, 10], hull, 20, 20)[0], [6, 6, 9, 9])
        self.assertIsNone(measure.source_patch_rect([2, 2], hull, 20, 20)[0])
        self.assertIsNone(measure.source_patch_rect([10, 10], [[0, 0]]*4, 20, 20)[0])
        self.assertIsNone(measure.source_patch_rect([10, 10], [[0, 0], [5, 0], [5, 5], [0, 5]], 20, 20)[0])

    def test_earliest_gate_is_chosen_even_if_its_geometry_will_fail(self):
        def pose(x):
            return {n: {"x": x, "y": .5, "visibility": .5, "presence": .5} for n in measure.TORSO}
        frames = [{}, pose(-1), pose(.5)]
        self.assertEqual(measure.first_gate_frame(frames, {"min_visibility": .5, "min_presence": .5}), 1)
        self.assertIsNone(measure.first_gate_frame([{}], {"min_visibility": .5, "min_presence": .5}))

    def test_constant_normalized_denominators_are_unavailable(self):
        pattern = np.array([[0, 3, 5], [9, 2, 1], [7, 4, 8]], dtype=np.uint8)
        self.assertEqual(measure.matching_candidates(np.zeros((10, 10), np.uint8), pattern)["candidates"], [])
        self.assertEqual(measure.matching_candidates(np.zeros((10, 10), np.uint8), np.ones((3, 3), np.uint8))["reason"], "constant_template_denominator")
        self.assertTrue(np.all(measure.patch_variances(np.ones((10, 10), np.uint8)*127, 3) == 0))

    def test_equal_competitors_are_retained_in_row_column_order_without_identity(self):
        template = np.array([[0, 3, 5], [9, 2, 1], [7, 4, 8]], dtype=np.uint8)
        gray = np.zeros((12, 12), dtype=np.uint8)
        gray[1:4, 1:4] = template
        gray[1:4, 7:10] = template
        result = measure.matching_candidates(gray, template)
        self.assertEqual(result["candidates"][0]["rectangle_xywh"], [1, 1, 3, 3])
        self.assertEqual(result["candidates"][1]["rectangle_xywh"], [7, 1, 3, 3])
        self.assertGreaterEqual(result["candidates"][0]["equal_score_positions_before_this_suppression"], 2)
        self.assertEqual(result["top_competitor_margin"], 0)
        self.assertIsNone(result["identity_decision"])
        for a, b in zip(result["candidates"], result["candidates"][1:]):
            self.assertFalse(measure.rectangles_overlap(a["rectangle_xywh"], b["rectangle_xywh"]))

    def test_exact_variance_matches_direct_patches(self):
        gray = np.arange(144, dtype=np.uint8).reshape(12, 12)
        variances = measure.patch_variances(gray, 9)
        for y, x in ((0, 0), (2, 1), (3, 3)):
            self.assertAlmostEqual(variances[y, x], float(np.var(gray[y:y+9, x:x+9].astype(float))), places=10)

    def test_failed_image_save_cannot_silently_drop_review_evidence(self):
        with patch.object(measure.cv2, "imwrite", return_value=False):
            with self.assertRaises(OSError):
                measure.write_image(Path("unused.png"), np.zeros((9, 9), np.uint8))

    def test_raw_integer_capture_time_binds_to_fractional_video_time(self):
        meta = {"frame_count": 2, "timestamps_ms": [0, 1000/30]}
        capture = {"selection_frames": [{"timestamp_ms": 0}, {"timestamp_ms": 33}]}
        text = "frame,timestamp_ms,landmark,x,y,visibility,presence\n1,33,LEFT_SHOULDER,.2,.3,.8,.9\n"
        with patch.object(Path, "open", side_effect=lambda *args, **kwargs: io.StringIO(text)):
            path = Path("unused_raw.csv")
            self.assertIn("LEFT_SHOULDER", measure.load_raw(path, meta, capture)[1])
            capture["selection_frames"][1]["timestamp_ms"] = 34
            with self.assertRaises(ValueError):
                measure.load_raw(path, meta, capture)

    def test_evaluator_rejects_changed_match_receipts(self):
        evaluator.verify_candidate_receipts({"score": .8}, {"score": .8})
        with self.assertRaises(ValueError):
            evaluator.verify_candidate_receipts({"score": .8}, {"score": .9})

    def test_missing_manual_shoulder_is_not_filled_from_other_points(self):
        frame = {"joints": [{"name": n, "status": "visible", "x_px": x, "y_px": y}
                            for n, (x, y) in zip(measure.TORSO, ((0, 0), (9, 0), (9, 9), (0, 9)))]}
        self.assertIsNotNone(evaluator.manual_proxy(frame))
        frame["joints"][0].update({"status": "not_observable", "x_px": None, "y_px": None})
        self.assertIsNone(evaluator.manual_proxy(frame))


if __name__ == "__main__":
    unittest.main()
