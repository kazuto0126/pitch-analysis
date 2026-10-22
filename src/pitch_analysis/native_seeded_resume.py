"""Explicit continuation of an interrupted native run, never replaying tracking.

The saved prefix, old claim and failed receipts stay immutable. A new claim and
worker permit only the exact never-executed tail, within the original budget.
"""
from __future__ import annotations

from contextlib import ExitStack
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path

import cv2

from .native_pose import NativePoseFrame
from .native_pose_estimator import RTMPoseNativeEstimator, prepare_rtmpose_input
from .native_pose_io import BoundReader, _loads, read_dataset, read_json, reference, sha256, write_dataset, write_json
from .native_pose_live import _approval, _utc, preflight_live
from .native_pose_review import summarize_native, write_native_overlay
from .native_pose_transport import IsolatedOnnxTransport
from .native_progress_log import append_event
from .native_seeded_live import _seeded_manifest
from .native_seeded_track import TRACK_POLICY


def _rows(path):
    return [_loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines()]


def _exact(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def preflight_resume(root: Path, config_path: Path):
    config = read_json(config_path)
    if config.get('schema_version') != 'native-seeded-resume-v1':
        raise ValueError('Expected an explicit native-seeded-resume-v1 configuration')
    _approval(config)
    if config.get('max_detector_calls') != 0 or config.get('max_tracking_replays') != 0:
        raise ValueError('Continuation permits no detector or tracking replay')
    required = ('original_config_ref', 'interrupted_receipt_ref', 'prior_claim_ref', 'partial_ref',
                'track_ref', 'native_manifest_ref', 'native_keypoints_ref', 'journal_ref', 'binary_ref')
    refs = config.get('source_refs', [])
    if any(config.get(key) not in refs for key in required):
        raise ValueError('All interrupted evidence must be source-bound')
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    original = reader.json(config['original_config_ref'])
    if original.get('schema_version') != 'native-seeded-track-run-v1' or original.get('track_policy') != TRACK_POLICY:
        raise ValueError('Original frozen tracking policy differs')
    old_reader = BoundReader(root, original['source_refs'])
    for ref in original['source_refs']:
        old_reader.path(ref)
    base, clips = preflight_live(root, old_reader.path(original['source_config_ref']))
    if len(clips) != 1:
        raise ValueError('Continuation is limited to one original source')
    clip = clips[0]
    interruption = reader.json(config['interrupted_receipt_ref'])
    prior_claim = reader.json(config['prior_claim_ref'])
    if (interruption.get('state') != 'interrupted_preserved_no_retry'
            or interruption.get('config_ref') != config['original_config_ref']
            or prior_claim.get('config_ref') != config['original_config_ref']
            or reader.path(config['prior_claim_ref']) != (root/original['once_only_claim_path']).resolve()):
        raise ValueError('Original interrupted state and claim must be preserved')
    mp, kp = reader.path(config['native_manifest_ref']), reader.path(config['native_keypoints_ref'])
    if mp.name != 'native_pose_manifest.json' or kp.name != 'native_keypoints.jsonl' or mp.parent != kp.parent:
        raise ValueError('Bound native dataset must be complete')
    manifest, frames = read_dataset(mp.parent)
    if (manifest['video']['sha256'] != clip['video_ref']['sha256']
            or manifest['backend']['model_sha256'] != base['model_ref']['sha256']
            or manifest['video']['frame_count'] != clip['frame_count']
            or Fraction(manifest['timebase']['fps_fraction']) != clip['fps']):
        raise ValueError('Interrupted native dataset has a different source/model/timebase')
    tracks = _rows(reader.path(config['track_ref']))
    partial = _rows(reader.path(config['partial_ref']))
    journal = _rows(reader.path(config['journal_ref']))
    starts = [r for r in journal if r.get('event') == 'started']
    ends = [r for r in journal if r.get('event') == 'completed']
    count = len(starts)
    if (len(ends) != count or len(journal) != count*2
            or any(journal[i*2] != starts[i] or journal[i*2+1] != ends[i] for i in range(count))
            or [r['attempt_index'] for r in starts] != list(range(1,count+1))
            or [r['attempt_index'] for r in ends] != list(range(1,count+1))
            or interruption.get('pose_calls_attempted') != count
            or interruption.get('pose_calls_completed') != count):
        raise ValueError('Indeterminate, duplicate or inconsistent prior model calls; refuse resume')
    offset = 0
    with reader.path(config['binary_ref']).open('rb') as stream:
        for started, completed in zip(starts, ends, strict=True):
            blob = stream.read(completed['output_length_bytes'])
            if (completed['output_offset_bytes'] != offset
                    or hashlib.sha256(blob).hexdigest() != completed['output_sha256']
                    or started['input_sha256'] != completed['input_sha256']
                    or started['model_sha256'] != base['model_ref']['sha256']):
                raise ValueError('Prior binary/input/model evidence differs')
            offset += len(blob)
        if stream.read(1):
            raise ValueError('Unaccounted prior model payload; refuse resume')
    if (not 0 < len(partial) < len(frames) or len(tracks) != len(frames)
            or len(partial) != interruption.get('source_pose_frames_saved')
            or len(partial) != config.get('prior_saved_pose_frames')):
        raise ValueError('Interrupted prefix is not a complete known saved range')
    new_prefix, cached_prefix = [], []
    for index, (frame, track) in enumerate(zip(frames, tracks, strict=True)):
        value = frame.to_dict()
        if (track.get('frame_index') != index or track.get('track_policy') != TRACK_POLICY
                or track.get('timestamp_ms') != float(Fraction(index*1000,1)/clip['fps'])
                or track.get('timestamp_ms') != value['timestamp_ms']
                or track.get('decoded_bgr_sha256') != value['decoded_bgr_sha256']
                or track.get('status') not in ('seeded','linked')
                or not _exact(track.get('selected_bbox_xyxy_px'), value['model_selection']['person_box_selection']['selected_bbox_xyxy_px'])):
            raise ValueError('Saved track and native source/frame/box pairing differ')
        if index < len(partial):
            NativePoseFrame(partial[index])
            if not _exact(partial[index], value) or value['model_selection'].get('pose_not_run') is not False:
                raise ValueError('Previously saved prediction was changed or is not executed')
            origin = value['model_selection'].get('coordinate_origin')
            if origin == 'new_inference':
                new_prefix.append(index)
                if value['model_selection']['isolated_worker_attempt_index'] != len(new_prefix):
                    raise ValueError('Prior frame-to-call mapping differs')
            elif origin == 'cached_exact_geometry':
                cached_prefix.append(index)
            else:
                raise ValueError('Unknown prior coordinate origin')
        elif (value['model_selection'].get('pose_not_run') is not True
                or value['model_selection'].get('pose_not_run_reason') != 'execution_interrupted_no_retry'
                or value['input_geometry']['input_mode'] != 'not_run'):
            raise ValueError('Tail contains previously executed or uncertain predictions')
    pending = list(range(len(partial), len(frames)))
    if (len(new_prefix) != count or cached_prefix != original['prior_inferred_frame_indices']
            or count != config.get('prior_new_pose_calls')
            or config.get('pending_frame_indices') != pending
            or type(config.get('max_new_pose_calls')) is not int
            or config['max_new_pose_calls'] != len(pending)
            or count+len(pending) != original['max_new_pose_calls']):
        raise ValueError('Resume set or total original inference budget differs')
    claim = (root/config['once_only_claim_path']).resolve()
    if claim.exists() or not claim.is_relative_to(root/'analysis_results') or not claim.parent.is_dir():
        raise ValueError('Fresh continuation claim inside project analysis_results required')
    return config, original, base, clip, frames, tracks, starts, pending, claim


def run_resume(root, config_path, output, *, pose_factory=None, render_overlay=True):
    root, config_path = Path(root).resolve(strict=True), Path(config_path).resolve(strict=True)
    output = Path(output).resolve()
    if not config_path.is_relative_to(root) or output.exists() or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('Project configuration and fresh project output required')
    config, original, base, clip, frames, tracks, prior_starts, pending, claim = preflight_resume(root,config_path)
    config_ref = reference(root,config_path)
    output.mkdir(parents=True,exist_ok=False)
    write_json(claim, {'config_ref':config_ref,'output':output.relative_to(root).as_posix(),
                       'claimed_at_utc':_utc(),'pending_frames':pending,'automatic_retries':False})
    receipt = {'schema_version':'native-seeded-resume-execution-v1','state':'running','config_ref':config_ref,
               'started_at_utc':_utc(),'pitch_id':clip['pitch_id'],'frame_count':clip['frame_count'],
               'prior_saved_pose_frames':len(frames)-len(pending),'prior_new_pose_calls':len(prior_starts),
               'prior_cached_pose_frames':original['prior_inferred_frame_indices'],
               'max_new_pose_calls':len(pending),'new_detector_calls':0,'new_tracking_replays':0,
               'pose_calls_attempted':0,'pose_calls_completed':0,'new_frames_saved':0,'failed_frame':None,
               'new_annotations':0,'formal_promotion':False,'quality_status':'not_calibrated','usable_for_analysis':None,
               'phase2_automatic_reliability':'NOT_PASSED'}
    progress = output/'progress'; progress.mkdir()
    append_event(progress,'started',receipt)
    pose_factory = pose_factory or IsolatedOnnxTransport
    worker = None
    capture = cv2.VideoCapture(str(clip['video_path']))
    worker_dir = output/'pose_worker'; worker_dir.mkdir()
    try:
        with ExitStack() as stack, (output/'continuation.partial.jsonl').open('x',encoding='utf-8',newline='\n') as stream:
            estimator = None
            previous_attempt = 0
            for index, track in enumerate(tracks):
                receipt['failed_frame'] = index
                okay, image = capture.read()
                time_ms = float(Fraction(index*1000,1)/clip['fps'])
                actual = capture.get(cv2.CAP_PROP_POS_MSEC)
                if (not okay or image.shape != (clip['height'],clip['width'],3)
                        or not math.isfinite(actual) or abs(actual-time_ms)>=1
                        or hashlib.sha256(image.tobytes()).hexdigest()!=track['decoded_bgr_sha256']):
                    raise ValueError(f'Source pixels/time changed at frame{index}')
                if index not in pending:
                    previous = frames[index].to_dict()
                    tensor, geometry = prepare_rtmpose_input(image,clip['crop_xyxy_px'],person_bbox_xyxy=track['selected_bbox_xyxy_px'])
                    if not _exact(geometry,previous['input_geometry']):
                        raise ValueError(f'Previously saved geometry changed at frame{index}')
                    if previous['model_selection']['coordinate_origin']=='new_inference':
                        digest = hashlib.sha256(tensor.astype('<f4',copy=False).tobytes()).hexdigest()
                        if digest != prior_starts[previous_attempt]['input_sha256']:
                            raise ValueError(f'Previously executed input differs at frame{index}')
                        previous_attempt += 1
                    continue
                if worker is None:
                    worker = stack.enter_context(pose_factory(root/base['runtime_ref']['path'],root/base['worker_ref']['path'],
                        root/base['model_ref']['path'],expected_model_sha256=base['model_ref']['sha256'],
                        max_calls=len(pending),output_dir=worker_dir))
                    if any(worker.metadata.get('runtime',{}).get(key)!=value for key,value in base['expected_runtime'].items()):
                        raise ValueError('Original isolated runtime differs')
                    estimator = RTMPoseNativeEstimator(worker,crop_xyxy=tuple(clip['crop_xyxy_px']))
                estimate = estimator.estimate(image,person_bbox_xyxy=track['selected_bbox_xyxy_px'])
                value = frames[index].to_dict()
                value['landmarks'], value['input_geometry'] = estimate.landmarks,estimate.input_geometry
                value['model_selection'] = {**value['model_selection'],'source':'explicit never-executed continuation over saved subject track',
                    'pose_not_run':False,'pose_not_run_reason':None,'coordinate_origin':'new_inference',
                    'new_pose_call':True,'isolated_worker_attempt_index':worker.calls_completed,
                    'run_segment':'continuation','run_segment_config_ref':config_ref}
                frame = NativePoseFrame(value)
                stream.write(json.dumps(frame.to_dict(),allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
                frames[index] = frame
                receipt.update(pose_calls_attempted=worker.calls_attempted,pose_calls_completed=worker.calls_completed,
                               new_frames_saved=receipt['new_frames_saved']+1)
                append_event(progress,f'frame-{index:06d}',receipt)
                if receipt['new_frames_saved']%25==0:
                    print(f'continuation {receipt["new_frames_saved"]}/{len(pending)}; source frame{index}',flush=True)
            if capture.read()[0]:
                raise ValueError('Source contains extra frames')
        if receipt['pose_calls_attempted']!=len(pending) or receipt['pose_calls_completed']!=len(pending):
            raise ValueError('Continuation did not execute exactly the approved tail')
        evidence = [*config['source_refs'],*[reference(root,p) for p in worker_dir.iterdir() if p.is_file()],
                    reference(root,output/'continuation.partial.jsonl')]
        manifest = _seeded_manifest(base,clip,original,config_ref,evidence)
        manifest['roi_provenance']['continuation'] = {'original_config_ref':config['original_config_ref'],
            'prior_prefix_copied_unchanged':len(frames)-len(pending),'new_pose_frame_indices':pending,
            'new_tracking_replays':0,'new_detector_calls':0}
        folder = output/'rtmpose'/clip['pitch_id']
        write_dataset(folder,manifest,frames)
        write_json(folder/'native_pose_summary.json',summarize_native(manifest,frames))
        if render_overlay:
            write_json(folder/'overlay_validation.json',write_native_overlay(clip['video_path'],manifest,frames,folder/'overlay_native.mp4'))
        changed = [ref['path'] for ref in config['source_refs'] if sha256(root/ref['path'])!=ref['sha256']]
        if changed:
            raise ValueError('Bound original sources changed: '+str(changed))
        receipt.update(state='completed',completed_at_utc=_utc(),failed_frame=None,
                       total_new_pose_calls_across_segments=len(prior_starts)+len(pending),
                       full_pose_frames_saved=len(frames),missing_pose_frames=[],source_sha256_changes=changed,
                       native_output=folder.relative_to(root).as_posix())
        append_event(progress,'completed',receipt)
        write_json(output/'run_receipt.json',receipt)
    except BaseException as error:
        if worker is not None:
            receipt.update(pose_calls_attempted=worker.calls_attempted,pose_calls_completed=worker.calls_completed)
        receipt.update(state='failed',failed_at_utc=_utc(),failure=f'{type(error).__name__}: {error}')
        try:
            append_event(progress,'failed',receipt)
            write_json(output/'failure_receipt.json',receipt)
        except Exception as record_error:
            error.add_note('Could not save failure receipt: '+str(record_error))
        raise
    finally:
        capture.release()
    return receipt
