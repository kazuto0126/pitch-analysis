"""Synthetic isolation, strict policy and one-call compatibility checks."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_rtmpose_response as run
import rtmpose_response_policy as policy
import measure_rtmpose_native as native


class ResponseExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.out=self.root/'out'; (self.out/'measurements').mkdir(parents=True)
        self.plan={'_sha256':'frozen','clips':[]}; refs=[]
        for pid in run.NAMES:
            target={'pitch_id':pid,'total_frames':4,'measurement_sources':{'video':{'sha256':'a'*64}}}
            gt={'schema_version':'ground-truth-v1','annotation_status':'reviewed','source_video':{
                'pitch_id':pid,'total_frames':4,'sha256':'a'*64},'labels':{r+'_reliability':[
                    {'start_frame':0,'end_frame':2,'status':'reliable'},
                    {'start_frame':3,'end_frame':3,'status':'unreliable'}] for r in run.ROLES}}
            path=self.root/(pid+'_gt.json'); run.save(path,gt); target['canonical_gt']=run.reference(self.root,path)
            self.plan['clips'].append(target)
            deficits=[99.,.2,.3,.6] if pid!='pitch_003' else [99.,.3,.300001,None]
            data={'pitch_id':pid,'frames':[{'frame_index':i,'timestamp_ms':i*10,'roles':{
                r:{'response_deficit':v} for r in run.ROLES}} for i,v in enumerate(deficits)]}
            path=self.out/'measurements'/(pid+'.json'); run.save(path,data); refs.append(run.reference(self.root,path))
        run.save(self.out/'measurements/measurement_run.json',{'plan_sha256':'frozen','clips':refs,'human_annotation_inputs':[]})

    def test_four_training_gt_only_and_numeric_file_contains_no_labels(self):
        query='pitch_003'; (self.root/(query+'_gt.json')).unlink()
        run.calibrate_stage(self.root,self.plan,self.out,query)
        d=run.read(self.out/'folds'/query/'calibration.json')
        self.assertEqual(sum(p.endswith('_gt.json') for p in d['read_paths']),4)
        self.assertFalse(any(query+'_gt.json' in p for p in d['read_paths']))
        self.assertTrue(all('trace' not in value for value in d['roles'].values()))
        self.assertEqual(d['roles']['throwing_elbow']['threshold'],.3)

    def test_apply_without_gt_no_recalibration_and_seed_missing_strict_equality(self):
        query='pitch_003'; run.calibrate_stage(self.root,self.plan,self.out,query)
        for path in self.root.glob('*_gt.json'): path.unlink()
        with patch.object(policy,'calibrate',side_effect=AssertionError('refit')):
            run.apply_stage(self.root,self.plan,self.out,query)
        d=run.read(self.out/'predictions'/f'{query}.json')
        self.assertFalse(any(p.endswith('_gt.json') for p in d['read_paths']))
        rows=[f['roles']['throwing_elbow'] for f in d['frames']]
        self.assertEqual([r['status'] for r in rows],['seed_excluded','no_warning','warning','insufficient_evidence'])
        self.assertTrue(rows[3]['effectiveness_eligible']); self.assertIsNone(rows[3]['review_required'])

    def test_completed_calibration_skips_and_incomplete_attempt_refuses(self):
        query='pitch_003'; run.calibrate_stage(self.root,self.plan,self.out,query)
        with patch.object(policy,'calibrate',side_effect=AssertionError('refit')):
            self.assertEqual(run.calibrate_stage(self.root,self.plan,self.out,query)['status'],'skipped_completed_calibration')
        folder=self.out/'folds/pitch_001'; folder.mkdir(); run.save(folder/'attempt.json',{})
        with self.assertRaisesRegex(ValueError,'retry refused'): run.calibrate_stage(self.root,self.plan,self.out,'pitch_001')

    def test_policy_ignores_unreliable_unknown_and_seed_for_maximum(self):
        training=[{'pitch_id':p,'rows':[{'frame_index':i,'canonical_label':label,'response_deficit':value}
            for i,(label,value) in enumerate([('reliable',99.),('reliable',.3),('unreliable',200.),('not_observable',300.)])]}
            for p in run.NAMES if p!='pitch_003']
        d=policy.calibrate(training,'pitch_003','throwing_wrist'); self.assertEqual(d['threshold'],.3)
        self.assertEqual(d['used_reliable_rows'],4)
        with self.assertRaises(ValueError): policy.calibrate(training[:3],'pitch_003','throwing_wrist')

    def test_failed_calibration_keeps_unknown_query_as_failed_without_hint(self):
        training=[{'pitch_id':p,'rows':[{'frame_index':0,'canonical_label':'reliable','response_deficit':9.},
            {'frame_index':1,'canonical_label':'reliable','response_deficit':None}]} for p in run.NAMES if p!='pitch_003']
        d=policy.calibrate(training,'pitch_003','throwing_elbow'); self.assertEqual(d['status'],'failed')
        r=policy.apply([{'frame_index':0,'response_deficit':0.},{'frame_index':1,'response_deficit':2.}],d)
        self.assertEqual(r[1]['status'],'calibration_failed'); self.assertFalse(r[1]['evaluated_warning'])

    def test_native_synthetic_call_once_repeat_and_unknown_attempt(self):
        model=self.root/'fake_model'; model.write_bytes(b'not an executable model')
        plan={'_sha256':'frozen','model':run.reference(self.root,model)}
        class Graph:
            calls=0
            def run(self,*args):
                self.calls+=1; return [np.zeros(s,dtype=np.float32) for s in native.SHAPES]
            def get_providers(self): return ['CPUExecutionProvider']
        graph=Graph()
        with patch.object(native,'session',return_value=graph),patch.object(native,'runtime',return_value={}):
            result=native.compatibility(self.root,plan,self.out); self.assertEqual(result['real_pose_calls'],0)
            self.assertEqual(native.compatibility(self.root,plan,self.out)['new_calls'],0)
        self.assertEqual(graph.calls,1)
        (self.out/'compatibility.json').unlink()
        with patch.object(native,'session',side_effect=AssertionError('no retry')):
            with self.assertRaisesRegex(ValueError,'retry refused'): native.compatibility(self.root,plan,self.out)

    def test_native_contract_refuses_decoded_points_and_float64(self):
        native.validate_outputs([np.zeros(s,dtype=np.float32) for s in native.SHAPES])
        with self.assertRaises(ValueError): native.validate_outputs([np.zeros((1,17,2),dtype=np.float32)])
        with self.assertRaises(ValueError): native.validate_outputs([np.zeros(s,dtype=np.float64) for s in native.SHAPES])

    def test_symbolic_joint_metadata_still_requires_exact_runtime_tensors(self):
        def node(name, shape): return SimpleNamespace(name=name, type='tensor(float)', shape=shape)
        inputs=[node('input',['batch',3,256,192])]
        outputs=[node('simcc_x',['batch','joint_axis',384]),node('simcc_y',['batch','joint_axis',512])]
        native.validate_metadata(inputs,outputs)
        outputs[1].shape[1]='different_axis'
        with self.assertRaises(ValueError): native.validate_metadata(inputs,outputs)
        outputs[0].shape[1]=outputs[1].shape[1]=16
        with self.assertRaises(ValueError): native.validate_metadata(inputs,outputs)
        outputs[0].shape[1]=outputs[1].shape[1]=17
        native.validate_metadata(inputs,outputs)
        outputs[1].shape[2]=511
        with self.assertRaises(ValueError): native.validate_metadata(inputs,outputs)
        with self.assertRaises(ValueError):
            native.validate_outputs([np.zeros((1,16,384),dtype=np.float32),np.zeros((1,16,512),dtype=np.float32)])


if __name__=='__main__': unittest.main()
