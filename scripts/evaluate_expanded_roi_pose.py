"""Offline four-arm audit of the fixed expanded ROI; no inference or GT edits."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import evaluate_assisted_roi_cohort as cohort
import assess_saved_roi_angles as angles
from measure_expanded_roi_pose import bound, save, read, sha, verify_execution, AttemptJournal
from measure_tracked_roi_pose import map_candidates, _pixel_hash
from measure_pose_mode_countercheck import selected_points, load_video_raw, finite_point, gate
from pitch_analysis.subject import PitcherSelector
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints

ARMS = ('expanded','narrow','image','video')
POLICY = {'arms':list(ARMS),'seed_excluded':0,'manual_reference_in_crop':'stratum_only',
    'same_frame_pairing':True,'original_gates':True,'manual_xy_only':'pitch_003',
    'original_review_labels':'context_only_not_new_prediction_truth','production_adoption':False,
    'pose_inference_calls':0,'tracker_inference_calls':0}


def independent_bounds(rectangle, w, h):
    if rectangle is None: return None
    x,y,rw,rh = rectangle
    if rw <= 0 or rh <= 0: return None
    bounds = [max(0,math.floor(x-rw/2)),max(0,math.floor(y-rh/2)),
              min(w,math.ceil(x+1.5*rw)),min(h,math.ceil(y+1.5*rh))]
    return bounds if bounds[2]>bounds[0] and bounds[3]>bounds[1] else None


def replay_expanded(frame, tracker, pixels, ms, technical_ms, selector, target):
    bounds = independent_bounds(tracker['usable_rectangle_xywh'],target['width'],target['height'])
    if (frame['crop_bounds_xyxy'] != bounds or frame['frame_index'] != tracker['frame_index']
        or frame['decoded_bgr_sha256'] != _pixel_hash(pixels)
        or frame['decoded_bgr_sha256'] != tracker['decoded_bgr_sha256']
        or any(not math.isclose(ms,t,rel_tol=0,abs_tol=1e-6) for t in (technical_ms,frame['native_timestamp_ms'],tracker['native_timestamp_ms']))
        or frame['timestamp_ms'] != round(ms)):
        raise ValueError('Expanded source/crop/PTS mismatch')
    if bounds:
        a,b,c,d = bounds; crop = np.ascontiguousarray(pixels[b:d,a:c])
        if (frame['crop_bgr_sha256'] != _pixel_hash(crop) or frame['crop_shape'] != list(crop.shape)
            or frame['crop_rgb_sha256'] != _pixel_hash(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB))
            or frame['inference_status'] != 'measured'): raise ValueError('Expanded pixels differ')
        mapped = map_candidates(frame['crop_candidates'],bounds,target['width'],target['height'])
    else:
        if frame['crop_candidates'] or frame['inference_status'] != 'roi_unavailable': raise ValueError('Fabricated missing ROI')
        mapped = []
    choice = asdict(selector.select(cohort._poses(mapped)))
    if (frame['full_image_candidates'] != mapped or frame['selection'] != choice
        or frame['warning_prediction'] is not None or frame['subject_alignment_verified'] is not False):
        raise ValueError('Expanded mapping/selector/semantics differ')


def point_state(point, crop_point, target, config, cropped):
    finite = finite_point(point)
    supported = bool(finite and 0<=point['x']<1 and 0<=point['y']<1 and
        (not cropped or finite_point(crop_point) and 0<=crop_point['x']<1 and 0<=crop_point['y']<1))
    return {'raw':point is not None,'finite':finite,'gate':gate(point,config),
        'input_support':supported,'supported_gate':bool(supported and gate(point,config)),
        'visibility':point['visibility'] if finite else None,'presence':point['presence'] if finite else None,
        'xy_px':[point['x']*target['width'],point['y']*target['height']] if finite else None}


def transitions(rows, before, after, field):
    result = {k:[] for k in ('both','lost','gained','neither')}
    for row in rows:
        a,b = bool(row['arms'][before][field]),bool(row['arms'][after][field])
        result['both' if a and b else 'lost' if a else 'gained' if b else 'neither'].append(row['frame_index'])
    return {k:{'count':len(v),'frames':v} for k,v in result.items()}


def joint_summary(rows):
    rows = [r for r in rows if r['frame_index']!=0]
    result = {'non_seed_frames':len(rows),'arms':{}}
    for arm in ARMS:
        values = [r['arms'][arm] for r in rows]
        result['arms'][arm] = {k:sum(p[k] for p in values) for k in ('raw','finite','gate','input_support','supported_gate')}
        result['arms'][arm].update({k:cohort.describe([p[k] for p in values if p[k] is not None]) for k in ('visibility','presence')})
        result['arms'][arm]['longest_missing_span'] = cohort.longest_span(rows,lambda r:not r['arms'][arm]['raw'])
        result['arms'][arm]['longest_unsupported_gate_span'] = cohort.longest_span(rows,lambda r:not r['arms'][arm]['supported_gate'])
        result['arms'][arm]['adjacent_supported_jump_px'] = cohort.describe([
            math.dist(a['arms'][arm]['xy_px'],b['arms'][arm]['xy_px']) for a,b in zip(rows,rows[1:])
            if b['frame_index']==a['frame_index']+1 and a['arms'][arm]['supported_gate'] and b['arms'][arm]['supported_gate']])
    result['transitions_to_expanded'] = {arm:{f:transitions(rows,arm,'expanded',f)
        for f in ('raw','gate','supported_gate')} for arm in ARMS[1:]}
    return result


def xy_summary(rows):
    rows = [r for r in rows if r['frame_index']!=0]
    visible = [r for r in rows if r['manual_status']=='visible']
    result = {'all_joint_records':len(rows),'manual_status_counts':dict(Counter(r['manual_status'] for r in rows)),
              'visible_reference_count':len(visible),'paired':{},'arms':{}}
    for arm in ARMS:
        errors = [r['errors_px'][arm] for r in visible if r['errors_px'][arm] is not None]
        result['arms'][arm] = {'supported_visible_count':len(errors),'visible_prediction_missing':len(visible)-len(errors),
                               'conditional_error_px':cohort.describe(errors)}
    for arm in ARMS[1:]:
        common = [r for r in visible if all(r['errors_px'][a] is not None for a in (arm,'expanded'))]
        delta = [r['errors_px']['expanded']-r['errors_px'][arm] for r in common]
        result['paired'][arm] = {'common_joint_records':len(common),
            'identities':[[r['frame_index'],r['joint']] for r in common],
            'baseline_px':cohort.describe([r['errors_px'][arm] for r in common]),
            'expanded_px':cohort.describe([r['errors_px']['expanded'] for r in common]),
            'improved':sum(v < -1e-8 for v in delta),'worsened':sum(v > 1e-8 for v in delta),
            'tied':sum(abs(v)<=1e-8 for v in delta)}
    return result


def angle_summary(rows):
    rows = [r for r in rows if r['frame_index']!=0]
    reference = [r for r in rows if r['manual_reference']['value_deg'] is not None]
    arms = (*ARMS,'video_processed')
    result = {'non_seed_frames':len(rows),'manual_reference_frames':len(reference),'arms':{},'paired':{},'transitions':{}}
    for arm in arms:
        errors = [r['streams'][arm]['signed_error_deg'] for r in rows if r['streams'][arm]['signed_error_deg'] is not None]
        result['arms'][arm] = {'numerical_support':sum(r['streams'][arm]['numerical_support'] for r in rows),
            'reference_with_prediction':len(errors),'reference_prediction_missing':len(reference)-len(errors),
            'conditional_error':angles.original.error_stats(errors)}
    for arm in arms[1:]:
        common = [r for r in rows if all(r['streams'][a]['signed_error_deg'] is not None for a in ('expanded',arm))]
        a,b = ([r['streams'][s]['signed_error_deg'] for r in common] for s in (arm,'expanded'))
        delta = [abs(y)-abs(x) for x,y in zip(a,b)]
        result['paired'][arm] = {'frames':[r['frame_index'] for r in common],'common_frames':len(common),
            'baseline':angles.original.error_stats(a),'expanded':angles.original.error_stats(b),
            'improved':sum(v < -1e-8 for v in delta),'worsened':sum(v > 1e-8 for v in delta),
            'tied':sum(abs(v)<=1e-8 for v in delta)}
        result['transitions'][arm] = {label:transitions([{'frame_index':r['frame_index'],
            'arms':{a:{'support':r['streams'][a]['numerical_support']} for a in (arm,'expanded')}} for r in part],arm,'expanded','support')
            for label,part in (('all_frames',rows),('visible_reference',reference))}
    return result


def evaluate(root, plan_path):
    root,plan_path = Path(root).resolve(),Path(plan_path).resolve()
    plan = read(plan_path); plan_sha = sha(plan_path)
    verify_execution(root,plan)
    if plan['evaluation_policy'] != POLICY: raise ValueError('Evaluation policy changed')
    for name,digest in plan['evaluator_code'].items(): bound(root,{'path':name,'sha256':digest})
    source_refs = list(plan['evaluation_lineage'].values())
    for ref in source_refs: bound(root,ref)
    output = (root/plan['evaluation_output_directory']).resolve()
    if output.exists() or not output.is_relative_to(root/'analysis_results') or output==root/'analysis_results':
        raise ValueError('New evaluation output required')
    measurements = root/plan['output_directory']; run = read(measurements/'cohort_measurements.json')
    if (run['status']!='sealed_expanded_roi_cohort' or run['plan_sha256']!=plan_sha
        or run['source_frames']!=592 or run['non_seed_frames']!=587 or run['pose_inference_calls']>592
        or run['tracker_inference_calls']!=0 or run['human_annotation_inputs']!=[] or run['production_adoption'] is not False):
        raise ValueError('Unsealed or differently scoped measurements')
    journal = AttemptJournal(measurements/'attempts.jsonl')
    if (run['attempts_sha256']!=sha(journal.path) or set(journal.started)!=set(journal.completed)
        or len(journal.started)!=run['pose_inference_calls']): raise ValueError('Attempt seal differs')
    old_angles = read(bound(root,plan['evaluation_lineage']['saved_angle_rows']))['features']
    output.mkdir(); reports = []; replayed = 0
    for clip,receipt in zip(plan['clips'],run['clips'],strict=True):
        target = clip['target']; pid = target['pitch_id']; refs = plan['evaluator_sources'][pid]
        source_refs.extend(refs.values())
        for ref in refs.values(): bound(root,ref)
        sources = clip['producer_sources']; expanded = read(bound(root,receipt['pose']))
        narrow,image,capture,config,canonical = (read(bound(root,refs[k])) for k in ('narrow_pose','full_frame_image','capture','clean_config','canonical_review'))
        if (receipt['target']!=target or receipt['pitch_id']!=pid or expanded['target']!=target
            or expanded['producer_sources']!=sources or expanded['plan_sha256']!=plan_sha
            or expanded['parameters']!=plan['parameters'] or expanded['options']!=plan['options']
            or expanded['human_annotation_inputs']!=[] or expanded['status']!='sealed_expanded_roi_clip'
            or expanded['inference_calls']!=sum(f['inference_status']=='measured' for f in expanded['frames'])
            or narrow['target']!=target or any(narrow['producer_sources'][k]!=sources[k] for k in ('video','metadata','video_technical','tracked_roi'))
            or image['video_sha256']!=sources['video']['sha256']): raise ValueError('Cross-arm sources differ')
        gates = angles._verify_clean_config(root,config,target,refs['original_raw'],refs['capture'])
        if image['gate']!=gates: raise ValueError('IMAGE gate differs')
        raw = load_video_raw(bound(root,refs['original_raw']),capture,target['total_frames'])
        cohort.validate_ground_truth(canonical,source_video_path=bound(root,sources['video']))
        if canonical['annotation_status']!='reviewed': raise ValueError('Unreviewed context')
        major = cohort.major_timeline(canonical,target['total_frames'])
        tracked,technical = (read(bound(root,sources[k])) for k in ('tracked_roi','video_technical'))
        manual = None
        if 'manual_xy' in refs:
            if pid!='pitch_003': raise ValueError('Unexpected manual coordinate cohort')
            manual = read(bound(root,refs['manual_xy']))
            validate_manual_keypoints(manual,source_video_path=bound(root,sources['video']))
            if manual['annotation_status']!='reviewed': raise ValueError('Unreviewed manual XY')
        for seq in (expanded['frames'],narrow['frames'],image['frames'],tracked['frames']):
            if [f['frame_index'] for f in seq]!=list(range(target['total_frames'])): raise ValueError('Incomplete frame denominator')
        rows,xy,angle_rows = [],[],{k:[] for k in old_angles}; selectors = [PitcherSelector() for _ in range(3)]
        video = cv2.VideoCapture(str(bound(root,sources['video'])))
        try:
            for i in range(target['total_frames']):
                ok,pixels = video.read()
                if not ok: raise ValueError('Source decode incomplete')
                ms = video.get(cv2.CAP_PROP_POS_MSEC)
                wide,small,control = expanded['frames'][i],narrow['frames'][i],image['frames'][i]
                if read(measurements/pid/'frames'/f'{i:04d}.json')!=wide: raise ValueError('Per-frame persistence differs')
                if wide['inference_status']=='measured' and journal.completed[wide['attempt_id']]['result_sha256']!=sha(measurements/pid/'frames'/f'{i:04d}.json'):
                    raise ValueError('Attempt/result hash differs')
                if wide['inference_status']=='measured' and journal.started[wide['attempt_id']]!={'event':'started','attempt_id':wide['attempt_id'],**wide['input_receipt']}:
                    raise ValueError('Attempt input receipt differs')
                replay_expanded(wide,tracked['frames'][i],pixels,ms,technical['timestamps_ms'][i],selectors[0],target)
                cohort.replay_frame(small,tracked['frames'][i],pixels,ms,technical['timestamps_ms'][i],selectors[1],target)
                cohort.replay_image_frame(control,pixels,ms,technical['timestamps_ms'][i],selectors[2],raw[i],capture['selection_frames'][i],target,gates)
                arms = {'expanded':selected_points(wide['full_image_candidates'],wide['selection']),
                    'narrow':selected_points(small['full_image_candidates'],small['selection']),
                    'image':selected_points(control['image_candidates'],control['image_selection']),'video':raw[i]}
                crops = {a:selected_points(f['crop_candidates'],f['selection']) for a,f in (('expanded',wide),('narrow',small))}
                choices = {'expanded':wide['selection'],'narrow':small['selection'],'image':control['image_selection'],'video':capture['selection_frames'][i]}
                frame = {'frame_index':i,'original_major_context':major[i],'selection':choices,'joints':{}}
                for name in JOINT_NAMES:
                    row = {'frame_index':i,'joint':name,'original_major_context':major[i],
                        'arms':{a:point_state(points.get(name),crops.get(a,{}).get(name),target,gates,a in crops) for a,points in arms.items()}}
                    frame['joints'][name] = row
                    if manual:
                        human = next(j for j in manual['frames'][i]['joints'] if j['name']==name)
                        reference = [human['x_px'],human['y_px']] if human['status']=='visible' else None
                        xy.append({**row,'manual_status':human['status'],'manual_xy_px':reference,
                            'reference_in_expanded_crop':angles.roi_audit.inside(wide['crop_bounds_xyxy'],*reference) if reference else None,
                            'errors_px':{a:math.dist(p['xy_px'],reference) if reference and p['supported_gate'] else None for a,p in row['arms'].items()}})
                rows.append(frame); replayed += 1
                if manual:
                    joints = {j['name']:j for j in manual['frames'][i]['joints']}
                    if not math.isclose(manual['frames'][i]['timestamp_ms'],ms,abs_tol=1e-6,rel_tol=0): raise ValueError('Manual frame timestamp differs')
                    for name,old in old_angles.items():
                        saved = old[i]; names = saved['required_landmarks']; ref = angles.original.manual_reference(joints,names)
                        if ref!=saved['manual_reference']: raise ValueError('Manual reference changed')
                        streams = {}
                        for arm,points in arms.items():
                            stream = angles._raw_stream(names,points,choices[arm]['status'],target['width'],target['height'],gates,crops.get(arm))
                            value,u = stream['numerical_supported_angle_deg'],stream['ungated_angle_deg']; r = ref['value_deg']
                            stream.update(signed_error_deg=value-r if value is not None and r is not None else None,
                                ungated_signed_error_deg=u-r if u is not None and r is not None else None)
                            if arm!='expanded' and stream!=saved['streams'][{'narrow':'crop','video':'video_raw'}.get(arm,arm)]:
                                raise ValueError('Replayed control angle differs')
                            streams[arm] = stream
                        streams['video_processed'] = saved['streams']['video_processed']
                        angle_rows[name].append({**saved,'streams':streams,
                            'reference_all_points_in_expanded_crop':all(angles.roi_audit.inside(wide['crop_bounds_xyxy'],joints[n]['x_px'],joints[n]['y_px']) for n in names) if ref['value_deg'] is not None else None})
            if video.read()[0]: raise ValueError('Extra source frame')
        finally: video.release()
        per_joint = {name:joint_summary([r['joints'][name] for r in rows]) for name in JOINT_NAMES}
        summary = {'pitch_id':pid,'source_frames':len(rows),'non_seed_frames':len(rows)-1,
            'selection':{a:dict(Counter(r['selection'][a]['status'] for r in rows[1:])) for a in ARMS},
            'per_joint':per_joint,'precise_xy':None,'angles':None}
        if manual:
            summary['precise_xy'] = {'all':xy_summary(xy),'per_joint':{n:xy_summary([r for r in xy if r['joint']==n]) for n in JOINT_NAMES}}
            summary['angles'] = {n:{'all':angle_summary(rs),'by_original_major':{str(v):angle_summary([r for r in rs if r['existing_major_hold'] is v]) for v in (False,True)},
                'by_original_eligibility':{str(v):angle_summary([r for r in rs if r['existing_eligible'] is v]) for v in (False,True)}} for n,rs in angle_rows.items()}
            save(output/'pitch_003_xy_rows.json',xy); save(output/'pitch_003_angle_rows.json',angle_rows)
        save(output/f'{pid}_frame_rows.json',rows); reports.append(summary)
    for ref in source_refs: bound(root,ref)
    verify_execution(root,plan)
    if sha(plan_path)!=plan_sha or replayed!=592: raise ValueError('Source denominator or plan changed')
    report = {'status':'complete_expanded_roi_evaluation','plan_sha256':plan_sha,'policy':POLICY,
        'source_frames_replayed':replayed,'non_seed_frames':587,'clips':reports,'production_adoption':False,
        'phase2_automatic_reliability':'NOT PASSED','new_pose_inference_calls':0,'new_tracker_calls':0}
    save(output/'evaluation.json',report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('plan',type=Path)
    args = parser.parse_args(); result = evaluate(Path(__file__).resolve().parents[1],args.plan)
    print(json.dumps({'replayed':result['source_frames_replayed'],'clips':[c['selection'] for c in result['clips']]}))
