"""Audit sealed angle availability and point-error changes; never select a remedy."""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

import assess_saved_roi_angles as parent
from check_movenet_compatibility import bound, sha, write

BASELINES = parent.STREAMS[1:]
TRANSITIONS = ('both_available', 'baseline_only', 'crop_only', 'neither_available')
CHANGES = ('improved', 'worsened', 'numerically_tied')
PATTERNS = ('all_three_smaller', 'all_three_larger', 'mixed_or_tied')
POLICY = {
    'scope': 'retrospective_saved_angle_support_transitions_and_visible_point_errors',
    'features': list(parent.original.FEATURES), 'baselines': list(BASELINES),
    'support': 'copy_previous_numerical_support_no_new_filter',
    'reference_availability': 'separate_from_all_four_support_transitions',
    'seed': 'save_frame_zero_exclude_from_main_summary',
    'reasons': 'all_original_nonexclusive_reasons_no_priority_partition',
    'angle_error_change': 'crop_absolute_error_minus_baseline_absolute_error_on_same_reference_frame',
    'numerical_degree_tie_tolerance_not_accuracy_gate': parent.original.TIE_TOLERANCE,
    'point_errors': 'visible_finite_manual_xy_only_source_pixels',
    'processed_point_source': 'original_reviewed_view_processed_landmark_never_raw_substitution',
    'pixel_error_pattern': 'exact_sign_descriptive_only_no_accuracy_gate',
    'crop_geometry': 'concurrent_context_not_proven_cause',
    'point_selection': 'all_three_fixed_feature_members_no_oracle_or_fallback',
    'pose_inference_calls': 0, 'tracker_inference_calls': 0,
    'production_adoption': False, 'coordinate_correction': False, 'new_binary_warning': False,
}
CODE_PATHS = {'auditor': 'scripts/audit_saved_roi_transitions.py',
    'tests': 'tests/test_saved_roi_transitions.py', 'parent_assessor': 'scripts/assess_saved_roi_angles.py',
    **{k:v for k,v in parent.CODE_PATHS.items() if k not in ('assessor','tests')}}
INPUTS = ('parent_execution', 'parent_assessment', 'prior_roi_loss_result')


def _finite(value):
    return type(value) in (int,float) and math.isfinite(value)


def _transition(before, after):
    return ('both_available' if after else 'baseline_only') if before else ('crop_only' if after else 'neither_available')


def _stream_points(stream, name, roles, names, frame, target):
    if name == 'video_processed':
        result = []
        for role in roles:
            p = frame['focus_joints'][role]['processed_landmark']
            point = [p['x']*target['width'],p['y']*target['height']] if p['usable'] and parent.original.finite_point([p['x'],p['y']]) else None
            result.append(point)
    else:
        points = stream['points']
        if len(points) != 3 or [p['landmark'] for p in points] != names:
            raise ValueError('Saved three-point stream mapping differs')
        result = [p['xy_px'] for p in points]
    if any(p is not None and not parent.original.finite_point(p) for p in result):
        raise ValueError('Nonfinite saved point coordinates')
    value = stream['numerical_supported_angle_deg']
    if (type(stream['numerical_support']) is not bool or stream['numerical_support'] != (value is not None) or
            value is not None and (not _finite(value) or not 0 <= value <= 180) or
            not isinstance(stream['unavailable_reasons'],list) or any(not isinstance(r,str) for r in stream['unavailable_reasons'])):
        raise ValueError('Invalid original angle availability or reasons')
    if value is not None and not parent.original.original_features.same_number(parent.original.angle(result),value):
        raise ValueError('Supported saved angle differs from its original point geometry')
    return deepcopy(result)


def audit_rows(saved_rows, manual, view, target):
    """Return every feature/baseline/frame, retaining unobservable reference rows."""
    total = target['total_frames']
    if (any(type(target[k]) is not int or target[k] <= 0 for k in ('total_frames','width','height')) or
            manual['source_video']['pitch_id'] != target['pitch_id'] or manual['source_video']['total_frames'] != total or
            manual['source_video']['sha256'] != view['source_artifacts']['original_video']['sha256'] or
            manual['image_size'] != {k:target[k] for k in ('width','height')} or view['pitch_id'] != target['pitch_id'] or
            set(saved_rows) != set(parent.original.FEATURES) or
            any([f['frame_index'] for f in frames] != list(range(total)) for frames in
                [manual['frames'],view['frames'],*saved_rows.values()])):
        raise ValueError('Manual, reviewed source or complete angle frame denominator differs')
    result = []
    for feature,expected_roles in parent.original.FEATURES.items():
        for baseline in BASELINES:
            for i,(saved,human,reviewed) in enumerate(zip(saved_rows[feature],manual['frames'],view['frames'],strict=True)):
                roles, names = saved['required_roles'],saved['required_landmarks']
                if (roles != list(expected_roles) or len(names) != 3 or
                        names != [reviewed['focus_joints'][r]['landmark'] for r in roles] or
                        saved['effectiveness_eligible'] is not (i != 0) or set(saved['streams']) != set(parent.STREAMS) or
                        saved['original_model_states'] != {r:reviewed['focus_joints'][r]['model_state'] for r in roles} or
                        saved['existing_major_hold'] != parent.original.parent.review.confirmed(reviewed['human_review']['major_pose_failure']) or
                        any(not _finite(t) for t in (saved['timestamp_ms'],human['timestamp_ms'],reviewed['timestamp_ms'])) or
                        abs(saved['timestamp_ms']-human['timestamp_ms']) > 1 or abs(saved['timestamp_ms']-reviewed['timestamp_ms']) > 1):
                    raise ValueError('Saved angle role, seed, original context or timestamp differs')
                joints = {j['name']:j for j in human['joints']}
                if len(joints) != len(human['joints']) or any(n not in joints for n in names):
                    raise ValueError('Missing or duplicate manual joint names')
                reference = parent.original.manual_reference(joints,names)
                if reference != saved['manual_reference']: raise ValueError('Saved manual reference differs')
                streams = {a:saved['streams'][a] for a in (baseline,'crop')}
                xy = {a:_stream_points(s,a,roles,names,reviewed,target) for a,s in streams.items()}
                reference_value = reference['value_deg']; reference_available = reference_value is not None
                errors = {a:s['numerical_supported_angle_deg']-reference_value
                    if s['numerical_support'] and reference_available else None for a,s in streams.items()}
                if any(not parent.original.original_features.same_number(errors[a],s['signed_error_deg']) for a,s in streams.items()):
                    raise ValueError('Saved angle error differs from unchanged manual reference')
                delta = abs(errors['crop'])-abs(errors[baseline]) if all(e is not None for e in errors.values()) else None
                change = None if delta is None else ('improved' if delta < -parent.original.TIE_TOLERANCE else
                    'worsened' if delta > parent.original.TIE_TOLERANCE else 'numerically_tied')
                points = []
                for j,(role,name) in enumerate(zip(roles,names,strict=True)):
                    joint = joints[name]
                    visible = joint['status'] == 'visible' and parent.original.finite_point([joint.get('x_px'),joint.get('y_px')])
                    manual_xy = [joint['x_px'],joint['y_px']] if visible else None
                    distance = {a:math.dist(manual_xy,xy[a][j]) if visible and xy[a][j] is not None else None for a in streams}
                    point_delta = distance['crop']-distance[baseline] if all(v is not None for v in distance.values()) else None
                    points.append({'role':role,'landmark':name,'manual_status':joint['status'],'manual_xy_px':manual_xy,
                        'baseline_xy_px':xy[baseline][j],'crop_xy_px':xy['crop'][j],
                        'baseline_error_px':distance[baseline],'crop_error_px':distance['crop'],
                        'crop_minus_baseline_error_px':point_delta,
                        'baseline_prediction_in_crop':parent.roi_audit.inside(saved['crop_bounds_xyxy'],*xy[baseline][j]) if xy[baseline][j] is not None else None,
                        'crop_prediction_in_crop':parent.roi_audit.inside(saved['crop_bounds_xyxy'],*xy['crop'][j]) if xy['crop'][j] is not None else None})
                deltas = [p['crop_minus_baseline_error_px'] for p in points]
                pattern = None
                if change is not None:
                    if any(v is None for v in deltas): raise ValueError('Comparable angle has unavailable visible point error')
                    pattern = 'all_three_smaller' if all(v < 0 for v in deltas) else 'all_three_larger' if all(v > 0 for v in deltas) else 'mixed_or_tied'
                result.append({'pitch_id':target['pitch_id'],'feature':feature,'baseline':baseline,
                    'frame_index':i,'timestamp_ms':saved['timestamp_ms'],'effectiveness_eligible':i != 0,
                    'availability_transition':_transition(streams[baseline]['numerical_support'],streams['crop']['numerical_support']),
                    'reference_available':reference_available,'manual_reference':deepcopy(reference),
                    'baseline_numerical_support':streams[baseline]['numerical_support'],'crop_numerical_support':streams['crop']['numerical_support'],
                    'baseline_angle_deg':streams[baseline]['numerical_supported_angle_deg'],'crop_angle_deg':streams['crop']['numerical_supported_angle_deg'],
                    'baseline_signed_error_deg':errors[baseline],'crop_signed_error_deg':errors['crop'],
                    'crop_minus_baseline_absolute_error_deg':delta,'angle_error_change':change,
                    'point_error_pattern':pattern,'points':points,
                    'baseline_unavailable_reasons':deepcopy(streams[baseline]['unavailable_reasons']),
                    'crop_unavailable_reasons':deepcopy(streams['crop']['unavailable_reasons']),
                    **{k:deepcopy(saved[k]) for k in ('original_model_states','existing_major_hold','existing_eligible',
                        'existing_review_status','original_feature_flags','reference_all_points_in_crop','crop_bounds_xyxy')}})
    return result


def _part(rows):
    transitions = {}
    for state in TRANSITIONS:
        part = [r for r in rows if r['availability_transition'] == state]
        transitions[state] = {'frames':len(part),'frame_indices':[r['frame_index'] for r in part],
            'reference_available':sum(r['reference_available'] for r in part),
            'reference_unavailable':sum(not r['reference_available'] for r in part),
            **{a+'_reason_counts_nonexclusive':dict(Counter(reason for r in part for reason in r[a+'_unavailable_reasons'])) for a in ('baseline','crop')},
            'manual_reason_counts_nonexclusive':dict(Counter(reason for r in part for reason in r['manual_reference']['unavailable_reasons']))}
    common = [r for r in rows if r['angle_error_change'] is not None]
    worse = [r for r in common if r['angle_error_change'] == 'worsened']
    return {'frame_denominator':len(rows),'reference_available':sum(r['reference_available'] for r in rows),
        'reference_unavailable':sum(not r['reference_available'] for r in rows),'transitions':transitions,
        'angle_common_frames':len(common),'angle_common_frame_indices':[r['frame_index'] for r in common],
        'angle_error_changes':{state:{'frames':sum(r['angle_error_change']==state for r in common),
            'frame_indices':[r['frame_index'] for r in common if r['angle_error_change']==state]} for state in CHANGES},
        'angle_worsened_point_patterns':{state:{'frames':sum(r['point_error_pattern']==state for r in worse),
            'frame_indices':[r['frame_index'] for r in worse if r['point_error_pattern']==state],
            'point_error_deltas_px':[{ 'frame_index':r['frame_index'],
                'deltas':[p['crop_minus_baseline_error_px'] for p in r['points']]} for r in worse if r['point_error_pattern']==state]}
            for state in PATTERNS}}


def summarize(records):
    grouped = {(feature,baseline):[r for r in records if r['feature']==feature and r['baseline']==baseline]
        for feature in parent.original.FEATURES for baseline in BASELINES}
    total = len(next(iter(grouped.values())))
    if (total == 0 or len(records) != total*len(grouped) or len({r['pitch_id'] for r in records}) != 1 or
            any([r['frame_index'] for r in part] != list(range(total)) for part in grouped.values())):
        raise ValueError('Complete feature/baseline/source denominator required')
    features = {f:{} for f in parent.original.FEATURES}
    for (feature,baseline),part in grouped.items():
        main = [r for r in part if r['effectiveness_eligible']]
        if len(main) != total-1: raise ValueError('Changed main seed denominator')
        features[feature][baseline] = {'source_frame_denominator':total,'saved_seed_frames':1,
            'full_source':_part(part),'main_non_seed':_part(main),
            'by_reference_available':{str(v):_part([r for r in main if r['reference_available'] is v]) for v in (False,True)},
            'by_original_major_hold':{str(v):_part([r for r in main if r['existing_major_hold'] is v]) for v in (False,True)},
            'by_original_eligibility':{v:_part([r for r in main if str(r['existing_eligible'])==v]) for v in sorted({str(r['existing_eligible']) for r in main})},
            'by_reference_in_crop':{k:_part([r for r in main if r['reference_all_points_in_crop'] is v]) for k,v in (('inside',True),('outside',False),('unavailable',None))}}
    return {'source_frames':total,'non_seed_frames':total-1,'source_records':len(records),
        'non_seed_records':sum(r['effectiveness_eligible'] for r in records),'features':features}


def _verify_parent_result(root, execution, assessment, refs):
    if (execution['status'] != 'frozen_before_saved_roi_angle_assessment' or execution['policy'] != parent.POLICY or
            any(type(execution[k]) is not int or execution[k] != 0 for k in ('pose_inference_budget','tracker_inference_budget')) or
            execution['production_adoption'] is not False): raise ValueError('Changed parent assessment protocol')
    for role,path in parent.CODE_PATHS.items():
        if execution['code'][role]['path'] != path: raise ValueError('Changed parent code role')
    refs.extend([*execution['code'].values(),*(execution[k] for k in parent.INPUTS)])
    refs.append(assessment['per_frame_comparison'])
    for ref in refs: bound(root,ref)
    if sha(parent.__file__) != execution['code']['assessor']['sha256']: raise ValueError('Changed parent assessor code')


def _history(root, ref, refs):
    result = parent.original.read(bound(root,ref))
    refs.extend(result[k] for k in ('frozen_audit','audit_code','audit_tests','parent_result','output'))
    report = parent.original.read(bound(root,result['output']))
    if (result['status'] != 'completed_retrospective_paired_roi_loss_diagnostic' or
            report['status'] != 'complete_offline_paired_loss_audit' or report['pose_inference_calls'] != 0 or
            report['tracker_inference_calls'] != 0 or report['human_annotations_modified'] is not False or
            any(report[k] != result[k] for k in ('source_frames','non_seed_frames'))):
        raise ValueError('Changed historical ROI loss scope')
    refs.extend({'path':p,'sha256':h} for p,h in report['source_bindings'].items())
    return {'result':deepcopy(ref),'output':deepcopy(result['output']),
        'source_frames':report['source_frames'],'non_seed_frames':report['non_seed_frames'],
        'use':'historical_source_only_no_new_592_frame_selector_trace'}


def run(root, plan_path, output):
    root,plan_path,output = (Path(p).resolve() for p in (root,plan_path,output))
    plan,plan_sha = parent.original.read(plan_path),sha(plan_path)
    if (plan['status'] != 'frozen_before_saved_roi_transition_audit' or plan['policy'] != POLICY or
            any(type(plan[k]) is not int or plan[k] != 0 for k in ('pose_inference_budget','tracker_inference_budget')) or
            plan['production_adoption'] is not False or output != (root/plan['output_directory']).resolve() or
            output.exists() or output == root/'analysis_results' or not output.is_relative_to(root/'analysis_results')):
        raise ValueError('Unfrozen transition audit scope, budget or exclusive output')
    for role,path in CODE_PATHS.items():
        if plan['code'][role]['path'] != path: raise ValueError('Changed transition code role')
    refs = [*plan['code'].values(),*(plan[k] for k in INPUTS)]
    for ref in refs: bound(root,ref)
    if sha(__file__) != plan['code']['auditor']['sha256']: raise ValueError('Changed running transition auditor')
    execution = parent.original.read(bound(root,plan['parent_execution']))
    if plan['target_pitch_id'] != execution['target_pitch_id']:
        raise ValueError('Declared transition target differs from parent execution')
    assessment = parent.original.read(bound(root,plan['parent_assessment']))
    _verify_parent_result(root,execution,assessment,refs)
    data,view,manual,old_rows,angle_execution = parent._angle_sources(root,execution,refs)
    measured,image,raw,capture,gate_config,point_count = parent._replay(root,execution,data,view,manual,refs)
    rows = parent.compare(data,view,manual,old_rows,measured,image,raw,capture,gate_config)
    if (assessment['status'] != 'complete_saved_roi_angle_assessment' or assessment['policy'] != parent.POLICY or
            assessment['plan_sha256'] != plan['parent_execution']['sha256'] or assessment['target'] != data['target'] or
            assessment['features'] != {name:parent.summarize(values) for name,values in rows.items()} or
            assessment['manual_provenance'] != manual['provenance'] or assessment['original_point_rows_reconstructed'] != point_count or
            assessment['source_frames_replayed'] != data['target']['total_frames'] or
            parent.original.read(bound(root,assessment['per_frame_comparison'])) != {
                'status':'complete_source_frame_saved_roi_angles','plan_sha256':plan['parent_execution']['sha256'],
                'target':data['target'],'policy':parent.POLICY,'features':rows} or
            assessment['predeclared_cases'] != {str(i):{name:values[i] for name,values in rows.items()} for i in execution['predeclared_case_frames']} or
            any(type(assessment[k]) is not int or assessment[k] != 0 for k in ('pose_inference_calls','tracker_inference_calls')) or
            any(assessment[k] is not False for k in ('production_adoption','coordinate_correction','new_binary_warning','original_use_restrictions_changed')) or
            assessment['phase2_status'] != 'NOT PASSED'):
        raise ValueError('Sealed parent angle rows, summary or scope differs from reconstruction')
    history = _history(root,plan['prior_roi_loss_result'],refs)
    records = audit_rows(rows,manual,view,data['target'])
    result = {'status':'complete_saved_roi_transition_audit','plan_sha256':plan_sha,'policy':POLICY,'target':data['target'],
        **summarize(records),'historical_roi_loss':history,'source_frames_replayed':data['target']['total_frames'],
        'original_point_rows_reconstructed':point_count,'pose_inference_calls':0,'tracker_inference_calls':0,
        'production_adoption':False,'coordinate_correction':False,'new_binary_warning':False,
        'human_annotations_modified':False,'original_use_restrictions_changed':False,'phase2_status':'NOT PASSED',
        'limitations':['Availability transitions include frames without a manual angle reference; missing is never zero error.',
            'Pixel error deltas outside angle support are diagnostic only; no point is selected or replaced.',
            'Unsigned angle and per-point distance have different numerical targets; their disagreement does not certify joint accuracy.',
            'Concurrent crop geometry and original missing reasons do not identify a proven failure cause.',
            'Previously inspected human-initialized single-clip diagnosis; no fallback repair or generalization claim.']}
    parent.original.parent.verify_fit_plan(root,parent.original.read(bound(root,angle_execution['parent_fit_plan'])))
    for ref in refs: bound(root,ref)
    if sha(plan_path) != plan_sha: raise ValueError('Transition plan changed during reconstruction')
    output.mkdir()
    row_path = output/'transition_rows.json'
    write(row_path,{'status':'complete_saved_roi_transition_rows','plan_sha256':plan_sha,
        'policy':POLICY,'target':data['target'],'records':records})
    result['transition_rows'] = {'path':row_path.relative_to(root).as_posix(),'sha256':sha(row_path)}
    write(output/'transition_summary.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path); parser.add_argument('output',type=Path)
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[1],args.plan,args.output)
    print(json.dumps({k:result[k] for k in ('source_frames','non_seed_frames','source_records','pose_inference_calls')}))
