"""GT-blind descriptive diagnostics on saved image features, outside production."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, payload):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write('\n')


def statistics(values):
    values = [float(v) for v in values if v is not None]
    if not values:
        return dict(n=0, median=None, p95=None, p99=None, max=None)
    return dict(n=len(values), median=float(np.median(values)),
                p95=float(np.percentile(values, 95)),
                p99=float(np.percentile(values, 99)), max=max(values))


def midrank_percentiles(values):
    """Missing values stay null; equal values never get different ranks."""
    present = np.asarray([v for v in values if v is not None], dtype=float)
    if not np.isfinite(present).all():
        raise ValueError('Nonfinite quality score')
    if not len(present):
        return [None] * len(values)
    ordered = np.sort(present)
    return [None if v is None else float(
        (np.searchsorted(ordered, v, side='left') +
         np.searchsorted(ordered, v, side='right')) / (2 * len(ordered)))
        for v in values]


def rank_group(percentile):
    return None if percentile is None else min(int(4 * percentile), 3)


def feature_diagnostics(frame):
    records = []
    for feature in frame['torso_features']:
        if not feature['numerically_usable']:
            continue
        position = feature.get('current_xy_px', feature.get('forward_xy_px'))
        if position is None or not np.isfinite(position).all():
            raise ValueError('Usable feature lacks finite saved position')
        previous = feature.get('previous_xy_px')
        if previous is not None and not np.isfinite(previous).all():
            raise ValueError('Nonfinite saved previous position')
        records.append(dict(feature_id=feature['feature_id'], current_xy_px=position,
                            previous_xy_px=previous,
                            fb_error_px=feature.get('fb_error_px'),
                            lifetime_frames=feature['lifetime_frames']))
    if len({r['feature_id'] for r in records}) != len(records):
        raise ValueError('Duplicate feature ID')
    positions = np.asarray([r['current_xy_px'] for r in records], dtype=float)
    center = np.median(positions, axis=0) if len(positions) else None
    motion_records = [r for r in records if r['previous_xy_px'] is not None]
    vectors = [np.asarray(r['current_xy_px']) - r['previous_xy_px'] for r in motion_records]
    median_motion = np.median(vectors, axis=0) if vectors else None
    for record in records:
        record['radial_distance_from_current_cohort_median_px'] = float(
            np.linalg.norm(np.asarray(record['current_xy_px']) - center))
        previous = record['previous_xy_px']
        record['movement_deviation_from_same_cohort_median_px'] = (
            float(np.linalg.norm(np.asarray(record['current_xy_px']) - previous - median_motion))
            if previous is not None else None)
    ranks = midrank_percentiles([r['fb_error_px'] for r in records])
    for record, rank in zip(records, ranks, strict=True):
        record['fb_per_frame_midrank'] = rank
        record['fb_per_frame_group'] = rank_group(rank)
    return records


def measure(input_root, plan_path, output_root):
    if output_root.exists():
        raise FileExistsError(f'Fresh output required: {output_root}')
    plan = read(plan_path)
    run = read(input_root / 'measurement_run.json')
    if run['status'] != 'measurements_only' or run['human_annotation_inputs'] or run['warning_predictions_generated']:
        raise ValueError('Expected annotation-free measurement-only source')
    producer = Path(__file__).with_name('measure_image_pose_evidence.py')
    if sha(producer) != run['producer_code_sha256']:
        raise ValueError('Original measurement producer changed')
    parameters = plan['parameters']
    if parameters['human_inputs_to_producer'] or parameters['warning_thresholds'] is not None:
        raise ValueError('GT or warning threshold in producer plan')
    if parameters['feature_rejection_or_reseeding']:
        raise ValueError('This experiment does not reject or reseed features')
    hashes = {str(plan_path): sha(plan_path),
              str(input_root / 'measurement_run.json'): sha(input_root / 'measurement_run.json')}
    clips = []
    for entry in run['results']:
        pitch = entry['pitch_id']
        path = input_root / pitch / 'image_pose_measurements.json'
        data = read(path)
        if data['pitch_id'] != pitch or data['total_frames'] != entry['total_frames']:
            raise ValueError('Clip binding mismatch')
        hashes[str(path)] = sha(path)
        for source in data['sources'].values():
            if sha(source['path']) != source['sha256']:
                raise ValueError('Saved source changed')
            hashes[source['path']] = source['sha256']
        if [f['frame_index'] for f in data['frames']] != list(range(data['total_frames'])):
            raise ValueError('Timeline mismatch')
        frames = []
        for frame in data['frames']:
            records = feature_diagnostics(frame)
            if len(records) != frame['active_feature_count']:
                raise ValueError('Numerical cohort count mismatch')
            cumulative = frame['torso_cumulative']
            expansion = (cumulative['current_hull_area_px2'] / cumulative['seed_hull_area_px2']
                         if cumulative and cumulative['seed_hull_area_px2'] else None)
            frames.append(dict(frame_index=frame['frame_index'], timestamp_ms=frame['timestamp_ms'],
                               original_measurement_state=frame['measurement_state'],
                               usable_feature_count=len(records), seed_feature_count=data['seed_feature_count'],
                               seed_survival_ratio=frame['seed_feature_survivor_ratio'],
                               cohort_hull_expansion_ratio=expansion, features=records,
                               foreground_verified=False, subject_identity_verified=False))
        flat = [r for frame in frames for r in frame['features']]
        ranks = midrank_percentiles([r['fb_error_px'] for r in flat])
        for record, rank in zip(flat, ranks, strict=True):
            record['fb_per_clip_midrank'] = rank
            record['fb_per_clip_group'] = rank_group(rank)
        scores = {name: statistics([r[name] for r in flat]) for name in parameters['quality_scores']}
        clips.append(dict(pitch_id=pitch, total_frames=data['total_frames'], width=data['width'],
                          height=data['height'], source_video=data['sources']['video'], frames=frames,
                          numerical_feature_frame_rows=len(flat), quality_scores=scores,
                          foreground_verified=False, subject_identity_verified=False))
    if any(sha(p) != h for p, h in hashes.items()):
        raise ValueError('Source changed during diagnostic measurement')
    output_root.mkdir(parents=True)
    parameters_hash = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
    result = dict(status='descriptive_validity_measurements_only',
                  producer_code_sha256=sha(__file__), plan_sha256=sha(plan_path),
                  parameters_sha256=parameters_hash, source_hashes=hashes,
                  human_annotation_inputs=[], warning_thresholds=None,
                  warning_predictions_generated=False, feature_rejection_or_reseeding=False,
                  clips=clips)
    write(output_root / 'feature_validity_measurements.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('measurement_root', type=Path)
    parser.add_argument('plan', type=Path)
    parser.add_argument('output_root', type=Path)
    args = parser.parse_args()
    result = measure(args.measurement_root, args.plan, args.output_root)
    print(json.dumps(dict(status=result['status'], frames=sum(c['total_frames'] for c in result['clips']))))
