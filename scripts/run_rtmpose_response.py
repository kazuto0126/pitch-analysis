"""Source-bound RTMPose response trial; never changes the production pipeline."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import cv2
from run_heavy_information import Reader, reference, read, save, sha, locked, timeline, NAMES, ROLES
from measure_pose_mode_countercheck import load_video_raw
import rtmpose_response_features as features
import rtmpose_response_policy as policy

SETTINGS = {'signal':'native_simcc_deficit_at_original_full_nearest_bin', 'maximum_real_pose_calls':592,
    'maximum_synthetic_pose_calls':1,'input_size':[192,256],'padding':1.25,'split_ratio':2,
    'color_order':'RGB','normalized_responses':False,'roi':'sealed_human_seeded_csrt',
    'calibration':'four_other_clip_reliable_maximum','comparison':'strict_greater',
    'frame0_excluded':True,'production_adoption':False}


def export_stage(root,plan,out):
    folder=out/'exports'
    if folder.exists(): raise ValueError('Fresh input export required')
    folder.mkdir(); receipts=[]
    for clip in plan['clips']:
        pid=clip['pitch_id']; s=clip['measurement_sources']; reader=Reader(root,list(s.values()))
        video=reader.path(s['video']); reader.json(s['metadata']); meta=reader.json(s['video_metadata'])
        capture=reader.json(s['capture']); gate=reader.json(s['clean_config']); roi=reader.json(s['roi'])
        if meta['sha256']!=s['video']['sha256'] or meta['frame_count']!=clip['total_frames']:
            raise ValueError('Source video binding differs')
        if len(roi['frames'])!=clip['total_frames'] or (gate['min_visibility'],gate['min_presence'])!=(.5,.5):
            raise ValueError('ROI/gate source differs')
        raw=load_video_raw(reader.path(s['raw_csv']),capture,clip['total_frames'])
        stream=cv2.VideoCapture(str(video)); contexts=[]; tensors=[]
        try:
            for i in range(clip['total_frames']):
                ok,image=stream.read()
                if not ok or image.shape[:2]!=(meta['height'],meta['width']): raise ValueError('Decode geometry differs')
                time=stream.get(cv2.CAP_PROP_POS_MSEC); timestamp=capture['selection_frames'][i]['timestamp_ms']
                pixel=hashlib.sha256(image.tobytes()).hexdigest(); rf=roi['frames'][i]
                if (rf['frame_index']!=i or pixel!=rf['decoded_bgr_sha256'] or round(time)!=timestamp or
                        not math.isclose(time,meta['timestamps_ms'][i],abs_tol=1e-6)):
                    raise ValueError('Original pixels or timeline differ')
                tensor,geometry=features.preprocess(image,rf['usable_rectangle_xywh'])
                tensors.append(tensor)
                contexts.append({'frame_index':i,'timestamp_ms':timestamp,'decoded_bgr_sha256':pixel,
                    'geometry':geometry,'original_raw':raw[i]})
            if stream.read()[0]: raise ValueError('Unexpected extra frames')
        finally: stream.release()
        array_path=folder/(pid+'.npy')
        with array_path.open('xb') as handle: np.save(handle,np.stack(tensors),allow_pickle=False)
        data={'pitch_id':pid,'total_frames':clip['total_frames'],'width':meta['width'],'height':meta['height'],
            'video_sha256':s['video']['sha256'],'gate':{k:gate[k] for k in ('min_visibility','min_presence')},
            'frames':contexts,'read_paths':reader.opened,'human_annotation_inputs':[],'plan_sha256':plan['_sha256']}
        path=folder/(pid+'.json'); save(path,data)
        receipts.append({'pitch_id':pid,'total_frames':clip['total_frames'],'context':reference(root,path),'tensor':reference(root,array_path)})
        print(json.dumps({'pitch_id':pid,'exported_frames':len(contexts),'new_pose_calls':0}),flush=True)
    result={'status':'sealed_gt_blind_rtmpose_inputs','plan_sha256':plan['_sha256'],'clips':receipts,'human_annotation_inputs':[]}
    save(folder/'export_run.json',result); return result


def measurement_stage(root,plan,out):
    export=read(out/'exports/export_run.json'); native=read(out/'native/native_run.json')
    child=read(out/'native_execution.json')
    if (export['plan_sha256']!=plan['_sha256'] or native['human_annotation_inputs']!=[] or native['native_frames']!=592 or
            native['plan_sha256']!=sha(out/'native_execution.json') or child['parent_plan_sha256']!=plan['_sha256'] or
            child['model']!=plan['model']):
        raise ValueError('Native run or GT-blind export incomplete')
    frames={(r['pitch_id'],r['frame_index']):r for r in native['frames']}
    folder=out/'measurements'; folder.mkdir(); receipts=[]
    for clip in export['clips']:
        reader=Reader(root,[clip['context'],*[ref for key,ref in frames.items() if key[0]==clip['pitch_id']]])
        context=reader.json(clip['context']); built=[]
        for item in context['frames']:
            ref=frames[(clip['pitch_id'],item['frame_index'])]
            with np.load(reader.path(ref),allow_pickle=False) as arrays:
                data=features.build_frame(item['original_raw'],arrays['simcc_x'],arrays['simcc_y'],item['geometry'],
                    context['width'],context['height'],context['gate'])
            built.append({**data,'frame_index':item['frame_index'],'timestamp_ms':item['timestamp_ms'],
                'decoded_bgr_sha256':item['decoded_bgr_sha256'],'geometry':item['geometry'],'native_ref':ref})
        result={k:context[k] for k in ('pitch_id','total_frames','width','height','video_sha256','gate')}
        result.update(status='sealed_rtmpose_response_measurements',plan_sha256=plan['_sha256'],frames=built,
            read_paths=reader.opened,human_annotation_inputs=[],new_pose_calls=0)
        path=folder/(clip['pitch_id']+'.json'); save(path,result); receipts.append(reference(root,path))
    result={'status':'sealed_all_rtmpose_response_measurements','plan_sha256':plan['_sha256'],'clips':receipts,'human_annotation_inputs':[]}
    save(folder/'measurement_run.json',result); return {'status':result['status'],'source_frames':592}


def measurement_receipt(plan,out):
    result=read(out/'measurements/measurement_run.json')
    if result['plan_sha256']!=plan['_sha256'] or len(result['clips'])!=5 or result['human_annotation_inputs']!=[]:
        raise ValueError('Measurement seal differs')
    return result


def calibrate_stage(root,plan,out,query):
    measured=measurement_receipt(plan,out)
    chosen=[(c,r) for c,r in zip(plan['clips'],measured['clips'],strict=True) if c['pitch_id']!=query]
    reader=Reader(root,[r for c,r in chosen]+[c['canonical_gt'] for c,r in chosen])
    folder=out/'folds'/query; folder.mkdir(parents=True,exist_ok=True); path=folder/'calibration.json'
    if path.exists():
        old=read(path)
        if old['plan_sha256']!=plan['_sha256']: raise ValueError('Saved calibration changed')
        return {'status':'skipped_completed_calibration','pitch_id':query}
    if (folder/'attempt.json').exists(): raise ValueError('Indeterminate calibration; retry refused')
    data={c['pitch_id']:reader.json(r) for c,r in chosen}; gt={c['pitch_id']:reader.json(c['canonical_gt']) for c,r in chosen}
    save(folder/'attempt.json',{'plan_sha256':plan['_sha256'],'query':query,'training_pitch_ids':list(data)})
    numeric={}; traces={}
    for role in ROLES:
        training=[]
        for clip,ref in chosen:
            pid=clip['pitch_id']; labels=timeline(gt[pid],clip,role)
            training.append({'pitch_id':pid,'rows':[{'frame_index':f['frame_index'],
                'response_deficit':f['roles'][role]['response_deficit'],'canonical_label':labels[f['frame_index']]}
                for f in data[pid]['frames']]})
        value=policy.calibrate(training,query,role); traces[role]=value.pop('trace'); numeric[role]=value
    save(folder/'training_trace.json',{'rows':traces,'read_paths':reader.opened})
    result={'pitch_id':query,'plan_sha256':plan['_sha256'],'roles':numeric,'read_paths':reader.opened}
    save(path,result); return {'pitch_id':query,'fold_status':{r:numeric[r]['status'] for r in ROLES}}


def apply_stage(root,plan,out,query):
    measured=measurement_receipt(plan,out); ref=measured['clips'][NAMES.index(query)]
    calibration=reference(root,out/'folds'/query/'calibration.json'); reader=Reader(root,[ref,calibration])
    data=reader.json(ref); numeric=reader.json(calibration)
    if data['pitch_id']!=query or numeric['pitch_id']!=query or numeric['plan_sha256']!=plan['_sha256']:
        raise ValueError('Query/numeric source mismatch')
    frames=[{'frame_index':f['frame_index'],'timestamp_ms':f['timestamp_ms'],'roles':{}} for f in data['frames']]
    for role in ROLES:
        values=policy.apply([{'frame_index':f['frame_index'],'response_deficit':f['roles'][role]['response_deficit']}
            for f in data['frames']],numeric['roles'][role])
        for frame,value in zip(frames,values,strict=True): frame['roles'][role]=value
    folder=out/'predictions'; folder.mkdir(exist_ok=True); path=folder/(query+'.json')
    result={'pitch_id':query,'plan_sha256':plan['_sha256'],'frames':frames,
        'fold_status':{r:numeric['roles'][r]['status'] for r in ROLES},'reads_annotations':False,'read_paths':reader.opened}
    if path.exists():
        if read(path)!=result: raise ValueError('Saved query predictions differ')
    else: save(path,result)
    return {'pitch_id':query,'warnings':{r:sum(f['roles'][r]['evaluated_warning'] for f in frames) for r in ROLES}}


def seal_stage(root,plan,out):
    refs=[reference(root,out/'predictions'/(pid+'.json')) for pid in NAMES]; reader=Reader(root,refs)
    for pid,ref in zip(NAMES,refs,strict=True):
        d=reader.json(ref)
        if d['pitch_id']!=pid or d['plan_sha256']!=plan['_sha256'] or d['reads_annotations']:
            raise ValueError('Incomplete annotation-free OOF')
    result={'status':'sealed_rtmpose_response_oof','plan_sha256':plan['_sha256'],'clips':refs}
    save(out/'predictions/prediction_run.json',result); return {'status':result['status']}


def evaluate_stage(root,plan,out):
    import evaluate_rtmpose_response as evaluation
    measured=measurement_receipt(plan,out); sealed=read(out/'predictions/prediction_run.json')
    if sealed['plan_sha256']!=plan['_sha256']: raise ValueError('OOF not sealed')
    refs=[*measured['clips'],*sealed['clips'],plan['baseline_evaluation'],plan['manual_xy'],plan['visibility_audit'],
        *[c['canonical_gt'] for c in plan['clips']],*[c['major_hints'] for c in plan['clips']]]
    reader=Reader(root,refs)
    m={pid:reader.json(ref) for pid,ref in zip(NAMES,measured['clips'],strict=True)}
    prediction={pid:reader.json(ref) for pid,ref in zip(NAMES,sealed['clips'],strict=True)}
    native_refs=[f['native_ref'] for d in m.values() for f in d['frames']]; native_reader=Reader(root,native_refs)
    for data in m.values():
        for frame in data['frames']:
            with np.load(native_reader.path(frame['native_ref']),allow_pickle=False) as arrays:
                frame['native_simcc_x']=arrays['simcc_x']; frame['native_simcc_y']=arrays['simcc_y']
    gt={c['pitch_id']:reader.json(c['canonical_gt']) for c in plan['clips']}
    major={c['pitch_id']:reader.json(c['major_hints']) for c in plan['clips']}
    result=evaluation.evaluate_clips(m,prediction,gt,reader.json(plan['baseline_evaluation']),major,
        reader.json(plan['manual_xy']),reader.json(plan['visibility_audit']))
    result.update(plan_sha256=plan['_sha256'],read_paths=reader.opened+native_reader.opened,
        pose_inference_calls=0,tracker_inference_calls=0,production_adoption=False)
    folder=out/'evaluation'; folder.mkdir(); save(folder/'evaluation.json',result)
    return {'status':result['status'],'decision':result['decision']}


def run(root,path,stage,query=None):
    root=root.resolve(); plan=read(path); plan['_sha256']=sha(path)
    if plan['settings']!=SETTINGS or tuple(c['pitch_id'] for c in plan['clips'])!=NAMES:
        raise ValueError('Frozen response settings differ')
    for ref in plan['code_sources']: Reader(root,[ref]).path(ref)
    out=(root/plan['output_path']).resolve()
    if not out.is_relative_to(root/'analysis_results') or not out.is_dir(): raise ValueError('Independent output required')
    if stage in ('calibrate','apply') and query not in NAMES: raise ValueError('Formal query required')
    with locked(out/'analysis_stage.lock'):
        if stage=='export': return export_stage(root,plan,out)
        if stage=='measurements': return measurement_stage(root,plan,out)
        if stage=='calibrate': return calibrate_stage(root,plan,out,query)
        if stage=='apply': return apply_stage(root,plan,out,query)
        if stage=='seal': return seal_stage(root,plan,out)
        if stage=='evaluate': return evaluate_stage(root,plan,out)
        raise ValueError('Unknown response stage')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('plan',type=Path)
    p.add_argument('stage',choices=('export','measurements','calibrate','apply','seal','evaluate')); p.add_argument('--query',choices=NAMES)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); a=p.parse_args()
    print(json.dumps(run(a.root,a.plan,a.stage,a.query)),flush=True)
