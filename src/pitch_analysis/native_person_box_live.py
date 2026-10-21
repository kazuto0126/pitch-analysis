"""One approved detector-conditioned native run; production analysis is untouched."""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import cv2

from .native_person_boxes import FINAL_SCORE_THRESHOLD, POLICY, prepare_detector_input, select_person_box
from .native_pose import NativePoseFrame, TOPOLOGIES, validate_manifest
from .native_pose_io import BoundReader, read_json, reference, sha256, write_dataset, write_json
from .native_pose_live import _manifest, _record, _utc, preflight_live


def preflight_person_box(root: Path, config_path: Path):
    config, clips = preflight_live(root, config_path)
    extension = config.get('person_box_conditioning', {})
    if extension.get('schema_version') != 'native-person-box-conditioning-v1' or len(clips) != 1:
        raise ValueError('One explicitly approved person-box clip required')
    if extension.get('policy') != POLICY or extension.get('final_score_threshold') != FINAL_SCORE_THRESHOLD:
        raise ValueError('Fixed person-box policy or detector threshold changed')
    if extension.get('max_detector_calls') != config['max_real_calls'] or not 1 <= config['max_real_calls'] <= 321:
        raise ValueError('Single-clip detector/pose limits must match and not exceed321')
    refs = extension.get('source_refs', [])
    required = [extension[key] for key in ('model_ref', 'worker_ref', 'metadata_ref')]
    if any(ref not in refs for ref in required):
        raise ValueError('Detector model/worker/metadata must be source-bound')
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    metadata = reader.json(extension['metadata_ref'])
    baked = metadata.get('actual_baked_postprocessing', {})
    if (metadata.get('status') != 'metadata_compatible_no_inference'
            or metadata.get('model_sha256') != extension['model_ref']['sha256']
            or metadata.get('real_detector_calls') != 0 or metadata.get('real_pose_calls') != 0
            or baked.get('nms_applied_in_graph') is not True or baked.get('second_nms') is not False
            or not math.isclose(baked.get('iou_threshold', -1), .65, abs_tol=1e-6)
            or not math.isclose(baked.get('score_threshold', -1), .01, abs_tol=1e-6)
            or extension.get('baked_postprocessing') != baked):
        raise ValueError('Exact zero-inference model preflight or baked NMS provenance changed')
    region = read_json(root / config['region_config_ref']['path'])
    original = next(item for item in region['clips'] if item['pitch_id'] == clips[0]['pitch_id'])
    if extension.get('operator_roi') != original['subject_roi']:
        raise ValueError('Person-box operator ROI differs from reviewed region configuration')
    claim_text = extension.get('once_only_claim_path')
    if not isinstance(claim_text, str):
        raise ValueError('An explicit once-only execution claim is required')
    claim = (root / claim_text).resolve()
    if not claim.is_relative_to(root / 'analysis_results') or claim.exists() or not claim.parent.is_dir():
        raise ValueError('Once-only execution claim must be new inside project analysis_results')
    return config, clips[0], extension, claim


def _missing_landmarks(reason):
    return [{'name': name, 'index': index, 'x_px': None, 'y_px': None,
             'z': None, 'visibility': None, 'presence': None, 'native_score': None,
             'coordinate_state': 'missing', 'missing_reason': reason,
             'source_record': {'pose_not_run': True, 'reason': reason}}
            for index, name in enumerate(TOPOLOGIES['coco_17']['names'])]


def _conditioned_manifest(config, clip, config_ref, extension, evidence_refs=()):
    manifest = _manifest(config, clip, config_ref)
    for ref in [*extension['source_refs'], *evidence_refs]:
        if ref not in manifest['source_refs']:
            manifest['source_refs'].append(ref)
    manifest['roi_provenance'].update(
        roi_source='detector-derived per-frame person box; HSU reviewed enclosing motion crop and operator ROI only',
        detector_model_ref=extension['model_ref'], person_box_policy=POLICY,
        operator_roi=extension['operator_roi'], per_frame_boxes_human_reviewed=False)
    return manifest


def run_person_box(root: str | Path, config_path: str | Path, output: str | Path, *,
                   detector_factory=None, pose_factory=None, render_overlay=True):
    root, config_path = Path(root).resolve(strict=True), Path(config_path).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(root / 'analysis_results'):
        raise ValueError('A new output within project analysis_results is required')
    config, clip, extension, claim = preflight_person_box(root, config_path)
    config_ref = reference(root, config_path)
    manifest = _conditioned_manifest(config, clip, config_ref, extension)
    validate_manifest(manifest)
    before = {ref['path']: ref['sha256'] for ref in manifest['source_refs']}
    output.mkdir(parents=True, exist_ok=False)
    write_json(claim, {'config_ref': config_ref, 'output': output.relative_to(root).as_posix(),
                      'claimed_at_utc': _utc(), 'automatic_retries': False})
    receipt = {'schema_version': 'native-person-box-execution-v1', 'state': 'running',
               'started_at_utc': _utc(), 'config_ref': config_ref, 'approval': config['approval'],
               'pitch_id': clip['pitch_id'], 'frame_count': clip['frame_count'],
               'max_detector_calls': extension['max_detector_calls'], 'max_pose_calls': config['max_real_calls'],
               'detector_calls_attempted': 0, 'detector_calls_completed': 0,
               'pose_calls_attempted': 0, 'pose_calls_completed': 0,
               'frames_completed': 0, 'failed_frame': None, 'new_annotations': 0,
               'formal_promotion': False, 'quality_status': 'not_calibrated',
               'usable_for_analysis': None, 'phase2_automatic_reliability': 'NOT_PASSED'}
    receipt_path = output / 'run_receipt.json'
    _record(receipt_path, receipt)
    from .native_person_box_transport import IsolatedDetectorTransport
    from .native_pose_transport import IsolatedOnnxTransport
    from .native_pose_estimator import RTMPoseNativeEstimator
    from .native_pose_review import summarize_native, write_native_overlay
    detector_factory = detector_factory or IsolatedDetectorTransport
    pose_factory = pose_factory or IsolatedOnnxTransport
    detector = pose = capture = None
    records, boxes = [], []
    worker_dirs = [output / 'detector_worker', output / 'pose_worker']
    for folder in worker_dirs:
        folder.mkdir()

    def counts():
        for prefix, worker in (('detector', detector), ('pose', pose)):
            if worker is not None:
                receipt[prefix + '_calls_attempted'] = worker.calls_attempted
                receipt[prefix + '_calls_completed'] = worker.calls_completed

    try:
        with ExitStack() as stack:
            detector = stack.enter_context(detector_factory(
                root / config['runtime_ref']['path'], root / extension['worker_ref']['path'],
                root / extension['model_ref']['path'], expected_model_sha256=extension['model_ref']['sha256'],
                max_calls=extension['max_detector_calls'], output_dir=worker_dirs[0]))
            pose = stack.enter_context(pose_factory(
                root / config['runtime_ref']['path'], root / config['worker_ref']['path'],
                root / config['model_ref']['path'], expected_model_sha256=config['model_ref']['sha256'],
                max_calls=config['max_real_calls'], output_dir=worker_dirs[1]))
            for worker in (detector, pose):
                for key, value in config['expected_runtime'].items():
                    if worker.metadata.get('runtime', {}).get(key) != value:
                        raise ValueError('Isolated runtime changed: ' + key)
            receipt.update(detector_metadata=detector.metadata, pose_metadata=pose.metadata)
            estimator = RTMPoseNativeEstimator(pose, crop_xyxy=tuple(clip['crop_xyxy_px']))
            capture = cv2.VideoCapture(str(clip['video_path']))
            with (output / 'native.partial.jsonl').open('x', encoding='utf-8', newline='\n') as native_sink, \
                    (output / 'person_boxes.jsonl').open('x', encoding='utf-8', newline='\n') as box_sink:
                for index in range(clip['frame_count']):
                    receipt['failed_frame'] = index
                    okay, image = capture.read()
                    timestamp = float(Fraction(index * 1000, 1) / clip['fps'])
                    native_time = capture.get(cv2.CAP_PROP_POS_MSEC)
                    if (not okay or image.shape != (clip['height'], clip['width'], 3)
                            or not math.isfinite(native_time) or abs(native_time-timestamp) >= 1):
                        raise ValueError(f'Source decode/timing changed at frame{index}')
                    pixel_sha = hashlib.sha256(image.tobytes()).hexdigest()
                    tensor, geometry = prepare_detector_input(image, clip['crop_xyxy_px'])
                    selection = select_person_box(detector.run(tensor), geometry, extension['operator_roi'])
                    box_record = {'frame_index': index, 'timestamp_ms': timestamp, 'decoded_bgr_sha256': pixel_sha,
                                  'detector_attempt_index': detector.calls_completed,
                                  'detector_input_geometry': geometry, **selection}
                    box_sink.write(json.dumps(box_record, allow_nan=False) + '\n'); box_sink.flush()
                    boxes.append(box_record)
                    missing = selection['status'] != 'selected'
                    if missing:
                        reason = selection['status']
                        landmarks = _missing_landmarks(reason)
                        pose_geometry = {'input_mode': 'not_run', 'roi_xywh': None,
                                         'affine_src_to_input': None, 'affine_input_to_src': None, 'sdk_geometry': None}
                    else:
                        estimate = estimator.estimate(image, person_bbox_xyxy=selection['selected_bbox_xyxy_px'])
                        landmarks, pose_geometry = estimate.landmarks, estimate.input_geometry
                    record = NativePoseFrame({
                        'schema_version': 'native-keypoints-v1', 'pitch_id': clip['pitch_id'],
                        'backend': 'rtmpose_live_onnx', 'topology': 'coco_17', 'frame_index': index,
                        'timestamp_ms': timestamp, 'source_video_sha256': clip['video_ref']['sha256'],
                        'decoded_bgr_sha256': pixel_sha,
                        'image_size': {'width': clip['width'], 'height': clip['height']},
                        'coordinate_space': 'original_image_pixels_xy', 'quality_status': 'not_calibrated',
                        'usable_for_analysis': None, 'input_geometry': pose_geometry,
                        'model_selection': {'source': 'detector-conditioned single person inside reviewed motion crop',
                            'inference_mode': 'live_stateless_roi', 'pose_not_run': missing,
                            'pose_not_run_reason': selection['status'] if missing else None,
                            'person_box_selection': selection,
                            'detector_attempt_index': detector.calls_completed,
                            'isolated_worker_attempt_index': None if missing else pose.calls_completed},
                        'landmarks': landmarks})
                    native_sink.write(json.dumps(record.to_dict(), allow_nan=False) + '\n'); native_sink.flush()
                    records.append(record)
                    receipt['frames_completed'] = index + 1
                    counts(); _record(receipt_path, receipt)
                    if (index+1) % 50 == 0:
                        print(f'person-box {index+1}/{clip["frame_count"]}; pose calls{pose.calls_completed}', flush=True)
                if capture.read()[0]:
                    raise ValueError('Unexpected extra source frames')
        if detector.calls_completed != clip['frame_count'] or pose.calls_completed != sum(row['status']=='selected' for row in boxes):
            raise ValueError('Completed calls differ from full source and explicit selections')
        evidence = [reference(root, file) for folder in worker_dirs for file in folder.iterdir() if file.is_file()]
        evidence.append(reference(root, output / 'person_boxes.jsonl'))
        manifest = _conditioned_manifest(config, clip, config_ref, extension, evidence)
        folder = output / 'rtmpose' / clip['pitch_id']
        write_dataset(folder, manifest, records)
        write_json(folder / 'native_pose_summary.json', summarize_native(manifest, records))
        if render_overlay:
            write_json(folder / 'overlay_validation.json', write_native_overlay(
                clip['video_path'], manifest, records, folder / 'overlay_native.mp4'))
        status_counts = dict(Counter(row['status'] for row in boxes))
        write_json(output / 'person_box_summary.json', {
            'total_frames': clip['frame_count'], 'status_counts': status_counts,
            'emitted_detections': sum(row['emitted_detection_count'] for row in boxes),
            'rejection_reasons': dict(Counter(reason for row in boxes for candidate in row['candidates']
                                              for reason in candidate['rejection_reasons'])),
            'selected_bbox_outside_crop_frames': [row['frame_index'] for row in boxes
                if row['selected_bbox_extends_outside_operator_crop']],
            'missing_frame_indices': [row['frame_index'] for row in boxes if row['status']!='selected'],
            'accuracy': None, 'new_annotations': 0, 'quality_status': 'not_calibrated',
            'limitations': ['No box or ambiguity causes missing, not a repaired pose.',
                           'Detected boxes can still mix people or truncate limbs.',
                           'Native coordinates and detector scores are not human visibility or reliable data.']})
        changed = [name for name, digest in before.items() if sha256(root/name) != digest]
        receipt.update(state='completed', completed_at_utc=_utc(), failed_frame=None,
                       source_files_checked=len(before), source_sha256_changes=changed,
                       status_counts=status_counts, native_output=folder.relative_to(root).as_posix(),
                       overlay_generated=render_overlay)
        if changed:
            raise ValueError('Bound source files changed during execution')
    except BaseException as error:
        counts()
        receipt.update(state='failed', failed_at_utc=_utc(), failure=f'{type(error).__name__}: {error}')
        _record(receipt_path, receipt)
        raise
    finally:
        if capture is not None:
            capture.release()
    _record(receipt_path, receipt)
    return receipt
