"""Evaluator-only comparison with reviewed visible torso geometry, not segmentation GT."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.manual_keypoints import validate_manual_keypoints
from measure_feature_validity_evidence import read, sha, write, statistics, midrank_percentiles


TORSO = ('LEFT_SHOULDER', 'RIGHT_SHOULDER', 'LEFT_HIP', 'RIGHT_HIP')
SCORES = ('fb_error_px', 'movement_deviation_from_same_cohort_median_px',
          'radial_distance_from_current_cohort_median_px')


def visible_torso_proxy(frame):
    joints = {r['name']: r for r in frame['joints']}
    absent = [n for n in TORSO if n not in joints or joints[n]['status'] != 'visible'
              or joints[n]['x_px'] is None or joints[n]['y_px'] is None]
    if absent:
        return None, ['human_visible_torso_landmarks_unavailable:' + ','.join(absent)]
    points = np.asarray([[joints[n]['x_px'], joints[n]['y_px']] for n in TORSO], dtype=np.float32)
    hull = cv2.convexHull(points)
    if not np.isfinite(points).all() or cv2.contourArea(hull) <= 0:
        return None, ['human_torso_proxy_degenerate']
    return hull, []


def signed_distance(position, hull):
    if hull is None or position is None:
        return None
    return float(cv2.pointPolygonTest(hull, tuple(float(v) for v in position), True))


def pair_state(previous_distance, current_distance):
    if previous_distance is None or current_distance is None:
        return None
    previous, current = previous_distance >= 0, current_distance >= 0
    return ('both_inside' if previous and current else
            'previous_only' if previous else 'current_only' if current else 'neither_inside')


def support_summary(rows):
    return dict(feature_frame_rows=len(rows), contributing_frames=len({r['frame_index'] for r in rows}),
                inside=sum(r['signed_distance_px'] >= 0 for r in rows),
                outside=sum(r['signed_distance_px'] < 0 for r in rows),
                outside_fraction=sum(r['signed_distance_px'] < 0 for r in rows) / len(rows) if rows else None,
                outside_distance_px=statistics([max(0, -r['signed_distance_px']) for r in rows]),
                fb_error_px=statistics([r['fb_error_px'] for r in rows]))


def conditional_score_auc(rows, score):
    available = [r for r in rows if r[score] is not None]
    positive = [r for r in available if r['signed_distance_px'] < 0]
    negative = [r for r in available if r['signed_distance_px'] >= 0]
    ranks = midrank_percentiles([r[score] for r in available])
    if positive and negative:
        n = len(available)
        rank_sum = sum(rank * n + .5 for r, rank in zip(available, ranks, strict=True)
                       if r['signed_distance_px'] < 0)
        auc = (rank_sum - len(positive) * (len(positive) + 1) / 2) / (len(positive) * len(negative))
    else:
        auc = None
    return dict(positive='outside_visible_torso_proxy', negative='inside_visible_torso_proxy',
                total_positive=sum(r['signed_distance_px'] < 0 for r in rows),
                total_negative=sum(r['signed_distance_px'] >= 0 for r in rows),
                measured_positive=len(positive), measured_negative=len(negative),
                conditional_rank_auc_higher_is_outside=auc,
                warning_or_foreground_accuracy=False)


def render_sheet(clip, frames, indices, proxies, output, title):
    """Diagnostic display; the human polygon is evaluator-only."""
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 18)
    bold = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 21)
    width, height = clip['width'], clip['height']
    panels = []
    video = cv2.VideoCapture(clip['source_video']['path'])
    try:
        for i in range(clip['total_frames']):
            ok, image = video.read()
            if not ok:
                raise ValueError('Diagnostic video decode failure')
            if i not in indices:
                continue
            picture = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(picture)
            hull = proxies.get(i)
            if hull is not None:
                points = [tuple(p[0]) for p in hull]
                draw.line(points + [points[0]], fill='#3efa93', width=3)
            low = 0
            for feature in frames[i]['features']:
                is_low = feature['fb_per_frame_group'] == 0
                low += is_low
                color = '#40d9ff' if is_low else '#f49bba'
                x, y = feature['current_xy_px']
                draw.ellipse((x-3, y-3, x+3, y+3), fill=color, outline='white')
            panel = Image.new('RGB', (width, height + 145), '#111723')
            text = ImageDraw.Draw(panel)
            text.text((10, 8), f'{clip["pitch_id"]} | frame {i}', font=bold, fill='white')
            text.text((10, 37), f'{len(frames[i]["features"])} features; {low} lowest-FB quartile', font=font, fill='white')
            panel.paste(picture, (0, 70))
            label = 'Green: visible torso PROXY, not body mask' if hull is not None else 'Human torso proxy unavailable'
            text.text((10, height+80), label, font=font, fill='#3efa93' if hull is not None else 'white')
            text.text((10, height+105), 'Blue: lowest frame-FB quartile; pink: others', font=font, fill='white')
            panels.append(panel)
    finally:
        video.release()
    columns = min(3, len(panels))
    rows = (len(panels) + columns - 1) // columns
    sheet = Image.new('RGB', (width * columns, (height + 145) * rows + 45), '#111723')
    ImageDraw.Draw(sheet).text((10, 9), title, font=bold, fill='white')
    for index, panel in enumerate(panels):
        sheet.paste(panel, ((index % columns)*width, 45+(index // columns)*(height+145)))
    sheet.save(output)


def evaluate(root, plan_path, baseline, manual_path, output):
    if output.exists():
        raise FileExistsError(f'Fresh output required: {output}')
    data_path = root / 'feature_validity_measurements.json'
    data, plan = read(data_path), read(plan_path)
    producer = Path(__file__).with_name('measure_feature_validity_evidence.py')
    if sha(producer) != data['producer_code_sha256'] or sha(plan_path) != data['plan_sha256']:
        raise ValueError('Frozen producer or plan changed')
    parameters_hash = hashlib.sha256(json.dumps(plan['parameters'], sort_keys=True).encode()).hexdigest()
    if parameters_hash != data['parameters_sha256']:
        raise ValueError('Frozen parameters changed')
    if data['human_annotation_inputs'] or data['warning_predictions_generated'] or data['warning_thresholds'] is not None:
        raise ValueError('Not an annotation-free validity experiment')
    hashes = dict(data['source_hashes'])
    hashes.update({str(data_path): sha(data_path), str(manual_path): sha(manual_path)})
    if any(sha(p) != h for p, h in hashes.items()):
        raise ValueError('Frozen source changed')
    manual = read(manual_path)
    validate_manual_keypoints(manual)
    if manual['annotation_status'] != 'reviewed':
        raise ValueError('Reviewed human coordinates required')
    mpitch = manual['source_video']['pitch_id']
    proxies, proxy_reasons = {}, {}
    for frame in manual['frames']:
        proxy, reason = visible_torso_proxy(frame)
        proxies[frame['frame_index']] = proxy
        proxy_reasons[frame['frame_index']] = reason
    clips, all_rows, all_frames = [], [], []
    output.mkdir(parents=True)
    for clip in data['clips']:
        pitch, total = clip['pitch_id'], clip['total_frames']
        gtp = baseline / 'ground_truth' / pitch / 'ground_truth.json'
        gt = read(gtp)
        validate_ground_truth(gt)
        if gt['annotation_status'] != 'reviewed' or gt['review_profile'] != 'phase2_full_review':
            raise ValueError('Full qualitative human reference required')
        if gt['source_video']['sha256'] != clip['source_video']['sha256'] or gt['source_video']['total_frames'] != total:
            raise ValueError('Qualitative source binding mismatch')
        hashes[str(gtp)] = sha(gtp)
        has_manual = pitch == mpitch
        if has_manual and (manual['source_video']['sha256'] != clip['source_video']['sha256'] or
                           manual['source_video']['total_frames'] != total):
            raise ValueError('Manual source binding mismatch')
        rows, frames = [], []
        for frame in clip['frames']:
            index = frame['frame_index']
            hull = proxies.get(index) if has_manual else None
            prior_hull = proxies.get(index-1) if has_manual else None
            values = []
            for feature in frame['features']:
                distance = signed_distance(feature['current_xy_px'], hull)
                previous_distance = signed_distance(feature['previous_xy_px'], prior_hull)
                row = dict(pitch_id=pitch, frame_index=index, **feature,
                           signed_distance_px=distance,
                           outside_distance_image_height=max(0, -distance)/clip['height'] if distance is not None else None,
                           previous_signed_distance_px=previous_distance,
                           pair_support=pair_state(previous_distance, distance))
                all_rows.append(row)
                if distance is not None:
                    rows.append(row)
                    values.append(row)
            reasons = (proxy_reasons[index] if has_manual else ['no_reviewed_torso_coordinates_for_clip'])
            pair_missing = []
            if index == 0:
                pair_missing.append('no_previous_frame')
            elif prior_hull is None:
                pair_missing.append('previous_human_proxy_unavailable')
            if hull is None:
                pair_missing.append('current_human_proxy_unavailable')
            major = any(item.get('status', 'confirmed') == 'confirmed' and
                        item['start_frame'] <= index <= item['end_frame']
                        for item in gt['labels']['major_pose_failure_intervals'])
            current = dict(pitch_id=pitch, frame_index=index, total_features=len(frame['features']),
                           current_proxy_available=hull is not None, current_proxy_unavailable_reasons=reasons,
                           pair_proxy_available=not pair_missing, pair_proxy_unavailable_reasons=pair_missing,
                           seed_survival_ratio=frame['seed_survival_ratio'],
                           cohort_hull_expansion_ratio=frame['cohort_hull_expansion_ratio'],
                           human_major_failure=major, foreground_verified=False,
                           support=support_summary(values) if hull is not None else None)
            frames.append(current)
            all_frames.append(current)
        bins = {}
        for mode in ('per_frame', 'per_clip'):
            key = 'fb_' + mode + '_group'
            bins[mode] = {str(group): support_summary([r for r in rows if r[key] == group]) for group in range(4)}
        pair_counts = dict(Counter(r['pair_support'] for r in rows if r['pair_support'] is not None))
        score_auc = {name: conditional_score_auc(rows, name) for name in SCORES} if has_manual else None
        contexts = {}
        for major in (False, True):
            selected = {f['frame_index'] for f in frames if f['human_major_failure'] == major}
            contexts['major_failure' if major else 'outside_major_failure'] = support_summary(
                [r for r in rows if r['frame_index'] in selected]) if has_manual else None
        clips.append(dict(pitch_id=pitch, total_frames=total,
                          proxy_eligible_frames=sum(f['current_proxy_available'] for f in frames),
                          proxy_unavailable_frames=[f['frame_index'] for f in frames if not f['current_proxy_available']],
                          paired_proxy_eligible_transitions=sum(f['pair_proxy_available'] for f in frames),
                          total_transitions=total-1, numerical_feature_frame_rows=clip['numerical_feature_frame_rows'],
                          feature_rows_with_proxy=len(rows), feature_rows_without_proxy=clip['numerical_feature_frame_rows']-len(rows),
                          current_support=support_summary(rows) if has_manual else None,
                          pair_support_counts=pair_counts if has_manual else None,
                          quality_rank_support=bins if has_manual else None,
                          conditional_quality_score_auc=score_auc,
                          major_failure_context=contexts,
                          image_only_quality_scores=clip['quality_scores'], foreground_verified=False))
        uniform = {0, total//3, 2*total//3, total-1}
        render_sheet(clip, clip['frames'], uniform, proxies if has_manual else {},
                     output / f'{pitch}_uniform_review.png', 'Saved image features | no body segmentation or identity validation')
        if has_manual:
            indices = {0, total//3, total-1}
            for item in gt['labels']['major_pose_failure_intervals']:
                indices.update({max(0, item['start_frame']-1), (item['start_frame']+item['end_frame'])//2})
            render_sheet(clip, clip['frames'], indices, proxies,
                         output / f'{pitch}_proxy_review.png', 'Human visible torso PROXY | green polygon is not a full-body mask')
    if any(sha(p) != h for p, h in hashes.items()):
        raise ValueError('Evaluation source changed')
    result = dict(status='feature_support_proxy_comparison_only', total_frames=sum(c['total_frames'] for c in clips),
                  producer_code_sha256=data['producer_code_sha256'], evaluator_code_sha256=sha(__file__),
                  plan_sha256=data['plan_sha256'], parameters_sha256=data['parameters_sha256'], clips=clips,
                  human_reference_is_foreground_segmentation=False, warning_predictions_generated=False,
                  warning_thresholds=None, phase2_acceptance='in_progress',
                  limits=['Torso hull is an evaluator-only visible geometry proxy, not full-body or identity GT.',
                          'Outside torso proxy does not establish background, another person or wrong identity.',
                          'Rows across frames and features are correlated; conditional AUC is not independent accuracy.',
                          'No other clip has reviewed torso XY; missing reference is not a validation pass.',
                          'Quality ranks are descriptive; no accepted threshold, feature filtering or reseed.'])
    write(output / 'feature_support_summary.json', result)
    write(output / 'feature_support_rows.json', dict(rows=all_rows))
    write(output / 'frame_support_summary.json', dict(frames=all_frames))
    write(output / 'evidence_integrity_check.json', dict(status='passed', source_hashes=hashes,
          source_files_unchanged=True, human_inputs_evaluator_only=True, new_warning_predictions=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurement_root', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('baseline', type=Path)
    parser.add_argument('manual_reference', type=Path)
    parser.add_argument('output_root', type=Path)
    args = parser.parse_args()
    result = evaluate(args.measurement_root, args.plan, args.baseline, args.manual_reference, args.output_root)
    print(json.dumps(dict(status=result['status'], frames=result['total_frames'])))
