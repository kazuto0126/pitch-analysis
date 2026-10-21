"""Associate saved eligible boxes after one explicit operator seed.

No detector, image, pose, GT or file access occurs here. Candidate eligibility is
an input fact from the previous run; it is never recomputed from model scores.
"""
from __future__ import annotations

from math import isfinite
from numbers import Real
import re

TRACK_POLICY = 'operator_seeded_mutual_unique_max_iou_v1'


def _index(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validated_frames(records):
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError('A nonempty complete saved-box timeline is required')
    eligible_frames = []
    previous_time = None
    for index, record in enumerate(records):
        if not isinstance(record, dict) or not _index(record.get('frame_index')) or record['frame_index'] != index:
            raise ValueError('Saved boxes require a complete ordered zero-based timeline')
        timestamp = record.get('timestamp_ms')
        if (not isinstance(timestamp, Real) or isinstance(timestamp, bool) or not isfinite(timestamp)
                or index == 0 and timestamp != 0 or previous_time is not None and timestamp <= previous_time):
            raise ValueError('Saved timestamps must be finite, start at zero and increase')
        previous_time = timestamp
        if not isinstance(record.get('decoded_bgr_sha256'), str) or not re.fullmatch('[a-f0-9]{64}', record['decoded_bgr_sha256']):
            raise ValueError('A saved decoded-pixel SHA256 is required for every frame')
        candidates = record.get('candidates')
        if not isinstance(candidates, (list, tuple)):
            raise ValueError('Every saved frame must declare its candidate list')
        seen_indices, seen_boxes, eligible = set(), set(), []
        for candidate in candidates:
            if not isinstance(candidate, dict) or not _index(candidate.get('output_index')):
                raise ValueError('Candidate output indices must be nonnegative integers')
            output_index = candidate['output_index']
            if output_index in seen_indices:
                raise ValueError('Duplicate candidate output index')
            seen_indices.add(output_index)
            if not isinstance(candidate.get('eligible'), bool):
                raise ValueError('Saved eligibility must be an explicit boolean')
            if not candidate['eligible']:
                continue
            box = candidate.get('bbox_original_xyxy_px')
            if (not isinstance(box, (list, tuple)) or len(box) != 4
                    or any(not isinstance(v, Real) or isinstance(v, bool) or not isfinite(v) for v in box)
                    or box[2] <= box[0] or box[3] <= box[1]):
                raise ValueError('An eligible candidate requires a finite positive-area box')
            key = tuple(box)
            if key in seen_boxes:
                raise ValueError('Duplicate eligible box geometry')
            seen_boxes.add(key)
            eligible.append({'output_index': output_index, 'box': list(box)})
        eligible_frames.append(eligible)
    return eligible_frames


def _iou(first, second):
    overlap_width = max(0., min(first[2], second[2]) - max(first[0], second[0]))
    overlap_height = max(0., min(first[3], second[3]) - max(first[1], second[1]))
    intersection = overlap_width * overlap_height
    first_area = (first[2] - first[0]) * (first[3] - first[1])
    second_area = (second[2] - second[0]) * (second[3] - second[1])
    union = first_area + second_area - intersection
    if not all(isfinite(v) for v in (intersection, first_area, second_area, union)) or union <= 0:
        raise ValueError('Box geometry cannot be represented as a finite IoU')
    return intersection / union


def associate_saved_boxes(records, *, seed_output_index: int) -> list[dict]:
    """Run the fixed mutual-unique-max positive-IoU policy exactly once.

    All adjacent matrices are retained, even after a terminal break. No later
    row can reacquire a subject. A link is geometric evidence, not identity GT.
    """
    eligible_frames = _validated_frames(records)
    if not _index(seed_output_index):
        raise ValueError('The operator seed must be a nonnegative output index')
    seeds = [box for box in eligible_frames[0] if box['output_index'] == seed_output_index]
    if len(seeds) != 1:
        raise ValueError('The operator seed must name one eligible first-frame candidate')
    selected_previous = None
    broken_at = None
    results = []
    for index, (record, current) in enumerate(zip(records, eligible_frames, strict=True)):
        previous = eligible_frames[index - 1] if index else []
        matrix = [[_iou(a['box'], b['box']) for b in current] for a in previous]
        chosen, match_iou = None, None
        if index == 0:
            chosen = seeds[0]
            status, reason = 'seeded', 'operator_confirmed_seed'
        elif broken_at is not None:
            status, reason = 'after_track_break', 'terminal_track_break'
        else:
            row_index = next(i for i, box in enumerate(previous) if box['output_index'] == selected_previous)
            row = matrix[row_index]
            maximum = max(row, default=0.)
            winners = [i for i, value in enumerate(row) if value == maximum]
            if maximum <= 0:
                status, reason = 'track_break_no_overlap', 'no_positive_overlap'
            elif len(winners) != 1:
                status, reason = 'track_break_tie', 'tied_current_candidates'
            else:
                column_index = winners[0]
                column = [values[column_index] for values in matrix]
                reverse_max = max(column)
                reverse_winners = [i for i, value in enumerate(column) if value == reverse_max]
                if len(reverse_winners) != 1:
                    status, reason = 'track_break_tie', 'tied_previous_candidates'
                elif reverse_winners[0] != row_index:
                    status, reason = 'track_break_non_mutual', 'current_prefers_another_previous_box'
                else:
                    chosen, match_iou = current[column_index], maximum
                    status, reason = 'linked', 'mutual_unique_maximum_overlap'
            if chosen is None:
                broken_at = index
        results.append({
            'track_policy': TRACK_POLICY, 'frame_index': record['frame_index'],
            'timestamp_ms': record['timestamp_ms'], 'decoded_bgr_sha256': record['decoded_bgr_sha256'],
            'status': status, 'reason': reason,
            'selected_output_index': chosen['output_index'] if chosen else None,
            'selected_bbox_xyxy_px': list(chosen['box']) if chosen else None,
            'previous_selected_output_index': selected_previous,
            'previous_eligible_output_indices': [box['output_index'] for box in previous],
            'current_eligible_output_indices': [box['output_index'] for box in current],
            'eligible_count': len(current), 'iou_matrix': matrix,
            'match_iou': match_iou, 'break_frame_index': broken_at,
        })
        selected_previous = chosen['output_index'] if chosen else None
    return results
