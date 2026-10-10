"""Paired offline loss decomposition; executes the original selector, no inference."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys
from types import SimpleNamespace

from pitch_analysis.subject import MAJOR_JOINTS, PitcherSelector


STATES = ('both_selected', 'new_loss', 'gain', 'both_unselected')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, data):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def bound(root, ref):
    path = (root / ref['path']).resolve()
    if not path.is_relative_to(root) or sha(path) != ref['sha256']:
        raise ValueError('Changed or outside bound source: ' + ref['path'])
    return path


def transition(before, after):
    if before:
        return 'both_selected' if after else 'new_loss'
    return 'gain' if after else 'both_unselected'


def continue_rules(selector_type=PitcherSelector):
    """Locate existing continue branches from source, without duplicating rules."""
    path = Path(selector_type.select.__code__.co_filename)
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    method = next(n for c in tree.body if isinstance(c, ast.ClassDef) and c.name == selector_type.__name__
                  for n in c.body if isinstance(n, ast.FunctionDef) and n.name == 'select')
    rules = {}

    def walk(node, conditions):
        if isinstance(node, ast.If):
            for child in node.body:
                walk(child, conditions + [ast.unparse(node.test)])
            for child in node.orelse:
                walk(child, conditions + ['not (' + ast.unparse(node.test) + ')'])
        elif isinstance(node, ast.Continue):
            rules[node.lineno] = conditions[-1] if conditions else None
        else:
            for child in ast.iter_child_nodes(node):
                walk(child, conditions)
    walk(method, [])
    return rules


def traced_select(selector, poses, rules):
    """Observe executed exclusion branches; restore any prior Python trace."""
    previous_trace = sys.gettrace()
    code = selector.select.__func__.__code__
    exclusions = []
    admitted = []
    before = {'previous': selector.previous, 'gap': selector.gap}

    def trace(frame, event, arg):
        if frame.f_code is not code:
            return None
        if event == 'line' and frame.f_lineno in rules:
            exclusions.append({'candidate_index': frame.f_locals['index'],
                'original_source_line': frame.f_lineno,
                'executed_original_condition': rules[frame.f_lineno]})
        elif event == 'return':
            admitted.extend(row[1] for row in frame.f_locals.get('candidates', []))
        return trace

    try:
        sys.settrace(trace)
        selection = selector.select(poses)
    finally:
        sys.settrace(previous_trace)
    return {'selection': asdict(selection), 'state_before': before,
        'state_after': {'previous': selector.previous, 'gap': selector.gap},
        'candidate_exclusions': exclusions, 'admitted_candidates': admitted}


def candidate_measurements(poses, previous):
    """Descriptive original quantities only; no new pass/fail classifier."""
    result = []
    for index, pose in enumerate(poses):
        if len(pose) < 29:
            result.append({'candidate_index': index, 'landmarks': len(pose)})
            continue
        values = [min(pose[i].visibility, pose[i].presence) for i in MAJOR_JOINTS]
        hip = [(pose[23].x + pose[24].x) / 2, (pose[23].y + pose[24].y) / 2]
        shoulder_y = (pose[11].y + pose[12].y) / 2
        ankle_y = (pose[27].y + pose[28].y) / 2
        height = ankle_y - shoulder_y
        result.append({'candidate_index': index, 'major_joint_indices': list(MAJOR_JOINTS),
            'major_confidences': values, 'mean_major_confidence': sum(values) / len(values),
            'hip_xy': hip, 'shoulder_to_ankle_height': height,
            'hip_distance_to_previous': None if previous is None else math.dist(hip, previous[:2])})
    return result


def support_state(point):
    if not point['selected_raw']:
        return 'selected_point_missing'
    if not point['finite']:
        return 'nonfinite'
    if not point['gate_pass']:
        return 'below_existing_gate'
    return 'supported_gate' if point['input_supported_raw'] else 'gate_but_extrapolated'


def joint_partition(frames, name):
    counts, loss_reasons, gain_reasons = Counter(), Counter(), Counter()
    outside = Counter()
    lost, gained = [], []
    for frame in frames:
        row = frame['joints'][name]
        before, after = (support_state(row['arms'][a]) for a in ('image', 'crop'))
        state = transition(before == 'supported_gate', after == 'supported_gate')
        counts[state] += 1
        if state == 'new_loss':
            loss_reasons[after] += 1
            lost.append(frame['frame_index'])
            bounds = frame['crop_bounds_xyxy']
            x, y = row['arms']['image']['xy_px']
            in_crop = bounds is not None and bounds[0] <= x < bounds[2] and bounds[1] <= y < bounds[3]
            outside['image_prediction_inside_crop' if in_crop else 'image_prediction_outside_crop'] += 1
        elif state == 'gain':
            gain_reasons[before] += 1
            gained.append(frame['frame_index'])
    return {'denominator': len(frames), 'paired_supported_gate': {k: counts[k] for k in STATES},
        'lost_frames': lost, 'gained_frames': gained, 'loss_state_partition': dict(loss_reasons),
        'gain_baseline_state_partition': dict(gain_reasons),
        'lost_joint_image_prediction_geometry_not_ground_truth': dict(outside)}


def audit(root, manifest, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Exclusive output under analysis_results required')
    manifest = (root / manifest).resolve()
    if not manifest.is_relative_to(root):
        raise ValueError('Manifest outside workspace')
    parent = read(manifest)
    plan_path = bound(root, parent['execution'])
    plan = read(plan_path)
    evaluation_path = bound(root, parent['evaluation'])
    evaluated = read(evaluation_path)
    if (parent['status'] != 'completed_bounded_assisted_roi_cohort_not_adopted' or
            evaluated['plan_sha256'] != sha(plan_path) or
            evaluated['denominators'] != {'source_frames': 592, 'non_seed_frames': 587,
                                         'new_source_frames': 477, 'reused_source_frames': 115}):
        raise ValueError('Incomplete or changed source cohort')
    selector_ref = plan['producer_dependencies']['src/pitch_analysis/subject.py']
    bound(root, selector_ref)
    if Path(PitcherSelector.select.__code__.co_filename).resolve() != root / selector_ref['path']:
        raise ValueError('Different original selector loaded')
    rules = continue_rules()
    dependencies = {str(manifest.relative_to(root)): sha(manifest),
        parent['execution']['path']: parent['execution']['sha256'],
        parent['evaluation']['path']: parent['evaluation']['sha256'],
        selector_ref['path']: selector_ref['sha256']}
    reports, all_counts = [], Counter()
    for clip, declared in zip(evaluated['clips'], plan['clips'], strict=True):
        name, total = clip['pitch_id'], clip['target']['total_frames']
        if (name != declared['target']['pitch_id'] or
                [f['frame_index'] for f in clip['frames']] != list(range(total))):
            raise ValueError('Changed source order/timeline')
        pose_ref = clip['sources']['pose']
        measured = read(bound(root, pose_ref))
        dependencies[pose_ref['path']] = pose_ref['sha256']
        if measured['target'] != clip['target'] or len(measured['frames']) != total:
            raise ValueError('Crop measurement target mismatch')
        selector = PitcherSelector()
        traces = []
        for frame, source in zip(clip['frames'], measured['frames'], strict=True):
            if (frame['frame_index'] != source['frame_index'] or
                    frame['selection']['crop'] != source['selection'] or
                    frame['crop_bounds_xyxy'] != source['crop_bounds_xyxy']):
                raise ValueError('Saved evaluation and pose receipt differ')
            poses = [[SimpleNamespace(**point) for point in candidate]
                     for candidate in source['full_image_candidates']]
            before = selector.previous
            trace = traced_select(selector, poses, rules)
            if trace['selection'] != source['selection']:
                raise ValueError('Original selector replay differs')
            state = transition(frame['selection']['image']['status'] == 'selected',
                               frame['selection']['crop']['status'] == 'selected')
            if frame['frame_index'] != 0:
                traces.append({'frame_index': frame['frame_index'], 'transition': state,
                    'inference_status': source['inference_status'], 'crop_candidate_count': len(poses),
                    'image_selection': frame['selection']['image'], **trace,
                    'candidate_measurements': candidate_measurements(poses, before)})
        counts = Counter(f['transition'] for f in traces)
        all_counts.update(counts)
        losses = [f for f in traces if f['transition'] == 'new_loss']
        categories = Counter('backend_no_candidate' if f['crop_candidate_count'] == 0 else
            'selector_ambiguous' if f['selection']['status'] == 'ambiguous' else 'selector_rejected' for f in losses)
        reports.append({'pitch_id': name, 'kind': clip['kind'], 'source_frames': total,
            'non_seed_frames': len(traces), 'selection_transitions': {k: counts[k] for k in STATES},
            'new_loss_categories': dict(categories), 'new_loss_frames': [f['frame_index'] for f in losses],
            'gained_frames': [f['frame_index'] for f in traces if f['transition'] == 'gain'],
            'joint_partitions': {j: joint_partition(clip['frames'][1:], j) for j in clip['frames'][0]['joints']},
            'frame_diagnostics': traces})
    if sum(all_counts.values()) != 587:
        raise ValueError('Fixed paired denominator changed')
    for name, digest in dependencies.items():
        bound(root, {'path': name, 'sha256': digest})
    report = {'status': 'complete_offline_paired_loss_audit', 'parent_result_manifest_sha256': sha(manifest),
        'audit_code_sha256': sha(__file__), 'source_bindings': dependencies,
        'source_frames': 592, 'non_seed_frames': 587, 'original_selector_replayed_frames': 592,
        'selection_transitions': {k: all_counts[k] for k in STATES}, 'clips': reports,
        'tracker_inference_calls': 0, 'pose_inference_calls': 0, 'human_annotations_modified': False,
        'new_warning_policy': None, 'phase2_automatic_reliability': 'NOT PASSED',
        'limits': ['Selection/support loss is availability, not anatomical accuracy.',
            'IMAGE prediction outside crop is a prediction proxy, not manual ground truth.',
            'Executed original exclusion branches diagnose rejection; they do not establish the backend failure cause.',
            'Original confidence/geometry/continuity rules are observed, not changed.',
            'No new model, crop strategy, fallback, correction, interpolation or human label is produced.']}
    output.mkdir(parents=True)
    write(output / 'paired_loss_audit.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = audit(args.root, args.manifest, args.output)
    print(json.dumps({k: result[k] for k in ('source_frames', 'non_seed_frames', 'selection_transitions', 'pose_inference_calls')}))
