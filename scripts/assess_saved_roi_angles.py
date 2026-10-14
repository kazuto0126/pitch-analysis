"""Read-only angle comparison of already sealed ROI, IMAGE and VIDEO outputs."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import asdict
import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import assess_manual_feature_angles as original
import diagnose_angle_reference_gaps as integrity
import evaluate_tracked_roi_pose as roi_audit
import measure_pose_mode_countercheck as mode
from check_movenet_compatibility import bound, sha, write

STREAMS = ('crop', 'image', 'video_raw', 'video_processed')
INPUTS = ('parent_angle_execution', 'parent_angle_assessment', 'roi_execution', 'roi_measurements',
    'roi_evaluation', 'roi_point_comparisons', 'image_measurements', 'source_alignment_audit')
POLICY = {'scope': 'saved_roi_image_video_angles_relative_to_same_visible_manual_2d_reference',
    'features': list(original.FEATURES), 'streams': list(STREAMS),
    'primary_support': 'selected_all_three_original_gates_finite_in_source_crop_predictions_also_in_crop',
    'reference': 'three_visible_finite_nondegenerate_source_pixel_manual_points',
    'manual_reference_in_crop': 'stratum_only_never_primary_filter',
    'ungated_angles': 'diagnostic_only_not_numerical_support_or_reliability',
    'video_processed': 'original_saved_base_secondary_only_original_holds_retained',
    'seed': 'save_frame_zero_exclude_from_main_effectiveness',
    'pairing': 'identical_frames_with_reference_and_both_numerically_supported_angles',
    'numerical_tie_tolerance_deg_not_accuracy_gate': original.TIE_TOLERANCE,
    'percentile': 'linear_interpolation_at_(n-1)*p',
    'new_binary_warning': False, 'coordinate_correction': False, 'production_adoption': False,
    'pose_inference_calls': 0, 'tracker_inference_calls': 0, 'three_dimensional_claim': False}
CODE_PATHS = {'assessor': 'scripts/assess_saved_roi_angles.py', 'tests': 'tests/test_saved_roi_angles.py',
    'angle_assessor': 'scripts/assess_manual_feature_angles.py',
    'angle_integrity_helpers': 'scripts/diagnose_angle_reference_gaps.py',
    'roi_evaluator': 'scripts/evaluate_tracked_roi_pose.py', 'roi_producer': 'scripts/measure_tracked_roi_pose.py',
    'mode_helpers': 'scripts/measure_pose_mode_countercheck.py', 'selector': 'src/pitch_analysis/subject.py',
    'pose_capture': 'src/pitch_analysis/pose_capture.py',
    **{k:v for k,v in original.CODE_PATHS.items() if k not in ('evaluator','tests')}}


def _point(point, width, height):
    if point is None or not original.finite_point([point.get('x'), point.get('y')]): return None
    xy = [point['x']*width, point['y']*height]
    return xy if original.finite_point(xy) else None


def _raw_stream(names, points, selection_status, width, height, config, crop_points=None):
    xy, records, reasons = [], [], []
    if selection_status != 'selected': reasons.append('selection_not_selected')
    for name in names:
        point = points.get(name); pixel = _point(point, width, height)
        finite = point is not None and all(type(point.get(k)) in (int,float) and math.isfinite(point[k])
            for k in ('x','y','visibility','presence'))
        passes = finite and mode.gate(point, config)
        inside = roi_audit.inside([0,0,width,height], *pixel) if pixel is not None else None
        cp = crop_points.get(name) if crop_points is not None else None
        in_crop = (cp is not None and _point(cp,1,1) is not None and 0 <= cp['x'] < 1 and 0 <= cp['y'] < 1) if crop_points is not None else None
        if point is None: reasons.append('selected_point_missing:'+name)
        elif not finite: reasons.append('nonfinite_point_or_confidence:'+name)
        elif not passes: reasons.append('below_original_gate:'+name)
        if pixel is not None and not inside: reasons.append('prediction_outside_source:'+name)
        if crop_points is not None and not in_crop: reasons.append('prediction_outside_or_missing_crop:'+name)
        xy.append(pixel)
        records.append({'landmark': name, 'xy_px': pixel, 'finite': finite, 'gate_pass': bool(passes),
            'in_source': inside, 'prediction_in_crop': in_crop})
    value = original.angle(xy)
    if value is None: reasons.append('missing_or_degenerate_projected_angle')
    supported = not reasons
    return {'selection_status': selection_status, 'points': records, 'ungated_angle_deg': value,
        'numerical_support': supported, 'numerical_supported_angle_deg': value if supported else None,
        'unavailable_reasons': reasons}


def compare(data, view, manual, previous_rows, roi_measurements, image_measurements, video_raw, capture, gate_config):
    """Pure comparison; no reference-in-crop selection and no gate modification."""
    integrity._verify_previous_rows(data, view, manual, previous_rows)
    target = data['target']; total, width, height = (target[k] for k in ('total_frames','width','height'))
    if (roi_measurements['target'] != target or any(image_measurements[k] != target[k]
            for k in ('pitch_id','total_frames','width','height')) or image_measurements['gate'] != gate_config or
            image_measurements['video_sha256'] != manual['source_video']['sha256'] or len(video_raw) != total or
            set(gate_config) != {'min_visibility','min_presence'} or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in gate_config.values())):
        raise ValueError('Saved streams, source identity, original gate or frame denominator differ')
    for frames in (roi_measurements['frames'], image_measurements['frames'], capture['selection_frames']):
        if [f['frame_index'] for f in frames] != list(range(total)): raise ValueError('Saved prediction timeline incomplete')
    rows = {name: [] for name in original.FEATURES}
    for i,(crop, image, human, selection) in enumerate(zip(roi_measurements['frames'], image_measurements['frames'],
            manual['frames'], capture['selection_frames'], strict=True)):
        if (crop['decoded_bgr_sha256'] != image['decoded_bgr_sha256'] or
                any(not math.isclose(crop['native_timestamp_ms'],t,rel_tol=0,abs_tol=1e-6)
                    for t in (image['native_timestamp_ms'],human['timestamp_ms'])) or
                selection['timestamp_ms'] != round(crop['native_timestamp_ms'])):
            raise ValueError('Saved source pixels or timeline differ')
        arms = {'crop': mode.selected_points(crop['full_image_candidates'],crop['selection']),
            'image': mode.selected_points(image['image_candidates'],image['image_selection']), 'video_raw': video_raw[i]}
        crop_points = mode.selected_points(crop['crop_candidates'],crop['selection'])
        choices = {'crop': crop['selection']['status'], 'image': image['image_selection']['status'], 'video_raw': selection['status']}
        joints = {j['name']: j for j in human['joints']}
        for feature,roles in original.FEATURES.items():
            old = previous_rows[feature][i]; names = old['required_landmarks']
            # Original raw named points and confidence are part of the angle source, not a new selection.
            for name in names:
                saved, point = data['frames'][i]['joints'][name]['raw'], video_raw[i].get(name)
                finite = mode.finite_point(point)
                if (finite != saved['finite'] or finite and (_point(point,width,height) != saved['xy_px'] or
                        point['visibility'] != saved['visibility'] or point['presence'] != saved['presence'])):
                    raise ValueError('Formal VIDEO raw point or confidence differs from parent source')
            streams = {arm: _raw_stream(names, points, choices[arm], width, height, gate_config,
                crop_points if arm == 'crop' else None) for arm,points in arms.items()}
            base = old['streams_deg']['processed_base']
            streams['video_processed'] = {'selection_status': selection['status'], 'points': None,
                'ungated_angle_deg': None, 'numerical_support': base is not None,
                'numerical_supported_angle_deg': base,
                'unavailable_reasons': [] if base is not None else ['original_processed_base_missing']}
            reference = old['manual_reference']['value_deg']
            visible = all(joints[n]['status'] == 'visible' and original.finite_point([joints[n].get('x_px'),joints[n].get('y_px')]) for n in names)
            in_crop = all(roi_audit.inside(crop['crop_bounds_xyxy'], joints[n]['x_px'], joints[n]['y_px']) for n in names) if visible and crop['crop_bounds_xyxy'] is not None else None
            for stream in streams.values():
                value, ungated = stream['numerical_supported_angle_deg'], stream['ungated_angle_deg']
                stream['signed_error_deg'] = value-reference if value is not None and reference is not None else None
                stream['ungated_signed_error_deg'] = ungated-reference if ungated is not None and reference is not None else None
            rows[feature].append({'frame_index': i, 'timestamp_ms': human['timestamp_ms'], 'effectiveness_eligible': i != 0,
                'required_roles': list(roles), 'required_landmarks': list(names), 'manual_reference': old['manual_reference'],
                'reference_all_points_in_crop': in_crop, 'crop_bounds_xyxy': crop['crop_bounds_xyxy'], 'streams': streams,
                'original_model_states': {r: view['frames'][i]['focus_joints'][r]['model_state'] for r in roles},
                **{k:old[k] for k in ('existing_review_status','existing_eligible','existing_major_hold','original_feature_flags')}})
    return rows


def _summary(rows):
    reference = [r for r in rows if r['manual_reference']['value_deg'] is not None]
    streams = {}
    for name in STREAMS:
        streams[name] = {'frame_denominator': len(rows), 'manual_reference_frames': len(reference),
            'manual_reference_missing': len(rows)-len(reference),
            'numerically_supported_frames': sum(r['streams'][name]['numerical_support'] for r in rows),
            'reference_present_prediction_missing': sum(r['streams'][name]['signed_error_deg'] is None for r in reference),
            'prediction_present_without_manual_reference': sum(r['streams'][name]['numerical_support'] and r['manual_reference']['value_deg'] is None for r in rows),
            'error_conditional_not_directly_comparable': original.error_stats([r['streams'][name]['signed_error_deg'] for r in rows if r['streams'][name]['signed_error_deg'] is not None]),
            'ungated_diagnostic_error': original.error_stats([r['streams'][name]['ungated_signed_error_deg'] for r in rows if r['streams'][name]['ungated_signed_error_deg'] is not None]),
            'unavailable_reason_counts_nonexclusive': dict(Counter(reason for r in rows for reason in r['streams'][name]['unavailable_reasons']))}
    pairs = {}
    for baseline in STREAMS[1:]:
        common = [r for r in rows if all(r['streams'][a]['signed_error_deg'] is not None for a in ('crop',baseline))]
        before, after = ([r['streams'][a]['signed_error_deg'] for r in common] for a in (baseline,'crop'))
        delta = [abs(b)-abs(a) for a,b in zip(before,after,strict=True)]
        pairs[baseline] = {'frame_denominator': len(rows), 'manual_reference_frames': len(reference),
            'common_frames': len(common), 'frame_indices': [r['frame_index'] for r in common],
            'baseline_error': original.error_stats(before), 'crop_error': original.error_stats(after),
            'improved': sum(v < -original.TIE_TOLERANCE for v in delta),
            'worsened': sum(v > original.TIE_TOLERANCE for v in delta),
            'numerically_tied': sum(abs(v) <= original.TIE_TOLERANCE for v in delta),
            'comparison_scope': 'secondary_original_processed_base' if baseline == 'video_processed' else 'primary_saved_raw_numerical_support'}
    return {'evaluation_frame_denominator': len(rows), 'manual_reference_frames': len(reference),
        'manual_unavailable_reason_counts_nonexclusive': dict(Counter(v for r in rows for v in r['manual_reference']['unavailable_reasons'])),
        'streams': streams, 'paired_crop_comparisons': pairs}


def summarize(rows, include_seed=False):
    selected = [r for r in rows if include_seed or r['effectiveness_eligible']]
    return {'source_frame_denominator': len(rows), 'saved_seed_frames': sum(not r['effectiveness_eligible'] for r in rows),
        'include_seed_in_this_summary': include_seed, **_summary(selected),
        'by_reference_in_crop': {key: _summary([r for r in selected if r['reference_all_points_in_crop'] is state])
            for key,state in (('inside',True),('outside',False),('unavailable',None))},
        'by_original_major_hold': {str(state): _summary([r for r in selected if r['existing_major_hold'] is state]) for state in (False,True)},
        'by_original_eligibility': {state: _summary([r for r in selected if str(r['existing_eligible']) == state])
            for state in sorted({str(r['existing_eligible']) for r in selected})}}


def _angle_sources(root, plan, refs):
    execution = original.read(bound(root,plan['parent_angle_execution']))
    if execution['status'] != 'frozen_before_manual_angle_assessment' or execution['policy'] != original.POLICY:
        raise ValueError('Changed parent angle protocol')
    for role,path in original.CODE_PATHS.items():
        if execution['code'][role]['path'] != path: raise ValueError('Changed parent angle code role')
    refs.extend([*execution['code'].values(),execution['parent_fit_plan'],execution['manual_coordinates'],execution['reviewed_feature_quality']])
    for ref in refs: bound(root,ref)
    parent = original.read(bound(root,execution['parent_fit_plan']))
    measurements, views = original.parent.verify_fit_plan(root,parent)
    indices = [i for i,d in enumerate(measurements) if d['target']['pitch_id'] == plan['target_pitch_id']]
    if len(indices) != 1 or execution['target_pitch_id'] != plan['target_pitch_id']: raise ValueError('Unique same-source target required')
    index = indices[0]; data, view = measurements[index], views[index]
    refs.extend(view['source_artifacts'].values())
    manual = original.read(bound(root,execution['manual_coordinates']))
    original.validate_manual_keypoints(manual,source_video_path=bound(root,view['source_artifacts']['original_video']))
    if manual['annotation_status'] != 'reviewed': raise ValueError('Reviewed manual coordinates required')
    features = original.read(bound(root,execution['reviewed_feature_quality'])); source = features['source_artifacts']
    refs.extend(source.values())
    if source['reviewed_reliability'] != parent['clips'][index]['reviewed_reliability']: raise ValueError('Changed original feature review')
    with bound(root,source['features']).open(encoding='utf-8-sig',newline='') as stream: saved_csv = list(csv.DictReader(stream))
    rebuilt = original.original_features.derive(view,saved_csv,original.read(bound(root,source['metrics'])),
        original.read(bound(root,source['feature_quality'])),original.read(bound(root,view['source_artifacts']['video_metadata'])))
    if any(features[k] != v for k,v in rebuilt.items()): raise ValueError('Original feature source reconstruction differs')
    rows = original.compare_rows(data,view,features,manual)
    assessment = original.read(bound(root,plan['parent_angle_assessment'])); refs.append(assessment['per_frame_comparison'])
    execution_sha = plan['parent_angle_execution']['sha256']
    if (assessment['status'] != 'complete_manual_reference_angle_assessment' or assessment['plan_sha256'] != execution_sha or
            assessment['policy'] != original.POLICY or assessment['target'] != data['target'] or
            assessment['manual_source'] != execution['manual_coordinates'] or assessment['manual_provenance'] != manual['provenance'] or
            assessment['features'] != {n:original.summarize(v) for n,v in rows.items()} or
            original.read(bound(root,assessment['per_frame_comparison'])) != {
                'status':'complete_115_frame_manual_angle_comparison','plan_sha256':execution_sha,'features':rows}):
        raise ValueError('Sealed original angle assessment differs')
    return data, view, manual, rows, execution


def _verify_image_plan(root, proposal, plan, image, refs):
    parent_refs = proposal['parent_only_sources']; refs.extend(parent_refs.values())
    execution = mode.read(bound(root,parent_refs['mode_execution'])); run_path = bound(root,parent_refs['mode_measurement_run'])
    run = mode.read(run_path); mode.validate_plan(execution)
    refs.extend({'path':p,'sha256':h} for p,h in execution['measurement_source_hashes'].items())
    if (execution['status'] != 'frozen_before_measurement' or execution['parameters'] != mode.PARAMETERS or
            execution['options'] != mode.OPTIONS or execution['producer_sha256'] != sha(mode.__file__) or
            run['status'] != 'measurements_only' or run['plan_sha256'] != parent_refs['mode_execution']['sha256'] or
            run['producer_sha256'] != execution['producer_sha256'] or run['human_annotation_inputs'] != [] or
            run['warning_predictions_generated'] is not False or
            any(run[k] != execution[k] for k in ('parameters','options','runtime','measurement_source_hashes'))):
        raise ValueError('Full-image measurement execution or run changed')
    receipts = [r for r in run['clips'] if r['pitch_id'] == plan['target_pitch_id']]
    clips = [c for c in execution['clips'] if c['pitch_id'] == plan['target_pitch_id']]
    if (len(receipts) != 1 or len(clips) != 1 or (run_path.parent/receipts[0]['path']).resolve() != bound(root,plan['image_measurements']) or
            receipts[0]['sha256'] != plan['image_measurements']['sha256'] or image['human_annotation_inputs'] != [] or
            image['original_predictions_modified'] is not False or image['warning_threshold'] is not None):
        raise ValueError('Unbound full-image clip or changed experimental semantics')
    return clips[0]


def _verify_clean_config(root, config, target, raw_ref, capture_ref):
    if (config['schema_version'] != 'pose-clean-v0.2' or
            (root/config['source_pose_csv']).resolve() != bound(root,raw_ref) or
            (root/config['source_context']).resolve() != bound(root,capture_ref) or
            any(config[k] != target[k] for k in ('width','height')) or
            config['requested_frames'] != target['total_frames'] or config['timeline_start_frame'] != 0 or
            config['timeline_end_frame'] != target['total_frames']-1):
        raise ValueError('Original gate configuration source or frame identity differs')
    return {k:config[k] for k in ('min_visibility','min_presence')}


def _replay(root, plan, data, view, manual, refs):
    execution = original.read(bound(root,plan['roi_execution'])); roi_audit.verify_execution(root,execution,evaluator=True)
    proposal = original.read(root/execution['proposal_manifest'])
    refs.extend([{'path':execution['proposal_manifest'],'sha256':execution['proposal_manifest_sha256']},
        *execution['producer_sources'].values(),*execution['producer_dependencies'].values(),
        *execution['evaluator_sources'].values(),*execution['evaluator_dependencies'].values()])
    if (execution['target'] != data['target'] or set(execution['evaluator_sources']) != roi_audit.EVALUATOR_ROLES or
            execution['evaluator_sources'] != proposal['evaluator_only_sources'] or
            execution['evaluator_dependencies'] != proposal['proposed_evaluator_dependencies'] or
            sha(root/'tests/test_tracked_roi_pose_evaluation.py') != execution['evaluator_test_sha256']):
        raise ValueError('Changed ROI evaluation sources or cohort')
    inventory = roi_audit.protected_inventory(root,proposal)
    refs.extend({'path':p,'sha256':h} for p,h in inventory.items())
    measured = original.read(bound(root,plan['roi_measurements'])); image = original.read(bound(root,plan['image_measurements']))
    for key in ('producer_sources','producer_dependencies','runtime','parameters','options','target'):
        if measured[key] != execution[key]: raise ValueError('ROI measurement seal differs: '+key)
    if (measured['status'] != 'sealed_measurements_only' or measured['plan_sha256'] != plan['roi_execution']['sha256'] or
            measured['producer_sha256'] != execution['producer_sha256'] or measured['human_annotation_inputs'] != [] or
            measured['warning_policy'] is not None or measured['original_predictions_modified'] is not False):
        raise ValueError('Changed sealed ROI measurement semantics')
    sources, evaluation_sources = execution['producer_sources'],execution['evaluator_sources']
    # Bind the exact original streams, not just their filenames or a same-sized clip.
    expected = {'original_raw':data['source_references']['original_raw'], 'capture':data['source_references']['capture'],
        'canonical_review':view['source_artifacts']['ground_truth']}
    if any(evaluation_sources[k] != v for k,v in expected.items()) or sources['video'] != view['source_artifacts']['original_video'] or evaluation_sources['full_frame_image'] != plan['image_measurements']:
        raise ValueError('ROI and formal angle sources differ')
    capture = original.read(bound(root,evaluation_sources['capture'])); config = original.read(bound(root,evaluation_sources['clean_config']))
    gate_config = _verify_clean_config(root,config,data['target'],evaluation_sources['original_raw'],evaluation_sources['capture'])
    raw = mode.load_video_raw(bound(root,evaluation_sources['original_raw']),capture,data['target']['total_frames'])
    canonical = original.read(bound(root,evaluation_sources['canonical_review']))
    roi_audit.validate_ground_truth(canonical,source_video_path=bound(root,sources['video']))
    if canonical['annotation_status'] != 'reviewed' or original.read(bound(root,evaluation_sources['manual_xy'])) != manual:
        raise ValueError('Different or unreviewed manual reference')
    clip = _verify_image_plan(root,proposal,plan,image,refs)
    for name,role in (('video','video'),('metadata','metadata'),('video_metadata','video_technical')):
        if clip[name] != sources[role]['path']: raise ValueError('IMAGE and ROI video sources differ')
    for name,role in (('raw_csv','original_raw'),('capture','capture'),('clean_config','clean_config')):
        if clip[name] != evaluation_sources[role]['path']: raise ValueError('IMAGE and VIDEO source paths differ')
    tracked = original.read(bound(root,sources['tracked_roi'])); technical = original.read(bound(root,sources['video_technical']))
    roi_audit.validate_tracked_roi(tracked,sources,data['target'])
    if (technical['sha256'] != sources['video']['sha256'] or tuple(technical[k] for k in ('frame_count','width','height')) !=
            tuple(data['target'][k] for k in ('total_frames','width','height'))): raise ValueError('Technical source dimensions differ')
    alignment = original.read(bound(root,plan['source_alignment_audit']))
    if (alignment['status'] != 'complete_source_alignment_no_detected_engineering_mismatch' or
            alignment['source_frame_count'] != data['target']['total_frames'] or alignment['role_mapping'] != data['important_joints'] or
            alignment['raw_predictions_or_annotations_modified'] is not False or
            any(alignment[k] != 0 for k in ('new_pose_inference_calls','new_tracker_inference_calls','new_classification_or_warning_calls'))):
        raise ValueError('Source alignment audit scope differs')
    for key in ('source_hashes_before_and_after_identical','original_png_and_reviewcopy_hashes'):
        refs.extend({'path':p,'sha256':h} for p,h in alignment[key].items())
    major = {i for item in canonical['labels']['major_pose_failure_intervals'] if item['status']=='confirmed'
        for i in range(item['start_frame'],item['end_frame']+1)}
    point_rows, states = [],[]; selector, image_selector = roi_audit.PitcherSelector(),roi_audit.PitcherSelector()
    video = cv2.VideoCapture(str(bound(root,sources['video'])))
    try:
        for i,(frame,control,human,aligned) in enumerate(zip(measured['frames'],image['frames'],manual['frames'],alignment['per_frame'],strict=True)):
            ok,pixels = video.read()
            if not ok: raise ValueError('Source decode incomplete')
            ms = video.get(cv2.CAP_PROP_POS_MSEC)
            roi_audit.replay_frame(frame,tracked['frames'][i],pixels,ms,technical['timestamps_ms'][i],selector)
            candidates = roi_audit.serialize_candidates([[SimpleNamespace(**p) for p in pose] for pose in control['image_candidates']])
            choice = asdict(image_selector.select([[SimpleNamespace(**p) for p in pose] for pose in candidates]))
            rebuilt = mode.frame_measurement(i,capture['selection_frames'][i]['timestamp_ms'],ms,frame['decoded_bgr_sha256'],
                candidates,choice,raw[i],capture['selection_frames'][i],data['target']['width'],data['target']['height'],gate_config)
            if (rebuilt != control or human['frame_index'] != i or aligned['frame_index'] != i or
                    aligned['decoded_bgr_sha256'] != frame['decoded_bgr_sha256'] or
                    not math.isclose(human['timestamp_ms'],ms,rel_tol=0,abs_tol=1e-6) or
                    not math.isclose(aligned['timestamp_ms'],ms,rel_tol=0,abs_tol=1e-6)):
                raise ValueError('Source/manual/full-image replay differs')
            arms = {'crop':mode.selected_points(frame['full_image_candidates'],frame['selection']),
                'image':mode.selected_points(control['image_candidates'],control['image_selection']), 'video':raw[i]}
            crop_points = mode.selected_points(frame['crop_candidates'],frame['selection'])
            if i != 0: point_rows.extend(roi_audit.point_row(i,j,frame['crop_bounds_xyxy'],arms,crop_points,gate_config,i in major) for j in human['joints'])
            states.append({'frame_index':i,'eligible':i!=0,'old_major':i in major,'crop':frame['selection']['status'],
                'image':control['image_selection']['status'],'video':capture['selection_frames'][i]['status']})
        if video.read()[0]: raise ValueError('Extra source frame')
    finally: video.release()
    evaluation = original.read(bound(root,plan['roi_evaluation'])); old_points = original.read(bound(root,plan['roi_point_comparisons']))
    if (old_points != {'seed_frame_excluded':0,'rows':point_rows} or evaluation['status'] != 'complete_offline_xy_evaluation' or
            evaluation['measurement_sha256'] != plan['roi_measurements']['sha256'] or evaluation['execution_sha256'] != plan['roi_execution']['sha256'] or
            evaluation['frames'] != states or evaluation['groups']['all_non_seed'] != roi_audit.summarize_points(point_rows) or
            evaluation['denominators']['manual_joint_records'] != len(point_rows) or
            measured['inference_calls'] != sum(f['inference_status']=='measured' for f in measured['frames'])):
        raise ValueError('Original sealed point comparison or evaluation differs')
    return measured,image,raw,capture,gate_config,len(point_rows)


def run(root, plan_path, output):
    root,plan_path,output = (Path(p).resolve() for p in (root,plan_path,output))
    plan,plan_sha = original.read(plan_path),sha(plan_path)
    if (plan['status'] != 'frozen_before_saved_roi_angle_assessment' or plan['policy'] != POLICY or
            any(type(plan[k]) is not int or plan[k] != 0 for k in ('pose_inference_budget','tracker_inference_budget')) or
            plan['production_adoption'] is not False or output != (root/plan['output_directory']).resolve() or
            output.exists() or output == root/'analysis_results' or not output.is_relative_to(root/'analysis_results')):
        raise ValueError('Unfrozen scope, inference, adoption or output directory')
    for role,path in CODE_PATHS.items():
        if plan['code'][role]['path'] != path: raise ValueError('Changed code role')
    refs = [*plan['code'].values(),*(plan[k] for k in INPUTS)]
    for ref in refs: bound(root,ref)
    if sha(__file__) != plan['code']['assessor']['sha256']: raise ValueError('Changed running saved-angle assessor')
    data,view,manual,old_rows,parent = _angle_sources(root,plan,refs)
    measured,image,raw,capture,gate_config,point_count = _replay(root,plan,data,view,manual,refs)
    rows = compare(data,view,manual,old_rows,measured,image,raw,capture,gate_config)
    case_frames = plan['predeclared_case_frames']
    if len(set(case_frames)) != len(case_frames) or any(type(i) is not int or not 0 <= i < data['target']['total_frames'] for i in case_frames):
        raise ValueError('Invalid predeclared case frames')
    result = {'status':'complete_saved_roi_angle_assessment','plan_sha256':plan_sha,'policy':POLICY,'target':data['target'],
        'features':{n:summarize(v) for n,v in rows.items()}, 'manual_provenance':manual['provenance'],
        'predeclared_cases':{str(i):{n:values[i] for n,values in rows.items()} for i in case_frames},
        'original_point_rows_reconstructed':point_count,'source_frames_replayed':data['target']['total_frames'],
        'pose_inference_calls':0,'tracker_inference_calls':0,'production_adoption':False,'coordinate_correction':False,
        'new_binary_warning':False,'original_use_restrictions_changed':False,'phase2_status':'NOT PASSED',
        'limitations':['Numerical support and gate passage do not establish accurate joints or subject identity.',
            'Below-gate or missing predictions are unavailable, not proven coordinate errors.',
            'Manual reference outside crop remains in primary comparisons when predictions are supported.',
            'One already reviewed clip with human-initialized tracking; no untouched validation or generalization claim.',
            'Visible manual 2D reference is not error-free physical truth; original major and feature holds remain.']}
    original.parent.verify_fit_plan(root,original.read(bound(root,parent['parent_fit_plan'])))
    for ref in refs: bound(root,ref)
    if sha(plan_path) != plan_sha: raise ValueError('Plan changed during read-only assessment')
    output.mkdir()
    frame_path = output/'per_frame_saved_roi_angles.json'
    write(frame_path,{'status':'complete_source_frame_saved_roi_angles','plan_sha256':plan_sha,'target':data['target'],'policy':POLICY,'features':rows})
    result['per_frame_comparison'] = {'path':frame_path.relative_to(root).as_posix(),'sha256':sha(frame_path)}
    write(output/'saved_roi_angle_assessment.json',result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path); parser.add_argument('output',type=Path)
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[1],args.plan,args.output)['features']))
