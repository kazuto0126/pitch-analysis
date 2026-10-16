"""One frozen, source-bound FEATURE/FIT/APPLY/EVALUATE run, with separate IO."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from measure_seeded_subject import sha, read
from measure_expanded_roi_pose import save, exclusive_run
from measure_pose_mode_countercheck import load_video_raw
import joint_quality_model as model

ROLES = ('throwing_elbow','throwing_wrist')
NAMES = [f'pitch_{i:03d}' for i in range(1,6)]
SETTINGS = {'C':1.0,'threshold':0.5,'max_iterations':100,'gradient_tolerance':1e-4,
    'armijo':1e-4,'max_backtracks':25,'feature_columns':13,'model_columns':22,
    'continuous_indices':[0,1,3,4,5,6,7,8,9],'seed_excluded':0,'class_weight':None,
    'production_adoption':False,'pose_inference_budget':0,'tracker_inference_budget':0,
    'classifier_fit_budget':10}
DECISION = {'throwing_elbow':{'min_tp':17,'max_fp':1,'min_non003_tp':10,'min_improved_non003_clips':2},
    'throwing_wrist':{'min_tp':27,'max_fp':1,'min_non003_tp':23,'min_improved_non003_clips':2}}


class Reader:
    """A stage may only open its declared inputs; GT references are not traversed."""
    def __init__(self, root, refs):
        self.root=Path(root).resolve(); self.refs={r['path']:r['sha256'] for r in refs}; self.opened=[]

    def path(self, ref):
        if self.refs.get(ref['path'])!=ref['sha256']: raise ValueError('Stage input not allowed: '+ref['path'])
        p=(self.root/ref['path']).resolve()
        if not p.is_relative_to(self.root) or sha(p)!=ref['sha256']: raise ValueError('Changed stage source: '+ref['path'])
        self.opened.append(ref['path']); return p

    def json(self, ref): return read(self.path(ref))


def reference(root, path):
    return {'path':path.relative_to(root).as_posix(),'sha256':sha(path)}


def labels(gt, clip, role):
    target=clip['target']; source=gt['source_video']
    if (gt['schema_version']!='ground-truth-v1' or gt['annotation_status']!='reviewed'
        or source['pitch_id']!=target['pitch_id'] or source['total_frames']!=target['total_frames']
        or source['sha256']!=clip['sources']['video']['sha256']): raise ValueError('GT target differs')
    result={}
    for interval in gt['labels'][role+'_reliability']:
        a,b,status=interval['start_frame'],interval['end_frame'],interval['status']
        if (type(a) is not int or type(b) is not int or not 0<=a<=b<target['total_frames']
            or status not in ('reliable','unreliable','uncertain','not_observable')): raise ValueError('Invalid label interval')
        for i in range(a,b+1):
            if i in result: raise ValueError('Overlapping canonical labels')
            result[i]=status
    if set(result)!=set(range(target['total_frames'])): raise ValueError('Incomplete canonical labels')
    return result


def training_rows(clips, label_sets, role, query):
    if query in label_sets: raise ValueError('Query GT supplied to FIT')
    X,y,audit=[],[],[]
    for clip in clips:
        pid=clip['target']['pitch_id']
        if pid==query: raise ValueError('Query features supplied to FIT')
        for frame in clip['frames']:
            i=frame['frame_index']; state=label_sets[pid][i]; point=frame['roles'][role]
            reason='seed_excluded' if i==0 else 'human_'+state if state not in ('reliable','unreliable') else 'raw_unavailable' if not point['raw_finite'] else None
            audit.append({'pitch_id':pid,'frame_index':i,'human_status':state,'excluded_reason':reason})
            if reason is None: X.append(point['features']); y.append(int(state=='unreliable'))
    return X,y,audit


def feature_stage(root, plan, output):
    import joint_quality_features as features
    refs=[r for c in plan['clips'] for r in c['sources'].values()]
    reader=Reader(root,refs); folder=output/'features'; folder.mkdir()
    clips=[]
    for clip in plan['clips']:
        sources=clip['sources']; capture=reader.json(sources['capture'])
        raw=load_video_raw(reader.path(sources['original_raw']),capture,clip['target']['total_frames'])
        data=features.build_clip(raw,capture,reader.json(sources['clean_config']),
            reader.json(sources['joint_disagreement']),reader.json(sources['native_measurement']))
        if data['target']!=clip['target']: raise ValueError('Feature target differs')
        path=folder/(clip['target']['pitch_id']+'.json'); save(path,data); clips.append(reference(root,path))
    result={'status':'sealed_joint_quality_features','plan_sha256':plan['_sha256'],'clips':clips,
        'source_frames':sum(c['target']['total_frames'] for c in plan['clips']),
        'human_annotation_inputs':[],'read_paths':reader.opened,'feature_names':list(features.FEATURE_NAMES),
        'pose_inference_calls':0,'tracker_inference_calls':0}
    if result['source_frames']!=592: raise ValueError('Feature denominator differs')
    save(folder/'feature_run.json',result); return result


def feature_receipt(root,plan,output):
    path=output/'features/feature_run.json'; receipt=read(path)
    if (receipt['status']!='sealed_joint_quality_features' or receipt['plan_sha256']!=plan['_sha256']
        or receipt['human_annotation_inputs']!=[] or len(receipt['clips'])!=5): raise ValueError('Feature seal differs')
    return receipt


def fit_stage(root, plan, output, query):
    feature_run=feature_receipt(root,plan,output)
    selected=[(clip,ref) for clip,ref in zip(plan['clips'],feature_run['clips'],strict=True) if clip['target']['pitch_id']!=query]
    if len(selected)!=4: raise ValueError('Four training clips required')
    reader=Reader(root,[r for c,r in selected]+[c['training_gt'] for c,r in selected])
    clips=[reader.json(r) for c,r in selected]
    human={c['target']['pitch_id']:reader.json(c['training_gt']) for c,r in selected}
    folder=output/'folds'/query; folder.mkdir(parents=True,exist_ok=True)
    models=[]
    for role in ROLES:
        path=folder/(role+'_model.json'); attempt=folder/(role+'_attempt.json')
        if path.exists():
            saved=read(path)
            if saved['plan_sha256']!=plan['_sha256'] or saved['query_pitch_id']!=query or saved['role']!=role:
                raise ValueError('Existing fit differs')
            models.append(reference(root,path)); continue
        if attempt.exists(): raise ValueError('Indeterminate classifier attempt; automatic refit refused')
        label_sets={c['target']['pitch_id']:labels(human[c['target']['pitch_id']],c,role) for c,r in selected}
        X,y,trace=training_rows(clips,label_sets,role,query)
        save(attempt,{'plan_sha256':plan['_sha256'],'query_pitch_id':query,'role':role,'training_pitch_ids':list(human)})
        pp=None
        try:
            pp=model.fit_preprocessor(X); fitted=model.fit_logistic(model.transform(X,pp),y)
        except ValueError as error:
            fitted={'status':'failed','failure_reason':str(error)}
        result={'status':'sealed_joint_quality_numeric_model','plan_sha256':plan['_sha256'],
            'query_pitch_id':query,'role':role,'training_pitch_ids':list(human),
            'preprocessor':pp,'model':fitted,'threshold':0.5,'probability_calibrated':False,
            'human_training_refs':[c['training_gt'] for c,r in selected]}
        save(path,result)
        save(folder/(role+'_training_trace.json'),{'query_pitch_id':query,'role':role,'rows':trace,
            'retained_rows':len(X),'class_counts':dict(Counter(y)),
            'excluded':dict(Counter(x['excluded_reason'] for x in trace if x['excluded_reason'])),
            'read_paths':reader.opened})
        models.append(reference(root,path))
    receipt={'status':'sealed_joint_quality_fold_models','plan_sha256':plan['_sha256'],
        'query_pitch_id':query,'models':models,'read_paths':reader.opened}
    path=folder/'fit_run.json'
    if path.exists():
        if read(path)!=receipt: raise ValueError('Fit run differs')
    else: save(path,receipt)
    return receipt


def apply_stage(root,plan,output,query):
    feature_run=feature_receipt(root,plan,output)
    index=NAMES.index(query); ref=feature_run['clips'][index]
    fit=read(output/'folds'/query/'fit_run.json')
    if fit['plan_sha256']!=plan['_sha256'] or fit['query_pitch_id']!=query: raise ValueError('Fit manifest differs')
    reader=Reader(root,[ref,*fit['models']]); features=reader.json(ref)
    if features['target']['pitch_id']!=query: raise ValueError('Query feature identity differs')
    numeric={r['role']:r for r in [reader.json(ref) for ref in fit['models']]}
    if set(numeric)!=set(ROLES): raise ValueError('Incomplete joint models')
    frames=[{'frame_index':f['frame_index'],'timestamp_ms':f['timestamp_ms'],'roles':{}} for f in features['frames']]
    statuses={}
    for role in ROLES:
        item=numeric[role]; statuses[role]=item['model']['status']
        if (item['query_pitch_id']!=query or query in item['training_pitch_ids'] or len(item['training_pitch_ids'])!=4
            or item['plan_sha256']!=plan['_sha256'] or item['threshold']!=0.5): raise ValueError('Query leakage or changed model')
        indices=[i for i,f in enumerate(features['frames']) if i!=0 and f['roles'][role]['raw_finite']]
        probabilities={}
        if statuses[role]=='converged':
            X=model.transform([features['frames'][i]['roles'][role]['features'] for i in indices],item['preprocessor'])
            probabilities=dict(zip(indices,model.predict_probability(X,item['model']).tolist(),strict=True))
        for i,frame in enumerate(frames):
            p=probabilities.get(i)
            state='seed_excluded' if i==0 else 'insufficient_evidence' if not features['frames'][i]['roles'][role]['raw_finite'] else 'fold_failed' if statuses[role]!='converged' else 'warning' if p>=0.5 else 'no_warning'
            frame['roles'][role]={'state':state,'probability':p,'warning':state=='warning'}
    result={'status':'sealed_joint_quality_out_of_fold_hints','plan_sha256':plan['_sha256'],
        'target':features['target'],'fold_status':statuses,'frames':frames,'training_pitch_ids':numeric[ROLES[0]]['training_pitch_ids'],
        'read_paths':reader.opened,'reads_annotations':False,'production_adoption':False}
    folder=output/'predictions'; folder.mkdir(exist_ok=True); path=folder/(query+'.json')
    if path.exists():
        if read(path)!=result: raise ValueError('Existing application differs')
    else: save(path,result)
    return result


def seal_predictions(root,plan,output):
    refs=[reference(root,output/'predictions'/(pid+'.json')) for pid in NAMES]
    reader=Reader(root,refs)
    for pid,ref in zip(NAMES,refs,strict=True):
        d=reader.json(ref)
        if d['target']['pitch_id']!=pid or d['plan_sha256']!=plan['_sha256']: raise ValueError('Incomplete predictions')
    result={'status':'sealed_all_out_of_fold_predictions','plan_sha256':plan['_sha256'],'clips':refs}
    save(output/'predictions/prediction_run.json',result); return result


def evaluate_stage(root,plan,output):
    from evaluate_joint_quality_classifier import evaluate_clips
    features=feature_receipt(root,plan,output); predictions=read(output/'predictions/prediction_run.json')
    if predictions['status']!='sealed_all_out_of_fold_predictions' or predictions['plan_sha256']!=plan['_sha256']:
        raise ValueError('All predictions must be sealed before evaluation')
    refs=[*features['clips'],*predictions['clips'],plan['manual_xy'],
        *(r for c in plan['clips'] for r in (c['training_gt'],c['sample_max'],c['reviewed_view']))]
    reader=Reader(root,refs)
    data=evaluate_clips([reader.json(r) for r in features['clips']],
        [reader.json(r) for r in predictions['clips']],
        {c['target']['pitch_id']:reader.json(c['training_gt']) for c in plan['clips']},
        {c['target']['pitch_id']:reader.json(c['sample_max']) for c in plan['clips']},
        {c['target']['pitch_id']:reader.json(c['reviewed_view']) for c in plan['clips']},reader.json(plan['manual_xy']))
    folder=output/'evaluation'; folder.mkdir()
    data.update(plan_sha256=plan['_sha256'],read_paths=reader.opened,
        production_adoption=False)
    save(folder/'evaluation.json',data); return data


def load_plan(root,path):
    plan=read(path)
    if (plan['status']!='frozen_before_joint_quality_classifier_trial' or plan['settings']!=SETTINGS
        or plan['decision']!=DECISION or [c['target']['pitch_id'] for c in plan['clips']]!=NAMES):
        raise ValueError('Changed approved experiment')
    for p,h in plan['code_hashes'].items():
        candidate=(root/p).resolve()
        if not candidate.is_relative_to(root) or sha(candidate)!=h: raise ValueError('Changed frozen code: '+p)
    if sha(root/plan['approved_protocol']['path'])!=plan['approved_protocol']['sha256']: raise ValueError('Changed protocol')
    plan['_sha256']=sha(path); return plan


def run(root,plan_path,stage,query=None):
    root,plan_path=Path(root).resolve(),Path(plan_path).resolve(); plan=load_plan(root,plan_path)
    output=(root/plan['output_directory']).resolve()
    if output==root/'analysis_results' or not output.is_relative_to(root/'analysis_results'): raise ValueError('Unsafe output')
    output.mkdir(parents=True,exist_ok=True)
    with exclusive_run(output/'stage.lock'):
        if stage=='features': return feature_stage(root,plan,output)
        if stage=='fit' and query in NAMES: return fit_stage(root,plan,output,query)
        if stage=='apply' and query in NAMES: return apply_stage(root,plan,output,query)
        if stage=='seal': return seal_predictions(root,plan,output)
        if stage=='evaluate': return evaluate_stage(root,plan,output)
        raise ValueError('Unknown stage or query')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('plan',type=Path)
    parser.add_argument('stage',choices=('features','fit','apply','seal','evaluate')); parser.add_argument('--query',choices=NAMES)
    args=parser.parse_args(); result=run(Path(__file__).resolve().parents[1],args.plan,args.stage,args.query)
    print(json.dumps({'stage':args.stage,'query':args.query,'status':result.get('status','completed')}))
