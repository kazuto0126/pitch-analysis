from copy import deepcopy
from itertools import permutations
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'scripts'), str(Path(__file__).resolve().parents[1]/'src')]
import diagnose_angle_reference_gaps as diagnosis


def sources(total=3):
    roles = tuple(dict.fromkeys(r for rs in diagnosis.previous.FEATURES.values() for r in rs))
    mapping = {role: 'joint_'+role for role in roles}
    points = [(20.,20.), (25.,30.), (35.,30.), (40.,40.), (42.,60.), (50.,80.)]
    data = {'target': {'pitch_id': 'synthetic', 'total_frames': total, 'width': 200, 'height': 100},
        'important_joints': mapping, 'frames': []}
    view = {'source_artifacts': {'original_video': {'sha256': 'a'*64}}, 'frames': []}
    manual = {'source_video': {'pitch_id': 'synthetic', 'total_frames': total, 'sha256': 'a'*64},
        'image_size': {'width': 200, 'height': 100}, 'frames': []}
    features = {'pitch_id': 'synthetic', 'frames': []}
    for i in range(total):
        data['frames'].append({'frame_index': i, 'joints': {
            mapping[r]: {'raw': {'finite': True, 'xy_px': list(p)}} for r,p in zip(roles, points)}})
        view['frames'].append({'frame_index': i, 'timestamp_ms': i*100/3,
            'focus_joints': {r: {'model_state': 'observed',
                'processed_landmark': {'x': p[0]/200, 'y': p[1]/100, 'usable': True}} for r,p in zip(roles, points)},
            'human_review': {'major_pose_failure': [{'status': 'confirmed'}] if i == 1 else []}})
        manual['frames'].append({'frame_index': i, 'timestamp_ms': i*100/3,
            'joints': [{'name': mapping[r], 'status': 'visible', 'x_px': p[0]+1, 'y_px': p[1]} for r,p in zip(roles, points)]})
        features['frames'].append({'frame_index': i, 'features': {name: {
            'saved_values': {key: diagnosis.previous.angle([points[roles.index(r)] for r in required])
                for key in ('base', 'feature_interpolated', 'smoothed')},
            'status': 'hold_major' if i == 1 else 'eligible', 'eligible': i != 1, 'saved_flags': ['saved_example']}
            for name,required in diagnosis.previous.FEATURES.items()}})
    return data, view, manual, features


class AngleReferenceGapTests(unittest.TestCase):
    def test_analytic_point_gradients_match_finite_differences_on_both_orientations(self):
        for points in ([(4.,1.),(1.,2.),(2.,6.)], [(4.,1.),(1.,2.),(2.,-3.)]):
            g = diagnosis.geometry(points)
            for i in range(3):
                for axis in range(2):
                    plus, minus = deepcopy(points), deepcopy(points)
                    plus[i] = list(plus[i]); minus[i] = list(minus[i])
                    plus[i][axis] += 1e-5; minus[i][axis] -= 1e-5
                    derivative = (diagnosis.geometry(plus)['angle_deg']-diagnosis.geometry(minus)['angle_deg'])/2e-5
                    self.assertAlmostEqual(g['point_jacobian_deg_per_px'][i][axis], derivative, places=7)

    def test_zero_and_straight_angles_are_valid_but_unsigned_derivatives_are_cusps(self):
        for points, angle in (([(1,0),(0,0),(2,0)], 0.), ([(-1,0),(0,0),(2,0)], 180.)):
            g = diagnosis.geometry(points)
            self.assertEqual(g['angle_deg'], angle)
            self.assertIsNone(g['point_jacobian_deg_per_px'])
            self.assertEqual(g['sensitivity_unavailable_reason'], 'collinear_unsigned_angle_cusp')
            self.assertIsNotNone(diagnosis.counterfactual_attribution(points, points)['attribution'])

    def test_zero_ray_missing_nonfinite_and_bool_points_do_not_make_an_angle(self):
        for points in ([(0,0),(0,0),(1,1)], [None,(0,0),(1,1)],
                [(float('nan'),0),(0,0),(1,1)], [(True,0),(0,0),(1,1)], []):
            self.assertIsNone(diagnosis.geometry(points)['angle_deg'])

    def test_short_nonzero_ray_is_not_clamped_and_has_large_local_sensitivity(self):
        g = diagnosis.geometry([(1e-9,0),(0,0),(0,2)])
        self.assertEqual(g['angle_deg'], 90.)
        self.assertTrue(math.isclose(g['point_sensitivity_deg_per_px'][0], 180/math.pi/1e-9, rel_tol=1e-15))
        self.assertAlmostEqual(g['point_sensitivity_deg_per_px'][2], 180/math.pi/2)

    def test_translation_and_uniform_scale_preserve_angle_and_inverse_scale_sensitivity(self):
        points = [(4.,1.),(1.,2.),(2.,6.)]
        a = diagnosis.geometry(points)
        b = diagnosis.geometry([(3*x+100,3*y-20) for x,y in points])
        self.assertAlmostEqual(a['angle_deg'], b['angle_deg'])
        for i in range(3):
            self.assertAlmostEqual(a['point_sensitivity_deg_per_px'][i], b['point_sensitivity_deg_per_px'][i]*3)
        for axis in range(2): self.assertAlmostEqual(sum(p[axis] for p in a['point_jacobian_deg_per_px']), 0.)

    def test_all_masks_permutations_and_shapley_efficiency_are_preserved(self):
        result = diagnosis.counterfactual_attribution([(5,1),(1,2),(2,5)], [(4,0),(0,0),(0,4)])
        attribution = result['attribution']
        self.assertEqual([h['mask'] for h in result['hybrids']], list(range(8)))
        self.assertEqual({tuple(v['order']) for v in attribution['permutations']}, set(permutations(('A','B','C'))))
        self.assertAlmostEqual(sum(attribution['point_contributions_deg']), result['original_absolute_error_deg'])
        self.assertAlmostEqual(attribution['efficiency_residual_deg'], 0., places=12)

    def test_negative_contributions_and_cancellation_survive_even_zero_original_error(self):
        result = diagnosis.counterfactual_attribution([(4,1),(1,1),(1,4)], [(4,0),(0,0),(0,4)])
        self.assertEqual(result['original_absolute_error_deg'], 0.)
        values = result['attribution']['point_contributions_deg']
        self.assertTrue(values[0] < 0 and values[2] < 0 and values[1] > 0)
        self.assertAlmostEqual(sum(values), 0.)

    def test_swapping_endpoints_swaps_attribution_without_selecting_an_order(self):
        pred, manual = [(5,1),(1,2),(2,5)], [(4,0),(0,0),(0,4)]
        a = diagnosis.counterfactual_attribution(pred, manual)['attribution']['point_contributions_deg']
        b = diagnosis.counterfactual_attribution(pred[::-1], manual[::-1])['attribution']['point_contributions_deg']
        for x,y in zip(a, b[::-1]): self.assertAlmostEqual(x, y)

    def test_one_degenerate_hybrid_nulls_whole_attribution_without_losing_original_error(self):
        result = diagnosis.counterfactual_attribution([(0,0),(1,1),(2,5)], [(4,0),(0,0),(0,4)])
        self.assertIsNotNone(result['original_absolute_error_deg'])
        self.assertIn(2, result['unavailable_hybrid_masks'])
        self.assertIsNone(result['attribution'])
        self.assertEqual(len(result['hybrids']), 8)

    def test_ray_direction_is_manual_to_prediction_clockwise_and_wrap_safe(self):
        manual, pred = [(1,0),(0,0),(0,1)], [(0,1),(0,0),(-1,0)]
        self.assertEqual(diagnosis._ray_delta(manual, pred, 0), 90.)
        self.assertEqual(diagnosis._ray_delta(pred, manual, 0), -90.)
        ray = lambda deg: (math.cos(math.radians(deg)), math.sin(math.radians(deg)))
        self.assertAlmostEqual(diagnosis._ray_delta([ray(179),(0,0),(1,1)], [ray(-179),(0,0),(1,1)], 0), 2.)

    def test_hidden_and_uncertain_xy_never_enter_hybrids_full_denominator_and_holds_retained(self):
        data, view, manual, features = sources()
        manual['frames'][1]['joints'][2]['status'] = 'not_observable'
        manual['frames'][2]['joints'][2]['status'] = 'uncertain'
        old = diagnosis.previous.compare_rows(data, view, features, manual)
        rows = diagnosis.diagnose_rows(data, view, manual, old)
        elbow = rows['throwing_elbow_angle']; summary = diagnosis.summarize(elbow)
        self.assertEqual((summary['source_frame_denominator'], summary['paired_manual_processed_frames']), (3,1))
        self.assertIsNone(elbow[1]['counterfactual']); self.assertIsNone(elbow[2]['counterfactual'])
        self.assertIsNone(elbow[1]['point_displacements'][2]['distance_px'])
        self.assertTrue(elbow[1]['existing_major_hold']); self.assertFalse(elbow[1]['existing_eligible'])
        self.assertEqual(summary['original_major_hold_frames'], 1)
        self.assertEqual(len(rows['lead_knee_angle']), 3)
        self.assertEqual(rows['lead_knee_angle'][0]['frame_index'], 0)

    def test_missing_processed_frame_and_original_states_remain_explicit(self):
        data, view, manual, features = sources()
        view['frames'][1]['focus_joints']['throwing_wrist']['processed_landmark']['usable'] = False
        view['frames'][1]['focus_joints']['throwing_wrist']['model_state'] = 'missing'
        for key in features['frames'][1]['features']['throwing_elbow_angle']['saved_values']:
            features['frames'][1]['features']['throwing_elbow_angle']['saved_values'][key] = None
        old = diagnosis.previous.compare_rows(data, view, features, manual)
        rows = diagnosis.diagnose_rows(data, view, manual, old)['throwing_elbow_angle']
        self.assertEqual(diagnosis.summarize(rows)['source_frame_denominator'], 3)
        self.assertEqual(diagnosis.summarize(rows)['paired_manual_processed_frames'], 2)
        self.assertEqual(rows[1]['original_model_states']['throwing_wrist'], 'missing')
        self.assertIn('processed_point_unavailable:throwing_wrist', rows[1]['unavailable_reasons'])
        self.assertIsNone(rows[1]['raw_processed_comparison'][2]['raw_equals_processed'])

    def test_source_identity_truncated_rows_and_changed_original_error_are_rejected(self):
        data, view, manual, features = sources()
        rows = diagnosis.previous.compare_rows(data, view, features, manual)
        bad = deepcopy(manual); bad['source_video']['sha256'] = 'b'*64
        with self.assertRaises(ValueError): diagnosis.diagnose_rows(data, view, bad, rows)
        bad_rows = deepcopy(rows); bad_rows['throwing_elbow_angle'].pop()
        with self.assertRaises(ValueError): diagnosis.diagnose_rows(data, view, manual, bad_rows)
        bad_rows = deepcopy(rows); bad_rows['throwing_elbow_angle'][0]['signed_errors_deg']['processed_base'] = 123.
        with self.assertRaises(ValueError): diagnosis.diagnose_rows(data, view, manual, bad_rows)

    def test_input_nonmutation_and_saved_errors_are_not_replaced_by_diagnostic_geometry(self):
        data, view, manual, features = sources()
        old = diagnosis.previous.compare_rows(data, view, features, manual)
        before = deepcopy((data, view, manual, old))
        rows = diagnosis.diagnose_rows(data, view, manual, old)
        diagnosis.summarize(rows['throwing_elbow_angle'])
        self.assertEqual((data, view, manual, old), before)
        self.assertEqual(rows['throwing_elbow_angle'][0]['original_saved_signed_error_deg'], old['throwing_elbow_angle'][0]['signed_errors_deg']['processed_base'])
        self.assertTrue(all(p['raw_equals_processed'] for p in rows['throwing_elbow_angle'][0]['raw_processed_comparison']))

    def test_wrapper_rejects_bad_bound_source_before_loading_data_or_writing(self):
        root = Path(__file__).resolve().parents[1]
        plan = {'status': 'frozen_before_angle_reference_gap_diagnosis', 'policy': diagnosis.POLICY,
            'code': {role: {'path': path, 'sha256': 'a'*64} for role,path in diagnosis.CODE_PATHS.items()},
            'parent_execution_plan': {'path': 'bad/execution.json', 'sha256': 'b'*64},
            'parent_assessment': {'path': 'bad/assessment.json', 'sha256': 'b'*64},
            'pose_inference_budget': 0, 'tracker_inference_budget': 0, 'production_adoption': False,
            'output_directory': 'analysis_results/synthetic_angle_diagnosis_never_created'}
        def reject_source(repo, ref):
            if ref['path'].startswith('bad/'): raise ValueError('Changed bound source')
            return repo/ref['path']
        with patch.object(diagnosis.previous, 'read', return_value=plan), patch.object(diagnosis, 'sha', return_value='a'*64), \
                patch.object(diagnosis, 'bound', side_effect=reject_source), patch.object(diagnosis.previous.parent, 'verify_fit_plan') as verify:
            with self.assertRaisesRegex(ValueError, 'Changed bound source'):
                diagnosis.run(root, root/'synthetic_plan.json', root/'analysis_results'/'synthetic_angle_diagnosis_never_created')
            verify.assert_not_called()

    def test_wrapper_rejects_changed_frozen_inference_adoption_or_output_before_sources(self):
        root = Path(__file__).resolve().parents[1]
        base = {'status': 'frozen_before_angle_reference_gap_diagnosis', 'policy': diagnosis.POLICY,
            'pose_inference_budget': 0, 'tracker_inference_budget': 0, 'production_adoption': False,
            'output_directory': 'analysis_results/synthetic_angle_diagnosis_never_created'}
        for key,value in (('pose_inference_budget', True), ('tracker_inference_budget', 1),
                ('production_adoption', True), ('output_directory', 'analysis_results/different_frozen_directory')):
            plan = {**base, key: value}
            with patch.object(diagnosis.previous, 'read', return_value=plan), patch.object(diagnosis, 'sha', return_value='a'*64), \
                    patch.object(diagnosis, 'bound') as bind:
                with self.assertRaisesRegex(ValueError, 'frozen inference, adoption or output'):
                    diagnosis.run(root, root/'synthetic_plan.json', root/base['output_directory'])
                bind.assert_not_called()


if __name__ == '__main__': unittest.main()
