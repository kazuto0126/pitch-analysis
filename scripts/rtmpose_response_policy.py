"""Frozen maximum native-response deficit calibration; no IO or inference."""
from __future__ import annotations
import math
from numbers import Real
from heavy_information_policy import PITCH_IDS, ROLES, decision


def finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def calibrate(training_clips, query_pitch_id, role):
    ids = [c['pitch_id'] for c in training_clips]
    if role not in ROLES or query_pitch_id not in PITCH_IDS or len(ids) != 4 or set(ids) != set(PITCH_IDS)-{query_pitch_id}:
        raise ValueError('Exactly the four other complete clips required')
    values, trace = [], []
    for clip in training_clips:
        if [r['frame_index'] for r in clip['rows']] != list(range(len(clip['rows']))):
            raise ValueError('Incomplete training timeline')
        for row in clip['rows']:
            label, value = row['canonical_label'], row['response_deficit']
            if label not in ('reliable', 'unreliable', 'not_observable', 'uncertain'):
                raise ValueError('Unknown canonical label')
            reason = 'seed' if row['frame_index'] == 0 else 'other_label' if label != 'reliable' else 'insufficient_evidence' if not finite(value) else None
            trace.append({'pitch_id': clip['pitch_id'], 'frame_index': row['frame_index'], 'label': label, 'excluded_reason': reason})
            if reason is None: values.append(float(value))
    return {'schema': 'rtmpose_response_maximum_v1', 'status': 'calibrated' if values else 'failed',
        'query_pitch_id': query_pitch_id, 'role': role, 'training_pitch_ids': sorted(ids),
        'threshold': max(values) if values else None, 'used_reliable_rows': len(values),
        'reason': None if values else 'no_finite_reliable_training_response', 'trace': trace}


def apply(rows, numeric):
    query = numeric['query_pitch_id']
    if (numeric['schema'] != 'rtmpose_response_maximum_v1' or query not in PITCH_IDS or
            numeric['role'] not in ROLES or len(numeric['training_pitch_ids']) != 4 or
            set(numeric['training_pitch_ids']) != set(PITCH_IDS)-{query} or
            numeric['status'] not in ('calibrated', 'failed') or
            (numeric['status'] == 'calibrated' and not finite(numeric['threshold'])) or
            (numeric['status'] == 'failed' and numeric['threshold'] is not None)):
        raise ValueError('Invalid fixed numeric calibration')
    if [r['frame_index'] for r in rows] != list(range(len(rows))):
        raise ValueError('Incomplete query timeline')
    results = []
    for row in rows:
        i, value = row['frame_index'], row['response_deficit']
        if value is not None and not finite(value): raise ValueError('Invalid native response deficit')
        warning = False
        if i == 0: status, review = 'seed_excluded', False
        elif numeric['status'] != 'calibrated': status, review = 'calibration_failed', None
        elif value is None: status, review = 'insufficient_evidence', None
        else:
            warning = value > numeric['threshold']
            status, review = ('warning' if warning else 'no_warning'), warning
        results.append({'frame_index': i, 'response_deficit': value, 'threshold': numeric['threshold'],
            'status': status, 'review_required': review, 'evaluated_warning': warning, 'effectiveness_eligible': i != 0})
    return results
