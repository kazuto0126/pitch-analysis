"""Evaluate sealed chain cues, without assigning errors to individual joints."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
from evaluate_joint_disagreement import expand_labels
from pitch_analysis.ground_truth import validate_ground_truth

CHAINS = {'arm_chain': ('throwing_shoulder', 'throwing_elbow', 'throwing_wrist'),
          'lead_leg_chain': ('lead_hip', 'lead_knee', 'lead_ankle')}
ANCHORS = ('throwing_shoulder', 'lead_hip')
LABELS = ('reliable', 'unreliable', 'uncertain', 'not_observable')
STATES = ('warning', 'within_reference_range', 'insufficient_evidence', 'seed_excluded')
SCREENS = ('old_jump_chain', 'previous_joint_cues_as_chain', 'new_chain_geometry', 'additive_chain_cues')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def chain_target(labels):
    if len(labels) != 3 or any(label not in LABELS for label in labels):
        raise ValueError('Chain target requires exactly three valid member labels')
    if 'unreliable' in labels:
        return 'unreliable'
    if all(label == 'reliable' for label in labels):
        return 'reliable'
    return 'uncertain' if 'uncertain' in labels else 'not_observable'


def score(rows, screen):
    if screen not in SCREENS:
        raise ValueError('Unknown chain screen')
    human, confusion = Counter(), dict.fromkeys(('tp', 'fn', 'fp', 'tn'), 0)
    excluded = dict.fromkeys(('uncertain', 'not_observable'), 0)
    insufficient = dict.fromkeys(LABELS, 0)
    warnings = 0
    for row in rows:
        label, state = row['target'], row['state']
        if label not in LABELS or state not in STATES[:-1] or type(row[screen]) is not bool:
            raise ValueError('Unknown chain target/state or non-boolean cue')
        warning = row[screen]
        human[label] += 1
        warnings += warning
        insufficient[label] += state == 'insufficient_evidence'
        if label in excluded:
            excluded[label] += warning
        else:
            confusion[('tp' if warning else 'fn') if label == 'unreliable' else ('fp' if warning else 'tn')] += 1
    positives, negatives = human['unreliable'], human['reliable']
    tp, fp = confusion['tp'], confusion['fp']
    return {'non_seed_chain_rows': len(rows), 'human_label_counts': {s: human[s] for s in LABELS},
            'human_positive': positives, 'human_negative': negatives,
            'human_excluded': human['uncertain'] + human['not_observable'], **confusion,
            'precision': tp / (tp + fp) if tp + fp else None,
            'recall': tp / positives if positives else None, 'fpr': fp / negatives if negatives else None,
            'warning_total': warnings, 'warning_on_excluded': excluded,
            'new_geometry_insufficient_by_target': insufficient}


def summarize(rows):
    return {'non_seed_chain_rows': len(rows), 'evidence_state_counts': dict(Counter(r['state'] for r in rows)),
            'screens': {s: score(rows, s) for s in SCREENS},
            'anchor_label_context': {key: {'rows': len(part), 'new_geometry': score(part, 'new_chain_geometry')}
                for key in sorted({r['anchor_labels'] for r in rows})
                for part in [[r for r in rows if r['anchor_labels'] == key]]},
            'member_model_state_context': {key: {'rows': len(part), 'new_geometry': score(part, 'new_chain_geometry')}
                for key in sorted({r['member_states'] for r in rows})
                for part in [[r for r in rows if r['member_states'] == key]]}}


def make_rows(data, canonical, pose, previous):
    name, total = data['target']['pitch_id'], data['target']['total_frames']
    mapping = data['important_joints']
    roles = tuple(role for chain in CHAINS.values() for role in chain)
    if (pose['pitch_id'] != name or pose['total_frames'] != total or pose['important_joints'] != mapping or
            pose['frame_indices'] != list(range(total)) or previous['target'] != data['target'] or
            previous['important_joints'] != mapping or
            [f['frame_index'] for f in data['frames']] != list(range(total)) or
            [f['frame_index'] for f in previous['frames']] != list(range(total))):
        raise ValueError('Changed chain/previous/pose identity or full frame denominator')
    labels = {r: expand_labels(canonical['labels'][r + '_reliability'], total) for r in roles}
    original = {r: pose['joints'][mapping[r]] for r in roles}
    for joint in original.values():
        if (len(joint['frame_states']) != total or
                any(s not in ('observed', 'interpolated', 'missing') for s in joint['frame_states']) or
                joint['frame_to_frame_jump']['candidate_count'] != len(set(joint['frame_to_frame_jump']['candidate_frames'])) or
                any(type(i) is not int or not 0 <= i < total for i in joint['frame_to_frame_jump']['candidate_frames'])):
            raise ValueError('Changed original state or jump context')
    rows = {chain: [] for chain in CHAINS}
    for frame, before in zip(data['frames'], previous['frames'], strict=True):
        i = frame['frame_index']
        if frame['effectiveness_eligible'] is not (i != 0):
            raise ValueError('Changed seed eligibility')
        for chain, members in CHAINS.items():
            cue = frame['chains'][chain]
            state, warning = cue['evidence_state'], cue['warning']
            if (state not in STATES or type(warning) is not bool or warning is not (state == 'warning') or
                    (state == 'seed_excluded') != (i == 0)):
                raise ValueError('Changed chain state or joint-promoted warning')
            for role in set(members) | set(ANCHORS):
                if (cue['dependency_raw_states'][role] != original[role]['frame_states'][i] or
                        before['joints'][role]['raw_model_state'] != original[role]['frame_states'][i]):
                    raise ValueError('Changed source model state')
            if i == 0:
                continue
            jump = any(i in original[r]['frame_to_frame_jump']['candidate_frames'] for r in members)
            old_cue = any(before['joints'][r]['warning'] for r in members)
            member_labels = [labels[r][i] for r in members]
            rows[chain].append({'frame_index': i, 'target': chain_target(member_labels), 'state': state,
                'old_jump_chain': jump, 'previous_joint_cues_as_chain': old_cue, 'new_chain_geometry': warning,
                'additive_chain_cues': jump or old_cue or warning,
                'anchor_labels': '|'.join(r + '=' + labels[r][i] for r in ANCHORS),
                'member_states': '|'.join(r + '=' + original[r]['frame_states'][i] for r in members),
                'member_labels': dict(zip(members, member_labels, strict=True))})
    return rows


def verify_receipt(data, application, plan_sha, training, *, sidecar=False):
    expected = 'sealed_chain_warning_sidecar' if sidecar else 'sealed_chain_warning_trial'
    if (data['status'] != expected or data['policy'] != application['policy'] or
            data['plan_sha256'] != plan_sha or data['producer_sha256'] != application['code']['producer_code']['sha256'] or
            data['calibration_artifact'] != application['calibration_artifact'] or data['human_training_inputs'] != training or
            data['supervised_calibration_used'] is not True or data['application_human_annotation_inputs'] != [] or
            any(data[k] is not False for k in ('production_adoption', 'major_warning_generated', 'joint_warning_generated')) or
            any(type(data[k]) is not int or data[k] != 0 for k in ('pose_inference_calls', 'tracker_inference_calls'))):
        raise ValueError('Unbound or adopted/joint-promoted/annotation-reading chain receipt')
    if not sidecar and (data['source_frames'] != 592 or data['non_seed_frames'] != 587):
        raise ValueError('Changed complete cohort denominator')


def evaluate(root, plan_path, run_path, output):
    import measure_chain_reliability as producer
    import calibrate_joint_reliability as previous_producer
    import evaluate_supervised_joint_warnings as previous_evaluator

    root, plan_path, run_path, output = (Path(p).resolve() for p in (root, plan_path, run_path, output))
    if output.exists() or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Exclusive new evaluation directory required')
    plan, run = read(plan_path), read(run_path)
    plan_sha, run_sha = sha(plan_path), sha(run_path)
    if plan['status'] != 'frozen_before_chain_warning_evaluation':
        raise ValueError('Unfrozen chain evaluation')
    application_path = bound(root, plan['producer_plan'])
    application = read(application_path)
    measurements, artifact = producer.verify_apply_plan(root, application)
    if producer.CHAINS != CHAINS or producer.ANCHORS != ANCHORS or producer.STATES != STATES:
        raise ValueError('Changed chain scope, anchor or state policy')
    for ref in [*plan['code'].values(), *application['code'].values(), *run['clips']]: bound(root, ref)
    if sha(__file__) != plan['code']['evaluator']['sha256'] or sha(producer.__file__) != application['code']['producer_code']['sha256']:
        raise ValueError('Unbound running code')
    verify_receipt(run, application, sha(application_path), artifact['human_training_inputs'])
    previous_application_path = bound(root, plan['previous_application_plan'])
    if plan['previous_application_plan'] != application['parent_apply_plan']:
        raise ValueError('Changed previous supervision comparison cohort')
    previous_application = read(previous_application_path)
    _, previous_artifact = previous_producer.verify_apply_plan(root, previous_application)
    prior_path = bound(root, plan['previous_warning_run'])
    prior = read(prior_path)
    previous_evaluator.verify_receipt(prior, previous_application, sha(previous_application_path),
        previous_application['calibration_artifact'], previous_artifact['human_training_inputs'])
    expected = producer.apply_reference(measurements, artifact)
    names = [d['target']['pitch_id'] for d in measurements]
    if (len(names) != 5 or sum(d['target']['total_frames'] for d in measurements) != 592 or
            names != [c['target']['pitch_id'] for c in plan['clips']] or
            names != [c['pitch_id'] for c in run['clips']] or names != [c['pitch_id'] for c in prior['clips']]):
        raise ValueError('Changed five-clip chain evaluation cohort')
    reports, per_frame, pooled = [], [], {chain: [] for chain in CHAINS}
    role_counts = {r: Counter() for members in CHAINS.values() for r in members}
    refs = [plan['producer_plan'], plan['previous_application_plan'], plan['previous_warning_run'],
        *plan['code'].values(), *application['code'].values(), *run['clips'], *prior['clips']]
    for setup, receipt, old_receipt, recomputed, fold, previous_fold, source in zip(plan['clips'], run['clips'], prior['clips'],
            expected, artifact['folds'], previous_artifact['folds'], artifact['measurement_sources'], strict=True):
        data, before = read(bound(root, receipt)), read(bound(root, old_receipt))
        verify_receipt(data, application, sha(application_path), fold['human_training_inputs'], sidecar=True)
        previous_evaluator.verify_receipt(before, previous_application, sha(previous_application_path),
            previous_application['calibration_artifact'], previous_fold['human_training_inputs'], sidecar=True)
        if data['source_reference'] != source or setup['target'] != recomputed['target']:
            raise ValueError('Chain source reference or evaluation target differs from fitted evidence')
        for key, value in recomputed.items():
            if data[key] != value:
                raise ValueError('Saved chain cue differs from sealed numeric reference')
        for ref in setup['sources'].values(): bound(root, ref)
        refs.extend(setup['sources'].values())
        video = bound(root, setup['sources']['video'])
        canonical = read(bound(root, setup['sources']['canonical_review']))
        validate_ground_truth(canonical, source_video_path=video)
        if (canonical['annotation_status'] != 'reviewed' or canonical['review_profile'] != 'phase2_full_review' or
                tuple(canonical['source_video'][k] for k in ('pitch_id', 'total_frames', 'sha256')) !=
                (setup['target']['pitch_id'], setup['target']['total_frames'], setup['sources']['video']['sha256'])):
            raise ValueError('Incomplete query review or source mismatch')
        pose = read(bound(root, setup['sources']['pose_reliability']))
        rows = make_rows(data, canonical, pose, before)
        reports.append({'pitch_id': data['target']['pitch_id'], 'chains': {c: summarize(r) for c, r in rows.items()}})
        per_frame.append({'pitch_id': data['target']['pitch_id'], 'chains': rows})
        for chain, values in rows.items():
            pooled[chain].extend(values)
            for row in values:
                for role, label in row['member_labels'].items(): role_counts[role][label] += 1
    if sum(len(rows) for rows in pooled.values()) != 1174 or sum(sum(c.values()) for c in role_counts.values()) != 3522:
        raise ValueError('Changed chain or original six-member denominators')
    for ref in refs: bound(root, ref)
    producer.verify_apply_plan(root, application)
    if sha(plan_path) != plan_sha or sha(run_path) != run_sha:
        raise ValueError('Chain evaluation inputs changed')
    result = {'status': 'complete_chain_warning_evaluation', 'plan_sha256': plan_sha, 'run_sha256': run_sha,
        'source_frames': 592, 'saved_chain_rows': 1184, 'non_seed_chain_rows': 1174,
        'non_seed_member_joint_rows': 3522, 'member_human_label_counts': {r: dict(c) for r, c in role_counts.items()},
        'supervised_calibration_used': True, 'clips': reports, 'aggregate': {c: summarize(r) for c, r in pooled.items()},
        'pose_inference_calls': 0, 'tracker_inference_calls': 0, 'production_adoption': False,
        'major_warning_generated': False, 'joint_warning_generated': False, 'phase2_status': 'NOT PASSED',
        'interpretation': 'Chain review cues only; no endpoint attribution, occlusion, identity or major correction claim. Full denominators and query anchor contexts retained. Development cross-validation.'}
    output.mkdir()
    rows_path = output / 'per_frame_chain_evaluation.json'
    write(rows_path, {'status': 'complete_chain_target_rows', 'plan_sha256': plan_sha,
        'run_sha256': run_sha, 'non_seed_chain_rows': 1174, 'clips': per_frame})
    result['per_frame_evaluation'] = {'path': rows_path.relative_to(root).as_posix(), 'sha256': sha(rows_path)}
    write(output / 'chain_warning_evaluation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'run', 'output'): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = evaluate(Path(__file__).resolve().parents[1], args.plan, args.run, args.output)
    print(json.dumps({c: r['screens']['new_chain_geometry'] for c, r in result['aggregate'].items()}))
