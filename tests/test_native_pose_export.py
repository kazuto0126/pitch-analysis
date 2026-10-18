"""Visible XY comparisons preserve unknowns and original Full context."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from export_native_pose_review import coordinate_comparison
from pitch_analysis.manual_keypoints import JOINT_NAMES


class SavedSource:
    def __init__(self, x, y):
        self.manifest = {'pitch_id': 'fixture', 'video': {'sha256': 'a' * 64},
                         'image_size': {'width': 10, 'height': 10}}
        self.points = [[{'name': name, 'x_px': x, 'y_px': y, 'visibility': .1, 'presence': .1}
                        for name in JOINT_NAMES] for _ in range(2)]

    def __len__(self):
        return len(self.points)

    def read_frame(self, index):
        return SimpleNamespace(to_dict=lambda: {'landmarks': deepcopy(self.points[index])})


class NativeExportComparisonTests(unittest.TestCase):
    def setUp(self):
        self.sources = {'mediapipe': SavedSource(4, 6), 'rtmpose': SavedSource(1, 3)}
        source = {'pitch_id': 'fixture', 'sha256': 'a' * 64, 'total_frames': 2}
        self.manual = {'source_video': source, 'image_size': {'width': 10, 'height': 10}, 'frames': [
            {'frame_index': i, 'joints': [{'name': name, 'status': 'visible', 'x_px': 1, 'y_px': 2}
                                         for name in JOINT_NAMES]} for i in range(2)]}
        self.gt = {'source_video': deepcopy(source), 'labels': {'major_pose_failure_intervals': [
            {'start_frame': 1, 'end_frame': 1, 'status': 'confirmed'}]}}

    def test_visible_same_point_pairing_ignores_legacy_score_gate(self):
        result = coordinate_comparison(self.sources, self.manual, self.gt)
        self.assertEqual(result['source_rows'], 24)
        values = result['non_seed']['RIGHT_ELBOW']['same_frame_same_joint_paired']
        self.assertEqual(values['mediapipe']['mean_px'], 5)
        self.assertEqual(values['rtmpose']['mean_px'], 1)
        self.assertEqual(values['rtmpose_closer'], 1)
        self.assertEqual(len(result['rows']), 24)
        self.assertEqual(result['original_full_major_frames'], [1])
        self.assertEqual(result['outside_original_full_major_hold']['RIGHT_ELBOW']['source_rows'], 0)

    def test_invisible_uncertain_and_native_missing_stay_in_denominators(self):
        invisible = self.manual['frames'][1]['joints'][0]
        invisible.update(status='not_observable', x_px=None, y_px=None)
        uncertain = self.manual['frames'][1]['joints'][1]
        uncertain.update(status='uncertain', x_px=None, y_px=None)
        self.sources['rtmpose'].points[1][3].update(x_px=None, y_px=None)
        result = coordinate_comparison(self.sources, self.manual, self.gt)
        self.assertEqual(result['non_seed_human_status_counts'], {'not_observable': 1, 'uncertain': 1, 'visible': 10})
        elbow = result['non_seed']['RIGHT_ELBOW']
        self.assertEqual(elbow['visible_rtmpose_missing'], 1)
        self.assertEqual(elbow['same_frame_same_joint_paired']['rtmpose']['n'], 0)
        self.assertIsNone(elbow['same_frame_same_joint_paired']['rtmpose']['mean_px'])
        self.assertIsNone(result['rows'][12]['rtmpose_error_px'])
        self.assertIsNone(result['rows'][13]['rtmpose_error_px'])

    def test_mismatched_reference_source_or_frame_sequence_is_rejected(self):
        self.manual['source_video']['sha256'] = 'b' * 64
        with self.assertRaisesRegex(ValueError, 'binding'):
            coordinate_comparison(self.sources, self.manual, self.gt)
        self.manual['source_video']['sha256'] = 'a' * 64
        self.manual['frames'][1]['frame_index'] = 3
        with self.assertRaisesRegex(ValueError, 'timeline'):
            coordinate_comparison(self.sources, self.manual, self.gt)

    def test_original_full_context_never_filters_native_comparison(self):
        a = coordinate_comparison(self.sources, self.manual, self.gt)
        self.gt['labels']['major_pose_failure_intervals'] = []
        b = coordinate_comparison(self.sources, self.manual, self.gt)
        self.assertEqual(a['non_seed'], b['non_seed'])
        self.assertEqual(a['all_human_status_counts'], b['all_human_status_counts'])
        self.assertEqual(len(a['rows']), len(b['rows']))


if __name__ == '__main__':
    unittest.main()
