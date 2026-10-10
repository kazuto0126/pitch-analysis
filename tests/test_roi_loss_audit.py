"""Offline loss-accounting and original-rule trace regressions."""
from dataclasses import asdict
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('audit_roi_losses', ROOT/'scripts/audit_roi_losses.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
from pitch_analysis.subject import PitcherSelector


def pose(*, confidence=.9, hip_x=.5, height=.5):
    values = [SimpleNamespace(x=hip_x,y=.3,visibility=confidence,presence=confidence) for _ in range(33)]
    for i in (23,24):
        values[i].y=.5
    for i in (27,28):
        values[i].y=.3+height
    return values


def point(state='supported_gate',xy=(2,2)):
    return {'selected_raw':state!='selected_point_missing','finite':state not in ('selected_point_missing','nonfinite'),
        'gate_pass':state in ('supported_gate','gate_but_extrapolated'),
        'input_supported_raw':state=='supported_gate','xy_px':list(xy)}


class OriginalTraceTests(unittest.TestCase):
    def compare(self, poses, *, previous=None, gap=0):
        original, traced=PitcherSelector(),PitcherSelector()
        original.previous=traced.previous=previous
        original.gap=traced.gap=gap
        expected=asdict(original.select(poses))
        result=audit.traced_select(traced,poses,audit.continue_rules())
        self.assertEqual(result['selection'],expected)
        self.assertEqual(traced.previous,original.previous)
        self.assertEqual(traced.gap,original.gap)
        return result

    def test_all_original_exclusion_conditions_are_observed_without_new_cutoff(self):
        cases=[([], 'len(pose)'),(pose(confidence=.1),'confidence'),
               (pose(hip_x=.01),'body_height'),(pose(height=.01),'body_height')]
        for candidate,condition in cases:
            with self.subTest(condition=condition):
                result=self.compare([candidate])
                self.assertEqual(result['selection']['status'],'rejected')
                self.assertEqual(len(result['candidate_exclusions']),1)
                self.assertIn(condition,result['candidate_exclusions'][0]['executed_original_condition'])

    def test_continuity_rejection_uses_original_state_and_recovery_gap(self):
        result=self.compare([pose(hip_x=.75)],previous=(.2,.5,.5))
        self.assertIn('distance',result['candidate_exclusions'][0]['executed_original_condition'])
        result=self.compare([pose(hip_x=.75)],previous=(.2,.5,.5),gap=7)
        self.assertEqual(result['selection']['status'],'selected')
        self.assertEqual(result['candidate_exclusions'],[])

    def test_ambiguous_candidates_stay_ambiguous_and_admitted(self):
        result=self.compare([pose(),pose()])
        self.assertEqual(result['selection']['status'],'ambiguous')
        self.assertEqual(set(result['admitted_candidates']),{0,1})
        self.assertEqual(result['candidate_exclusions'],[])

    def test_empty_backend_is_not_an_excluded_candidate(self):
        result=self.compare([])
        self.assertEqual(result['selection']['candidate_count'],0)
        self.assertEqual(result['candidate_exclusions'],[])

    def test_existing_trace_is_restored_after_success_and_exception(self):
        before=sys.gettrace()
        def prior(frame,event,arg):
            return prior
        try:
            sys.settrace(prior)
            self.compare([pose()])
            self.assertIs(sys.gettrace(),prior)
            with self.assertRaises(TypeError):
                audit.traced_select(PitcherSelector(),None,audit.continue_rules())
            self.assertIs(sys.gettrace(),prior)
        finally:
            sys.settrace(before)

    def test_selected_candidate_is_not_replaced_by_a_rejected_one(self):
        result=self.compare([pose(confidence=.1),pose()])
        self.assertEqual(result['selection']['index'],1)
        self.assertEqual(result['admitted_candidates'],[1])
        self.assertEqual(result['candidate_exclusions'][0]['candidate_index'],0)


class PairedAccountingTests(unittest.TestCase):
    def test_transition_truth_table_retains_shared_failures_and_gains(self):
        self.assertEqual([audit.transition(*pair) for pair in [(True,True),(True,False),(False,True),(False,False)]],
                         list(audit.STATES))

    def test_joint_losses_have_disjoint_reasons_and_keep_fixed_denominator(self):
        states=[('supported_gate','below_existing_gate'),('supported_gate','gate_but_extrapolated'),
                ('supported_gate','selected_point_missing'),('selected_point_missing','supported_gate'),
                ('below_existing_gate','below_existing_gate'),('supported_gate','supported_gate')]
        frames=[{'frame_index':i+1,'crop_bounds_xyxy':[0,0,3,3],
                 'joints':{'RIGHT_ELBOW':{'arms':{'image':point(old,xy=(4,4) if i==0 else (2,2)),
                                                'crop':point(new)}}}} for i,(old,new) in enumerate(states)]
        summary=audit.joint_partition(frames,'RIGHT_ELBOW')
        self.assertEqual(summary['denominator'],6)
        self.assertEqual(summary['paired_supported_gate'],{'both_selected':1,'new_loss':3,'gain':1,'both_unselected':1})
        self.assertEqual(summary['loss_state_partition'],{'below_existing_gate':1,'gate_but_extrapolated':1,'selected_point_missing':1})
        self.assertEqual(summary['lost_joint_image_prediction_geometry_not_ground_truth'],
                         {'image_prediction_outside_crop':1,'image_prediction_inside_crop':2})
        self.assertEqual(summary['lost_frames'],[1,2,3])
        self.assertEqual(summary['gained_frames'],[4])

    def test_half_open_crop_boundary_is_outside_even_if_gate_passes(self):
        frame={'frame_index':1,'crop_bounds_xyxy':[0,0,3,3],
               'joints':{'X':{'arms':{'image':point(xy=(3,1)),'crop':point('selected_point_missing')}}}}
        result=audit.joint_partition([frame],'X')
        self.assertEqual(result['lost_joint_image_prediction_geometry_not_ground_truth'],{'image_prediction_outside_crop':1})

    def test_nonfinite_and_missing_remain_distinct(self):
        self.assertEqual(audit.support_state(point('nonfinite')),'nonfinite')
        self.assertEqual(audit.support_state(point('selected_point_missing')),'selected_point_missing')
        self.assertEqual(audit.joint_partition([],'X')['denominator'],0)

    def test_measurements_are_descriptive_and_do_not_classify_reliability(self):
        result=audit.candidate_measurements([pose(),[]],(.2,.5,.5))
        self.assertAlmostEqual(result[0]['hip_distance_to_previous'],.3)
        self.assertEqual(len(result[0]['major_confidences']),8)
        self.assertAlmostEqual(result[0]['shoulder_to_ankle_height'],.5)
        self.assertNotIn('passed',result[0])
        self.assertNotIn('reliable',result[0])
        self.assertEqual(result[1],{'candidate_index':1,'landmarks':0})

    def test_hash_or_workspace_escape_is_refused(self):
        with patch.object(audit,'sha',return_value='actual'):
            for ref in ({'path':'docs/STATUS.md','sha256':'wrong'},
                        {'path':'../outside.json','sha256':'actual'}):
                with self.subTest(ref=ref),self.assertRaises(ValueError):
                    audit.bound(ROOT,ref)

    def test_output_cannot_overwrite_or_escape_analysis_results(self):
        for output in (ROOT/'analysis_results',ROOT/'elsewhere'):
            with self.subTest(output=output),self.assertRaises(ValueError):
                audit.audit(ROOT,'unused',output)


if __name__=='__main__':
    unittest.main()
