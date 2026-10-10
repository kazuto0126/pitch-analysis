"""Offline geometry and source audit for one frozen, human-initialized CSRT arm."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import math
from pathlib import Path

import cv2

from measure_seeded_subject import read, sha, write, verify_execution, verify_sources
from evaluate_person_support import contains, join_memberships, protected_inventory, torso_context, verify_reviews
from pitch_analysis.pose_capture import LANDMARK_NAMES


TORSO = ('LEFT_SHOULDER', 'RIGHT_SHOULDER', 'LEFT_HIP', 'RIGHT_HIP')
REVIEW_FRAMES = [38,70,78,86,87,95,104,105,112,114]
DENOMINATORS = {'source_frames':115, 'non_seed_frames':114, 'manual_joint_records':1368,
    'visible_xy':1195, 'not_observable':171, 'uncertain':2, 'torso_proxy_available':105,
    'torso_proxy_missing':9, 'major_frames':18, 'other_non_seed_frames':96}


def rectangle_geometry(rectangle, width, height):
    if not isinstance(rectangle, (list, tuple)) or len(rectangle) != 4:
        raise ValueError('Malformed receipt rectangle')
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in rectangle):
        raise ValueError('Nonfinite or nonnumeric receipt rectangle')
    x,y,w,h = rectangle
    if w <= 0 or h <= 0:
        raise ValueError('Nonpositive receipt rectangle')
    intersects = x < width and y < height and x+w > 0 and y+h > 0
    truncated = not (0 <= x and 0 <= y and x+w <= width and y+h <= height)
    return intersects, truncated


def validate_timeline(measured, seed, target):
    """Keep terminal missing frames in the denominator; never infer ownership."""
    frames=measured['frames']
    if [f['frame_index'] for f in frames] != list(range(target['total_frames'])):
        raise ValueError('Incomplete or reordered receipt timeline')
    if measured['initialization_calls'] != 1:
        raise ValueError('Exactly one initialization call required')
    terminal = None
    updates = 0
    init_failed = frames[0]['tracking_status'] == 'init_failed'
    for i,f in enumerate(frames):
        if f['subject_assignment'] is not None or f['warning_prediction'] is not None:
            raise ValueError('Unexpected automatic ownership or warning')
        if f['raw_tracking_score'] is not None and not math.isfinite(f['raw_tracking_score']):
            raise ValueError('Nonfinite score in JSON receipt')
        if i == 0:
            if f['native_update_success'] is not None or f['native_rectangle_xywh'] is not None:
                raise ValueError('Initialization must not impersonate update')
            expected = None if init_failed else seed['rectangle_xywh']
            if f['usable_rectangle_xywh'] != expected or f['tracking_status'] not in ('initialized','init_failed'):
                raise ValueError('Initialization receipt differs from declared seed')
            if f['raw_tracking_score'] is not None:
                raise ValueError('No update score exists at initialization')
            if init_failed:
                if not str(f['failure_reason']).startswith('native_initialization_exception: '):
                    raise ValueError('Initialization failure lacks native exception')
                terminal = 0
            elif f['failure_reason'] is not None:
                raise ValueError('Successful initialization has failure reason')
        elif terminal is not None:
            status = ('not_attempted_after_initialization_failure' if init_failed else
                      'not_attempted_after_terminal_break')
            if (f['tracking_status'] != status or f['native_update_success'] is not None or
                f['usable_rectangle_xywh'] is not None or f['native_rectangle_xywh'] is not None or
                f['raw_tracking_score'] is not None):
                raise ValueError('Tracker resumed or reused a box after terminal break')
        else:
            updates += 1
            if f['tracking_status'] == 'terminal_break':
                if f['usable_rectangle_xywh'] is not None or not f['failure_reason']:
                    raise ValueError('Terminal frame needs explicit missing output/reason')
                reason=f['failure_reason']
                native=f['native_rectangle_xywh']
                success=f['native_update_success']
                if reason=='native_update_false':
                    if success is not False:
                        raise ValueError('False-return terminal contradicts native boolean')
                elif reason=='invalid_native_rectangle':
                    if success is not True or native is not None:
                        raise ValueError('Invalid-geometry terminal contradicts native receipt')
                    try:
                        rectangle_geometry(f['native_rectangle_diagnostic'],target['width'],target['height'])
                    except ValueError:
                        pass
                    else:
                        raise ValueError('Valid rectangle falsely marked invalid')
                elif reason=='native_rectangle_fully_outside_image':
                    if success is not True or rectangle_geometry(native,target['width'],target['height'])[0]:
                        raise ValueError('Outside terminal contradicts native geometry')
                elif reason.startswith('native_update_exception: '):
                    if success is not None or native is not None:
                        raise ValueError('Exception terminal carries a completed native update')
                else:
                    raise ValueError('Unknown terminal reason; score error is not a tracking break')
                terminal = i
            elif f['tracking_status'] == 'native_success':
                if (f['native_update_success'] is not True or f['usable_rectangle_xywh'] != f['native_rectangle_xywh'] or
                    f['usable_rectangle_xywh'] is None or f['failure_reason'] is not None):
                    raise ValueError('Successful receipt must preserve native rectangle')
            else:
                raise ValueError('Unrecognized update status')
        if f['usable_rectangle_xywh'] is not None:
            intersects,truncated = rectangle_geometry(f['usable_rectangle_xywh'],target['width'],target['height'])
            if not intersects or f['truncated'] != truncated:
                raise ValueError('Unusable geometry or altered truncation state')
    if measured['native_update_calls'] != updates:
        raise ValueError('Native update call count differs from receipt')
    recorded=measured['terminal_break']
    if (recorded is None) != (terminal is None) or (recorded is not None and recorded['frame_index'] != terminal):
        raise ValueError('Terminal break summary differs from receipt')
    if recorded is not None and recorded['reason']!=frames[terminal]['failure_reason']:
        raise ValueError('Terminal break reason differs from receipt')


def frame_geometry(manual_frame, rectangle):
    counts=Counter(j['status'] for j in manual_frame['joints'])
    visible=[j for j in manual_frame['joints'] if j['status']=='visible']
    inside=[] if rectangle is None else [j['name'] for j in visible if contains(rectangle,(j['x_px'],j['y_px']))]
    outside=[] if rectangle is None else [j['name'] for j in visible if j['name'] not in inside]
    unavailable=[j['name'] for j in visible] if rectangle is None else []
    torso={j['name']:j for j in manual_frame['joints'] if j['name'] in TORSO}
    proxy=all(torso[name]['status']=='visible' for name in TORSO)
    proxy_status=('reference_missing' if not proxy else 'tracker_unavailable' if rectangle is None else
                  'inside' if all(name in inside for name in TORSO) else 'outside')
    return {'manual_joint_status_counts':dict(counts),'visible_inside':inside,'visible_outside':outside,
        'visible_tracker_unavailable':unavailable,'torso_proxy_status':proxy_status}


def summarize(rows):
    eligible=[f for f in rows if f['frame_index'] != 0]
    status_counts=Counter(f['tracking_status'] for f in eligible)
    visibility=Counter()
    joints={}
    for f in eligible:
        visibility.update(f['geometry']['manual_joint_status_counts'])
        for status,key in (('inside','visible_inside'),('outside','visible_outside'),('tracker_unavailable','visible_tracker_unavailable')):
            for name in f['geometry'][key]:
                joints.setdefault(name,Counter())[status]+=1
    torso=Counter(f['geometry']['torso_proxy_status'] for f in eligible)
    major=[f for f in eligible if f['canonical_major_pose_failure']]
    actual={'source_frames':len(rows),'non_seed_frames':len(eligible),'manual_joint_records':sum(visibility.values()),
        'visible_xy':visibility['visible'],'not_observable':visibility['not_observable'],'uncertain':visibility['uncertain'],
        'torso_proxy_available':len(eligible)-torso['reference_missing'],'torso_proxy_missing':torso['reference_missing'],
        'major_frames':len(major),'other_non_seed_frames':len(eligible)-len(major)}
    if actual != DENOMINATORS:
        raise ValueError('Frozen denominator changed: '+repr(actual))
    parts={key:sum(values[key] for values in joints.values()) for key in ('inside','outside','tracker_unavailable')}
    if sum(parts.values()) != 1195 or sum(torso.values()) != 114:
        raise ValueError('Missing predictions dropped from fixed geometry partitions')
    return {'denominators':actual,'non_seed_tracking_states':dict(status_counts),
        'usable_non_seed_frames':sum(f['usable_rectangle_xywh'] is not None for f in eligible),
        'visible_joint_partition':parts,'per_joint_visible_partition':{name:dict(values) for name,values in joints.items()},
        'torso_proxy_partition':dict(torso),
        'major_usable_frames':sum(f['usable_rectangle_xywh'] is not None for f in major),
        'major_manual_torso_inside_frames':sum(f['geometry']['torso_proxy_status']=='inside' for f in major),
        'major_original_raw_torso_inside_frames':sum(f['raw_torso_all_four_inside'] is True for f in major),
        'identity_accuracy':None,'box_iou':None,'new_warning_counts':None,'warning_policy':None,
        'original_fn_frames_unchanged':18,'phase2_automatic_reliability':'NOT PASSED'}


def make_questions(frames, sampling):
    if sampling['frames'] != REVIEW_FRAMES:
        raise ValueError('Changed fixed review frames/order')
    by_frame={f['frame_index']:f for f in frames}
    questions=[]
    slots=[]
    for index in sampling['frames']:
        frame=by_frame[index]
        rectangle=frame['usable_rectangle_xywh']
        slots.append({'frame_index':index,'state':'no_candidate' if rectangle is None else 'unreviewed'})
        if rectangle is not None:
            questions.append({'query_id':f'pitch_003_csrt_f{index:04d}','frame_index':index,
                'native_timestamp_ms':frame['native_timestamp_ms'],'decoded_bgr_sha256':frame['decoded_bgr_sha256'],
                'rectangle_xywh':rectangle,'truncated':frame['truncated'],'conclusion':None,
                'extent_observation':None,'raw_user_reply':None,'reviewer':None,'reviewed_at_utc':None,
                'confidence':None,'note':None})
    if len(slots)!=10 or len(questions)>10:
        raise ValueError('Changed fixed review budget')
    return {'status':'insufficient_evidence_pending_review','fixed_sampling_slots':slots,
        'questions':questions,'questions_count':len(questions),'slots_count':10,
        'allowed_conclusions':['pitcher','other','mixed','uncertain'],
        'instruction':'Judge visible ownership of this NEW outlined rectangle; do not transfer old HOG answers or infer hidden joints.'}


def evaluate(root, plan_path, measurements, output):
    root,output=root.resolve(),output.resolve()
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('New output inside analysis_results required')
    plan,measured=read(plan_path),read(measurements)
    verify_execution(root,plan,evaluator=True)
    verify_sources(root,plan['evaluator_sources'])
    verify_sources(root,plan['evaluator_context_sources'])
    verify_sources(root,plan['evaluator_dependencies'])
    if sha(root/'tests/test_seeded_subject_evaluation.py')!=plan['evaluator_test_sha256']:
        raise ValueError('Evaluator tests changed')
    proposal=read(root/plan['proposal_manifest'])
    if sha(root/proposal['proposal_path'])!=proposal['proposal_sha256']:
        raise ValueError('Proposal text changed')
    if (plan['evaluator_sources']!=proposal['evaluator_only_sources'] or
        plan['evaluator_context_sources']!=proposal['evaluator_context_sources'] or
        plan['review_sampling']!=proposal['review_sampling'] or
        proposal['evaluation_denominators']!=DENOMINATORS):
        raise ValueError('Evaluator settings differ from proposal')
    inventory=protected_inventory(root,proposal)
    measurement_sha=sha(measurements)
    seed=read(root/plan['producer_sources']['initialization']['path'])
    for key,expected in {'status':'sealed_measurements_only','plan_sha256':sha(plan_path),
        'producer_sha256':plan['producer_sha256'],'producer_sources':plan['producer_sources'],
        'runtime':plan['runtime'],'parameters':plan['parameters'],'target':plan['target'],
        'human_annotation_inputs':[plan['producer_sources']['initialization']],'pose_inputs':[],
        'warning_policy':None,'subject_assignment':None,'calibrated_confidence':None}.items():
        if measured[key]!=expected:
            raise ValueError('Measurement seal differs: '+key)
    validate_timeline(measured,seed,plan['target'])
    data={name:read(root/plan['evaluator_sources'][name]['path']) for name in
        ('capture','manual_xy','canonical_review','membership_original','membership_supplement')}
    manual,canonical=data['manual_xy'],data['canonical_review']
    verify_reviews(root,plan['producer_sources'],measured,manual,canonical,data['membership_original'],data['membership_supplement'])
    trace=data['capture']['selection_frames']
    if [f['frame_index'] for f in trace]!=list(range(115)):
        raise ValueError('Capture frame mapping changed')
    raw=[{} for _ in range(115)]
    with (root/plan['evaluator_sources']['original_raw']['path']).open(encoding='utf-8-sig',newline='') as source:
        for r in csv.DictReader(source):
            i,name=int(r['frame']),r['landmark']
            if not 0<=i<115 or name not in LANDMARK_NAMES or name in raw[i] or int(r['timestamp_ms'])!=trace[i]['timestamp_ms']:
                raise ValueError('Original raw frame mapping changed')
            raw[i][name]=(float(r['x'])*510,float(r['y'])*628)
    if any(set(r)!=set(LANDMARK_NAMES) for r in raw):
        raise ValueError('Incomplete original raw')
    hog=read(root/plan['evaluator_context_sources']['hog_measurements']['path'])
    if hog['producer_sources']['video']!=plan['producer_sources']['video'] or len(hog['frames'])!=115:
        raise ValueError('HOG source context mismatch')
    output.mkdir(parents=True)
    rows=[]
    capture=cv2.VideoCapture(str(root/plan['producer_sources']['video']['path']))
    try:
        for i,(receipt,m) in enumerate(zip(measured['frames'],manual['frames'],strict=True)):
            ok,pixels=capture.read()
            if not ok or pixels.shape!=(628,510,3):
                raise ValueError('Independent decode missing or resized')
            pixel_sha=hashlib.sha256(pixels.tobytes()).hexdigest()
            timestamp=capture.get(cv2.CAP_PROP_POS_MSEC)
            if (pixel_sha!=receipt['decoded_bgr_sha256'] or pixel_sha!=hog['frames'][i]['decoded_bgr_sha256'] or
                not math.isclose(timestamp,receipt['native_timestamp_ms'],rel_tol=0,abs_tol=1e-6) or
                not math.isclose(timestamp,m['timestamp_ms'],rel_tol=0,abs_tol=1e-6) or
                trace[i]['timestamp_ms']!=round(timestamp) or m['frame_index']!=i):
                raise ValueError('Independent native pixel/PTS/manual mapping mismatch')
            rect=receipt['usable_rectangle_xywh']
            major=any(r['status']=='confirmed' and r['start_frame']<=i<=r['end_frame']
                for r in canonical['labels']['major_pose_failure_intervals'])
            raw_inside=None if rect is None else all(contains(rect,raw[i][name]) for name in TORSO)
            rows.append({**receipt,'eligible_for_geometry':i!=0,'geometry':frame_geometry(m,rect),
                'canonical_major_pose_failure':major,'raw_torso_all_four_inside':raw_inside,
                'hog_torso_context':torso_context(m,hog['frames'][i]['candidates'])})
        if capture.read()[0]:
            raise ValueError('Extra independent decoded frame')
    finally:
        capture.release()
    summary=summarize(rows)
    summary.update({'independent_source_frames_verified':115,'independent_tracker_replay':False,
        'initialization_calls':measured['initialization_calls'],'native_update_calls':measured['native_update_calls'],
        'terminal_break':measured['terminal_break'],
        'hog_non_seed_torso_inside_any_frame_count':sum(any(c['all_four_inside'] is True for c in f['hog_torso_context']['candidates']) for f in rows[1:])})
    memberships=join_memberships(data['membership_original'],data['membership_supplement'])
    for q in memberships:
        rect=rows[q['frame_index']]['usable_rectangle_xywh']
        q['inside_tracker_rectangle']=None if rect is None else contains(rect,q['image_xy_px'])
    questions=make_questions(rows,plan['review_sampling'])
    capture=cv2.VideoCapture(str(root/plan['producer_sources']['video']['path']))
    try:
        for i in range(115):
            ok,pixels=capture.read()
            if not ok:
                raise ValueError('Review image decode incomplete')
            if hashlib.sha256(pixels.tobytes()).hexdigest()!=rows[i]['decoded_bgr_sha256']:
                raise ValueError('Review image source changed')
            for q in (q for q in questions['questions'] if q['frame_index']==i):
                image=pixels.copy()
                x,y,w,h=q['rectangle_xywh']
                # Rounding only for a display outline; measured native geometry stays untouched.
                cv2.rectangle(image,(round(x),round(y)),(round(x+w)-1,round(y+h)-1),(0,220,255),2)
                cv2.putText(image,f"frame {i} / CSRT ownership UNREVIEWED",(8,20),cv2.FONT_HERSHEY_SIMPLEX,.43,(0,220,255),1)
                image_path=output/(q['query_id']+'.png')
                if not cv2.imwrite(str(image_path),image):
                    raise ValueError('Cannot save fresh ownership image')
                q.update({'image_path':image_path.relative_to(root).as_posix(),'image_sha256':sha(image_path)})
    finally:
        capture.release()
    summary.update({'fixed_review_slots':10,'ownership_questions':len(questions['questions']),
        'review_slots_without_candidate':sum(s['state']=='no_candidate' for s in questions['fixed_sampling_slots']),
        'ownership_answers':0,'conclusion':'insufficient_evidence_pending_review' if questions['questions'] else 'insufficient_evidence_no_fixed_slot_candidates'})
    verify_execution(root,plan,evaluator=True)
    verify_sources(root,plan['evaluator_sources']); verify_sources(root,plan['evaluator_context_sources'])
    protected_inventory(root,proposal)
    if sha(measurements)!=measurement_sha:
        raise ValueError('Measurement seal changed during evaluation')
    write(output/'seeded_subject_evaluation.json',{'summary':summary,'plan_sha256':sha(plan_path),
        'measurements_sha256':measurement_sha,'evaluator_sha256':sha(__file__),'frames':rows,
        'membership_context':memberships,'evaluator_sources':plan['evaluator_sources'],
        'limits':['Known development case with human-confirmed initialization; frame0 excluded',
            'Point containment is geometry, not identity or anatomical correctness',
            'Raw tracker score is not calibrated confidence; missing predictions remain in fixed denominators',
            'New rectangle questions remain blank; old HOG answers are not transferred',
            'No production core, thresholds, formal videos, raw predictions or GT were modified']})
    write(output/'ownership_questions.json',questions)
    write(output/'source_integrity_check.json',{'protected_physical_files':len(inventory),'unchanged':True,
        'protected_source_hashes':inventory,'sealed_measurements_sha256':measurement_sha,
        'producer_sources':plan['producer_sources'],'evaluator_sources':plan['evaluator_sources']})
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan_path',type=Path);parser.add_argument('measurements',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    print(json.dumps(evaluate(**vars(parser.parse_args())),indent=2))
