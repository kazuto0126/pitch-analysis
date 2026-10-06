"""Synthetic checks for evidence validity, separate from production pose logic."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

directory = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(directory))
try:
    import measure_feature_validity_evidence as measure
    spec = importlib.util.spec_from_file_location('feature_support_evaluator', directory / 'evaluate_feature_support_evidence.py')
    evaluate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluate)
finally:
    sys.path.pop(0)


def human_frame():
    positions = [(0, 0), (10, 0), (0, 10), (10, 10)]
    return {'joints': [dict(name=name, status='visible', x_px=x, y_px=y)
                       for name, (x, y) in zip(evaluate.TORSO, positions, strict=True)]}


class FeatureSupportExperimentTests(unittest.TestCase):
    def test_missing_values_and_ties_keep_shared_rank(self):
        ranks = measure.midrank_percentiles([1, 1, 2, None])
        np.testing.assert_allclose(ranks[:3], [1/3, 1/3, 5/6])
        self.assertIsNone(ranks[3])
        self.assertEqual(measure.rank_group(ranks[0]), measure.rank_group(ranks[1]))
        self.assertEqual(measure.midrank_percentiles([4, 4, 4]), [.5, .5, .5])
        self.assertEqual(measure.midrank_percentiles([None]), [None])
        with self.assertRaises(ValueError):
            measure.midrank_percentiles([float('nan')])

    def test_occluded_landmark_does_not_create_three_point_proxy(self):
        frame = human_frame()
        frame['joints'][1].update(status='not_observable', x_px=None, y_px=None)
        hull, reasons = evaluate.visible_torso_proxy(frame)
        self.assertIsNone(hull)
        self.assertIn('RIGHT_SHOULDER', reasons[0])
        frame = human_frame()
        for joint in frame['joints']:
            joint['y_px'] = 0
        self.assertIsNone(evaluate.visible_torso_proxy(frame)[0])

    def test_signed_distance_and_boundary_membership_have_known_geometry(self):
        hull, reasons = evaluate.visible_torso_proxy(human_frame())
        self.assertEqual(reasons, [])
        self.assertAlmostEqual(evaluate.signed_distance([5, 5], hull), 5)
        self.assertAlmostEqual(evaluate.signed_distance([15, 5], hull), -5)
        self.assertEqual(evaluate.signed_distance([0, 5], hull), 0)
        self.assertIsNone(evaluate.signed_distance([5, 5], None))

    def test_pair_support_requires_both_human_endpoints(self):
        self.assertEqual(evaluate.pair_state(1, 1), 'both_inside')
        self.assertEqual(evaluate.pair_state(1, -1), 'previous_only')
        self.assertEqual(evaluate.pair_state(-1, 1), 'current_only')
        self.assertEqual(evaluate.pair_state(-1, -1), 'neither_inside')
        self.assertIsNone(evaluate.pair_state(None, -1))
        self.assertIsNone(evaluate.pair_state(1, None))

    def test_small_fb_and_coherent_motion_do_not_imply_torso_support(self):
        features = [dict(feature_id=i, numerically_usable=True,
                         forward_xy_px=[50+x, 50+y], previous_xy_px=[49+x, 50+y],
                         fb_error_px=.001, lifetime_frames=10)
                    for i, (x, y) in enumerate([(0, 0), (3, 0), (0, 3)])]
        rows = measure.feature_diagnostics(dict(torso_features=features))
        hull, _ = evaluate.visible_torso_proxy(human_frame())
        for row in rows:
            self.assertEqual(row['movement_deviation_from_same_cohort_median_px'], 0)
            self.assertLess(evaluate.signed_distance(row['current_xy_px'], hull), 0)
            self.assertEqual(row['fb_error_px'], .001)

    def test_auc_matches_pair_comparison_and_reports_missing_scores(self):
        rows = [dict(signed_distance_px=d, fb_error_px=v)
                for d, v in [(-1, 2), (-1, 3), (1, 1), (1, 2), (-1, None)]]
        result = evaluate.conditional_score_auc(rows, 'fb_error_px')
        self.assertEqual(result['conditional_rank_auc_higher_is_outside'], .875)
        self.assertEqual(result['total_positive'], 3)
        self.assertEqual(result['measured_positive'], 2)
        self.assertFalse(result['warning_or_foreground_accuracy'])
        self.assertIsNone(evaluate.conditional_score_auc(rows[:2], 'fb_error_px')['conditional_rank_auc_higher_is_outside'])

    def test_fresh_output_requirement_preserves_existing_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / 'original.txt'
            marker.write_text('preserve')
            with self.assertRaises(FileExistsError):
                measure.measure(root, root / 'plan.json', root)
            self.assertEqual(marker.read_text(), 'preserve')

    def test_saved_diagnostics_ignore_invalid_gt_and_preserve_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'saved'
            source.mkdir()
            (source / 'ground_truth.json').write_text('INTENTIONALLY INVALID HUMAN FILE')
            parameters = dict(human_inputs_to_producer=[], warning_thresholds=None,
                              feature_rejection_or_reseeding=False, quality_scores=list(evaluate.SCORES))
            plan_path = root / 'plan.json'
            plan_path.write_text(json.dumps(dict(parameters=parameters)))
            old_producer = directory / 'measure_image_pose_evidence.py'
            run = dict(status='measurements_only', human_annotation_inputs=[], warning_predictions_generated=False,
                       producer_code_sha256=measure.sha(old_producer),
                       results=[dict(pitch_id='pitch_test', total_frames=2)])
            (source / 'measurement_run.json').write_text(json.dumps(run))
            clip_dir = source / 'pitch_test'
            clip_dir.mkdir()
            frames = []
            for index in range(2):
                features = [dict(feature_id=i, numerically_usable=True, current_xy_px=[x+index, y],
                                 previous_xy_px=[x, y] if index else None,
                                 fb_error_px=.2 if index else None, lifetime_frames=index)
                            for i, (x, y) in enumerate([(2, 2), (8, 2), (2, 8)])]
                frames.append(dict(frame_index=index, timestamp_ms=index*30, torso_features=features,
                                   active_feature_count=3, torso_cumulative=None,
                                   measurement_state='seed_only' if index == 0 else 'numerically_supported_unverified_seed',
                                   seed_feature_survivor_ratio=1))
            payload = dict(pitch_id='pitch_test', total_frames=2, width=20, height=20,
                           seed_feature_count=3, frames=frames, sources={'video':{'path':str(source/'measurement_run.json'),
                           'sha256':measure.sha(source/'measurement_run.json')}})
            file = clip_dir / 'image_pose_measurements.json'
            file.write_text(json.dumps(payload))
            before = file.read_bytes()
            result = measure.measure(source, plan_path, root / 'output')
            self.assertEqual(file.read_bytes(), before)
            self.assertEqual(result['human_annotation_inputs'], [])
            self.assertFalse(result['feature_rejection_or_reseeding'])
            self.assertFalse(result['warning_predictions_generated'])
            self.assertFalse(result['clips'][0]['foreground_verified'])
            self.assertEqual(result['clips'][0]['numerical_feature_frame_rows'], 6)
            self.assertTrue(all(r['fb_per_clip_group'] == 2 for r in result['clips'][0]['frames'][1]['features']))


if __name__ == '__main__':
    unittest.main()
