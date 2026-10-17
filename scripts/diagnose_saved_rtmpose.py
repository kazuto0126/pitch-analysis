"""Read-only post-decision diagnostics. No model calls, calibration or adoption."""
from __future__ import annotations
import argparse
from collections import Counter
import math
from pathlib import Path
import numpy as np
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints
from run_heavy_information import Reader, read, reference, save, sha


def xy_error(xy, target):
    if xy is None:
        return None
    return math.hypot(xy[0]-target[0], xy[1]-target[1])


def finite_xy(point, x_key, y_key, scale=(1, 1)):
    if not point or any(point.get(k) is None or not math.isfinite(point[k]) for k in (x_key,y_key)):
        return None
    return [point[x_key]*scale[0], point[y_key]*scale[1]]


def stats(values):
    return {'n':len(values), 'mean_px':float(np.mean(values)) if values else None,
        'median_px':float(np.median(values)) if values else None,
        'p95_px':float(np.percentile(values,95)) if values else None,
        'maximum_px':max(values) if values else None}


def summarize(rows):
    visible=[r for r in rows if r['human_status']=='visible']
    paired=[r for r in visible if r['full_error_px'] is not None and r['rtmpose_error_px'] is not None]
    return {'source_rows':len(rows),'human_status_counts':dict(Counter(r['human_status'] for r in rows)),
        'visible_full_missing':sum(r['full_error_px'] is None for r in visible),
        'visible_rtmpose_missing':sum(r['rtmpose_error_px'] is None for r in visible),
        'visible_full_gate_pass':sum(r['full_gate_pass'] for r in visible),
        'same_frame_same_joint_paired':{
            'full':stats([r['full_error_px'] for r in paired]),
            'rtmpose':stats([r['rtmpose_error_px'] for r in paired]),
            'rtmpose_closer':sum(r['rtmpose_error_px']<r['full_error_px'] for r in paired),
            'rtmpose_farther':sum(r['rtmpose_error_px']>r['full_error_px'] for r in paired),
            'exactly_equal':sum(r['rtmpose_error_px']==r['full_error_px'] for r in paired)},
        'native_coordinate_without_visible_human_reference':sum(r['human_status']!='visible' and
            r['rtmpose_xy_px'] is not None for r in rows)}


def diagnose(root, plan_path, result_receipt, output):
    root=root.resolve(); plan=read(plan_path); receipt=read(result_receipt)
    if receipt['execution']!=reference(root,plan_path) or receipt['decision']['status']!='rejected':
        raise ValueError('Completed rejected trial required; no new policy evaluation')
    if output.exists() or not output.resolve().is_relative_to(root/'analysis_results'):
        raise ValueError('Fresh independent diagnostic output required')
    trial=root/plan['output_path']; measured=read(trial/'measurements/measurement_run.json')
    exported=read(trial/'exports/export_run.json')
    refs=[receipt['artifacts']['evaluation/evaluation.json'],receipt['artifacts']['measurements/measurement_run.json'],
        receipt['artifacts']['exports/export_run.json'],plan['manual_xy'],*measured['clips'],
        next(c['context'] for c in exported['clips'] if c['pitch_id']=='pitch_003')]
    for clip in plan['clips']:
        refs.extend(reference(root,trial/'folds'/clip['pitch_id']/name) for name in ('calibration.json','training_trace.json'))
    reader=Reader(root,refs)
    evaluation=reader.json(receipt['artifacts']['evaluation/evaluation.json'])
    sources={read(root/ref['path'])['pitch_id']:reader.json(ref) for ref in measured['clips']}
    contexts=reader.json(next(c['context'] for c in exported['clips'] if c['pitch_id']=='pitch_003'))
    manual=reader.json(plan['manual_xy']); validate_manual_keypoints(manual)
    data=sources['pitch_003']
    if (manual['annotation_status']!='reviewed' or manual['source_video']['pitch_id']!='pitch_003' or
            manual['source_video']['sha256']!=data['video_sha256'] or contexts['video_sha256']!=data['video_sha256'] or
            manual['source_video']['total_frames']!=data['total_frames'] or
            manual['image_size']!={'width':data['width'],'height':data['height']}):
        raise ValueError('Manual/source pixel contract differs')
    if any([f['frame_index'] for f in value['frames']]!=list(range(data['total_frames'])) for value in (manual,data,contexts)):
        raise ValueError('Incomplete or unordered coordinate frames')
    existing={(r['pitch_id'],r['frame_index'],r['role']):r for r in evaluation['frame_joint_rows']}
    rows=[]
    for human, native, context in zip(manual['frames'],data['frames'],contexts['frames'],strict=True):
        index=human['frame_index']; joints={j['name']:j for j in human['joints']}
        decoded={j['name']:j for j in native['native_keypoints']}
        if len(decoded)!=17 or len(joints)!=12: raise ValueError('Joint mapping changed')
        for joint in JOINT_NAMES:
            target=joints[joint]; raw=context['original_raw'].get(joint)
            full_xy=finite_xy(raw,'x','y',(data['width'],data['height']))
            native_xy=finite_xy(decoded[joint],'x_px','y_px')
            truth=finite_xy(target,'x_px','y_px') if target['status']=='visible' else None
            if (target['status']=='visible')!=(truth is not None): raise ValueError('Visible human XY missing')
            gate=full_xy is not None and all(raw.get(k) is not None and math.isfinite(raw[k]) and raw[k]>=data['gate']['min_'+k]
                for k in ('visibility','presence'))
            rows.append({'frame_index':index,'joint':joint,'human_status':target['status'],
                'human_xy_px':truth,'full_xy_px':full_xy,'rtmpose_xy_px':native_xy,'full_gate_pass':gate,
                'full_error_px':xy_error(full_xy,truth) if truth is not None else None,
                'rtmpose_error_px':xy_error(native_xy,truth) if truth is not None else None,
                'effectiveness_eligible':index!=0,
                'original_major_hold':existing[('pitch_003',index,'throwing_elbow')]['original_context']['major_hold']})
    maxima=[]
    for clip in plan['clips']:
        pid=clip['pitch_id']; calibration=reader.json(reference(root,trial/'folds'/pid/'calibration.json'))
        traces=reader.json(reference(root,trial/'folds'/pid/'training_trace.json'))
        for role,numeric in calibration['roles'].items():
            suppliers=[]
            for trace in traces['rows'][role]:
                frame=sources[trace['pitch_id']]['frames'][trace['frame_index']]
                signal=frame['roles'][role]
                if trace['excluded_reason'] is None and signal['response_deficit']==numeric['threshold']:
                    suppliers.append({'pitch_id':trace['pitch_id'],'frame_index':trace['frame_index'],
                        'canonical_label_of_original_full':trace['label'], 'response_deficit':signal['response_deficit'],
                        'full_xy_px':signal['full_xy_px'],'full_input_xy':signal['full_input_xy'],'bins':signal['bins'],
                        'native_score':signal['native_score'],'native_xy_px':signal['native_xy_px']})
            if not suppliers: raise ValueError('Saved maximum source not found')
            maxima.append({'query_pitch_id':pid,'role':role,'saved_threshold':numeric['threshold'],'suppliers':suppliers})
    missed={}
    for role in ('throwing_elbow','throwing_wrist'):
        fn=[r for r in evaluation['frame_joint_rows'] if r['role']==role and r['effectiveness_eligible'] and
            r['canonical_label']=='unreliable' and not r['screens']['rtmpose_response']['evaluated_warning']]
        missed[role]={'count':len(fn),'reason_counts':dict(Counter(r['evidence_reason'] or 'measured_not_above_saved_threshold' for r in fn)),
            'original_gate_pass':sum(r['raw_gate_pass'] for r in fn),'covered_by_existing_major_hint':sum(r['existing_major_review_required'] for r in fn)}
    summary={'status':'complete_saved_outputs_diagnostic_no_new_trial','source_rows':len(rows),
        'source_video':'pitch_003','all_frames':{'rows':len(rows),'human_status_counts':dict(Counter(r['human_status'] for r in rows))},
        'non_seed':{joint:summarize([r for r in rows if r['joint']==joint and r['effectiveness_eligible']]) for joint in JOINT_NAMES},
        'original_major_hold_subset':{joint:summarize([r for r in rows if r['joint']==joint and r['effectiveness_eligible'] and r['original_major_hold']]) for joint in JOINT_NAMES},
        'saved_threshold_sources':maxima,'missed_original_wrong_points':missed,
        'new_inference_calls':0,'new_calibrations':0,'new_labels':0,'threshold_or_decision_changes':False,
        'adoption_decision':'remains_rejected','phase2_automatic_reliability':'NOT_PASSED',
        'scope':'Post-decision continuous XY diagnosis only. No classifier, new hint, normalization, threshold search or model replacement.',
        'limitations':['Exact XY accuracy applies only to the existing visible manual points in pitch_003.',
            'Canonical reliability labels target original Full, not RTMPose.',
            'Native coordinates on occluded points are model estimates, not observed truth.',
            'Existing human-initialized CSRT ROI is a prerequisite.'],
        'source_refs':refs,'read_paths':reader.opened,'helper':reference(root,Path(__file__))}
    for ref in refs: Reader(root,[ref]).path(ref)
    output.mkdir(parents=True)
    save(output/'frame_joint_rows.json',{'rows':rows})
    summary['frame_joint_rows']=reference(root,output/'frame_joint_rows.json')
    save(output/'summary.json',summary)
    return {'status':summary['status'],'rows':len(rows),'missed_reasons':missed}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('plan',type=Path); p.add_argument('result_receipt',type=Path); p.add_argument('output',type=Path)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]); args=p.parse_args()
    import json
    print(json.dumps(diagnose(args.root,args.plan,args.result_receipt,args.output)),flush=True)
