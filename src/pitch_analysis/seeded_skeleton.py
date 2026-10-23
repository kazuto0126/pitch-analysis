"""Source-bound, operator-seeded COCO17 skeleton capture for one prepared pitch.

Detection, subject association, and pose have separate saved evidence. A first
frame detection is supplied by preparation and is never inferred a second time.
This entry does not feed MediaPipe's 33-point feature or quality contracts.
"""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
from datetime import datetime, timedelta
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path

import cv2

from .contracts import load_input
from .native_person_boxes import FINAL_SCORE_THRESHOLD, POLICY, prepare_detector_input, select_person_box
from .native_person_box_live import _missing_landmarks
from .native_pose import CAPABILITIES, NativePoseFrame, validate_manifest
from .native_pose_io import BoundReader, read_json, reference, sha256, write_dataset, write_json
from .native_pose_live import _utc
from .native_progress_log import append_event
from .native_seeded_track import TRACK_POLICY, associate_saved_boxes


_REF_KEYS = ('video_ref', 'metadata_ref', 'runtime_ref', 'model_ref', 'worker_ref',
             'detector_model_ref', 'detector_worker_ref', 'frame0_ref')


def _utc_review(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return False
    return parsed.utcoffset() == timedelta(0)


def _preflight(root: Path, preparation_path: Path, seed_path: Path, output: Path):
    if (not preparation_path.is_relative_to(root) or not seed_path.is_relative_to(root)
            or not preparation_path.is_relative_to(root / 'analysis_results')
            or output.exists() or not output.is_relative_to(root / 'analysis_results')
            or not output.parent.is_dir()):
        raise ValueError('Source-bound preparation/seed and a fresh analysis output are required')
    claim = preparation_path.parent / 'execution_claim.json'
    if claim.exists():
        raise ValueError('This prepared source has already been claimed for execution')

    prep = read_json(preparation_path)
    if (prep.get('schema_version') != 'seeded-skeleton-preparation-v1'
            or prep.get('status') != 'awaiting_operator_seed'):
        raise ValueError('Expected an awaiting_operator_seed skeleton preparation')
    refs = prep.get('source_refs')
    if not isinstance(refs, list) or any(prep.get(key) not in refs for key in _REF_KEYS):
        raise ValueError('Every required source, model, worker and frame-zero record must be bound')
    if prep.get('seed_image_ref') is not None and prep['seed_image_ref'] not in refs:
        raise ValueError('The operator seed image must be source-bound')
    reader = BoundReader(root, refs)
    source_paths = {key: reader.path(prep[key]) for key in _REF_KEYS}
    for ref in refs:
        reader.path(ref)
    payload = load_input(source_paths['video_ref'], source_paths['metadata_ref'])
    if (payload['pitch_id'] != prep.get('pitch_id')
            or payload['pitcher']['id'] != prep.get('pitcher_id')):
        raise ValueError('Pitch input and prepared identity differ')
    count, width, height = (prep.get(key) for key in ('frame_count', 'width', 'height'))
    if any(type(value) is not int or value < 1 for value in (count, width, height)):
        raise ValueError('Prepared frame count and image size must be positive integers')
    try:
        fps = Fraction(prep['fps_fraction'])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise ValueError('Prepared source requires a positive fractional FPS') from None
    if fps <= 0 or prep['fps_fraction'] not in (str(fps), f'{fps.numerator}/{fps.denominator}'):
        raise ValueError('Prepared source requires a canonical positive fractional FPS')
    crop = prep.get('crop_xyxy_px')
    roi = prep.get('operator_roi')
    if (crop != [0, 0, width, height] or roi != [0, 0, 1, 1]):
        raise ValueError('Common skeleton entry requires the prepared full-source crop/ROI')
    expected_runtime = prep.get('expected_runtime')
    if not isinstance(expected_runtime, dict) or not expected_runtime:
        raise ValueError('Expected isolated runtime metadata is required')
    if prep.get('max_detector_calls', count - 1) != count - 1 or prep.get('max_pose_calls', count) != count:
        raise ValueError('Per-source detector and pose limits must preserve the full timeline')

    frame0 = reader.json(prep['frame0_ref'])
    if (frame0.get('frame_index') != 0 or frame0.get('timestamp_ms') != 0
            or frame0.get('policy') != POLICY
            or frame0.get('final_score_threshold') != FINAL_SCORE_THRESHOLD
            or frame0.get('operator_roi') != roi
            or not isinstance(frame0.get('decoded_bgr_sha256'), str)
            or not isinstance(frame0.get('candidates'), list)
            or not isinstance(frame0.get('detector_input_geometry', frame0.get('detector_geometry')), dict)):
        raise ValueError('Prepared frame-zero detector record differs from the fixed policy')
    detector_geometry = frame0.get('detector_input_geometry', frame0.get('detector_geometry'))
    if detector_geometry.get('crop_xyxy_px') != crop or detector_geometry.get('source_size') != [width, height]:
        raise ValueError('Prepared frame-zero detector geometry differs from source')
    eligible = [item for item in frame0['candidates'] if item.get('eligible') is True]
    choices = [{'display_number': number, 'output_index': item['output_index'],
                'bbox_original_xyxy_px': item['bbox_original_xyxy_px']}
               for number, item in enumerate(eligible, 1)]
    if prep.get('display_choices') != choices:
        raise ValueError('Displayed seed choices differ from saved eligible frame-zero boxes')

    seed = read_json(seed_path)
    if (seed.get('schema_version') != 'native-subject-seed-v1'
            or seed.get('status') != 'operator_confirmed'
            or seed.get('ground_truth') is not False
            or seed.get('pitch_id') != prep['pitch_id']
            or seed.get('frame_index') != 0
            or seed.get('source_video_ref') != prep['video_ref']
            or seed.get('saved_detection_ref') != prep['frame0_ref']
            or seed.get('decoded_bgr_sha256') != frame0['decoded_bgr_sha256']
            or not _utc_review(seed.get('reviewed_at_utc'))
            or any(not isinstance(seed.get(key), str) or not seed[key].strip()
                   for key in ('reviewer', 'user_reply'))):
        raise ValueError('An exact source-bound human first-box seed is required')
    selected_index = seed.get('selected_output_index')
    matches = [item for item in frame0['candidates']
               if item.get('eligible') is True and item.get('output_index') == selected_index]
    if (type(selected_index) is not int or selected_index < 0 or len(matches) != 1
            or matches[0].get('bbox_original_xyxy_px') != seed.get('selected_bbox_xyxy_px')):
        raise ValueError('The human seed must select an exact eligible frame-zero candidate')
    return prep, frame0, seed, source_paths, count, width, height, fps, claim


def _image(capture, index: int, *, width: int, height: int, fps: Fraction,
           expected_pixel_sha: str | None = None):
    okay, image = capture.read()
    expected_time = float(Fraction(index * 1000, 1) / fps)
    actual_time = capture.get(cv2.CAP_PROP_POS_MSEC)
    if (not okay or image.shape != (height, width, 3)
            or not math.isfinite(actual_time) or abs(actual_time - expected_time) >= 1):
        raise ValueError(f'Source decode, geometry or fractional time changed at frame {index}')
    pixel_sha = hashlib.sha256(image.tobytes()).hexdigest()
    if expected_pixel_sha is not None and pixel_sha != expected_pixel_sha:
        raise ValueError(f'Source pixel SHA changed at frame {index}')
    return image, expected_time, pixel_sha


def _write_row(stream, value: dict) -> None:
    stream.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
    stream.flush()
    os.fsync(stream.fileno())


def _manifest(root: Path, prep: dict, seed: dict, prep_ref: dict, seed_ref: dict,
              generated_refs: list[dict], fps: Fraction) -> dict:
    refs = [prep_ref, seed_ref, *prep['source_refs'], *generated_refs]
    distinct = {ref['path']: ref for ref in refs}
    result = {
        'schema_version': 'native-pose-manifest-v1', 'pitch_id': prep['pitch_id'],
        'backend': {'name': 'rtmpose_live_onnx', 'model_sha256': prep['model_ref']['sha256'],
                    'model_version': 'rtmpose_m_body7_20230504',
                    'score_semantics': 'min(max(SimCC_x),max(SimCC_y)); native response, not calibrated accuracy'},
        'topology': 'coco_17', 'image_size': {'width': prep['width'], 'height': prep['height']},
        'video': {'path': prep['video_ref']['path'], 'sha256': prep['video_ref']['sha256'],
                  'frame_count': prep['frame_count'], 'fps': float(fps)},
        'timebase': {'frame_index_base': 0,
                     'timestamp_semantics': 'frame_index * 1000 / fractional_fps; zero origin',
                     'fps_fraction': f'{fps.numerator}/{fps.denominator}'},
        'capabilities': CAPABILITIES['coco_17'], 'quality_status': 'not_calibrated',
        'usable_for_analysis': None, 'inference_mode': 'live_stateless_roi',
        'source_refs': list(distinct.values()),
        'roi_provenance': {
            'config_ref': prep_ref, 'review_ref': seed_ref,
            'reviewer': seed['reviewer'], 'reviewed_at_utc': seed['reviewed_at_utc'],
            'roi_source': 'operator-confirmed frame-zero person box then mutual unique positive IoU over saved detections',
            'crop_xyxy_px': prep['crop_xyxy_px'], 'operator_roi': prep['operator_roi'],
            'seed_ref': seed_ref, 'track_policy': TRACK_POLICY,
            'per_frame_boxes_human_reviewed': False,
        },
        'original_overlay': None,
    }
    validate_manifest(result)
    return result


def run_seeded_skeleton(root, preparation_path, seed_path, output, *,
                        detector_factory=None, pose_factory=None, render_overlay=True):
    """Execute one claimed, fully source-bound native skeleton run.

    Model factories are injectable for synthetic tests. No call is retried, and
    any failure leaves its claim, progress and partial records in place.
    """
    root = Path(root).resolve(strict=True)
    preparation_path = Path(preparation_path).resolve(strict=True)
    seed_path = Path(seed_path).resolve(strict=True)
    output = Path(output).resolve()
    prep, frame0, seed, paths, count, width, height, fps, claim = _preflight(
        root, preparation_path, seed_path, output)
    from .native_person_box_transport import IsolatedDetectorTransport
    from .native_pose_transport import IsolatedOnnxTransport
    from .native_pose_estimator import RTMPoseNativeEstimator
    from .native_pose_review import summarize_native, write_native_overlay

    detector_factory = detector_factory or IsolatedDetectorTransport
    pose_factory = pose_factory or IsolatedOnnxTransport
    prep_ref, seed_ref = reference(root, preparation_path), reference(root, seed_path)
    bound_hashes = {ref['path']: ref['sha256'] for ref in [prep_ref, seed_ref, *prep['source_refs']]}
    write_json(claim, {'schema_version': 'seeded-skeleton-execution-claim-v1',
                       'preparation_ref': prep_ref, 'seed_ref': seed_ref,
                       'source_video_ref': prep['video_ref'], 'pose_model_ref': prep['model_ref'],
                       'detector_model_ref': prep['detector_model_ref'],
                       'output': output.relative_to(root).as_posix(),
                       'claimed_at_utc': _utc(), 'max_new_detector_calls': count - 1,
                       'max_pose_calls': count, 'automatic_retries': False})
    output.mkdir(parents=True, exist_ok=False)
    progress = output / 'progress'
    detector_dir, pose_dir = output / 'detector_worker', output / 'pose_worker'
    detector_dir.mkdir()
    pose_dir.mkdir()
    receipt = {'schema_version': 'seeded-skeleton-execution-v1', 'state': 'running',
               'started_at_utc': _utc(), 'preparation_ref': prep_ref, 'seed_ref': seed_ref,
               'runner_implementation_sha256': sha256(Path(__file__).resolve()),
               'pitch_id': prep['pitch_id'], 'frame_count': count,
               'frame0_detector_reused': True, 'max_new_detector_calls': count - 1,
               'max_pose_calls': count, 'new_detector_calls_attempted': 0,
               'new_detector_calls_completed': 0, 'pose_calls_attempted': 0,
               'pose_calls_completed': 0, 'frames_completed': 0,
               'failed_stage': None, 'failed_frame': None,
               'track_replays_completed': 0, 'quality_status': 'not_calibrated',
               'usable_for_analysis': None, 'identity_switch_confirmed': None,
               'accuracy': None, 'phase2_automatic_reliability': 'NOT_PASSED',
               'new_annotations': 0, 'formal_promotion': False}
    detector = pose = None
    closed_detector_attempts = closed_detector_completions = detector_sessions = 0
    detections, tracks, frames = [], [], []
    stage, failed_frame = 'detector', None
    append_event(progress, 'started', dict(receipt))
    try:
        with ExitStack() as stack:
            detector_scope = ExitStack()
            stack.callback(lambda: detector_scope.close())
            with (output / 'person_boxes.jsonl').open('x', encoding='utf-8', newline='\n') as sink:
                capture = cv2.VideoCapture(str(paths['video_ref']))
                try:
                    if not capture.isOpened():
                        raise ValueError('Prepared source video cannot open')
                    for index in range(count):
                        failed_frame = index
                        image, timestamp, pixel_sha = _image(
                            capture, index, width=width, height=height, fps=fps,
                            expected_pixel_sha=frame0['decoded_bgr_sha256'] if index == 0 else None)
                        if index == 0:
                            row = frame0
                        else:
                            # The isolated detector transport has a per-session 321-call
                            # ceiling. Continue only after a completed session; each new
                            # session gets its own exclusive evidence and no retry.
                            if detector is None or detector.calls_completed == min(321, count - 1 - closed_detector_completions):
                                if detector is not None:
                                    closed_detector_attempts += detector.calls_attempted
                                    closed_detector_completions += detector.calls_completed
                                    detector_scope.close()
                                    detector_scope = ExitStack()
                                    detector = None
                                session_dir = detector_dir / f'segment_{detector_sessions:03d}'
                                session_dir.mkdir()
                                detector_sessions += 1
                                detector = detector_scope.enter_context(detector_factory(
                                    paths['runtime_ref'], paths['detector_worker_ref'], paths['detector_model_ref'],
                                    expected_model_sha256=prep['detector_model_ref']['sha256'],
                                    max_calls=min(321, count - 1 - closed_detector_completions),
                                    output_dir=session_dir))
                                if any(detector.metadata.get('runtime', {}).get(key) != value
                                       for key, value in prep['expected_runtime'].items()):
                                    raise ValueError('Isolated detector runtime changed')
                            tensor, geometry = prepare_detector_input(image, prep['crop_xyxy_px'])
                            selection = select_person_box(detector.run(tensor), geometry, prep['operator_roi'])
                            row = {'frame_index': index, 'timestamp_ms': timestamp,
                                   'decoded_bgr_sha256': pixel_sha,
                                   'detector_attempt_index': closed_detector_completions + detector.calls_completed,
                                   'detector_worker_segment': detector_sessions - 1,
                                   'detector_input_geometry': geometry, **selection}
                        _write_row(sink, row)
                        detections.append(row)
                        if detector is not None:
                            receipt.update(new_detector_calls_attempted=closed_detector_attempts + detector.calls_attempted,
                                           new_detector_calls_completed=closed_detector_completions + detector.calls_completed,
                                           detector_worker_sessions=detector_sessions)
                        append_event(progress, f'detected-{index:06d}', dict(receipt))
                        if index and index % 50 == 0:
                            print(f'{prep["pitch_id"]}: detected {index+1}/{count}', flush=True)
                    if capture.read()[0]:
                        raise ValueError('Source contains extra frames after prepared timeline')
                finally:
                    capture.release()

            stage, failed_frame = 'association', None
            tracks = associate_saved_boxes(detections, seed_output_index=seed['selected_output_index'])
            with (output / 'subject_track.jsonl').open('x', encoding='utf-8', newline='\n') as sink:
                for row in tracks:
                    _write_row(sink, row)
            receipt['track_replays_completed'] = 1
            append_event(progress, 'associated', dict(receipt))

            stage = 'pose'
            capture = cv2.VideoCapture(str(paths['video_ref']))
            if not capture.isOpened():
                capture.release()
                raise ValueError('Prepared source video cannot open for pose')
            estimator = None
            try:
                with (output / 'native.partial.jsonl').open('x', encoding='utf-8', newline='\n') as sink:
                    for index, track in enumerate(tracks):
                        failed_frame = index
                        image, timestamp, pixel_sha = _image(
                            capture, index, width=width, height=height, fps=fps,
                            expected_pixel_sha=detections[index]['decoded_bgr_sha256'])
                        linked = track['status'] in ('seeded', 'linked')
                        if linked:
                            if pose is None:
                                pose = stack.enter_context(pose_factory(
                                    paths['runtime_ref'], paths['worker_ref'], paths['model_ref'],
                                    expected_model_sha256=prep['model_ref']['sha256'],
                                    max_calls=count, output_dir=pose_dir))
                                if any(pose.metadata.get('runtime', {}).get(key) != value
                                       for key, value in prep['expected_runtime'].items()):
                                    raise ValueError('Isolated pose runtime changed')
                                estimator = RTMPoseNativeEstimator(pose, crop_xyxy=tuple(prep['crop_xyxy_px']))
                            estimate = estimator.estimate(image, person_bbox_xyxy=track['selected_bbox_xyxy_px'])
                            landmarks, geometry = estimate.landmarks, estimate.input_geometry
                            reason = None
                        else:
                            reason = track['status']
                            landmarks = _missing_landmarks(reason)
                            geometry = {'input_mode': 'not_run', 'roi_xywh': None,
                                        'affine_src_to_input': None, 'affine_input_to_src': None,
                                        'sdk_geometry': None}
                        selection = {'status': track['status'], 'eligible_count': track['eligible_count'],
                                     'selected_output_index': track['selected_output_index'],
                                     'selected_bbox_xyxy_px': track['selected_bbox_xyxy_px']}
                        frame = NativePoseFrame({
                            'schema_version': 'native-keypoints-v1', 'pitch_id': prep['pitch_id'],
                            'backend': 'rtmpose_live_onnx', 'topology': 'coco_17',
                            'frame_index': index, 'timestamp_ms': timestamp,
                            'source_video_sha256': prep['video_ref']['sha256'],
                            'decoded_bgr_sha256': pixel_sha,
                            'image_size': {'width': width, 'height': height},
                            'coordinate_space': 'original_image_pixels_xy',
                            'quality_status': 'not_calibrated', 'usable_for_analysis': None,
                            'input_geometry': geometry,
                            'model_selection': {
                                'source': 'operator-seeded mutual-IoU subject track',
                                'inference_mode': 'live_stateless_roi', 'pose_not_run': not linked,
                                'pose_not_run_reason': reason, 'coordinate_origin': 'new_inference' if linked else 'not_run',
                                'new_pose_call': linked,
                                'isolated_worker_attempt_index': pose.calls_completed if linked else None,
                                'person_box_selection': selection, 'track_policy': TRACK_POLICY,
                                'initial_seed_ref': seed_ref,
                            },
                            'landmarks': landmarks,
                        })
                        _write_row(sink, frame.to_dict())
                        frames.append(frame)
                        receipt['frames_completed'] = index + 1
                        if pose is not None:
                            receipt.update(pose_calls_attempted=pose.calls_attempted,
                                           pose_calls_completed=pose.calls_completed)
                        append_event(progress, f'posed-{index:06d}', dict(receipt))
                        if (index+1) % 50 == 0:
                            print(f'{prep["pitch_id"]}: pose {index+1}/{count}; calls{receipt["pose_calls_completed"]}', flush=True)
                    if capture.read()[0]:
                        raise ValueError('Source contains extra frames after prepared timeline')
            finally:
                capture.release()

        stage, failed_frame = 'export', None
        generated = [reference(root, path) for folder in (detector_dir, pose_dir)
                     for path in folder.rglob('*') if path.is_file()]
        generated.extend(reference(root, output / name) for name in ('person_boxes.jsonl', 'subject_track.jsonl'))
        manifest = _manifest(root, prep, seed, prep_ref, seed_ref, generated, fps)
        native_folder = output / 'rtmpose' / prep['pitch_id']
        native_folder.parent.mkdir()
        write_dataset(native_folder, manifest, frames)
        write_json(native_folder / 'native_pose_summary.json', summarize_native(manifest, frames))
        if render_overlay:
            write_json(native_folder / 'overlay_validation.json', write_native_overlay(
                paths['video_ref'], manifest, frames, native_folder / 'overlay_native.mp4'))
        status_counts = dict(Counter(row['status'] for row in tracks))
        missing = [row['frame_index'] for row in tracks if row['status'] not in ('seeded', 'linked')]
        write_json(output / 'seeded_skeleton_summary.json', {
            'schema_version': 'seeded-skeleton-summary-v1', 'pitch_id': prep['pitch_id'],
            'total_frames': count, 'track_status_counts': status_counts,
            'first_break_frame': next((row['frame_index'] for row in tracks
                                       if row['status'].startswith('track_break_')), None),
            'missing_frame_indices': missing, 'native_pose_frames': count - len(missing),
            'quality_status': 'not_calibrated', 'usable_for_analysis': None,
            'identity_switch_confirmed': None, 'accuracy': None,
            'phase2_automatic_reliability': 'NOT_PASSED',
            'note': 'A human frame-zero choice and geometric links do not establish every-frame identity or joint accuracy.',
        })
        changed = [name for name, digest in bound_hashes.items() if sha256(root / name) != digest]
        if changed:
            raise ValueError('Bound source files changed during skeleton execution')
        receipt.update(state='completed', completed_at_utc=_utc(), failed_stage=None,
                       failed_frame=None, source_sha256_changes=[],
                       track_status_counts=status_counts,
                       native_output=native_folder.relative_to(root).as_posix(),
                       overlay_generated=render_overlay)
        append_event(progress, 'completed', dict(receipt))
        write_json(output / 'run_receipt.json', receipt)
    except BaseException as error:
        if detector is not None:
            receipt.update(new_detector_calls_attempted=closed_detector_attempts + detector.calls_attempted,
                           new_detector_calls_completed=closed_detector_completions + detector.calls_completed)
        if pose is not None:
            receipt.update(pose_calls_attempted=pose.calls_attempted,
                           pose_calls_completed=pose.calls_completed)
        receipt.update(state='failed', failed_at_utc=_utc(), failed_stage=stage,
                       failed_frame=failed_frame, failure=f'{type(error).__name__}: {error}')
        try:
            append_event(progress, 'run-failed', dict(receipt))
        except OSError:
            pass
        try:
            write_json(output / 'run_receipt.json', receipt)
        except OSError:
            pass
        raise
    return receipt
