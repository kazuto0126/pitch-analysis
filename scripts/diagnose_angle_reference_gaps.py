"""Describe visible-reference 2D angle discrepancies without correcting a pose."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from itertools import permutations
import math
from pathlib import Path
import json

import assess_manual_feature_angles as previous
from check_movenet_compatibility import bound, sha, write

POINTS = ('A', 'B', 'C')
POLICY = {
    'scope': 'visible_manual_reference_counterfactual_angle_diagnosis_only',
    'features': list(previous.FEATURES), 'include_frame_zero': True,
    'angle': 'atan2_absolute_cross_dot_unsigned_0_to_180_degrees_source_pixels',
    'replacement': 'all_eight_subsets_of_three_visible_manual_points',
    'attribution': 'mean_absolute_error_reduction_over_all_six_permutations',
    'degenerate_hybrid': 'retain_original_error_but_null_entire_attribution',
    'negative_contributions': 'retained',
    'signed_ray_difference': 'manual_to_prediction_atan2_cross_dot_positive_clockwise_in_image_xy',
    'sensitivity': 'analytic_local_degrees_per_pixel_not_annotation_uncertainty',
    'raw_processed_comparison': 'exact_source_pixel_equality_with_numeric_distance_not_a_source_change_claim',
    'cusp': 'exact_collinearity_nulls_jacobian_not_finite_angle',
    'hidden_manual_points': 'never_used', 'coordinate_correction': False,
    'new_binary_warning': False, 'production_adoption': False,
    'pose_inference_calls': 0, 'tracker_inference_calls': 0,
    'three_dimensional_claim': False,
}
CODE_PATHS = {
    'diagnoser': 'scripts/diagnose_angle_reference_gaps.py',
    'tests': 'tests/test_angle_reference_gaps.py',
    'previous_assessor': 'scripts/assess_manual_feature_angles.py',
    **{k: v for k, v in previous.CODE_PATHS.items() if k not in ('evaluator', 'tests')},
}


def geometry(points):
    """A-B-C angle and its local derivatives; image x is right, y is down."""
    result = {'angle_deg': None, 'ray_lengths_px': [None, None],
        'point_jacobian_deg_per_px': None, 'point_sensitivity_deg_per_px': None,
        'angle_unavailable_reason': None, 'sensitivity_unavailable_reason': None}
    if not isinstance(points, (list, tuple)) or len(points) != 3 or not all(previous.finite_point(p) for p in points):
        result['angle_unavailable_reason'] = 'nonfinite_or_missing_points'
        result['sensitivity_unavailable_reason'] = 'angle_unavailable'
        return result
    a, b, c = points
    u, v = ([p[0]-b[0], p[1]-b[1]] for p in (a, c))
    lengths = [math.hypot(*ray) for ray in (u, v)]
    if not all(math.isfinite(x) for x in (*u, *v, *lengths)):
        result['angle_unavailable_reason'] = 'nonfinite_ray_geometry'
    else:
        result['ray_lengths_px'] = lengths
        if not all(lengths): result['angle_unavailable_reason'] = 'zero_length_ray'
    if result['angle_unavailable_reason']:
        result['sensitivity_unavailable_reason'] = 'angle_unavailable'
        return result
    un, vn = ([q/length for q in ray] for ray, length in zip((u, v), lengths))
    cross, dot = un[0]*vn[1]-un[1]*vn[0], un[0]*vn[0]+un[1]*vn[1]
    result['angle_deg'] = math.degrees(math.atan2(abs(cross), dot))
    if cross == 0:
        result['sensitivity_unavailable_reason'] = 'collinear_unsigned_angle_cusp'
        return result
    sign, factor = (1 if cross > 0 else -1), 180/math.pi
    ga = [sign*un[1]/lengths[0]*factor, -sign*un[0]/lengths[0]*factor]
    gc = [-sign*vn[1]/lengths[1]*factor, sign*vn[0]/lengths[1]*factor]
    jacobian = [ga, [-ga[0]-gc[0], -ga[1]-gc[1]], gc]
    if not all(math.isfinite(q) for point in jacobian for q in point):
        result['sensitivity_unavailable_reason'] = 'nonfinite_local_sensitivity'
    else:
        result['point_jacobian_deg_per_px'] = jacobian
        result['point_sensitivity_deg_per_px'] = [math.hypot(*point) for point in jacobian]
    return result


def counterfactual_attribution(pred3, manual3):
    """Symmetric reference-dependent bookkeeping, not a causal point diagnosis."""
    model, reference = geometry(pred3), geometry(manual3)
    hybrids = []
    valid_lists = all(isinstance(p, (list, tuple)) and len(p) == 3 for p in (pred3, manual3))
    for mask in range(8):
        points = [manual3[i] if mask & (1 << i) else pred3[i] for i in range(3)] if valid_lists else None
        g = geometry(points)
        error = abs(g['angle_deg']-reference['angle_deg']) if g['angle_deg'] is not None and reference['angle_deg'] is not None else None
        hybrids.append({'mask': mask, 'replaced_points': [POINTS[i] for i in range(3) if mask & (1 << i)],
            'angle_deg': g['angle_deg'], 'absolute_error_deg': error,
            'angle_unavailable_reason': g['angle_unavailable_reason']})
    result = {'point_order': list(POINTS), 'mask_convention': 'bit_i_replaces_point_i_with_visible_manual_coordinate',
        'model_geometry': model, 'manual_geometry': reference,
        'original_absolute_error_deg': hybrids[0]['absolute_error_deg'],
        'hybrids': hybrids, 'attribution': None,
        'unavailable_hybrid_masks': [h['mask'] for h in hybrids if h['absolute_error_deg'] is None]}
    if result['unavailable_hybrid_masks']: return result
    details = []
    for order in permutations(range(3)):
        mask, contributions = 0, [0., 0., 0.]
        for point in order:
            after = mask | (1 << point)
            contributions[point] = hybrids[mask]['absolute_error_deg']-hybrids[after]['absolute_error_deg']
            mask = after
        details.append({'order': [POINTS[i] for i in order], 'point_contributions_deg': contributions})
    values = [math.fsum(d['point_contributions_deg'][i] for d in details)/6 for i in range(3)]
    reduction = hybrids[0]['absolute_error_deg']-hybrids[7]['absolute_error_deg']
    result['attribution'] = {'point_contributions_deg': values, 'permutations': details,
        'sum_contributions_deg': math.fsum(values), 'error_reduction_deg': reduction,
        'efficiency_residual_deg': math.fsum(values)-reduction}
    return result


def _verify_previous_rows(data, view, manual, rows):
    """Reconstruct prior rows with their saved streams, preserving every frame."""
    total = data['target']['total_frames']
    if set(rows) != set(previous.FEATURES) or any(len(values) != total for values in rows.values()):
        raise ValueError('Incomplete prior angle frame denominator')
    features = {'pitch_id': data['target']['pitch_id'], 'frames': []}
    for i in range(total):
        frame = {'frame_index': i, 'features': {}}
        for name in previous.FEATURES:
            row = rows[name][i]
            frame['features'][name] = {'saved_values': {
                'base': row['streams_deg']['processed_base'],
                'feature_interpolated': row['streams_deg']['feature_interpolated'],
                'smoothed': row['streams_deg']['feature_smoothed']},
                'status': row['existing_review_status'], 'eligible': row['existing_eligible'],
                'saved_flags': row['original_feature_flags']}
        features['frames'].append(frame)
    if previous.compare_rows(data, view, features, manual) != rows:
        raise ValueError('Prior rows differ from bound manual or original pose sources')


def _ray_delta(manual, model, endpoint):
    if not all(previous.finite_point(p) for p in (manual[endpoint], manual[1], model[endpoint], model[1])): return None
    u, v = ([p[endpoint][j]-p[1][j] for j in range(2)] for p in (manual, model))
    lengths = [math.hypot(*ray) for ray in (u, v)]
    if not all(lengths) or not all(math.isfinite(x) for x in lengths): return None
    un, vn = ([q/length for q in ray] for ray, length in zip((u, v), lengths))
    return math.degrees(math.atan2(un[0]*vn[1]-un[1]*vn[0], un[0]*vn[0]+un[1]*vn[1]))


def diagnose_rows(data, view, manual, previous_rows):
    """Retain full source denominators; use only explicitly visible manual XY."""
    _verify_previous_rows(data, view, manual, previous_rows)
    width, height = (data['target'][k] for k in ('width', 'height'))
    result = {name: [] for name in previous.FEATURES}
    for i, (measured, reviewed, human) in enumerate(zip(data['frames'], view['frames'], manual['frames'], strict=True)):
        manual_joints = {j['name']: j for j in human['joints']}
        for feature, roles in previous.FEATURES.items():
            old, mapping = previous_rows[feature][i], data['important_joints']
            model, reference, comparisons, displacements = [], [], [], []
            for role in roles:
                name, saved = mapping[role], reviewed['focus_joints'][role]
                p, raw, human_point = saved['processed_landmark'], measured['joints'][name]['raw'], manual_joints[name]
                point = [p['x']*width, p['y']*height] if p['usable'] and p['x'] is not None and p['y'] is not None else None
                manual_xy = [human_point.get('x_px'), human_point.get('y_px')] if human_point['status'] == 'visible' else None
                model.append(point); reference.append(manual_xy)
                raw_xy = raw['xy_px'] if raw['finite'] else None
                paired = previous.finite_point(raw_xy) and previous.finite_point(point)
                comparisons.append({'role': role, 'landmark': name, 'raw_finite': raw['finite'],
                    'processed_finite': previous.finite_point(point),
                    'raw_equals_processed': raw_xy == point if paired else None,
                    'raw_to_processed_distance_px': math.dist(raw_xy, point) if paired else None})
                delta = [point[j]-manual_xy[j] for j in range(2)] if previous.finite_point(point) and previous.finite_point(manual_xy) else None
                displacements.append({'role': role, 'landmark': name, 'manual_status': human_point['status'],
                    'model_minus_manual_px': delta, 'distance_px': math.hypot(*delta) if delta is not None else None})
            g_model, g_manual = geometry(model), geometry(reference)
            reasons = list(old['manual_reference']['unavailable_reasons'])
            reasons.extend('processed_point_unavailable:'+role for role,p in zip(roles, model) if not previous.finite_point(p))
            if g_model['angle_unavailable_reason'] and not any(r.startswith('processed_point_unavailable:') for r in reasons):
                reasons.append('processed_'+g_model['angle_unavailable_reason'])
            comparable = old['signed_errors_deg']['processed_base'] is not None
            counterfactual = counterfactual_attribution(model, reference) if comparable else None
            result[feature].append({'frame_index': i, 'timestamp_ms': old['timestamp_ms'],
                'required_roles': list(roles), 'required_landmarks': list(old['required_landmarks']),
                'original_saved_base_angle_deg': old['streams_deg']['processed_base'],
                'original_saved_signed_error_deg': old['signed_errors_deg']['processed_base'],
                'original_model_states': {r: reviewed['focus_joints'][r]['model_state'] for r in roles},
                'existing_review_status': old['existing_review_status'], 'existing_eligible': old['existing_eligible'],
                'existing_major_hold': old['existing_major_hold'], 'original_feature_flags': old['original_feature_flags'],
                'manual_reference': old['manual_reference'], 'model_geometry': g_model, 'manual_geometry': g_manual,
                'point_displacements': displacements, 'raw_processed_comparison': comparisons,
                'signed_ray_direction_difference_deg': [_ray_delta(reference, model, endpoint) for endpoint in (0, 2)],
                'counterfactual': counterfactual, 'unavailable_reasons': reasons})
    return result


def summarize(rows):
    paired = [r for r in rows if r['original_saved_signed_error_deg'] is not None]
    attributed = [r for r in paired if r['counterfactual']['attribution'] is not None]
    return {'source_frame_denominator': len(rows), 'paired_manual_processed_frames': len(paired),
        'manual_or_processed_unavailable_frames': len(rows)-len(paired),
        'attributed_frames': len(attributed), 'degenerate_hybrid_frames': len(paired)-len(attributed),
        'original_saved_error': previous.error_stats([r['original_saved_signed_error_deg'] for r in paired]),
        'unavailable_reason_counts_nonexclusive': dict(Counter(v for r in rows for v in r['unavailable_reasons'])),
        'model_sensitivity_unavailable_reason_counts': dict(Counter(r['model_geometry']['sensitivity_unavailable_reason'] or 'available' for r in rows)),
        'original_major_hold_frames': sum(bool(r['existing_major_hold']) for r in rows),
        'original_eligible_counts': dict(Counter(str(r['existing_eligible']) for r in rows)),
        'point_contributions_deg': {p: {'count': len(attributed),
            'negative_count': sum(v < 0 for v in values),
            'mean': math.fsum(values)/len(values) if values else None,
            'minimum': min(values, default=None), 'maximum': max(values, default=None)}
            for i,p in enumerate(POINTS) for values in [[r['counterfactual']['attribution']['point_contributions_deg'][i] for r in attributed]]},
        'maximum_absolute_efficiency_residual_deg': max((abs(r['counterfactual']['attribution']['efficiency_residual_deg']) for r in attributed), default=None)}


def run(root, plan_path, output):
    """Revalidate the sealed assessment, then write a separate diagnosis only."""
    root, plan_path, output = (Path(p).resolve() for p in (root, plan_path, output))
    plan, plan_sha = previous.read(plan_path), sha(plan_path)
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('Exclusive new angle diagnosis directory required')
    if plan['status'] != 'frozen_before_angle_reference_gap_diagnosis' or plan['policy'] != POLICY:
        raise ValueError('Changed frozen angle diagnosis policy')
    if (any(type(plan[k]) is not int or plan[k] != 0 for k in ('pose_inference_budget','tracker_inference_budget')) or
            plan['production_adoption'] is not False or output != (root/plan['output_directory']).resolve()):
        raise ValueError('Changed frozen inference, adoption or output declarations')
    for role,path in CODE_PATHS.items():
        if plan['code'][role]['path'] != path: raise ValueError('Changed bound diagnosis code role')
    refs = [*plan['code'].values(), plan['parent_execution_plan'], plan['parent_assessment']]
    for ref in refs: bound(root, ref)
    if sha(__file__) != plan['code']['diagnoser']['sha256']: raise ValueError('Changed running angle diagnoser')
    old_path = bound(root, plan['parent_execution_plan'])
    old, old_sha = previous.read(old_path), sha(old_path)
    if (old['status'] != 'frozen_before_manual_angle_assessment' or old['policy'] != previous.POLICY or
            old['target_pitch_id'] != plan['target_pitch_id']): raise ValueError('Changed parent assessment policy or target')
    for role,path in previous.CODE_PATHS.items():
        if old['code'][role]['path'] != path: raise ValueError('Changed parent code role')
    refs.extend([*old['code'].values(), old['parent_fit_plan'], old['manual_coordinates'], old['reviewed_feature_quality']])
    for ref in refs: bound(root, ref)
    if sha(previous.__file__) != old['code']['evaluator']['sha256']: raise ValueError('Changed running parent assessor')
    fit_plan = previous.read(bound(root, old['parent_fit_plan']))
    measurements, views = previous.parent.verify_fit_plan(root, fit_plan)
    indices = [i for i,d in enumerate(measurements) if d['target']['pitch_id'] == plan['target_pitch_id']]
    if len(indices) != 1: raise ValueError('Unique target clip required')
    index = indices[0]; data, view = measurements[index], views[index]
    refs.extend(view['source_artifacts'].values())
    manual = previous.read(bound(root, old['manual_coordinates']))
    previous.validate_manual_keypoints(manual, source_video_path=bound(root, view['source_artifacts']['original_video']))
    if manual['annotation_status'] != 'reviewed': raise ValueError('Completed coordinate review required')
    feature_view = previous.read(bound(root, old['reviewed_feature_quality']))
    source = feature_view['source_artifacts']; refs.extend(source.values())
    if source['reviewed_reliability'] != fit_plan['clips'][index]['reviewed_reliability']:
        raise ValueError('Feature source differs from verified parent review')
    for ref in source.values(): bound(root, ref)
    with bound(root, source['features']).open(encoding='utf-8-sig', newline='') as stream: csv_rows = list(csv.DictReader(stream))
    rebuilt = previous.original_features.derive(view, csv_rows, previous.read(bound(root, source['metrics'])),
        previous.read(bound(root, source['feature_quality'])), previous.read(bound(root, view['source_artifacts']['video_metadata'])))
    if any(feature_view[k] != v for k,v in rebuilt.items()): raise ValueError('Feature source reconstruction differs')
    old_rows = previous.compare_rows(data, view, feature_view, manual)
    assessment = previous.read(bound(root, plan['parent_assessment']))
    refs.append(assessment['per_frame_comparison'])
    old_frame_data = previous.read(bound(root, assessment['per_frame_comparison']))
    if (old_frame_data != {'status': 'complete_115_frame_manual_angle_comparison', 'plan_sha256': old_sha, 'features': old_rows} or
            assessment['status'] != 'complete_manual_reference_angle_assessment' or assessment['plan_sha256'] != old_sha or
            assessment['policy'] != previous.POLICY or assessment['target'] != data['target'] or
            assessment['manual_source'] != old['manual_coordinates'] or assessment['manual_provenance'] != manual['provenance'] or
            assessment['features'] != {name: previous.summarize(values) for name,values in old_rows.items()} or
            assessment['phase2_status'] != 'NOT PASSED' or any(assessment[k] is not False for k in
                ('production_adoption', 'coordinate_correction', 'original_use_restrictions_changed')) or
            any(type(assessment[k]) is not int or assessment[k] != 0 for k in ('pose_inference_calls','tracker_inference_calls'))):
        raise ValueError('Sealed assessment differs from verified original sources or scope')
    rows = diagnose_rows(data, view, manual, old_rows)
    result = {'status': 'complete_angle_reference_gap_diagnosis', 'plan_sha256': plan_sha, 'policy': POLICY,
        'target': data['target'], 'parent_execution_plan': plan['parent_execution_plan'],
        'parent_assessment': plan['parent_assessment'], 'manual_source': old['manual_coordinates'],
        'manual_provenance': manual['provenance'], 'features': {k: summarize(v) for k,v in rows.items()},
        'pose_inference_calls': 0, 'tracker_inference_calls': 0, 'production_adoption': False,
        'coordinate_correction': False, 'new_binary_warning': False, 'original_use_restrictions_changed': False,
        'phase2_status': 'NOT PASSED', 'limitations': [
            'Visible manual 2D coordinates are a reviewed reference, not error-free physical truth.',
            'Hybrid poses are diagnostic constructions; contributions are not causal error attribution.',
            'Local derivatives are not human annotation error intervals; short projected rays amplify sensitivity.',
            'No hidden coordinates, corrected poses, events, 3D inference, ranking or new acceptance gate.']}
    previous.parent.verify_fit_plan(root, previous.read(bound(root, old['parent_fit_plan'])))
    for ref in refs: bound(root, ref)
    if sha(plan_path) != plan_sha: raise ValueError('Diagnosis plan changed during verification')
    output.mkdir()
    rows_path = output/'per_frame_angle_reference_gaps.json'
    write(rows_path, {'status': 'complete_source_frame_angle_reference_gaps', 'plan_sha256': plan_sha,
        'target': data['target'], 'policy': POLICY, 'features': rows})
    result['per_frame_diagnosis'] = {'path': rows_path.relative_to(root).as_posix(), 'sha256': sha(rows_path)}
    write(output/'diagnosis_summary.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path); parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[1], args.plan, args.output)['features']))
