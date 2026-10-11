"""Export immutable full RGB frames for an isolated runtime; no model or GT."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from check_movenet_compatibility import bound, sha, write

SOURCE_ROLES = {'video', 'metadata', 'video_technical'}


def validate_clip(root, clip):
    if set(clip['sources']) != SOURCE_ROLES:
        raise ValueError('Exporter permits only video/metadata/technical inputs')
    for ref in clip['sources'].values():
        bound(root, ref)
    target, sources = clip['target'], clip['sources']
    metadata = json.loads(bound(root, sources['metadata']).read_text(encoding='utf-8'))
    technical = json.loads(bound(root, sources['video_technical']).read_text(encoding='utf-8'))
    if (metadata.get('pitch_id') != target['pitch_id'] or
            metadata.get('video', {}).get('file') != Path(sources['video']['path']).name or
            technical.get('sha256') != sources['video']['sha256'] or
            (technical.get('frame_count'), technical.get('width'), technical.get('height')) !=
            (target['total_frames'], target['width'], target['height'])):
        raise ValueError('Input identity/shape/frame count mismatch')
    pts = technical.get('timestamps_ms')
    fps = technical.get('fps')
    if (not isinstance(pts, list) or len(pts) != target['total_frames'] or
            not all(math.isfinite(v) for v in pts) or pts[0] != 0 or
            any(b <= a for a, b in zip(pts, pts[1:])) or
            not isinstance(fps, (int, float)) or not math.isfinite(fps) or fps <= 0):
        raise ValueError('Invalid bound timeline')
    return technical


def pixel_receipt(frame, index, native_ms, technical, target):
    if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8 or
            frame.shape != (target['height'], target['width'], 3)):
        raise ValueError('Decoded frame shape/dtype mismatch')
    if (not math.isfinite(native_ms) or not math.isclose(native_ms,
            technical['timestamps_ms'][index], abs_tol=1e-6, rel_tol=0)):
        raise ValueError('Decoded PTS differs from bound timeline')
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return rgb, {'frame_index': index, 'native_timestamp_ms': native_ms,
        'timestamp_ms': round(native_ms), 'frame_time_sec': index / technical['fps'],
        'decoded_bgr_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
        'decoded_rgb_sha256': hashlib.sha256(rgb.tobytes()).hexdigest()}


def export(root, plan_path):
    root, plan_path = root.resolve(), plan_path.resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError('Plan outside workspace')
    plan_sha = sha(plan_path)
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    if plan['status'] != 'frozen_before_input_export' or plan['pose_inference_budget'] != 0:
        raise ValueError('Unfrozen input-only export plan')
    for ref in plan['sources'].values():
        bound(root, ref)
    if sha(__file__) != plan['sources']['exporter_code']['sha256']:
        raise ValueError('Unbound exporter')
    technical = [validate_clip(root, c) for c in plan['clips']]
    output = (root / plan['output_directory']).resolve()
    if not output.is_relative_to(root / 'analysis_results') or output.exists():
        raise ValueError('Fresh exclusive output required under analysis_results')
    output.mkdir(parents=True)
    refs = []
    for clip, tech in zip(plan['clips'], technical, strict=True):
        target, frames, pixels = clip['target'], [], []
        capture = cv2.VideoCapture(str(bound(root, clip['sources']['video'])))
        try:
            for index in range(target['total_frames']):
                ok, frame = capture.read()
                if not ok:
                    raise ValueError('Missing decoded source frame')
                rgb, receipt = pixel_receipt(frame, index, capture.get(cv2.CAP_PROP_POS_MSEC), tech, target)
                pixels.append(rgb)
                frames.append(receipt)
            if capture.read()[0]:
                raise ValueError('Extra decoded source frame')
        finally:
            capture.release()
        archive = output / (target['pitch_id'] + '.npz')
        with archive.open('xb') as stream:
            np.savez(stream, rgb=np.stack(pixels))
        archive_ref = {'path': archive.relative_to(root).as_posix(), 'sha256': sha(archive)}
        receipt = {'status': 'sealed_full_frame_rgb_inputs', 'target': target,
            'sources': clip['sources'], 'source_video': clip['sources']['video'],
            'plan_sha256': plan_sha, 'exporter_sha256': sha(__file__),
            'fps_float': tech['fps'], 'archive': archive_ref, 'frame_key': 'rgb',
            'frames': frames, 'human_annotation_inputs': [], 'pose_inference_calls': 0,
            'runtime': {'opencv': cv2.__version__, 'numpy': np.__version__},
            'limits': 'Full original frame, BGR-to-RGB only; no resizing, cropping, GT or model.'}
        path = output / (target['pitch_id'] + '.json')
        write(path, receipt)
        refs.append({'pitch_id': target['pitch_id'], 'receipt':
            {'path': path.relative_to(root).as_posix(), 'sha256': sha(path)}, 'archive': archive_ref})
        print(json.dumps({'pitch_id': target['pitch_id'], 'frames': len(frames),
                          'archive_bytes': archive.stat().st_size}), flush=True)
    for ref in plan['sources'].values():
        bound(root, ref)
    for clip in plan['clips']:
        validate_clip(root, clip)
    if sha(plan_path) != plan_sha:
        raise ValueError('Export plan changed during decoding')
    result = {'status': 'sealed_full_frame_rgb_cohort', 'plan_sha256': plan_sha,
              'clips': refs, 'source_frames': sum(c['target']['total_frames'] for c in plan['clips']),
              'pose_inference_calls': 0, 'human_annotation_inputs': []}
    write(output / 'export_run.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = export(args.root, args.plan)
    print(json.dumps({'status': result['status'], 'source_frames': result['source_frames']}))
