"""Operator-seeded native capture over saved detections, with no detector calls."""
from __future__ import annotations

from collections import Counter
from contextlib import ExitStack
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

import cv2

from .native_person_box_live import _missing_landmarks
from .native_pose import NativePoseFrame, validate_manifest
from .native_pose_io import BoundReader, read_dataset, read_json, reference, sha256, write_dataset, write_json
from .native_pose_live import _approval, _manifest, _record, _utc, preflight_live
from .native_seeded_cache import cache_geometry_matches
from .native_seeded_track import TRACK_POLICY, associate_saved_boxes


def preflight_seeded(root: Path, config_path: Path):
    config = read_json(config_path)
    if config.get('schema_version') != 'native-seeded-track-run-v1':
        raise ValueError('Expected native-seeded-track-run-v1')
    _approval(config)
    if config.get('track_policy') != TRACK_POLICY or config.get('max_detector_calls') != 0:
        raise ValueError('Frozen association policy and zero detector calls required')
    required = ('source_config_ref', 'seed_ref', 'detections_ref', 'cached_manifest_ref', 'cached_keypoints_ref', 'cached_receipt_ref')
    refs = config.get('source_refs', [])
    if any(config[key] not in refs for key in required):
        raise ValueError('All input, seed, detection and cache sources must be declared')
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    base, clips = preflight_live(root, reader.path(config['source_config_ref']))
    if len(clips) != 1 or clips[0]['frame_count'] > 321:
        raise ValueError('One approved source timeline of at most321frames required')
    clip = clips[0]
    manifest_path = reader.path(config['cached_manifest_ref'])
    keys_path = reader.path(config['cached_keypoints_ref'])
    if manifest_path.name != 'native_pose_manifest.json' or keys_path.name != 'native_keypoints.jsonl' or manifest_path.parent != keys_path.parent:
        raise ValueError('The bound native cache must be one complete dataset')
    cached_manifest, cached_frames = read_dataset(manifest_path.parent)
    cached_receipt = reader.json(config['cached_receipt_ref'])
    if (cached_receipt.get('state') != 'completed' or cached_receipt.get('pitch_id') != clip['pitch_id']
            or cached_receipt.get('frame_count') != clip['frame_count']
            or cached_manifest['pitch_id'] != clip['pitch_id']
            or cached_manifest['video']['sha256'] != clip['video_ref']['sha256']
            or cached_manifest['video']['frame_count'] != clip['frame_count']
            or Fraction(cached_manifest['timebase']['fps_fraction']) != clip['fps']):
        raise ValueError('Previous person-box evidence differs from the declared source timeline')
    with reader.path(config['detections_ref']).open(encoding='utf-8') as stream:
        detections = [json.loads(line) for line in stream]
    if len(detections) != clip['frame_count'] or len(cached_frames) != clip['frame_count']:
        raise ValueError('Saved detections and native cache must retain every source frame')
    for index, row in enumerate(detections):
        if (row.get('frame_index') != index or row.get('timestamp_ms') != float(Fraction(index*1000, 1)/clip['fps'])
                or row.get('policy') != 'unique_person_box_center_in_operator_roi_v1'
                or row.get('final_score_threshold') != .7 or not isinstance(row.get('decoded_bgr_sha256'), str)):
            raise ValueError('Original saved candidate protocol or source time changed')
    prior = [index for index, frame in enumerate(cached_frames)
             if frame.to_dict()['model_selection'].get('pose_not_run') is False]
    if prior != config.get('prior_inferred_frame_indices') or len(prior) != cached_receipt.get('pose_calls_completed'):
        raise ValueError('Already-inferred person-box frames differ from bound evidence')
    budget = config.get('max_new_pose_calls')
    if isinstance(budget, bool) or not isinstance(budget, int) or not 0 <= budget <= 319 or budget != clip['frame_count']-len(prior):
        raise ValueError('New pose budget must exclude every already-inferred frame')
    seed = reader.json(config['seed_ref'])
    if (seed.get('schema_version') != 'native-subject-seed-v1' or seed.get('status') != 'operator_confirmed'
            or seed.get('ground_truth') is not False or seed.get('pitch_id') != clip['pitch_id']
            or seed.get('frame_index') != 0 or seed.get('source_video_ref') != clip['video_ref']
            or seed.get('saved_detection_ref') != config['detections_ref']
            or seed.get('decoded_bgr_sha256') != detections[0]['decoded_bgr_sha256']):
        raise ValueError('Source-bound initial operator confirmation required')
    _approval({'status': 'approved', 'approval': {key: seed.get(key) for key in ('reviewer', 'reviewed_at_utc', 'user_reply')}})
    initial = [candidate for candidate in detections[0]['candidates']
               if candidate['eligible'] and candidate['output_index'] == seed.get('selected_output_index')]
    if (isinstance(seed.get('selected_output_index'), bool) or len(initial) != 1
            or initial[0]['bbox_original_xyxy_px'] != seed.get('selected_bbox_xyxy_px')):
        raise ValueError('Confirmed seed is not the exact saved eligible candidate')
    claim_text = config.get('once_only_claim_path')
    if not isinstance(claim_text, str):
        raise ValueError('Once-only replay and inference claim required')
    claim = (root / claim_text).resolve()
    if not claim.is_relative_to(root/'analysis_results') or claim.exists() or not claim.parent.is_dir():
        raise ValueError('Once-only claim must be new inside project analysis_results')
    return config, base, clip, detections, seed, cached_manifest, cached_frames, prior, claim


def _seeded_manifest(base, clip, config, config_ref, evidence=()):
    manifest = _manifest(base, clip, config_ref)
    for ref in [*config['source_refs'], *evidence]:
        if ref not in manifest['source_refs']:
            manifest['source_refs'].append(ref)
    manifest['roi_provenance'].update(
        roi_source='operator-confirmed initial subject, then mutual unique maximum IoU over saved eligible boxes',
        seed_ref=config['seed_ref'], saved_detections_ref=config['detections_ref'], track_policy=TRACK_POLICY,
        per_frame_boxes_human_reviewed=False,
        coordinate_origin='new person-box inference or exact-source/model/frame/geometry native cache')
    return manifest


def run_seeded(root: str | Path, config_path: str | Path, output: str | Path, *, pose_factory=None, render_overlay=True):
    root, config_path = Path(root).resolve(strict=True), Path(config_path).resolve(strict=True)
    if not config_path.is_relative_to(root):
        raise ValueError('Run configuration must be within project')
    output = Path(output).resolve()
    if output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('A new output directory inside project analysis_results is required')
    config, base, clip, detections, seed, cache_manifest, cache_frames, prior, claim = preflight_seeded(root, config_path)
    config_ref = reference(root, config_path)
    manifest = _seeded_manifest(base, clip, config, config_ref)
    validate_manifest(manifest)
    before = {ref['path']: ref['sha256'] for ref in manifest['source_refs']}
    output.mkdir(parents=True, exist_ok=False)
    write_json(claim, {'config_ref': config_ref, 'output': output.relative_to(root).as_posix(),
                      'claimed_at_utc': _utc(), 'automatic_retries': False})
    receipt = {'schema_version': 'native-seeded-track-execution-v1', 'state': 'running', 'started_at_utc': _utc(),
               'config_ref': config_ref, 'approval': config['approval'], 'pitch_id': clip['pitch_id'],
               'frame_count': clip['frame_count'], 'seed_output_index': seed['selected_output_index'],
               'detector_calls': 0, 'max_new_pose_calls': config['max_new_pose_calls'],
               'pose_calls_attempted': 0, 'pose_calls_completed': 0, 'cached_pose_frames_reused': 0,
               'tracking_replays_attempted': 0, 'tracking_replays_completed': 0,
               'frames_completed': 0, 'failed_frame': None, 'new_annotations': 0, 'formal_promotion': False,
               'quality_status': 'not_calibrated', 'usable_for_analysis': None, 'phase2_automatic_reliability': 'NOT_PASSED'}
    receipt_path = output/'run_receipt.json'
    _record(receipt_path, receipt)
    from .native_pose_estimator import RTMPoseNativeEstimator, prepare_rtmpose_input
    from .native_pose_transport import IsolatedOnnxTransport
    from .native_pose_review import summarize_native, write_native_overlay
    pose_factory = pose_factory or IsolatedOnnxTransport
    worker = None
    capture = None
    records, origins = [], []
    worker_dir = output/'pose_worker'; worker_dir.mkdir()
    try:
        receipt['tracking_replays_attempted'] = 1; _record(receipt_path, receipt)
        tracks = associate_saved_boxes(detections, seed_output_index=seed['selected_output_index'])
        receipt['tracking_replays_completed'] = 1
        with (output/'subject_track.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
            for track in tracks:
                stream.write(json.dumps(track, allow_nan=False)+'\n')
        _record(receipt_path, receipt)
        with ExitStack() as stack:
            capture = cv2.VideoCapture(str(clip['video_path']))
            estimator = None
            with (output/'native.partial.jsonl').open('x', encoding='utf-8', newline='\n') as stream:
                for index, track in enumerate(tracks):
                    receipt['failed_frame'] = index
                    okay, image = capture.read()
                    timestamp = float(Fraction(index*1000, 1)/clip['fps'])
                    actual = capture.get(cv2.CAP_PROP_POS_MSEC)
                    if (not okay or image.shape != (clip['height'], clip['width'], 3)
                            or not math.isfinite(actual) or abs(actual-timestamp) >= 1):
                        raise ValueError(f'Source decode/timing changed at frame{index}')
                    pixel_sha = hashlib.sha256(image.tobytes()).hexdigest()
                    if pixel_sha != detections[index]['decoded_bgr_sha256']:
                        raise ValueError(f'Saved detector source pixels differ at frame{index}')
                    linked = track['status'] in ('seeded', 'linked')
                    origin, reason, cache_reasons, cached_selection = 'not_run', track['status'], [], None
                    attempt = None
                    if linked and index in prior:
                        _, expected_geometry = prepare_rtmpose_input(image, clip['crop_xyxy_px'], person_bbox_xyxy=track['selected_bbox_xyxy_px'])
                        cached_record = cache_frames[index].to_dict()
                        reusable, cache_reasons = cache_geometry_matches(
                            cache_manifest, cached_record, model_sha256=base['model_ref']['sha256'],
                            source_video_sha256=clip['video_ref']['sha256'], frame_index=index, timestamp_ms=timestamp,
                            decoded_bgr_sha256=pixel_sha, person_bbox_xyxy=track['selected_bbox_xyxy_px'], input_geometry=expected_geometry)
                        if reusable:
                            landmarks, geometry = cached_record['landmarks'], cached_record['input_geometry']
                            cached_selection = cached_record['model_selection']
                            origin, reason = 'cached_exact_geometry', None
                            receipt['cached_pose_frames_reused'] += 1
                        else:
                            reason = 'cache_geometry_mismatch_no_rerun'
                    elif linked:
                        if worker is None:
                            worker = stack.enter_context(pose_factory(
                                root/base['runtime_ref']['path'], root/base['worker_ref']['path'], root/base['model_ref']['path'],
                                expected_model_sha256=base['model_ref']['sha256'], max_calls=config['max_new_pose_calls'], output_dir=worker_dir))
                            for key, value in base['expected_runtime'].items():
                                if worker.metadata.get('runtime', {}).get(key) != value:
                                    raise ValueError('Isolated runtime changed: '+key)
                            receipt['worker_metadata'] = worker.metadata
                            estimator = RTMPoseNativeEstimator(worker, crop_xyxy=tuple(clip['crop_xyxy_px']))
                        estimate = estimator.estimate(image, person_bbox_xyxy=track['selected_bbox_xyxy_px'])
                        landmarks, geometry = estimate.landmarks, estimate.input_geometry
                        origin, reason, attempt = 'new_inference', None, worker.calls_completed
                    if origin == 'not_run':
                        landmarks = _missing_landmarks(reason)
                        geometry = {'input_mode':'not_run','roi_xywh':None,'affine_src_to_input':None,'affine_input_to_src':None,'sdk_geometry':None}
                    selected = {'status':track['status'], 'eligible_count':track['eligible_count'],
                                'selected_output_index':track['selected_output_index'], 'selected_bbox_xyxy_px':track['selected_bbox_xyxy_px']}
                    model_selection = {'source':'operator-seeded association over saved detections', 'inference_mode':'live_stateless_roi',
                        'pose_not_run':origin=='not_run', 'pose_not_run_reason':reason, 'coordinate_origin':origin,
                        'new_pose_call':origin=='new_inference', 'isolated_worker_attempt_index':attempt,
                        'person_box_selection':selected, 'track_policy':TRACK_POLICY,
                        'initial_seed_ref':config['seed_ref'], 'cache_check_reasons':cache_reasons,
                        'cached_native_source_ref':config['cached_keypoints_ref'] if origin=='cached_exact_geometry' else None,
                        'cached_source_model_selection':cached_selection}
                    frame = NativePoseFrame({'schema_version':'native-keypoints-v1','pitch_id':clip['pitch_id'],
                        'backend':manifest['backend']['name'],'topology':'coco_17','frame_index':index,'timestamp_ms':timestamp,
                        'source_video_sha256':clip['video_ref']['sha256'],'decoded_bgr_sha256':pixel_sha,
                        'image_size':{'width':clip['width'],'height':clip['height']},'coordinate_space':'original_image_pixels_xy',
                        'quality_status':'not_calibrated','usable_for_analysis':None,'input_geometry':geometry,
                        'model_selection':model_selection,'landmarks':landmarks})
                    stream.write(json.dumps(frame.to_dict(), allow_nan=False)+'\n'); stream.flush()
                    records.append(frame); origins.append(origin)
                    receipt['frames_completed'] = index+1
                    if worker is not None:
                        receipt.update(pose_calls_attempted=worker.calls_attempted, pose_calls_completed=worker.calls_completed)
                    _record(receipt_path, receipt)
                    if (index+1)%50==0:
                        print(f'seeded {index+1}/{clip["frame_count"]}; newpose{receipt["pose_calls_completed"]}; reused{receipt["cached_pose_frames_reused"]}', flush=True)
                if capture.read()[0]:raise ValueError('Unexpected extra source frames')
        if receipt['pose_calls_completed'] != origins.count('new_inference') or receipt['pose_calls_attempted']>config['max_new_pose_calls']:
            raise ValueError('New pose calls differ from declared coordinate origins')
        evidence = [reference(root,p) for p in worker_dir.iterdir() if p.is_file()]
        evidence.append(reference(root,output/'subject_track.jsonl'))
        manifest = _seeded_manifest(base,clip,config,config_ref,evidence)
        folder=output/'rtmpose'/clip['pitch_id']
        write_dataset(folder,manifest,records)
        write_json(folder/'native_pose_summary.json',summarize_native(manifest,records))
        if render_overlay:
            write_json(folder/'overlay_validation.json',write_native_overlay(clip['video_path'],manifest,records,folder/'overlay_native.mp4'))
        status_counts=dict(Counter(track['status'] for track in tracks))
        origin_counts=dict(Counter(origins))
        write_json(output/'seeded_track_summary.json',{'total_frames':len(tracks),'track_status_counts':status_counts,
            'coordinate_origin_counts':origin_counts,'first_break_frame':next((t['frame_index'] for t in tracks if t['status'].startswith('track_break_')),None),
            'linked_frame_indices':[t['frame_index'] for t in tracks if t['status'] in ('seeded','linked')],
            'cached_reused_frame_indices':[i for i,v in enumerate(origins) if v=='cached_exact_geometry'],
            'missing_frame_indices':[i for i,v in enumerate(origins) if v=='not_run'],
            'identity_switch_confirmed':None,'accuracy':None,'new_annotations':0,'quality_status':'not_calibrated',
            'limitations':['Initial operation confirmation is not per-frame identity GT.',
                           'Geometric association can link the wrong person; coordinates do not establish reliability.']})
        changed=[name for name,digest in before.items() if sha256(root/name)!=digest]
        receipt.update(state='completed',completed_at_utc=_utc(),failed_frame=None,source_files_checked=len(before),source_sha256_changes=changed,
                       track_status_counts=status_counts,coordinate_origin_counts=origin_counts,
                       native_output=folder.relative_to(root).as_posix(),overlay_generated=render_overlay)
        if changed:raise ValueError('Bound source files changed during execution')
    except BaseException as error:
        if worker is not None:receipt.update(pose_calls_attempted=worker.calls_attempted,pose_calls_completed=worker.calls_completed)
        receipt.update(state='failed',failed_at_utc=_utc(),failure=f'{type(error).__name__}: {error}')
        _record(receipt_path,receipt);raise
    finally:
        if capture is not None:capture.release()
    _record(receipt_path,receipt)
    return receipt
