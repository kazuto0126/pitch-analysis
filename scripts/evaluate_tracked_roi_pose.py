"""Offline paired XY audit of sealed crop predictions; never creates human labels."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from measure_tracked_roi_pose import (TARGET, crop_bounds, map_candidates, serialize_candidates,
    read, sha, write, verify_execution, verify_sources, validate_tracked_roi)
from measure_pose_mode_countercheck import load_video_raw, selected_points, gate
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.manual_keypoints import validate_manual_keypoints, JOINT_NAMES
from pitch_analysis.pose_capture import LANDMARK_NAMES
from pitch_analysis.subject import PitcherSelector


EXAMPLE_FRAMES = [38, 70, 78, 87, 92, 95, 101, 104, 112]
OLD_INSIDE_FAILURE_FRAMES = list(range(87, 93)) + list(range(101, 105))
DENOMINATORS = {'source_frames':115, 'non_seed_frames':114, 'manual_joint_records':1368,
    'visible_xy':1195, 'not_observable':171, 'uncertain':2, 'torso_proxy_available':105,
    'torso_proxy_missing':9, 'major_frames':18, 'other_non_seed_frames':96,
    'visible_reference_in_crop':1151, 'visible_reference_outside_crop':44,
    'major_visible_xy':190, 'major_reference_in_crop':189, 'major_reference_outside_crop':1,
    'other_visible_xy':1005, 'other_reference_in_crop':962, 'other_reference_outside_crop':43}
EVALUATOR_ROLES = {'original_raw', 'capture', 'clean_config', 'manual_xy',
                   'canonical_review', 'full_frame_image'}


def protected_inventory(root, proposal):
    ref = proposal['protected_source_inventory']
    if sha(root/ref['path']) != ref['sha256']:
        raise ValueError('Protected inventory manifest changed')
    hashes = read(root/ref['path'])[ref['key']]
    if len(hashes) != ref['physical_files']:
        raise ValueError('Protected inventory denominator changed')
    verify_sources(root, {p:{'path':p, 'sha256':h} for p,h in hashes.items()})
    return hashes


def stats(values):
    values = sorted(values)
    if not values:
        return {'count':0, 'mean_px':None, 'median_px':None, 'p90_px':None}
    def percentile(q):
        at = (len(values)-1)*q
        lo,hi = math.floor(at),math.ceil(at)
        return values[lo] + (values[hi]-values[lo])*(at-lo)
    return {'count':len(values), 'mean_px':sum(values)/len(values),
            'median_px':percentile(.5), 'p90_px':percentile(.9)}


def inside(bounds, x, y):
    return bounds is not None and bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]


def point_row(index, joint, bounds, arms, crop_points, config, major):
    """Retain every manual status, unavailable prediction and unsupported estimate."""
    visible = joint['status'] == 'visible'
    reference_inside = inside(bounds, joint['x_px'], joint['y_px']) if visible else None
    row = {'frame_index':index, 'joint':joint['name'], 'manual_status':joint['status'],
           'old_prediction_major_failure':major, 'reference_in_crop':reference_inside, 'arms':{}}
    for name,points in arms.items():
        p = points.get(joint['name'])
        finite = p is not None and all(math.isfinite(p[k]) for k in ('x','y','visibility','presence'))
        passes = gate(p, config)
        error = math.hypot(p['x']*TARGET['width']-joint['x_px'],
                           p['y']*TARGET['height']-joint['y_px']) if visible and finite else None
        support = None
        if name == 'crop':
            cp = crop_points.get(joint['name'])
            support = (bounds is not None and cp is not None and
                       0 <= cp['x'] < 1 and 0 <= cp['y'] < 1)
        row['arms'][name] = {'selected_point_present':p is not None, 'finite':finite,
            'gate_pass':passes, 'prediction_in_crop':support, 'xy_error_px':error,
            'gated_error_px':error if passes else None}
    row['paired'] = {}
    for baseline in ('image','video'):
        old,new = row['arms'][baseline],row['arms']['crop']
        eligible = (visible and reference_inside and new['prediction_in_crop'] and
                    new['gate_pass'] and old['gate_pass'])
        delta = new['xy_error_px']-old['xy_error_px'] if eligible else None
        row['paired'][baseline] = {'eligible':bool(eligible), 'crop_minus_baseline_error_px':delta}
    return row


def summarize_points(rows):
    """Conditional arm means are separate; paired means always use identical points."""
    visible = [r for r in rows if r['manual_status']=='visible']
    arms = {}
    for arm in ('crop','image','video'):
        records = [r['arms'][arm] for r in visible]
        arms[arm] = {'visible_denominator':len(visible),
            'selected_points':sum(r['selected_point_present'] for r in records),
            'gate_pass':sum(r['gate_pass'] for r in records),
            'missing':sum(not r['selected_point_present'] for r in records),
            'below_gate':sum(r['finite'] and not r['gate_pass'] for r in records),
            'gated_error_conditional':stats([r['gated_error_px'] for r in records if r['gated_error_px'] is not None])}
        if arm=='crop':
            arms[arm].update({'gated_prediction_outside_crop':sum(r['gate_pass'] and not r['prediction_in_crop'] for r in records),
                'supported_gated_points':sum(r['arms']['crop']['gate_pass'] and r['arms']['crop']['prediction_in_crop']
                    and r['reference_in_crop'] for r in visible)})
    pairs = {}
    for baseline in ('image','video'):
        common = [r for r in visible if r['paired'][baseline]['eligible']]
        deltas = [r['paired'][baseline]['crop_minus_baseline_error_px'] for r in common]
        pairs[baseline] = {'common_points':len(common),
            'baseline_error':stats([r['arms'][baseline]['xy_error_px'] for r in common]),
            'crop_error':stats([r['arms']['crop']['xy_error_px'] for r in common]),
            'crop_minus_baseline_error':stats(deltas),
            'improved':sum(d<0 for d in deltas), 'worsened':sum(d>0 for d in deltas),
            'exactly_tied':sum(d==0 for d in deltas)}
    return {'manual_records':len(rows), 'status_counts':dict(Counter(r['manual_status'] for r in rows)),
            'visible_reference_in_crop':sum(r['reference_in_crop'] is True for r in visible),
            'visible_reference_outside_crop':sum(r['reference_in_crop'] is False for r in visible),
            'per_arm_conditional_not_directly_comparable':arms, 'supported_paired':pairs}


def replay_frame(frame, tracker_frame, pixels, native_ms, technical_ms, selector):
    """Recompute source/crop pixels, affine mapping and selection without inference."""
    if pixels.shape != (TARGET['height'], TARGET['width'], 3) or pixels.dtype != np.uint8:
        raise ValueError('Independent decode dimensions/type mismatch')
    digest = hashlib.sha256(pixels.tobytes()).hexdigest()
    if (digest != frame['decoded_bgr_sha256'] or digest != tracker_frame['decoded_bgr_sha256'] or
        any(not math.isclose(native_ms,t,rel_tol=0,abs_tol=1e-6) for t in
            (technical_ms, frame['native_timestamp_ms'],tracker_frame['native_timestamp_ms'])) or
        frame['timestamp_ms'] != round(native_ms)):
        raise ValueError('Independent source pixel/PTS mismatch')
    rect = tracker_frame['usable_rectangle_xywh']
    bounds = crop_bounds(rect, TARGET['width'], TARGET['height'])
    if frame['tracker_rectangle_xywh'] != rect or frame['crop_bounds_xyxy'] != bounds:
        raise ValueError('Derived crop differs from sealed tracking geometry')
    candidates = frame['crop_candidates']
    # Validate all 33 landmarks, not just the selected subset.
    serialized = serialize_candidates([[SimpleNamespace(**p) for p in pose] for pose in candidates])
    if serialized != candidates:
        raise ValueError('Candidate serialization mismatch')
    if bounds is None:
        if (candidates or frame['inference_status']!='roi_unavailable' or
            any(frame[k] is not None for k in ('crop_bgr_sha256','crop_rgb_sha256','crop_shape'))):
            raise ValueError('Missing ROI falsely contains measured pixels/pose')
        mapped = []
    else:
        x0,y0,x1,y1 = bounds
        bgr = np.ascontiguousarray(pixels[y0:y1,x0:x1].copy())
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if (frame['crop_bgr_sha256'] != hashlib.sha256(bgr.tobytes()).hexdigest() or
            frame['crop_rgb_sha256'] != hashlib.sha256(rgb.tobytes()).hexdigest() or
            frame['crop_shape'] != list(bgr.shape) or frame['inference_status']!='measured'):
            raise ValueError('Independent crop pixel/color receipt mismatch')
        mapped = map_candidates(candidates,bounds,TARGET['width'],TARGET['height'])
    if mapped != frame['full_image_candidates']:
        raise ValueError('Mapped XY/Z/confidence differs from sealed crop candidates')
    selection = asdict(selector.select([[SimpleNamespace(**p) for p in pose] for pose in mapped]))
    if selection != frame['selection'] or frame['warning_prediction'] is not None or frame['subject_alignment_verified'] is not False:
        raise ValueError('Original selector replay or experimental semantics mismatch')


def figure(pixels, index, bounds, references, arms):
    panels = []
    edges = [('LEFT_SHOULDER','RIGHT_SHOULDER'),('LEFT_SHOULDER','LEFT_HIP'),('RIGHT_SHOULDER','RIGHT_HIP'),
             ('LEFT_HIP','RIGHT_HIP')]
    for side in ('LEFT','RIGHT'):
        edges.extend((side+'_'+a,side+'_'+b) for a,b in
                     [('SHOULDER','ELBOW'),('ELBOW','WRIST'),('HIP','KNEE'),('KNEE','ANKLE')])
    for name in ('source','image','crop'):
        panel = pixels.copy()
        if bounds is not None:
            x0,y0,x1,y1=bounds
            cv2.rectangle(panel,(x0,y0),(x1-1,y1-1),(0,220,255),1)
        cv2.putText(panel,f'f{index} {name} | green=visible manual',(5,19),cv2.FONT_HERSHEY_SIMPLEX,.4,(255,255,255),1)
        points = arms.get(name,{})
        def xy(p): return (round(p['x']*TARGET['width']),round(p['y']*TARGET['height']))
        for a,b in edges:
            if a in points and b in points:
                cv2.line(panel,xy(points[a]),xy(points[b]),(230,30,210),1)
        for joint in references:
            if joint['status']=='visible':
                cv2.circle(panel,(round(joint['x_px']),round(joint['y_px'])),4,(40,255,40),1)
        for name_,p in points.items():
            if name_ in JOINT_NAMES:
                cv2.circle(panel,xy(p),2,(230,30,210),-1)
        panels.append(panel)
    return np.concatenate(panels,axis=1)


def evaluate(root, plan_path, measurements, output):
    root,output = Path(root).resolve(),Path(output).resolve()
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('New evaluation output inside analysis_results required')
    plan_path,measurements = Path(plan_path).resolve(),Path(measurements).resolve()
    plan,measured = read(plan_path),read(measurements)
    measurement_sha,plan_sha = sha(measurements),sha(plan_path)
    verify_execution(root,plan,evaluator=True)
    proposal = read(root/plan['proposal_manifest'])
    if (set(plan['evaluator_sources']) != EVALUATOR_ROLES or
        plan['evaluator_sources'] != proposal['evaluator_only_sources'] or
        plan['evaluator_dependencies'] != proposal['proposed_evaluator_dependencies'] or
        proposal['evaluation_denominators'] != DENOMINATORS or
        sha(root/proposal['proposal_path']) != proposal['proposal_sha256'] or
        sha(root/'tests/test_tracked_roi_pose_evaluation.py') != plan['evaluator_test_sha256']):
        raise ValueError('Frozen evaluator sources/settings/tests changed')
    for refs in (plan['evaluator_sources'],plan['evaluator_dependencies'],proposal['parent_only_sources']):
        verify_sources(root,refs)
    inventory = protected_inventory(root,proposal)
    for key in ('producer_sources','producer_dependencies','runtime','parameters','options','target'):
        if measured[key] != plan[key]:
            raise ValueError('Measurement seal mismatch: '+key)
    if (measured['status']!='sealed_measurements_only' or measured['plan_sha256']!=plan_sha or
        measured['producer_sha256']!=plan['producer_sha256'] or measured['human_annotation_inputs']!=[] or
        measured['warning_policy'] is not None or measured['original_predictions_modified'] is not False or
        [f['frame_index'] for f in measured['frames']] != list(range(TARGET['total_frames']))):
        raise ValueError('Unsealed/incomplete measurement or changed semantics')
    sources = plan['producer_sources']
    data = {k:read(root/v['path']) for k,v in plan['evaluator_sources'].items() if k!='original_raw'}
    manual,canonical,full = (data[k] for k in ('manual_xy','canonical_review','full_frame_image'))
    video = root/sources['video']['path']
    validate_manual_keypoints(manual,source_video_path=video)
    validate_ground_truth(canonical,source_video_path=video)
    if (manual['annotation_status']!='reviewed' or canonical['annotation_status']!='reviewed' or
        manual['image_size']!={'width':510,'height':628} or
        any(d['source_video']['pitch_id']!='pitch_003' for d in (manual,canonical))):
        raise ValueError('Unreviewed or mismatched reference')
    config = data['clean_config']
    gate_config = {k:config[k] for k in ('min_visibility','min_presence')}
    if (gate_config!={'min_visibility':.5,'min_presence':.5} or full['gate']!=gate_config or
        full['video_sha256']!=sources['video']['sha256'] or
        (full['total_frames'],full['width'],full['height'])!=(115,510,628) or
        [f['frame_index'] for f in full['frames']]!=list(range(115))):
        raise ValueError('Saved full-frame IMAGE control cohort/gate mismatch')
    raw = load_video_raw(root/plan['evaluator_sources']['original_raw']['path'],data['capture'],115)
    tracked = read(root/sources['tracked_roi']['path'])
    technical = read(root/sources['video_technical']['path'])
    validate_tracked_roi(tracked,sources,TARGET)
    major = {i for interval in canonical['labels']['major_pose_failure_intervals'] if interval['status']=='confirmed'
             for i in range(interval['start_frame'],interval['end_frame']+1)}
    rows,examples,frame_states,torso_missing = [],[],[],0
    selector,image_selector = PitcherSelector(),PitcherSelector()
    capture = cv2.VideoCapture(str(video))
    output.mkdir(parents=True)
    try:
        for i,(frame,m,control) in enumerate(zip(measured['frames'],manual['frames'],full['frames'],strict=True)):
            ok,pixels = capture.read()
            if not ok: raise ValueError('Independent source decode incomplete')
            ms = capture.get(cv2.CAP_PROP_POS_MSEC)
            replay_frame(frame,tracked['frames'][i],pixels,ms,technical['timestamps_ms'][i],selector)
            if (control['decoded_bgr_sha256']!=frame['decoded_bgr_sha256'] or
                not math.isclose(control['native_timestamp_ms'],ms,abs_tol=1e-6,rel_tol=0) or
                not math.isclose(m['timestamp_ms'],ms,abs_tol=1e-6,rel_tol=0) or m['frame_index']!=i):
                raise ValueError('Manual/IMAGE/source frame mapping mismatch')
            image_candidates = serialize_candidates([[SimpleNamespace(**p) for p in pose] for pose in control['image_candidates']])
            original_image_selection = asdict(image_selector.select([[SimpleNamespace(**p) for p in pose] for pose in image_candidates]))
            if original_image_selection!=control['image_selection']:
                raise ValueError('Saved IMAGE selector replay differs')
            arms = {'crop':selected_points(frame['full_image_candidates'],frame['selection']),
                    'image':selected_points(control['image_candidates'],control['image_selection']), 'video':raw[i]}
            crop_points = selected_points(frame['crop_candidates'],frame['selection'])
            if i!=0:
                rows.extend(point_row(i,j,frame['crop_bounds_xyxy'],arms,crop_points,gate_config,i in major) for j in m['joints'])
                torso_missing += any(j['status']!='visible' for j in m['joints'] if j['name'] in
                                     ('LEFT_SHOULDER','RIGHT_SHOULDER','LEFT_HIP','RIGHT_HIP'))
            frame_states.append({'frame_index':i,'eligible':i!=0,'old_major':i in major,
                'crop':frame['selection']['status'],'image':control['image_selection']['status'],
                'video':data['capture']['selection_frames'][i]['status']})
            if i in EXAMPLE_FRAMES:
                path = output/f'frame_{i:04d}.png'
                if not cv2.imwrite(str(path),figure(pixels,i,frame['crop_bounds_xyxy'],m['joints'],arms)):
                    raise ValueError('Cannot save comparison image')
                examples.append({'frame_index':i,'path':path.relative_to(root).as_posix(),'sha256':sha(path)})
        if capture.read()[0]: raise ValueError('Extra independent decoded frame')
    finally:
        capture.release()
    groups = {'all_non_seed':rows,'old_major18':[r for r in rows if r['old_prediction_major_failure']],
              'other96':[r for r in rows if not r['old_prediction_major_failure']],
              'old_wrong_torso_inside10':[r for r in rows if r['frame_index'] in OLD_INSIDE_FAILURE_FRAMES]}
    summaries = {key:summarize_points(part) for key,part in groups.items()}
    counts = Counter(r['manual_status'] for r in rows)
    actual = {'source_frames':len(frame_states),'non_seed_frames':len(frame_states)-1,'manual_joint_records':len(rows),
        'visible_xy':counts['visible'],'not_observable':counts['not_observable'],'uncertain':counts['uncertain'],
        'torso_proxy_available':114-torso_missing,'torso_proxy_missing':torso_missing,
        'major_frames':len(major-{0}),'other_non_seed_frames':114-len(major-{0})}
    for prefix,group in (('visible',summaries['all_non_seed']),('major',summaries['old_major18']),('other',summaries['other96'])):
        if prefix!='visible': actual[prefix+'_visible_xy']=group['status_counts'].get('visible',0)
        actual[prefix+'_reference_in_crop']=group['visible_reference_in_crop']
        actual[prefix+'_reference_outside_crop']=group['visible_reference_outside_crop']
    if actual!=DENOMINATORS: raise ValueError('Frozen denominator differs: '+repr(actual))
    if measured['inference_calls']!=sum(f['inference_status']=='measured' for f in measured['frames']):
        raise ValueError('Inference count does not match receipts')
    verify_execution(root,plan,evaluator=True)
    for refs in (plan['evaluator_sources'],plan['evaluator_dependencies'],proposal['parent_only_sources']): verify_sources(root,refs)
    if protected_inventory(root,proposal)!=inventory or sha(measurements)!=measurement_sha or sha(plan_path)!=plan_sha:
        raise ValueError('Source/measurement/plan changed during evaluation')
    report = {'status':'complete_offline_xy_evaluation','measurement_sha256':measurement_sha,
        'execution_sha256':plan_sha,'evaluator_sha256':sha(__file__),'denominators':actual,
        'groups':summaries,'per_joint':{name:summarize_points([r for r in rows if r['joint']==name]) for name in JOINT_NAMES},
        'frame_selection_counts':{arm:dict(Counter(f[arm] for f in frame_states[1:])) for arm in ('crop','image','video')},
        'frames':frame_states,'examples':examples,'independent_source_frames_verified':115,
        'independent_crop_pixel_and_mapping_frames_verified':115,'independent_selector_replay_frames':115,
        'protected_physical_files_verified':len(inventory),'warning_policy':None,'new_warning_counts':None,
        'identity_accuracy':None,'event_accuracy':None,'passed':None,'phase2_automatic_reliability':'NOT PASSED',
        'scope':'known pitch_003, human-initialized crop sensitivity; old major labels are grouping only',
        'hidden_xy_used_as_truth':False,'original_predictions_modified':False}
    write(output/'point_comparisons.json',{'seed_frame_excluded':0,'rows':rows})
    write(output/'roi_pose_evaluation.json',report)
    return report


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path)
    parser.add_argument('measurements',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = evaluate(args.root,args.plan,args.measurements,args.output)
    print(json.dumps({'denominators':result['denominators'],'selection_counts':result['frame_selection_counts'],
                      'primary':result['groups']['all_non_seed']['supported_paired']['image']}))
