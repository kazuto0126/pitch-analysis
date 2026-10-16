"""Stage input isolation and one-fit resume semantics on synthetic data only."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'scripts'),str(Path(__file__).resolve().parents[1]/'src')]
import run_joint_quality_classifier as execution


def fixture(root):
    output=root/'out'; folder=output/'features'; folder.mkdir(parents=True)
    clips,refs=[],[]
    for n,pid in enumerate(execution.NAMES):
        target={'pitch_id':pid,'total_frames':5,'width':100,'height':200}
        frames=[]
        for i in range(5):
            f=[i/10.,.8,1.,i/9.,i/8.,.1,.2,.1,.5,.8,1.,0.,0.]
            frames.append({'frame_index':i,'timestamp_ms':i*10.,'roles':{
                r:{'raw_finite':i!=3,'features':f} for r in execution.ROLES}})
        path=folder/(pid+'.json'); execution.save(path,{'target':target,'frames':frames})
        refs.append(execution.reference(root,path))
        gt={'schema_version':'ground-truth-v1','annotation_status':'reviewed',
            'source_video':{'pitch_id':pid,'total_frames':5,'sha256':'a'*64},
            'labels':{r+'_reliability':[{'start_frame':i,'end_frame':i,'status':s} for i,s in enumerate(
                ('reliable','reliable','unreliable','unreliable','not_observable'))] for r in execution.ROLES}}
        human=root/(pid+'_gt.json'); execution.save(human,gt)
        clips.append({'target':target,'sources':{'video':{'sha256':'a'*64}},'training_gt':execution.reference(root,human)})
    execution.save(folder/'feature_run.json',{'status':'sealed_joint_quality_features','plan_sha256':'frozen',
        'human_annotation_inputs':[],'clips':refs})
    return {'_sha256':'frozen','clips':clips},output


class JointQualityExecutionTests(unittest.TestCase):
    def test_reader_refuses_query_even_if_file_exists(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); path=root/'gt.json'; execution.save(path,{})
            ref=execution.reference(root,path)
            with self.assertRaisesRegex(ValueError,'not allowed'): execution.Reader(root,[]).json(ref)

    def test_fit_never_opens_query_and_apply_never_opens_any_gt(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); plan,out=fixture(root); query='pitch_003'
            (root/(query+'_gt.json')).unlink()  # No query labels available to FIT.
            receipt=execution.fit_stage(root,plan,out,query)
            self.assertEqual(len(receipt['models']),2)
            self.assertFalse(any(query+'_gt.json' in p for p in receipt['read_paths']))
            first=[execution.read(root/r['path']) for r in receipt['models']]
            self.assertTrue(all(x['model']['status']=='converged' for x in first))
            with patch.object(execution.model,'fit_logistic',side_effect=AssertionError('no refit')):
                execution.fit_stage(root,plan,out,query)
            for path in root.glob('*_gt.json'): path.unlink()
            with patch.object(execution.model,'fit_logistic',side_effect=AssertionError('APPLY cannot FIT')):
                result=execution.apply_stage(root,plan,out,query)
            self.assertTrue(all('_gt.json' not in p for p in result['read_paths']))
            self.assertEqual(result['frames'][3]['roles']['throwing_elbow']['state'],'insufficient_evidence')
            self.assertEqual(result['frames'][0]['roles']['throwing_wrist']['state'],'seed_excluded')

    def test_started_fit_without_result_refuses_retry(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); plan,out=fixture(root); folder=out/'folds/pitch_003'; folder.mkdir(parents=True)
            execution.save(folder/'throwing_elbow_attempt.json',{'started':True})
            with patch.object(execution.model,'fit_logistic',side_effect=AssertionError('no retry')):
                with self.assertRaisesRegex(ValueError,'refit refused'): execution.fit_stage(root,plan,out,'pitch_003')

    def test_training_exclusions_keep_audit_denominator(self):
        clip={'target':{'pitch_id':'train'},'frames':[{'frame_index':i,'roles':{'throwing_elbow':{
            'raw_finite':i!=2,'features':[0.]*13}}} for i in range(4)]}
        X,y,trace=execution.training_rows([clip],{'train':{0:'reliable',1:'unreliable',2:'reliable',3:'uncertain'}},'throwing_elbow','query')
        self.assertEqual(len(X),1); self.assertEqual(y,[1]); self.assertEqual(len(trace),4)
        self.assertEqual([r['excluded_reason'] for r in trace],['seed_excluded',None,'raw_unavailable','human_uncertain'])

    def test_query_labels_and_features_rejected(self):
        with self.assertRaisesRegex(ValueError,'Query GT'): execution.training_rows([],{'query':{}},'throwing_elbow','query')
        with self.assertRaisesRegex(ValueError,'Query features'): execution.training_rows([{'target':{'pitch_id':'query'}}],{},'throwing_elbow','query')

    def test_labels_require_complete_source_bound_intervals(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); plan,out=fixture(root); clip=plan['clips'][0]
            gt=execution.read(root/clip['training_gt']['path'])
            self.assertEqual(len(execution.labels(gt,clip,'throwing_elbow')),5)
            gt['labels']['throwing_elbow_reliability'].pop()
            with self.assertRaisesRegex(ValueError,'Incomplete'): execution.labels(gt,clip,'throwing_elbow')


if __name__=='__main__': unittest.main()
