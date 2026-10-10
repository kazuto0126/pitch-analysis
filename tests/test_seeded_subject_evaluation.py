"""Fixed-denominator and no-label-transfer regressions for isolated CSRT audit."""
import importlib.util
from pathlib import Path
import sys
import subprocess
from copy import deepcopy
import unittest

DIR=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(DIR))
try:
    import evaluate_seeded_subject as audit
finally:
    sys.path.pop(0)


def manual(index=1):
    names=(*audit.TORSO,'RIGHT_ELBOW','RIGHT_WRIST','LEFT_ELBOW','LEFT_WRIST','RIGHT_KNEE','LEFT_KNEE','RIGHT_ANKLE','LEFT_ANKLE')
    return {'frame_index':index,'joints':[{'name':n,'status':'visible','x_px':5,'y_px':5} for n in names]}


class SeededGeometryTests(unittest.TestCase):
    def test_cli_dispatches_to_plan_read_before_any_execution(self):
        result=subprocess.run([sys.executable,'-B',str(DIR/'evaluate_seeded_subject.py'),
            '__absent_csrt_plan__.json','__absent_csrt_measurement__.json',
            str(DIR.parent/'analysis_results'/'__absent_csrt_output__')],capture_output=True,text=True,cwd=DIR.parent)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('FileNotFoundError',result.stderr)
        self.assertIn('__absent_csrt_plan__.json',result.stderr)
        self.assertNotIn('unexpected keyword argument',result.stderr)
    def test_half_open_rectangle_and_partial_overflow_are_not_clamped(self):
        self.assertTrue(audit.contains([-5,0,10,10],[0,0]))
        self.assertFalse(audit.contains([-5,0,10,10],[5,5]))
        self.assertEqual(audit.rectangle_geometry([-5,0,10,10],510,628),(True,True))

    def test_missing_tracker_keeps_all_visible_references(self):
        result=audit.frame_geometry(manual(),None)
        self.assertEqual(len(result['visible_tracker_unavailable']),12)
        self.assertEqual(result['visible_inside'],[])
        self.assertEqual(result['torso_proxy_status'],'tracker_unavailable')

    def test_hidden_and_uncertain_coordinates_never_enter_xy_geometry(self):
        m=manual()
        m['joints'][0].update(status='not_observable',x_px=5,y_px=5)
        m['joints'][1].update(status='uncertain',x_px=5,y_px=5)
        result=audit.frame_geometry(m,[0,0,10,10])
        self.assertEqual(len(result['visible_inside']),10)
        self.assertEqual(result['torso_proxy_status'],'reference_missing')

    def test_malformed_and_nonfinite_rectangles_rejected(self):
        for rect in ([0,0,0,10],[0,0,float('inf'),10],[True,0,10,10],[0,0,10]):
            with self.subTest(rect=rect), self.assertRaises(ValueError):
                audit.rectangle_geometry(rect,510,628)

    def test_fixed_slots_missing_candidates_are_not_replaced_or_answered(self):
        sampling={'frames':[38,70,78,86,87,95,104,105,112,114]}
        frames=[{'frame_index':i,'usable_rectangle_xywh':None,'truncated':None,
            'native_timestamp_ms':i*1000/30,'decoded_bgr_sha256':'f'*64} for i in range(115)]
        frames[38]['usable_rectangle_xywh']=[1,2,10,20]
        result=audit.make_questions(frames,sampling)
        self.assertEqual(result['slots_count'],10)
        self.assertEqual(result['questions_count'],1)
        self.assertEqual(sum(s['state']=='no_candidate' for s in result['fixed_sampling_slots']),9)
        self.assertIsNone(result['questions'][0]['conclusion'])
        self.assertIsNone(result['questions'][0]['extent_observation'])

    def test_seed_frame_cannot_raise_eligible_geometric_coverage(self):
        rows=[]
        # Construct the frozen 114-frame reference partition; all tracker outputs missing.
        remaining_hidden,remaining_uncertain=171,2
        for i in range(115):
            if i==0:
                counts={'visible':12};proxy='inside'
            else:
                hidden=min(12,remaining_hidden);remaining_hidden-=hidden
                uncertain=min(12-hidden,remaining_uncertain);remaining_uncertain-=uncertain
                counts={'visible':12-hidden-uncertain,'not_observable':hidden,'uncertain':uncertain}
                proxy='reference_missing' if 70<=i<=78 else 'tracker_unavailable'
            rows.append({'frame_index':i,'tracking_status':'initialized' if i==0 else 'not_attempted_after_terminal_break',
                'usable_rectangle_xywh':[0,0,100,100] if i==0 else None,
                'canonical_major_pose_failure':87<=i<=104,'raw_torso_all_four_inside':None,
                'geometry':{'manual_joint_status_counts':counts,'visible_inside':['seed']*12 if i==0 else [],
                    'visible_outside':[],'visible_tracker_unavailable':['point']*counts['visible'] if i else [],
                    'torso_proxy_status':proxy}})
        result=audit.summarize(rows)
        self.assertEqual(result['visible_joint_partition'],{'inside':0,'outside':0,'tracker_unavailable':1195})
        self.assertEqual(result['denominators'],audit.DENOMINATORS)
        self.assertEqual(result['usable_non_seed_frames'],0)

    def test_seed_duplicate_or_substituted_review_frames_are_rejected(self):
        for bad in ([0,*audit.REVIEW_FRAMES[1:]], [38,38,*audit.REVIEW_FRAMES[2:]],
                    [39,*audit.REVIEW_FRAMES[1:]]):
            with self.subTest(frames=bad), self.assertRaisesRegex(ValueError,'fixed review frames'):
                audit.make_questions([],{'frames':bad})


class SeededReceiptTests(unittest.TestCase):
    def fixture(self):
        seed={'rectangle_xywh':[1,2,10,20]}
        target={'total_frames':4,'width':510,'height':628}
        base={'native_rectangle_xywh':[1,2,10,20],'usable_rectangle_xywh':[1,2,10,20],
            'native_update_success':True,'tracking_status':'native_success','failure_reason':None,
            'raw_tracking_score':.1,'score_error':None,'subject_assignment':None,'warning_prediction':None,
            'native_rectangle_diagnostic':None,'truncated':False}
        frames=[dict(deepcopy(base),frame_index=i) for i in range(4)]
        frames[0].update(tracking_status='initialized',native_update_success=None,native_rectangle_xywh=None,raw_tracking_score=None)
        report={'frames':frames,'initialization_calls':1,'native_update_calls':3,'terminal_break':None}
        return report,seed,target

    def terminal(self,report,reason='native_update_false'):
        report['frames'][1].update(tracking_status='terminal_break',usable_rectangle_xywh=None,
            native_update_success=False,failure_reason=reason)
        for f in report['frames'][2:]:
            f.update(tracking_status='not_attempted_after_terminal_break',usable_rectangle_xywh=None,
                native_update_success=None,native_rectangle_xywh=None,raw_tracking_score=None)
        report.update(native_update_calls=1,terminal_break={'frame_index':1,'reason':reason})

    def test_normal_receipt_and_raw_score_error_without_break_are_accepted(self):
        report,seed,target=self.fixture()
        report['frames'][2].update(raw_tracking_score=None,score_error='native read unavailable')
        audit.validate_timeline(report,seed,target)

    def test_native_false_terminal_keeps_fixed_missing_tail(self):
        report,seed,target=self.fixture();self.terminal(report)
        audit.validate_timeline(report,seed,target)

    def test_successful_valid_rectangle_cannot_be_forged_into_terminal(self):
        for reason in ('native_update_false','invalid_native_rectangle','native_rectangle_fully_outside_image',
                       'score_error','native_update_exception: ValueError: invented'):
            report,seed,target=self.fixture();self.terminal(report,reason)
            report['frames'][1]['native_update_success']=True
            with self.subTest(reason=reason),self.assertRaises(ValueError):
                audit.validate_timeline(report,seed,target)

    def test_false_update_cannot_be_counted_as_native_success(self):
        report,seed,target=self.fixture();report['frames'][1]['native_update_success']=False
        with self.assertRaises(ValueError):audit.validate_timeline(report,seed,target)

    def test_terminal_tail_cannot_resume_or_reuse_previous_box(self):
        for field,value in (('usable_rectangle_xywh',[1,2,10,20]),('native_update_success',True),
                            ('tracking_status','native_success'),('raw_tracking_score',.1)):
            report,seed,target=self.fixture();self.terminal(report)
            report['frames'][2][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):audit.validate_timeline(report,seed,target)

    def test_initialization_failure_keeps_all_nonseed_frames_unattempted(self):
        report,seed,target=self.fixture()
        reason='native_initialization_exception: RuntimeError: unavailable'
        report['frames'][0].update(tracking_status='init_failed',usable_rectangle_xywh=None,failure_reason=reason)
        for f in report['frames'][1:]:
            f.update(tracking_status='not_attempted_after_initialization_failure',usable_rectangle_xywh=None,
                native_update_success=None,native_rectangle_xywh=None,raw_tracking_score=None)
        report.update(native_update_calls=0,terminal_break={'frame_index':0,'reason':reason})
        audit.validate_timeline(report,seed,target)


if __name__=='__main__':
    unittest.main()
