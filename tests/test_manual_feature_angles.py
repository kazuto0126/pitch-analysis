from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).resolve().parents[1]/'src')]
import assess_manual_feature_angles as assess


class ManualFeatureAngleTests(unittest.TestCase):
    def row(self, reference=90., raw=90., base=90., smooth=90.):
        return {'frame_index': 0, 'manual_reference': {'value_deg': reference, 'unavailable_reasons': []},
            'streams_deg': {'raw_unfiltered': raw, 'processed_base': base, 'feature_interpolated': base, 'feature_smoothed': smooth},
            'model_state_context': 'observed|observed|missing', 'existing_review_status': 'hold_joint_review', 'existing_major_hold': True}

    def test_known_right_and_straight_angles(self):
        self.assertAlmostEqual(assess.angle([(1,0),(0,0),(0,1)]), 90.)
        self.assertAlmostEqual(assess.angle([(-1,0),(0,0),(1,0)]), 180.)

    def test_missing_nonfinite_and_degenerate_angles_stay_null(self):
        for points in ([(0,0),(0,0),(1,0)], [(1,0),None,(0,1)], [(1,0),(0,0),(float('nan'),1)]):
            self.assertIsNone(assess.angle(points))

    def test_occluded_guessed_coordinate_never_becomes_reference(self):
        joints = {n: {'status': 'visible', 'x_px': p[0], 'y_px': p[1]} for n,p in zip(('a','b','c'), [(1,0),(0,0),(0,1)])}
        joints['c']['status'] = 'not_observable'
        self.assertIsNone(assess.manual_reference(joints, ('a','b','c'))['value_deg'])
        self.assertEqual(assess.manual_reference(joints, ('a','b','c'))['unavailable_reasons'], ['manual_not_observable:c'])

    def test_original_pixel_plane_preserves_aspect_ratio(self):
        # These are already source pixels; normalizing each axis separately distorts the angle.
        pixel = assess.angle([(200,0),(0,0),(200,100)])
        normalized = assess.angle([(1,0),(0,0),(1,1)])
        self.assertAlmostEqual(pixel, 26.56505117707799)
        self.assertAlmostEqual(normalized, 45.)

    def test_unavailable_prediction_remains_in_reference_denominator(self):
        rows = [self.row(base=None), self.row(reference=None), self.row(base=100.)]
        result = assess.stream_summary(rows, 'processed_base')
        self.assertEqual((result['source_frame_denominator'], result['manual_reference_frames'], result['paired_frames']), (3,2,1))
        self.assertEqual(result['reference_present_prediction_missing'], 1)
        self.assertEqual(result['prediction_present_without_manual_reference'], 1)
        self.assertEqual(result['mae_deg'], 10.)

    def test_paired_change_uses_identical_frames_and_reports_worsening(self):
        rows = [self.row(raw=110.,base=95.), self.row(raw=91.,base=100.), self.row(raw=None,base=90.), self.row(reference=None)]
        result = assess.paired_change(rows, 'raw_unfiltered', 'processed_base')
        self.assertEqual(result['paired_frames'], 2)
        self.assertEqual((result['error_decreased'],result['error_increased'],result['numerically_equal']), (1,1,0))

    def test_empty_reference_statistics_are_null(self):
        result = assess.stream_summary([self.row(reference=None)], 'raw_unfiltered')
        self.assertEqual(result['paired_frames'], 0)
        self.assertIsNone(result['mae_deg']); self.assertIsNone(result['p95_absolute_deg'])

    def test_percentile_uses_declared_linear_interpolation(self):
        self.assertEqual(assess.percentile([0., 10., 20.], .95), 19.)

    def test_existing_major_and_joint_holds_do_not_disappear_from_assessment(self):
        result = assess.summarize([self.row(base=130.)])
        self.assertEqual(result['streams']['processed_base']['mae_deg'], 40.)
        self.assertEqual(result['by_existing_major_hold']['True']['source_frames'], 1)

    def test_input_rows_are_not_changed_by_summary(self):
        rows = [self.row(),self.row(reference=None)]; original = deepcopy(rows)
        assess.summarize(rows)
        self.assertEqual(rows, original)


if __name__ == '__main__': unittest.main()
