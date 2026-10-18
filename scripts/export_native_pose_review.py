"""Export source-bound cached native poses without estimation or quality gating."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path

import numpy as np
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints
from pitch_analysis.native_pose_io import BoundReader, read_json, reference, write_dataset, write_json
from pitch_analysis.native_pose_sources import load_cached_sources
from pitch_analysis.native_pose_review import summarize_native, write_native_overlay


def error_stats(values):
    return {'n': len(values), 'mean_px': float(np.mean(values)) if values else None,
            'median_px': float(np.median(values)) if values else None,
            'p95_px': float(np.percentile(values, 95)) if values else None,
            'maximum_px': max(values) if values else None}


def coordinate_comparison(sources, manual, original_full_gt):
    """Human XY evaluates coordinates; Full qualitative labels supply context only."""
    full, native = sources['mediapipe'], sources['rtmpose']
    source = manual['source_video']; count = source['total_frames']
    for item in (full, native):
        manifest = item.manifest
        if (len(item) != count or manifest['pitch_id'] != source['pitch_id'] or
                manifest['video']['sha256'] != source['sha256'] or
                manifest['image_size'] != manual['image_size']):
            raise ValueError('Human/source coordinate binding differs')
    if [f['frame_index'] for f in manual['frames']] != list(range(count)):
        raise ValueError('Human coordinate timeline is incomplete')
    gt_source = original_full_gt['source_video']
    if any(gt_source[k] != source[k] for k in ('pitch_id', 'sha256', 'total_frames')):
        raise ValueError('Original Full context is from a different source')
    major = set()
    for interval in original_full_gt['labels']['major_pose_failure_intervals']:
        if interval['status'] != 'confirmed':
            continue
        first, last = interval['start_frame'], interval['end_frame']
        if not 0 <= first <= last < count:
            raise ValueError('Original major context is outside the timeline')
        major.update(range(first, last + 1))
    rows = []
    for i, frame in enumerate(manual['frames']):
        human = {j['name']: j for j in frame['joints']}
        a = {j['name']: j for j in full.read_frame(i).to_dict()['landmarks']}
        b = {j['name']: j for j in native.read_frame(i).to_dict()['landmarks']}
        if set(human) != set(JOINT_NAMES):
            raise ValueError('Manual coordinate joint set differs')
        for joint in JOINT_NAMES:
            point = human[joint]; visible = point['status'] == 'visible'
            if point['status'] not in ('visible', 'not_observable', 'uncertain'):
                raise ValueError('Unreviewed human coordinates cannot become reference')
            errors = {}
            for key, predicted in (('mediapipe', a[joint]), ('rtmpose', b[joint])):
                xy = [predicted['x_px'], predicted['y_px']]
                finite = all(v is not None and math.isfinite(v) for v in xy)
                errors[key] = math.hypot(xy[0] - point['x_px'], xy[1] - point['y_px']) if visible and finite else None
            rows.append({'frame_index': i, 'joint': joint, 'human_status': point['status'],
                         'human_xy_px': [point['x_px'], point['y_px']] if visible else None,
                         'mediapipe_error_px': errors['mediapipe'], 'rtmpose_error_px': errors['rtmpose'],
                         'effectiveness_eligible': i != 0, 'original_full_major_hold': i in major})

    def summarize(selected):
        result = {}
        for joint in JOINT_NAMES:
            subset = [r for r in selected if r['joint'] == joint]
            visible = [r for r in subset if r['human_status'] == 'visible']
            paired = [r for r in visible if r['mediapipe_error_px'] is not None and r['rtmpose_error_px'] is not None]
            result[joint] = {
                'source_rows': len(subset), 'human_status_counts': dict(Counter(r['human_status'] for r in subset)),
                'visible_mediapipe_missing': sum(r['mediapipe_error_px'] is None for r in visible),
                'visible_rtmpose_missing': sum(r['rtmpose_error_px'] is None for r in visible),
                'same_frame_same_joint_paired': {
                    'mediapipe': error_stats([r['mediapipe_error_px'] for r in paired]),
                    'rtmpose': error_stats([r['rtmpose_error_px'] for r in paired]),
                    'rtmpose_closer': sum(r['rtmpose_error_px'] < r['mediapipe_error_px'] for r in paired),
                    'rtmpose_farther': sum(r['rtmpose_error_px'] > r['mediapipe_error_px'] for r in paired),
                    'exactly_equal': sum(r['rtmpose_error_px'] == r['mediapipe_error_px'] for r in paired)}}
        return result

    eligible = [r for r in rows if r['effectiveness_eligible']]
    return {'pitch_id': source['pitch_id'], 'source_rows': len(rows),
            'all_human_status_counts': dict(Counter(r['human_status'] for r in rows)),
            'non_seed_human_status_counts': dict(Counter(r['human_status'] for r in eligible)),
            'non_seed': summarize(eligible),
            'original_full_major_hold_subset': summarize([r for r in eligible if r['original_full_major_hold']]),
            'outside_original_full_major_hold': summarize([r for r in eligible if not r['original_full_major_hold']]),
            'rows': rows, 'original_full_major_frames': sorted(major),
            'interpretation': 'Visible manual XY only. Full major context is not RTMPose correctness GT. No quality threshold or model selection.'}


def export_review(root, execution_path, result_path, output):
    root = root.resolve(); output = output.resolve()
    if output.exists() or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('Fresh output inside analysis_results required')
    sources = load_cached_sources(root, execution_path, result_path)
    plan = read_json(execution_path); result = read_json(result_path)
    if result['execution'] != reference(root, execution_path):
        raise ValueError('Source execution binding differs')
    if list(sources) != [clip['pitch_id'] for clip in plan['clips']]:
        raise ValueError('Source clip list differs')
    output.mkdir(parents=True)
    write_json(output / 'execution.json', {
        'approval': '核准第一版接入實作', 'created_at_utc': datetime.now(timezone.utc).isoformat(),
        'approved_plan': reference(root, root / 'docs/phase2_rtmpose_native_backend_plan_20261017.md'),
        'source_execution': reference(root, execution_path), 'source_result': reference(root, result_path),
        'new_model_inference_limit': 0, 'new_calibration_limit': 0, 'new_annotation_limit': 0})
    exports = []; all_read_paths = []
    for pid, pair in sources.items():
        clip_result = {'pitch_id': pid, 'backends': {}}
        for name, source in pair.items():
            frames = [source.read_frame(i) for i in range(len(source))]
            folder = output / pid / name
            write_dataset(folder, source.manifest, frames)
            summary = summarize_native(source.manifest, frames)
            write_json(folder / 'native_pose_summary.json', summary)
            exported = {'frames': len(source), 'topology': source.manifest['topology'],
                        'manifest': reference(root, folder / 'native_pose_manifest.json'),
                        'keypoints': reference(root, folder / 'native_keypoints.jsonl'),
                        'summary': reference(root, folder / 'native_pose_summary.json')}
            if name == 'rtmpose':
                overlay = write_native_overlay(root / source.manifest['video']['path'], source.manifest, frames,
                                               folder / 'overlay_native.mp4')
                write_json(folder / 'overlay_validation.json', overlay)
                exported['overlay'] = reference(root, folder / 'overlay_native.mp4')
                exported['overlay_validation'] = overlay
            else:
                exported['original_overlay'] = source.manifest['original_overlay']
            all_read_paths.extend(source.read_paths)
            clip_result['backends'][name] = exported
        exports.append(clip_result)
        print(json.dumps({'pitch_id': pid, 'frames_per_backend': len(pair['rtmpose']), 'new_model_calls': 0}), flush=True)
    write_json(output / 'native_export_seal.json', {'status': 'sealed_all_native_exports', 'clips': exports,
                                                 'prediction_annotation_file_reads': 0})
    # Only the comparison stage reads human data, after every prediction is saved.
    manual_ref = plan['manual_xy']
    manual_reader = BoundReader(root, [manual_ref])
    manual = manual_reader.json(manual_ref); validate_manual_keypoints(manual)
    pid = manual['source_video']['pitch_id']
    clip = next(c for c in plan['clips'] if c['pitch_id'] == pid)
    reader = BoundReader(root, [clip['canonical_gt']])
    comparison = coordinate_comparison(sources[pid], manual, reader.json(clip['canonical_gt']))
    comparisons = {p: comparison if p == pid else {'pitch_id': p, 'precise_accuracy': None,
                   'reason': 'No reviewed exact XY reference; original Full qualitative labels are not RTMPose correctness labels.'}
                   for p in sources}
    comparison_reads = manual_reader.opened + reader.opened
    write_json(output / 'backend_comparison.json', {'clips': comparisons, 'read_paths': comparison_reads,
               'quality_adoption': False, 'native_true_positive_or_false_positive_rates': None})
    for pair in sources.values():
        for source in pair.values():
            check = BoundReader(root, source.manifest['source_refs'])
            for ref in source.manifest['source_refs']:
                check.path(ref)
    summary = {'status': 'native_exports_complete_pending_integration_audit', 'clips': exports,
               'source_frames_per_backend': sum(len(p['rtmpose']) for p in sources.values()),
               'new_rtmpose_inference_calls': 0, 'new_tracker_calls': 0, 'new_calibrations': 0,
               'new_annotations': 0, 'production_backend_changed': False,
               'native_quality_status': 'not_calibrated', 'phase2_automatic_reliability': 'NOT_PASSED',
               'producer_read_paths': sorted(set(all_read_paths)), 'comparison_read_paths': comparison_reads,
               'comparison': reference(root, output / 'backend_comparison.json'),
               'adoption_decision': 'No live backend, native score gate or production adoption in this delivery.'}
    write_json(output / 'integration_summary.json', summary)
    return {'status': summary['status'], 'source_frames_per_backend': summary['source_frames_per_backend'],
            'new_rtmpose_overlays': len(exports), 'new_rtmpose_inference_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('execution', type=Path); parser.add_argument('result', type=Path); parser.add_argument('output', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(export_review(args.root, args.execution, args.result, args.output)), flush=True)
