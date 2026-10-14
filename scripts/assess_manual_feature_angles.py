"""Quantify existing 2D feature errors against reviewed visible manual points."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import math
from pathlib import Path

import calibrate_joint_reliability as parent
import export_reviewed_feature_quality as original_features
from check_movenet_compatibility import bound, sha, write
from pitch_analysis.geometry import joint_angle
from pitch_analysis.manual_keypoints import validate_manual_keypoints

FEATURES = {'throwing_elbow_angle': ('throwing_shoulder', 'throwing_elbow', 'throwing_wrist'),
            'lead_knee_angle': ('lead_hip', 'lead_knee', 'lead_ankle')}
STREAMS = ('raw_unfiltered', 'processed_base', 'feature_interpolated', 'feature_smoothed')
TIE_TOLERANCE = 1e-8
POLICY = {'scope': 'existing_two_2d_angles_relative_to_visible_manual_reference',
    'reference': 'all_three_points_visible_finite_nondegenerate_source_pixels', 'include_frame_zero': True,
    'streams': list(STREAMS), 'numerical_tie_tolerance_deg_not_accuracy_gate': TIE_TOLERANCE,
    'percentile': 'linear_interpolation_at_(n-1)*p', 'held_frames_retained': True,
    'coordinate_correction': False, 'new_warning': False, 'production_adoption': False,
    'pose_inference_calls': 0, 'tracker_inference_calls': 0, 'three_dimensional_claim': False}
CODE_PATHS = {'evaluator': 'scripts/assess_manual_feature_angles.py',
    'tests': 'tests/test_manual_feature_angles.py', 'parent_helpers': 'scripts/calibrate_joint_reliability.py',
    'feature_helpers': 'scripts/export_reviewed_feature_quality.py', 'geometry': 'src/pitch_analysis/geometry.py',
    'manual_validator': 'src/pitch_analysis/manual_keypoints.py', 'native_helpers': 'scripts/check_movenet_compatibility.py'}


def read(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def finite_point(point):
    return (isinstance(point, (list, tuple)) and len(point) == 2 and
            all(type(v) in (int, float) and math.isfinite(v) for v in point))


def angle(points):
    return joint_angle(*points) if len(points) == 3 and all(finite_point(p) for p in points) else None


def manual_reference(joints, names):
    points, reasons = [], []
    for name in names:
        joint = joints[name]
        point = [joint.get('x_px'), joint.get('y_px')]
        if joint['status'] != 'visible': reasons.append('manual_' + joint['status'] + ':' + name)
        elif not finite_point(point): reasons.append('manual_nonfinite:' + name)
        points.append(point)
    value = None if reasons else angle(points)
    if value is None and not reasons: reasons.append('manual_degenerate_projected_joint')
    return {'value_deg': value, 'unavailable_reasons': reasons,
        'member_statuses': {name: joints[name]['status'] for name in names}}


def percentile(values, p):
    if not values: return None
    ordered = sorted(values); x = (len(ordered)-1)*p; a = int(x); b = min(a+1, len(ordered)-1)
    return ordered[a] + (ordered[b]-ordered[a])*(x-a)


def error_stats(signed):
    absolute = [abs(v) for v in signed]
    return {'paired_frames': len(signed), 'mae_deg': sum(absolute)/len(signed) if signed else None,
        'median_absolute_deg': percentile(absolute, .5), 'p95_absolute_deg': percentile(absolute, .95),
        'rmse_deg': math.sqrt(sum(v*v for v in signed)/len(signed)) if signed else None,
        'mean_signed_deg': sum(signed)/len(signed) if signed else None,
        'maximum_absolute_deg': max(absolute, default=None)}


def stream_summary(rows, stream):
    if stream not in STREAMS: raise ValueError('Unknown saved angle stream')
    supported = [r for r in rows if r['manual_reference']['value_deg'] is not None]
    signed = [r['streams_deg'][stream]-r['manual_reference']['value_deg'] for r in supported if r['streams_deg'][stream] is not None]
    return {'source_frame_denominator': len(rows), 'manual_reference_frames': len(supported),
        'manual_reference_missing': len(rows)-len(supported),
        'reference_present_prediction_missing': sum(r['streams_deg'][stream] is None for r in supported),
        'prediction_present_without_manual_reference': sum(r['streams_deg'][stream] is not None and r['manual_reference']['value_deg'] is None for r in rows),
        **error_stats(signed)}


def paired_change(rows, before, after):
    common = [r for r in rows if r['manual_reference']['value_deg'] is not None and
        r['streams_deg'][before] is not None and r['streams_deg'][after] is not None]
    a = [r['streams_deg'][before]-r['manual_reference']['value_deg'] for r in common]
    b = [r['streams_deg'][after]-r['manual_reference']['value_deg'] for r in common]
    delta = [abs(y)-abs(x) for x, y in zip(a, b, strict=True)]
    return {'paired_frames': len(common), 'frame_indices': [r['frame_index'] for r in common],
        'before': error_stats(a), 'after': error_stats(b),
        'error_decreased': sum(v < -TIE_TOLERANCE for v in delta),
        'error_increased': sum(v > TIE_TOLERANCE for v in delta),
        'numerically_equal': sum(abs(v) <= TIE_TOLERANCE for v in delta),
        'numerical_tie_tolerance_deg_not_accuracy_gate': TIE_TOLERANCE}


def summarize(rows):
    return {'source_frame_denominator': len(rows), 'streams': {s: stream_summary(rows, s) for s in STREAMS},
        'paired_raw_to_base': paired_change(rows, 'raw_unfiltered', 'processed_base'),
        'paired_base_to_smoothed': paired_change(rows, 'processed_base', 'feature_smoothed'),
        'manual_unavailable_reason_counts_nonexclusive': dict(Counter(reason for r in rows for reason in r['manual_reference']['unavailable_reasons'])),
        **{name: {key: {'source_frames': len(part), 'streams': {s: stream_summary(part, s) for s in STREAMS}}
            for key in sorted({str(r[field]) for r in rows}) for part in [[r for r in rows if str(r[field]) == key]]}
            for name, field in (('by_original_model_states', 'model_state_context'), ('by_existing_review_status', 'existing_review_status'),
                                ('by_existing_major_hold', 'existing_major_hold'))}}


def compare_rows(data, view, feature_view, manual):
    target, mapping = data['target'], data['important_joints']
    total, width, height = (target[k] for k in ('total_frames', 'width', 'height'))
    if (manual['source_video']['pitch_id'] != target['pitch_id'] or manual['source_video']['total_frames'] != total or
            manual['image_size'] != {'width': width, 'height': height} or
            manual['source_video']['sha256'] != view['source_artifacts']['original_video']['sha256'] or
            feature_view['pitch_id'] != target['pitch_id'] or len(feature_view['frames']) != total or
            [f['frame_index'] for f in manual['frames']] != list(range(total))):
        raise ValueError('Manual coordinates, source frames, size or feature identity differ')
    rows = {name: [] for name in FEATURES}
    for i, (measured, reviewed, saved, human) in enumerate(zip(data['frames'], view['frames'], feature_view['frames'], manual['frames'], strict=True)):
        if (measured['frame_index'] != i or reviewed['frame_index'] != i or saved['frame_index'] != i or
                abs(human['timestamp_ms']-reviewed['timestamp_ms']) > 1): raise ValueError('Angle source timeline differs')
        human_points = {j['name']: j for j in human['joints']}
        for name, roles in FEATURES.items():
            names = tuple(mapping[r] for r in roles)
            reference = manual_reference(human_points, names)
            raw = [measured['joints'][n]['raw']['xy_px'] if measured['joints'][n]['raw']['finite'] else None for n in names]
            processed = []
            for r in roles:
                p = reviewed['focus_joints'][r]['processed_landmark']
                processed.append([p['x']*width, p['y']*height] if p['usable'] and p['x'] is not None and p['y'] is not None else None)
            original = saved['features'][name]
            if not original_features.same_number(angle(processed), original['saved_values']['base']):
                raise ValueError('Saved base angle differs from original processed source-pixel geometry')
            streams = {'raw_unfiltered': angle(raw), 'processed_base': original['saved_values']['base'],
                'feature_interpolated': original['saved_values']['feature_interpolated'], 'feature_smoothed': original['saved_values']['smoothed']}
            rows[name].append({'frame_index': i, 'timestamp_ms': human['timestamp_ms'], 'manual_reference': reference,
                'streams_deg': streams, 'signed_errors_deg': {s: v-reference['value_deg'] if v is not None and reference['value_deg'] is not None else None for s,v in streams.items()},
                'model_state_context': '|'.join(r+'='+reviewed['focus_joints'][r]['model_state'] for r in roles),
                'existing_review_status': original['status'], 'existing_eligible': original['eligible'],
                'existing_major_hold': parent.review.confirmed(reviewed['human_review']['major_pose_failure']),
                'original_feature_flags': original['saved_flags'], 'required_landmarks': list(names)})
    return rows


def assess(root, plan_path, output):
    root, plan_path, output = (Path(p).resolve() for p in (root, plan_path, output))
    plan, plan_sha = read(plan_path), sha(plan_path)
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('Exclusive new angle-assessment directory required')
    if plan['status'] != 'frozen_before_manual_angle_assessment' or plan['policy'] != POLICY:
        raise ValueError('Changed frozen angle assessment policy')
    for role, path in CODE_PATHS.items():
        if plan['code'][role]['path'] != path: raise ValueError('Changed bound angle code role')
    refs = [*plan['code'].values(), plan['parent_fit_plan'], plan['manual_coordinates'], plan['reviewed_feature_quality']]
    for r in refs: bound(root, r)
    if sha(__file__) != plan['code']['evaluator']['sha256']: raise ValueError('Changed running angle assessor')
    measurements, views = parent.verify_fit_plan(root, read(bound(root, plan['parent_fit_plan'])))
    index = next(i for i,d in enumerate(measurements) if d['target']['pitch_id'] == plan['target_pitch_id'])
    data, view = measurements[index], views[index]
    refs.extend(view['source_artifacts'].values())
    manual = read(bound(root, plan['manual_coordinates']))
    validate_manual_keypoints(manual, source_video_path=bound(root, view['source_artifacts']['original_video']))
    if manual['annotation_status'] != 'reviewed': raise ValueError('Completed coordinate review required')
    feature_view = read(bound(root, plan['reviewed_feature_quality']))
    source = feature_view['source_artifacts']
    if source['reviewed_reliability'] != read(bound(root, plan['parent_fit_plan']))['clips'][index]['reviewed_reliability']:
        raise ValueError('Feature view differs from verified parent review')
    for r in source.values(): bound(root, r)
    refs.extend(source.values())
    with bound(root, source['features']).open(encoding='utf-8-sig', newline='') as stream: csv_rows = list(csv.DictReader(stream))
    rebuilt = original_features.derive(view, csv_rows, read(bound(root, source['metrics'])), read(bound(root, source['feature_quality'])),
        read(bound(root, view['source_artifacts']['video_metadata'])))
    if any(feature_view[k] != v for k,v in rebuilt.items()): raise ValueError('Feature view differs from original source reconstruction')
    rows = compare_rows(data, view, feature_view, manual)
    result = {'status': 'complete_manual_reference_angle_assessment', 'plan_sha256': plan_sha, 'policy': POLICY,
        'target': data['target'], 'manual_provenance': manual['provenance'], 'manual_source': plan['manual_coordinates'],
        'features': {name: summarize(values) for name,values in rows.items()},
        'other_formal_clips': {d['target']['pitch_id']: 'not_assessed_no_manual_coordinates_in_this_assessment' for i,d in enumerate(measurements) if i != index},
        'pose_inference_calls': 0, 'tracker_inference_calls': 0, 'production_adoption': False,
        'phase2_status': 'NOT PASSED', 'coordinate_correction': False, 'original_use_restrictions_changed': False,
        'limitations': ['Relative to visible manual 2D annotations, whose numeric uncertainty is not quantified.',
            'Source-pixel projection only, no 3D biomechanics or event accuracy.',
            'Angle agreement cannot establish skeleton alignment or subject identity; original holds remain.',
            'Conditional error summaries retain complete manual/prediction missing denominators; no accuracy/pass cutoff.']}
    for r in refs: bound(root, r)
    if sha(plan_path) != plan_sha: raise ValueError('Angle plan changed during assessment')
    output.mkdir()
    rows_path = output/'per_frame_angle_comparison.json'
    write(rows_path, {'status': 'complete_115_frame_manual_angle_comparison', 'plan_sha256': plan_sha, 'features': rows})
    result['per_frame_comparison'] = {'path': rows_path.relative_to(root).as_posix(), 'sha256': sha(rows_path)}
    write(output/'angle_assessment.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    result = assess(Path(__file__).resolve().parents[1], args.plan, args.output)
    print(json.dumps({name: data['streams'] for name,data in result['features'].items()}))
