"""One fixed 2x IMAGE experiment; durable attempts, no GT or tracker execution."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from measure_tracked_roi_pose import (OPTIONS, PARAMETERS as NARROW_PARAMETERS, runtime,
    crop_bounds, serialize_candidates, map_candidates, validate_tracked_roi, _pixel_hash)
from measure_seeded_subject import read, sha
from pitch_analysis.pose_estimator import PoseEstimate
from pitch_analysis.subject import PitcherSelector

PARAMETERS = {**NARROW_PARAMETERS, 'crop': 'saved_float_xywh_centered_2x_floor_ceil_intersection',
              'expansion_width': 2, 'expansion_height': 2}
CODE_PATHS = ['scripts/measure_expanded_roi_pose.py', 'tests/test_expanded_roi_pose.py',
    'scripts/measure_tracked_roi_pose.py', 'scripts/measure_seeded_subject.py',
    'src/pitch_analysis/subject.py', 'src/pitch_analysis/pose_capture.py',
    'src/pitch_analysis/pose_estimator.py']
TARGETS = [('pitch_001',87,434,616), ('pitch_002',175,460,634),
           ('pitch_003',115,510,628), ('pitch_004',114,532,676), ('pitch_005',101,512,598)]


def bound(root, ref):
    path = (root/ref['path']).resolve()
    if not path.is_relative_to(root) or sha(path) != ref['sha256']:
        raise ValueError('Changed or external bound input: '+ref['path'])
    return path


def save(path, data):
    """Exclusive durable JSON; a partial file is an error, never silently replaced."""
    with Path(path).open('x', encoding='utf-8', newline='\n') as sink:
        json.dump(data, sink, ensure_ascii=False, indent=2, allow_nan=False)
        sink.write('\n'); sink.flush(); os.fsync(sink.fileno())


def same_or_save(path, data):
    if path.exists():
        if read(path) != data: raise ValueError('Saved artifact differs: '+str(path))
    else: save(path, data)


@contextmanager
def exclusive_run(path):
    """OS lock released on crash; simultaneous invocations cannot issue duplicates."""
    with Path(path).open('a+b') as stream:
        if stream.tell() == 0:
            stream.write(b'0'); stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try: yield
        finally:
            stream.seek(0)
            if os.name == 'nt': msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def expand_bounds(rectangle, width, height):
    if rectangle is None: return None
    # Validate the original float receipt, before expansion or clipping.
    crop_bounds(rectangle, width, height)
    x,y,w,h = rectangle
    if w <= 0 or h <= 0: return None
    result = [max(0,math.floor(x-w/2)),max(0,math.floor(y-h/2)),
              min(width,math.ceil(x+3*w/2)),min(height,math.ceil(y+3*h/2))]
    return result if result[2]>result[0] and result[3]>result[1] else None


class AttemptJournal:
    def __init__(self, path, budget=592):
        self.path, self.budget = Path(path), budget
        self.started, self.completed = {}, {}
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines():
                self._apply(json.loads(line))

    def _apply(self, event):
        key = event['attempt_id']
        if event['event'] == 'started':
            if key in self.started or len(self.started) >= self.budget:
                raise ValueError('Duplicate or over-budget attempt')
            self.started[key] = event
        elif event['event'] == 'completed':
            if key not in self.started or key in self.completed:
                raise ValueError('Unstarted or duplicate completion')
            self.completed[key] = event
        else: raise ValueError('Unknown journal event')

    def append(self, event):
        self._apply(event)
        with self.path.open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(json.dumps(event, sort_keys=True, allow_nan=False)+'\n')
            stream.flush(); os.fsync(stream.fileno())

    def existing(self, key, receipt, path):
        if key in self.started and self.started[key] != {'event':'started','attempt_id':key, **receipt}:
            raise ValueError('Attempt input changed')
        if not path.exists():
            if key in self.started: raise ValueError('Indeterminate prior attempt; automatic retry refused: '+key)
            return None
        result = read(path)
        if result['attempt_id'] != key or result['input_receipt'] != receipt:
            raise ValueError('Persisted attempt source differs')
        if result['inference_status'] == 'measured':
            if key not in self.started: raise ValueError('Result without durable started event')
            event = {'event':'completed','attempt_id':key,'result_sha256':sha(path)}
            if key in self.completed:
                if self.completed[key] != event: raise ValueError('Completed result changed')
            else: self.append(event)  # Crash after fsync result, before completion: no inference.
        elif key in self.started: raise ValueError('Missing ROI with an inference attempt')
        return result


class ImagePoseEstimator:
    """Local IMAGE adapter satisfying PoseEstimator, leaving production VIDEO intact."""
    backend_name = 'mediapipe_pose_landmarker_image_experiment'

    def __init__(self, model):
        import mediapipe as mp
        self.mp = mp
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
            running_mode=mp.tasks.vision.RunningMode.IMAGE, **OPTIONS)
        self.detector = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def estimate(self, frame_bgr, timestamp_ms):
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB,
                              data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        return PoseEstimate(self.detector.detect(image).pose_landmarks)

    def __enter__(self): return self
    def __exit__(self, *args): self.detector.close()


def verify_execution(root, plan):
    if (plan['status'] != 'frozen_before_expanded_roi_measurement' or plan['parameters'] != PARAMETERS
        or plan['options'] != OPTIONS or plan['runtime'] != runtime()
        or plan['source_frames'] != 592 or plan['non_seed_frames'] != 587
        or plan['pose_inference_budget'] != 592 or plan['tracker_inference_budget'] != 0
        or plan['human_annotation_inputs'] != [] or plan['production_adoption'] is not False):
        raise ValueError('Changed experiment scope or runtime')
    if set(plan['producer_code']) != set(CODE_PATHS): raise ValueError('Unbound producer code')
    for path, digest in plan['producer_code'].items(): bound(root, {'path':path,'sha256':digest})
    bound(root, plan['model'])
    if not plan['native_binding_hashes']: raise ValueError('Missing native hashes')
    for path, digest in plan['native_binding_hashes'].items(): bound(root, {'path':path,'sha256':digest})
    if [tuple(c['target'][k] for k in ('pitch_id','total_frames','width','height')) for c in plan['clips']] != TARGETS:
        raise ValueError('Changed five-clip cohort')
    for clip in plan['clips']:
        if set(clip['producer_sources']) != {'video','metadata','video_technical','tracked_roi'}:
            raise ValueError('Unexpected producer inputs')
        for ref in clip['producer_sources'].values(): bound(root,ref)
    # Evaluator references are intentionally never opened or hashed here.


def measure_clip(root, clip, output, journal, estimator_factory):
    target, sources = clip['target'],clip['producer_sources']
    tracked,technical,metadata = (read(bound(root,sources[k])) for k in ('tracked_roi','video_technical','metadata'))
    validate_tracked_roi(tracked,sources,target)
    if (metadata['schema_version'] != 'pitch-input-v1' or metadata['pitch_id'] != target['pitch_id']
        or technical['sha256'] != sources['video']['sha256']
        or [technical[k] for k in ('frame_count','width','height')] != [target[k] for k in ('total_frames','width','height')]
        or len(technical['timestamps_ms']) != target['total_frames']):
        raise ValueError('Technical or metadata source differs')
    output.mkdir(exist_ok=True)
    frames_dir = output/'frames'; frames_dir.mkdir(exist_ok=True)
    selector, frames, estimator = PitcherSelector(), [], None
    capture = cv2.VideoCapture(str(bound(root,sources['video'])))
    try:
        for i in range(target['total_frames']):
            ok,pixels = capture.read(); tracker = tracked['frames'][i]
            ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            if (not ok or pixels.dtype != np.uint8 or pixels.shape != (target['height'],target['width'],3)
                or _pixel_hash(pixels) != tracker['decoded_bgr_sha256'] or not math.isfinite(ms)
                or any(not math.isclose(ms,t,abs_tol=1e-6,rel_tol=0) for t in (technical['timestamps_ms'][i],tracker['native_timestamp_ms']))):
                raise ValueError('Source pixels or timestamp mismatch')
            bounds = expand_bounds(tracker['usable_rectangle_xywh'],target['width'],target['height'])
            bgr = None if bounds is None else np.ascontiguousarray(pixels[bounds[1]:bounds[3],bounds[0]:bounds[2]].copy())
            receipt = {'frame_index':i,'native_timestamp_ms':ms,'decoded_bgr_sha256':_pixel_hash(pixels),
                'tracker_rectangle_xywh':tracker['usable_rectangle_xywh'],'crop_bounds_xyxy':bounds,
                'crop_shape':None if bgr is None else list(bgr.shape),
                'crop_bgr_sha256':None if bgr is None else _pixel_hash(bgr),
                'crop_rgb_sha256':None if bgr is None else _pixel_hash(cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB))}
            key = f"{target['pitch_id']}:{i}"; path = frames_dir/f'{i:04d}.json'
            saved = journal.existing(key,receipt,path)
            if saved is not None:
                candidates = saved['crop_candidates']
                if serialize_candidates([[SimpleNamespace(**p) for p in pose] for pose in candidates]) != candidates:
                    raise ValueError('Malformed persisted candidates')
            elif bounds is None: candidates = []
            else:
                if estimator is None: estimator = estimator_factory()
                journal.append({'event':'started','attempt_id':key,**receipt})
                result = estimator.estimate(bgr,round(ms))
                candidates = serialize_candidates(result.pose_landmarks)
                if _pixel_hash(bgr) != receipt['crop_bgr_sha256']: raise ValueError('Input mutated')
            mapped = map_candidates(candidates,bounds,target['width'],target['height']) if bounds else []
            choice = asdict(selector.select([[SimpleNamespace(**p) for p in pose] for pose in mapped]))
            frame = {**receipt,'timestamp_ms':round(ms),'attempt_id':key,'input_receipt':receipt,
                'effectiveness_eligible':i!=0,'crop_candidates':candidates,'full_image_candidates':mapped,
                'selection':choice,'inference_status':'measured' if bounds else 'roi_unavailable',
                'warning_prediction':None,'subject_alignment_verified':False}
            if saved is not None:
                if saved != frame: raise ValueError('Persisted mapping or selector replay differs')
            else:
                save(path,frame)
                if bounds: journal.append({'event':'completed','attempt_id':key,'result_sha256':sha(path)})
            frames.append(frame)
        if capture.read()[0]: raise ValueError('Extra decoded frame')
    finally:
        capture.release()
        if estimator is not None: estimator.__exit__(None,None,None)
    return {'status':'sealed_expanded_roi_clip','target':target,'producer_sources':sources,
        'parameters':PARAMETERS,'options':OPTIONS,'frames':frames,
        'inference_calls':sum(f['inference_status']=='measured' for f in frames),
        'human_annotation_inputs':[],'production_adoption':False,'warning_policy':None}


def run(root, plan_path):
    root,plan_path = Path(root).resolve(),Path(plan_path).resolve()
    plan,plan_sha = read(plan_path),sha(plan_path)
    verify_execution(root,plan)
    output = (root/plan['output_directory']).resolve()
    if output == root/'analysis_results' or not output.is_relative_to(root/'analysis_results'):
        raise ValueError('Unsafe output directory')
    output.mkdir(parents=True,exist_ok=True)
    with exclusive_run(output/'run.lock'):
        same_or_save(output/'execution_receipt.json',{'plan_sha256':plan_sha})
        journal = AttemptJournal(output/'attempts.jsonl',plan['pose_inference_budget'])
        expected = {f'{p}:{i}' for p,n,w,h in TARGETS for i in range(n)}
        if not set(journal.started) <= expected: raise ValueError('Unexpected journal identity')
        before = len(journal.started); clips = []
        for clip in plan['clips']:
            result = measure_clip(root,clip,output/clip['target']['pitch_id'],journal,
                lambda: ImagePoseEstimator(bound(root,plan['model'])))
            result['plan_sha256'] = plan_sha
            path = output/clip['target']['pitch_id']/'expanded_roi_pose_measurements.json'
            same_or_save(path,result)
            clips.append({'pitch_id':clip['target']['pitch_id'],'target':clip['target'],
                'pose':{'path':path.relative_to(root).as_posix(),'sha256':sha(path)}})
            print(json.dumps({'pitch_id':clip['target']['pitch_id'],'saved_frames':len(result['frames']),
                              'total_attempts':len(journal.started)}),flush=True)
        verify_execution(root,plan)
        if sha(plan_path) != plan_sha or set(journal.started) != set(journal.completed):
            raise ValueError('Unsealed attempts or changed plan')
        report = {'status':'sealed_expanded_roi_cohort','plan_sha256':plan_sha,'clips':clips,
            'source_frames':592,'non_seed_frames':587,'pose_inference_calls':len(journal.started),
            'tracker_inference_calls':0,'attempts_sha256':sha(journal.path),
            'human_annotation_inputs':[],'production_adoption':False}
        same_or_save(output/'cohort_measurements.json',report)
        return {**report,'new_calls_this_invocation':len(journal.started)-before}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path)
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[1],args.plan)))
