"""Complete denominators and paired comparisons of isolated expanded input."""
from pathlib import Path
import sys
import unittest
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parents[1]/'src')]
import evaluate_expanded_roi_pose as e


class ExpandedEvaluationTests(unittest.TestCase):
    def test_independent_fractional_geometry(self):
        self.assertEqual(e.independent_bounds([10.6,20.8,11.2,13.4],100,100),[5,14,28,41])

    def test_input_support_requires_crop_and_source(self):
        point={'x':.5,'y':.5,'visibility':.9,'presence':.9}
        cfg={'min_visibility':.5,'min_presence':.5}; t={'width':100,'height':100}
        state=e.point_state(point,{**point,'x':1.1},t,cfg,True)
        self.assertTrue(state['gate']); self.assertFalse(state['supported_gate'])

    def test_below_gate_is_missing_support_not_zero_error(self):
        p={'x':.5,'y':.5,'visibility':.1,'presence':.9}
        state=e.point_state(p,p,{'width':100,'height':100},{'min_visibility':.5,'min_presence':.5},True)
        self.assertTrue(state['raw']); self.assertFalse(state['supported_gate'])

    def test_transitions_keep_all_four_cells(self):
        rows=[{'frame_index':i,'arms':{'a':{'s':a},'b':{'s':b}}} for i,(a,b) in enumerate(((1,1),(1,0),(0,1),(0,0)))]
        result=e.transitions(rows,'a','b','s')
        self.assertEqual([result[k]['frames'] for k in ('both','lost','gained','neither')],[[0],[1],[2],[3]])

    def test_xy_crop_outside_reference_kept(self):
        rows=[{'frame_index':1,'joint':'RIGHT_ELBOW','manual_status':'visible','reference_in_expanded_crop':False,
               'errors_px':dict(expanded=4.,narrow=10.,image=None,video=2.)}]
        r=e.xy_summary(rows)
        self.assertEqual(r['paired']['narrow']['common_joint_records'],1)
        self.assertEqual(r['paired']['image']['common_joint_records'],0)
        self.assertEqual(r['arms']['image']['visible_prediction_missing'],1)

    def test_xy_hidden_and_seed_not_used(self):
        rows=[{'frame_index':i,'joint':'x','manual_status':status,'errors_px':{a:3. for a in e.ARMS}}
              for i,status in ((0,'visible'),(1,'not_observable'),(2,'uncertain'))]
        r=e.xy_summary(rows)
        self.assertEqual(r['all_joint_records'],2); self.assertEqual(r['visible_reference_count'],0)
        self.assertEqual(r['paired']['narrow']['common_joint_records'],0)

    def test_angle_pair_denominator_and_losses(self):
        rows=[]
        for i,errors in enumerate(((1,1),(2,None),(None,3),(4,2))):
            streams={a:{'numerical_support':errors[0] is not None,'signed_error_deg':errors[0]} for a in (*e.ARMS,'video_processed')}
            streams['expanded']={'numerical_support':errors[1] is not None,'signed_error_deg':errors[1]}
            rows.append({'frame_index':i,'manual_reference':{'value_deg':90},'streams':streams})
        r=e.angle_summary(rows)
        self.assertEqual(r['non_seed_frames'],3)
        self.assertEqual(r['paired']['image']['common_frames'],1)
        self.assertEqual(r['paired']['image']['frames'],[3])
        self.assertEqual(r['transitions']['image']['all_frames']['lost']['frames'],[1])
        self.assertEqual(r['transitions']['image']['all_frames']['gained']['frames'],[2])


if __name__=='__main__': unittest.main()
