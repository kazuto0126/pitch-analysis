"""Explicit, source-bound live native capture, isolated from production analysis.

Only the separately approved native estimator is invoked. No production gate,
selector, interpolation, annotation, or acquisition operation is called here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re

import cv2

from .contracts import load_input
from .native_pose import CAPABILITIES, NativePoseFrame, validate_manifest
from .native_pose_io import BoundReader, read_json, reference, sha256, write_dataset, write_json


REVIEW_ITEMS = ('pitcher_identity', 'pitch_delivery_visible', 'not_replay_or_slow_motion',
                'not_mirrored', 'full_body_in_frame', 'preparation_complete', 'follow_through_complete')
LIVE_MODE = 'live_stateless_roi'


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _record(path: Path, payload: dict) -> None:
    temporary = path.with_name(path.name + '.tmp')
    write_json(temporary, payload)
    temporary.replace(path)


def _approval(payload: dict) -> dict:
    if payload.get('status') != 'approved':
        raise ValueError('Explicit live implementation approval is required')
    approval = payload.get('approval', {})
    for key in ('reviewer', 'reviewed_at_utc', 'user_reply'):
        if not isinstance(approval.get(key), str) or not approval[key].strip():
            raise ValueError(f'Approval requires {key}')
    date = datetime.fromisoformat(approval['reviewed_at_utc'].replace('Z', '+00:00'))
    if date.utcoffset() is None or date.utcoffset().total_seconds() != 0:
        raise ValueError('Approval timestamp must be UTC')
    return approval


def _manifest(config, clip, config_ref, worker_refs=()):
    fps = clip['fps']
    return {
        'schema_version': 'native-pose-manifest-v1', 'pitch_id': clip['pitch_id'],
        'backend': {'name': 'rtmpose_live_onnx', 'model_sha256': config['model_ref']['sha256'],
                    'model_version': 'rtmpose_m_body7_20230504',
                    'score_semantics': 'min(max(SimCC_x),max(SimCC_y)); native response, not calibrated accuracy'},
        'topology': 'coco_17', 'image_size': {'width': clip['width'], 'height': clip['height']},
        'video': {'path': clip['video_ref']['path'], 'sha256': clip['video_ref']['sha256'],
                  'frame_count': clip['frame_count'], 'fps': float(fps)},
        'timebase': {'frame_index_base': 0, 'timestamp_semantics': 'frame_index * 1000 / fractional_fps; zero origin',
                     'fps_fraction': f'{fps.numerator}/{fps.denominator}'},
        'capabilities': CAPABILITIES['coco_17'], 'quality_status': 'not_calibrated', 'usable_for_analysis': None,
        'inference_mode': LIVE_MODE,
        'source_refs': [config_ref, config['model_ref'], config['runtime_ref'], config['worker_ref'],
                        config['region_config_ref'], clip['video_ref'], clip['metadata_ref'], clip['review_ref'],
                        clip['timeline_ref'], *config.get('implementation_refs', []), *worker_refs],
        'roi_provenance': {'config_ref': config_ref, 'review_ref': clip['review_ref'],
                           'reviewer': clip['region_confirmation']['reviewer'],
                           'reviewed_at_utc': clip['region_confirmation']['reviewed_at_utc'],
                           'roi_source': 'HSU-confirmed source-bound fixed full-motion crop',
                           'crop_xyxy_px': clip['crop_xyxy_px'], 'operator_region_config_ref': config['region_config_ref']},
        'original_overlay': None}


def preflight_live(root: str | Path, config_path: str | Path) -> tuple[dict, list[dict]]:
    """Resolve every source and review before output or an ONNX session exists."""
    root = Path(root).resolve(strict=True)
    config_path = Path(config_path).resolve(strict=True)
    if not config_path.is_relative_to(root):
        raise ValueError('Configuration must be inside the project root')
    config = read_json(config_path)
    if config.get('schema_version') != 'native-live-run-v1':
        raise ValueError('Expected native-live-run-v1')
    _approval(config)
    clips = config.get('clips')
    if not isinstance(clips, list) or not 1 <= len(clips) <= 5:
        raise ValueError('One through five explicitly bound clips required')
    limit = config.get('max_real_calls')
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1684:
        raise ValueError('Explicit call limit must be between 1 and 1684')
    refs = [config[key] for key in ('model_ref', 'runtime_ref', 'worker_ref', 'region_config_ref')]
    refs.extend(config.get('implementation_refs', []))
    for clip in clips:
        refs.extend(clip[key] for key in ('video_ref', 'metadata_ref', 'review_ref', 'timeline_ref'))
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    regions = reader.json(config['region_config_ref'])
    if regions.get('status') != 'operator_confirmed' or not regions.get('operator_confirmation'):
        raise ValueError('Source-bound operator region confirmation required')
    checked, seen = [], set()
    for item in clips:
        pid = item['pitch_id']
        if not isinstance(pid, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_]{0,79}', pid) or pid in seen:
            raise ValueError('Unsafe or duplicate pitch identifier')
        seen.add(pid)
        video, metadata = reader.path(item['video_ref']), reader.path(item['metadata_ref'])
        payload = load_input(video, metadata)
        if payload['pitch_id'] != pid or payload['pitcher']['id'] != config['pitcher_id']:
            raise ValueError(f'{pid}: input identity differs from configuration')
        human = reader.json(item['review_ref'])
        if (human.get('overall_status') != 'review_complete' or set(human.get('items', {})) != set(REVIEW_ITEMS)
                or any(human['items'][key].get('latest', {}).get('conclusion') != 'pass' for key in REVIEW_ITEMS)
                or human.get('source_video_sha256') != item['video_ref']['sha256']):
            raise ValueError(f'{pid}: seven source-bound human input passes required')
        timeline = reader.json(item['timeline_ref'])
        fps = Fraction(item['fps_fraction'])
        total = item['frame_count']
        if (fps <= 0 or isinstance(total, bool) or not isinstance(total, int) or total <= 0
                or timeline['source_video_sha256'] != item['video_ref']['sha256']
                or timeline['frame_count'] != total or Fraction(timeline['fractional_fps']) != fps):
            raise ValueError(f'{pid}: verified import timeline differs')
        original = next((c for c in regions['clips'] if c['pitch_id'] == pid), None)
        if (not original or original['video_sha256'] != item['video_ref']['sha256']
                or original['expected_pixel_bounds_xyxy_exclusive'] != item['crop_xyxy_px']):
            raise ValueError(f'{pid}: crop is not the confirmed source setting')
        capture = cv2.VideoCapture(str(video))
        try:
            if not capture.isOpened():
                raise ValueError(f'{pid}: source cannot open')
            width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) != total or abs(capture.get(cv2.CAP_PROP_FPS) - float(fps)) >= 1e-6:
                raise ValueError(f'{pid}: decoded source metadata differs')
            decoded = 0
            while True:
                okay, image = capture.read()
                if not okay:
                    break
                timestamp = float(Fraction(decoded * 1000, 1) / fps)
                native_time = capture.get(cv2.CAP_PROP_POS_MSEC)
                if (image.shape != (height, width, 3) or not math.isfinite(native_time)
                        or abs(native_time - timestamp) >= 1):
                    raise ValueError(f'{pid}: source decode/timing differs at {decoded}')
                decoded += 1
            if decoded != total:
                raise ValueError(f'{pid}: actual decode count differs')
        finally:
            capture.release()
        crop = item['crop_xyxy_px']
        if (not isinstance(crop, list) or len(crop) != 4 or any(isinstance(v, bool) or not isinstance(v, int) for v in crop)
                or not 0 <= crop[0] < crop[2] <= width or not 0 <= crop[1] < crop[3] <= height):
            raise ValueError(f'{pid}: invalid pixel crop')
        checked.append({**item, 'video_path': video, 'width': width, 'height': height, 'fps': fps,
                        'region_confirmation': regions['operator_confirmation']})
    if sum(c['frame_count'] for c in checked) != limit:
        raise ValueError('Call limit must equal the complete approved source timelines')
    return config, checked


def run_live(root: str | Path, config_path: str | Path, output: str | Path, *,
             transport_factory=None, render_overlays: bool = True) -> dict:
    root, config_path = Path(root).resolve(strict=True), Path(config_path).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('A new output directory within project analysis_results is required')
    config, clips = preflight_live(root, config_path)
    from .native_pose_estimator import RTMPoseNativeEstimator
    from .native_pose_transport import IsolatedOnnxTransport
    from .native_pose_review import summarize_native, write_native_overlay

    factory = transport_factory or IsolatedOnnxTransport
    config_ref = reference(root, config_path)
    for clip in clips:
        validate_manifest(_manifest(config, clip, config_ref))
    output.mkdir(parents=True, exist_ok=False)
    worker_dir = output / 'worker'
    worker_dir.mkdir()
    refs = [config[key] for key in ('model_ref', 'runtime_ref', 'worker_ref', 'region_config_ref')]
    refs.extend(config.get('implementation_refs', []))
    refs += [c[key] for c in clips for key in ('video_ref', 'metadata_ref', 'review_ref', 'timeline_ref')]
    before = {r['path']: r['sha256'] for r in [config_ref, *refs]}
    receipt = {'schema_version': 'native-live-execution-v1', 'state': 'running', 'started_at_utc': _utc(),
               'config_ref': config_ref, 'approval': config['approval'], 'max_real_calls': config['max_real_calls'],
               'calls_attempted': 0, 'calls_completed': 0, 'clips': [], 'new_annotations': 0,
               'formal_promotion': False, 'phase2_automatic_reliability': 'NOT_PASSED'}
    receipt_path = output / 'run_receipt.json'
    write_json(receipt_path, receipt)
    captures = []
    transport = None
    try:
        with factory(root / config['runtime_ref']['path'], root / config['worker_ref']['path'],
                     root / config['model_ref']['path'], expected_model_sha256=config['model_ref']['sha256'],
                     max_calls=config['max_real_calls'], output_dir=worker_dir) as transport:
            receipt['worker_metadata'] = transport.metadata
            expected_runtime = config.get('expected_runtime', {})
            for key, value in expected_runtime.items():
                if transport.metadata.get('runtime', {}).get(key) != value:
                    raise ValueError(f'Isolated runtime changed: {key}')
            for clip in clips:
                pid, records = clip['pitch_id'], []
                entry = {'pitch_id': pid, 'state': 'capturing', 'frames_completed': 0,
                         'frame_count': clip['frame_count'], 'failed_frame': None}
                receipt['clips'].append(entry)
                _record(receipt_path, receipt)
                estimator = RTMPoseNativeEstimator(transport, crop_xyxy=tuple(clip['crop_xyxy_px']))
                capture = cv2.VideoCapture(str(clip['video_path']))
                journal = output / f'{pid}.partial.jsonl'
                print(f'START {pid}', flush=True)
                try:
                    with journal.open('x', encoding='utf-8', newline='\n') as stream:
                        for index in range(clip['frame_count']):
                            entry['failed_frame'] = index
                            okay, image = capture.read()
                            if not okay or image.shape != (clip['height'], clip['width'], 3):
                                raise ValueError(f'{pid}: source decode failure at {index}')
                            timestamp = float(Fraction(index * 1000, 1) / clip['fps'])
                            native_time = capture.get(cv2.CAP_PROP_POS_MSEC)
                            if not math.isfinite(native_time) or abs(native_time - timestamp) >= 1:
                                raise ValueError(f'{pid}: source timing mismatch at {index}')
                            estimate = estimator.estimate(image)
                            record = NativePoseFrame({
                                'schema_version': 'native-keypoints-v1', 'pitch_id': pid, 'backend': 'rtmpose_live_onnx',
                                'topology': 'coco_17', 'frame_index': index, 'timestamp_ms': timestamp,
                                'source_video_sha256': clip['video_ref']['sha256'],
                                'decoded_bgr_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
                                'image_size': {'width': clip['width'], 'height': clip['height']},
                                'coordinate_space': 'original_image_pixels_xy', 'quality_status': 'not_calibrated',
                                'usable_for_analysis': None, 'input_geometry': estimate.input_geometry,
                                'model_selection': {'source': 'HSU-confirmed fixed model-input region', 'inference_mode': LIVE_MODE,
                                                    'isolated_worker_attempt_index': transport.calls_completed},
                                'landmarks': estimate.landmarks})
                            stream.write(json.dumps(record.to_dict(), allow_nan=False) + '\n')
                            stream.flush()
                            records.append(record)
                            entry['frames_completed'] = index + 1
                            if (index + 1) % 100 == 0:
                                print(f'{pid}: {index+1}/{clip["frame_count"]}', flush=True)
                        okay, _ = capture.read()
                        if okay:
                            raise ValueError(f'{pid}: source has extra frames')
                    entry.update(state='captured', failed_frame=None)
                    captures.append((clip, records))
                    receipt.update(calls_attempted=transport.calls_attempted, calls_completed=transport.calls_completed)
                    _record(receipt_path, receipt)
                finally:
                    capture.release()
        if receipt['calls_completed'] != config['max_real_calls']:
            raise ValueError('Completed model calls differ from the complete source timelines')
        worker_refs = [reference(root, p) for p in worker_dir.iterdir() if p.is_file()]
        for clip, records in captures:
            pid = clip['pitch_id']
            manifest = _manifest(config, clip, config_ref, worker_refs)
            folder = output / 'rtmpose' / pid
            write_dataset(folder, manifest, records)
            write_json(folder / 'native_pose_summary.json', summarize_native(manifest, records))
            if render_overlays:
                inspection = write_native_overlay(clip['video_path'], manifest, records, folder / 'overlay_native.mp4')
                write_json(folder / 'overlay_validation.json', inspection)
            entry = next(e for e in receipt['clips'] if e['pitch_id'] == pid)
            entry.update(state='completed', native_output=folder.relative_to(root).as_posix(),
                         overlay_generated=render_overlays)
            _record(receipt_path, receipt)
            print(f'COMPLETED {pid}', flush=True)
        changed = [path for path, digest in before.items() if sha256(root / path) != digest]
        receipt.update(state='completed', completed_at_utc=_utc(), source_files_checked=len(before), source_sha256_changes=changed)
        if changed:
            raise ValueError('Source artifacts changed during native run')
    except BaseException as error:
        receipt.update(state='failed', failed_at_utc=_utc(), failure=f'{type(error).__name__}: {error}')
        if transport is not None:
            receipt.update(calls_attempted=transport.calls_attempted, calls_completed=transport.calls_completed)
        _record(receipt_path, receipt)
        raise
    _record(receipt_path, receipt)
    return receipt
