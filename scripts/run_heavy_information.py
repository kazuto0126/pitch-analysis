"""One source-bound Heavy trial; measurement, calibration, application and evaluation.

The production pipeline and the rejected thirteen-feature classifier are untouched.
Each stage has a separate file allowlist. A persisted inference attempt without a
completed clip refuses automatic remeasurement, including after a process crash.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform

from pitch_analysis.pose_capture import LANDMARK_NAMES
from pitch_analysis.pose_estimator import MediaPipePoseEstimator
from pitch_analysis.subject import PitcherSelector
from measure_pose_mode_countercheck import load_video_raw
import heavy_information_policy as policy

NAMES = tuple(f'pitch_{i:03}' for i in range(1, 6))
ROLES = ('throwing_elbow', 'throwing_wrist')
JOINTS = {'throwing_elbow': 'RIGHT_ELBOW', 'throwing_wrist': 'RIGHT_WRIST'}
SETTINGS = {'running_mode': 'VIDEO', 'num_poses': 4, 'min_pose_detection_confidence': .5,
    'min_pose_presence_confidence': .5, 'min_tracking_confidence': .5,
    'crop': None, 'resize': None, 'new_tracker_inference': False, 'frame0_excluded': True,
    'signal': 'full_heavy_selected_same_joint_distance_divided_by_original_diagonal',
    'calibration': 'maximum_finite_reliable_training_distance', 'comparison': 'strict_greater',
    'new_pose_call_budget': 592, 'automatic_adoption': False}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def save(path, data):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def reference(root, path):
    return {'path': Path(path).resolve().relative_to(root.resolve()).as_posix(), 'sha256': sha(path)}


class Reader:
    def __init__(self, root, refs):
        self.root = Path(root).resolve()
        self.allowed = {r['path']: r['sha256'] for r in refs}
        self.opened = []

    def path(self, ref):
        if self.allowed.get(ref['path']) != ref['sha256']:
            raise ValueError('Stage input not allowed: ' + ref['path'])
        path = (self.root / ref['path']).resolve()
        if not path.is_relative_to(self.root) or sha(path) != ref['sha256']:
            raise ValueError('Changed or external stage input: ' + ref['path'])
        self.opened.append(ref['path'])
        return path

    def json(self, ref):
        return read(self.path(ref))


@contextmanager
def locked(path):
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
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def runtime():
    return {'python': platform.python_version(), 'mediapipe': version('mediapipe'),
        'opencv': version('opencv-contrib-python'), 'numpy': version('numpy')}


def finite(point):
    return point is not None and all(isinstance(point.get(k), (int, float)) and
        not isinstance(point[k], bool) and math.isfinite(point[k]) for k in ('x', 'y', 'visibility', 'presence'))


def serialize(poses):
    result, nonfinite = [], []
    for index, pose in enumerate(poses):
        if len(pose) != 33:
            raise ValueError('Heavy must preserve the 33-point native contract')
        points = []
        for joint, point in enumerate(pose):
            values = {}
            for key in ('x', 'y', 'z', 'visibility', 'presence'):
                value = float(getattr(point, key))
                values[key] = value if math.isfinite(value) else None
                if values[key] is None:
                    nonfinite.append({'candidate': index, 'landmark': LANDMARK_NAMES[joint], 'field': key})
            points.append(values)
        result.append(points)
    if len(result) > 4:
        raise ValueError('Heavy exceeded the fixed four-candidate limit')
    return result, nonfinite


def measured_roles(original, candidates, choice, width, height, gate):
    after = dict(zip(LANDMARK_NAMES, candidates[choice['index']], strict=True)) if choice['status'] == 'selected' else {}
    result = {}
    for role, name in JOINTS.items():
        before, point = original.get(name), after.get(name)
        raw_finite = finite(before)
        available = raw_finite and finite(point)
        distance = math.hypot((before['x']-point['x'])*width,
            (before['y']-point['y'])*height) if available else None
        available = available and math.isfinite(distance)
        result[role] = {'original_point': before, 'heavy_point': point,
            'raw_finite': raw_finite,
            'raw_gate_pass': raw_finite and before['visibility'] >= gate['min_visibility'] and before['presence'] >= gate['min_presence'],
            'distance_px': distance if available else None,
            'distance_diagonal': distance / math.hypot(width, height) if available else None,
            'evidence_status': 'measured' if available else 'insufficient_evidence'}
    return result


def measure_clip(root, plan, output, query, estimator_factory=None):
    import cv2
    clip = next(c for c in plan['clips'] if c['pitch_id'] == query)
    refs = [*clip['measurement_sources'].values(), plan['heavy_model']]
    reader = Reader(root, refs)
    folder = output / 'measurements'; folder.mkdir(exist_ok=True)
    target = folder / (query + '.json'); journal = folder / (query + '_attempts.jsonl')
    if target.exists():
        saved = read(target)
        if saved['plan_sha256'] != plan['_sha256'] or saved['journal_sha256'] != sha(journal):
            raise ValueError('Persisted Heavy clip differs')
        return {'status': 'skipped_completed_measurement', 'pitch_id': query, 'new_inference_calls': 0}
    if journal.exists():
        raise ValueError('Indeterminate Heavy attempt; automatic remeasurement refused')
    sources = clip['measurement_sources']
    video = reader.path(sources['video']); reader.json(sources['metadata'])
    meta = reader.json(sources['video_metadata']); capture = reader.json(sources['capture'])
    gate = reader.json(sources['clean_config'])
    if (meta['sha256'] != sources['video']['sha256'] or meta['frame_count'] != clip['total_frames'] or
            capture['subject_selection'] != 'rear_centerfield_broadcast' or
            (gate['min_visibility'], gate['min_presence']) != (.5, .5)):
        raise ValueError('Baseline protocol changed')
    raw = load_video_raw(reader.path(sources['raw_csv']), capture, clip['total_frames'])
    weight = reader.path(plan['heavy_model'])
    total, width, height = clip['total_frames'], meta['width'], meta['height']
    stream = cv2.VideoCapture(str(video))
    if not stream.isOpened() or (int(stream.get(cv2.CAP_PROP_FRAME_COUNT)), int(stream.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(stream.get(cv2.CAP_PROP_FRAME_HEIGHT))) != (total, width, height):
        stream.release(); raise ValueError('Heavy input decode geometry changed')
    selector = PitcherSelector(); frames = []
    factory = estimator_factory or (lambda model: MediaPipePoseEstimator(model, num_poses=4))
    try:
        with journal.open('x', encoding='utf-8', newline='\n') as audit, factory(weight) as estimator:
            def append(data):
                audit.write(json.dumps(data, ensure_ascii=False, allow_nan=False) + '\n')
                audit.flush(); os.fsync(audit.fileno())
            for index in range(total):
                ok, image = stream.read()
                if not ok:
                    raise ValueError('Incomplete Heavy input decode')
                native_ms = stream.get(cv2.CAP_PROP_POS_MSEC)
                timestamp = capture['selection_frames'][index]['timestamp_ms']
                if timestamp != round(native_ms) or not math.isclose(native_ms, meta['timestamps_ms'][index], abs_tol=1e-6):
                    raise ValueError('Heavy timeline differs from baseline')
                pixel_sha = hashlib.sha256(image.tobytes()).hexdigest()
                append({'event': 'started', 'frame_index': index, 'timestamp_ms': timestamp, 'decoded_bgr_sha256': pixel_sha})
                result = estimator.estimate(image, timestamp)
                candidates, invalid = serialize(result.pose_landmarks)
                choice = asdict(selector.select(result.pose_landmarks))
                frame = {'frame_index': index, 'timestamp_ms': timestamp, 'native_timestamp_ms': native_ms,
                    'decoded_bgr_sha256': pixel_sha, 'heavy_candidates': candidates, 'heavy_selection': choice,
                    'nonfinite_fields': invalid, 'original_selection': capture['selection_frames'][index],
                    'roles': measured_roles(raw[index], candidates, choice, width, height, gate)}
                append({'event': 'completed', 'frame_index': index, 'measurement': frame})
                frames.append(frame)
            if stream.read()[0]:
                raise ValueError('Extra Heavy input frames')
    finally:
        stream.release()
    saved = {'status': 'sealed_heavy_measurement', 'plan_sha256': plan['_sha256'], 'pitch_id': query,
        'total_frames': total, 'width': width, 'height': height, 'video_sha256': sources['video']['sha256'],
        'gate': {k: gate[k] for k in ('min_visibility', 'min_presence')}, 'frames': frames,
        'journal_sha256': sha(journal), 'read_paths': reader.opened, 'human_annotation_inputs': [],
        'new_pose_inference_calls': total, 'new_tracker_inference_calls': 0, 'production_adoption': False}
    save(target, saved)
    return {'status': saved['status'], 'pitch_id': query, 'frames': total,
        'selected': sum(f['heavy_selection']['status'] == 'selected' for f in frames),
        'measured_joint_rows': sum(r['evidence_status'] == 'measured' for f in frames for r in f['roles'].values()),
        'new_inference_calls': total}


def seal_measurements(root, plan, output):
    refs = [reference(root, output/'measurements'/(pid+'.json')) for pid in NAMES]
    reader = Reader(root, refs); calls = 0
    for clip, ref in zip(plan['clips'], refs, strict=True):
        item = reader.json(ref)
        if item['pitch_id'] != clip['pitch_id'] or item['plan_sha256'] != plan['_sha256'] or item['total_frames'] != clip['total_frames']:
            raise ValueError('Incomplete Heavy measurements')
        calls += item['new_pose_inference_calls']
    if calls != 592:
        raise ValueError('Heavy call budget differs')
    result = {'status': 'sealed_all_heavy_measurements', 'plan_sha256': plan['_sha256'],
        'clips': refs, 'new_pose_inference_calls': calls, 'human_annotation_inputs': [], 'read_paths': reader.opened}
    save(output/'measurements/measurement_run.json', result)
    return result


def measurement_receipt(root, plan, output):
    result = read(output/'measurements/measurement_run.json')
    if result['plan_sha256'] != plan['_sha256'] or len(result['clips']) != 5 or result['human_annotation_inputs'] != []:
        raise ValueError('Heavy measurement seal differs')
    return result


def timeline(gt, clip, role):
    source = gt['source_video']
    if (gt['schema_version'] != 'ground-truth-v1' or gt['annotation_status'] != 'reviewed' or
            source['pitch_id'] != clip['pitch_id'] or source['total_frames'] != clip['total_frames'] or
            source['sha256'] != clip['measurement_sources']['video']['sha256']):
        raise ValueError('Canonical target binding differs')
    result = [None] * clip['total_frames']
    for item in gt['labels'][role+'_reliability']:
        a, b, status = (item[k] for k in ('start_frame', 'end_frame', 'status'))
        if type(a) is not int or type(b) is not int or not 0 <= a <= b < len(result) or status not in ('reliable', 'unreliable', 'uncertain', 'not_observable'):
            raise ValueError('Invalid canonical interval')
        for i in range(a, b+1):
            if result[i] is not None:
                raise ValueError('Overlapping canonical labels')
            result[i] = status
    if None in result:
        raise ValueError('Incomplete canonical labels')
    return result


def calibrate_stage(root, plan, output, query):
    sealed = measurement_receipt(root, plan, output)
    selected = [(c, r) for c, r in zip(plan['clips'], sealed['clips'], strict=True) if c['pitch_id'] != query]
    reader = Reader(root, [r for c, r in selected] + [c['canonical_gt'] for c, r in selected])
    folder = output/'folds'/query; folder.mkdir(parents=True, exist_ok=True)
    path = folder/'calibration.json'
    if path.exists():
        saved = read(path)
        if saved['plan_sha256'] != plan['_sha256'] or saved['pitch_id'] != query:
            raise ValueError('Persisted calibration differs')
        return saved
    attempt = folder/'calibration_attempt.json'
    if attempt.exists():
        raise ValueError('Indeterminate calibration attempt; automatic retry refused')
    data = {c['pitch_id']: reader.json(r) for c, r in selected}
    gt = {c['pitch_id']: reader.json(c['canonical_gt']) for c, r in selected}
    save(attempt, {'plan_sha256': plan['_sha256'], 'pitch_id': query, 'training_pitch_ids': list(data)})
    calibrations = {}
    for role in ROLES:
        training = []
        for clip, ref in selected:
            pid = clip['pitch_id']; labels = timeline(gt[pid], clip, role)
            training.append({'pitch_id': pid, 'rows': [dict(frame_index=f['frame_index'],
                distance_diagonal=f['roles'][role]['distance_diagonal'], canonical_label=labels[f['frame_index']])
                for f in data[pid]['frames']]})
        calibrations[role] = policy.calibrate(training, query, role)
    saved = {'status': 'sealed_heavy_calibration', 'pitch_id': query, 'plan_sha256': plan['_sha256'],
        'roles': calibrations, 'read_paths': reader.opened}
    save(path, saved)
    return saved


def apply_stage(root, plan, output, query):
    sealed = measurement_receipt(root, plan, output)
    ref = sealed['clips'][NAMES.index(query)]
    numeric_ref = reference(root, output/'folds'/query/'calibration.json')
    reader = Reader(root, [ref, numeric_ref]); item = reader.json(ref); numeric = reader.json(numeric_ref)
    if item['pitch_id'] != query or numeric['pitch_id'] != query or numeric['plan_sha256'] != plan['_sha256']:
        raise ValueError('Heavy query/calibration mismatch')
    frames = [{'frame_index': f['frame_index'], 'roles': {}} for f in item['frames']]
    statuses = {}
    for role in ROLES:
        calibration = numeric['roles'][role]; statuses[role] = calibration['status']
        if calibration['query_pitch_id'] != query or set(calibration['training_pitch_ids']) != set(NAMES)-{query}:
            raise ValueError('Calibration query leakage')
        values = policy.apply([{'frame_index': f['frame_index'],
            'distance_diagonal': f['roles'][role]['distance_diagonal']} for f in item['frames']], calibration)
        for frame, value in zip(frames, values, strict=True):
            frame['roles'][role] = value
    result = {'status': 'sealed_heavy_out_of_fold_hints', 'pitch_id': query, 'plan_sha256': plan['_sha256'],
        'fold_status': statuses, 'frames': frames, 'read_paths': reader.opened,
        'reads_annotations': False, 'production_adoption': False}
    folder = output/'predictions'; folder.mkdir(exist_ok=True); path = folder/(query+'.json')
    if path.exists():
        if read(path) != result:
            raise ValueError('Persisted Heavy hints differ')
    else:
        save(path, result)
    return {'pitch_id': query, 'fold_status': statuses,
        'warnings': {role: sum(f['roles'][role]['evaluated_warning'] for f in frames) for role in ROLES}}


def seal_predictions(root, plan, output):
    refs = [reference(root, output/'predictions'/(pid+'.json')) for pid in NAMES]
    reader = Reader(root, refs)
    for pid, ref in zip(NAMES, refs, strict=True):
        result = reader.json(ref)
        if result['pitch_id'] != pid or result['plan_sha256'] != plan['_sha256'] or result['reads_annotations']:
            raise ValueError('Incomplete annotation-free Heavy predictions')
    result = {'status': 'sealed_all_heavy_predictions', 'plan_sha256': plan['_sha256'], 'clips': refs}
    save(output/'predictions/prediction_run.json', result)
    return result


def evaluate_stage(root, plan, output):
    import evaluate_heavy_information as evaluation
    predictions = read(output/'predictions/prediction_run.json')
    measurements = measurement_receipt(root, plan, output)
    if predictions['plan_sha256'] != plan['_sha256']:
        raise ValueError('Heavy predictions not sealed')
    refs = [*measurements['clips'], *predictions['clips'], plan['baseline_evaluation'], plan['manual_xy'],
        *[c['canonical_gt'] for c in plan['clips']], *[c['major_hints'] for c in plan['clips']]]
    reader = Reader(root, refs)
    measured = {pid: reader.json(ref) for pid, ref in zip(NAMES, measurements['clips'], strict=True)}
    predicted = {pid: reader.json(ref) for pid, ref in zip(NAMES, predictions['clips'], strict=True)}
    gt = {c['pitch_id']: reader.json(c['canonical_gt']) for c in plan['clips']}
    baseline = reader.json(plan['baseline_evaluation'])
    major = {c['pitch_id']: reader.json(c['major_hints']) for c in plan['clips']}
    result = evaluation.evaluate_clips(measured, predicted, gt, baseline, major, reader.json(plan['manual_xy']))
    result.update(plan_sha256=plan['_sha256'], read_paths=reader.opened,
        new_pose_inference_calls=0, new_tracker_inference_calls=0, production_adoption=False)
    folder = output/'evaluation'; folder.mkdir(exist_ok=True)
    save(folder/'evaluation.json', result)
    return {'status': 'sealed_heavy_evaluation', 'decision': result['decision']}


def load_plan(root, path):
    data = read(path)
    if data['settings'] != SETTINGS or data['runtime'] != runtime():
        raise ValueError('Heavy frozen settings/runtime differ')
    if tuple(c['pitch_id'] for c in data['clips']) != NAMES or sum(c['total_frames'] for c in data['clips']) != 592:
        raise ValueError('Heavy fixed dataset differs')
    for ref in data['code_sources']:
        Reader(root, [ref]).path(ref)
    data['_sha256'] = sha(path)
    return data


def run(root, plan_path, stage, query=None):
    root = root.resolve(); plan = load_plan(root, plan_path)
    output = (root/plan['output_path']).resolve()
    if not output.is_relative_to(root/'analysis_results') or not output.is_dir():
        raise ValueError('Heavy output must be its fresh independent analysis_results directory')
    if stage in ('measure', 'calibrate', 'apply') and query not in NAMES:
        raise ValueError('One formal query clip required')
    with locked(output/'stage.lock'):
        if stage == 'measure': return measure_clip(root, plan, output, query)
        if stage == 'seal-measurements': return seal_measurements(root, plan, output)
        if stage == 'calibrate': return calibrate_stage(root, plan, output, query)
        if stage == 'apply': return apply_stage(root, plan, output, query)
        if stage == 'seal-predictions': return seal_predictions(root, plan, output)
        if stage == 'evaluate': return evaluate_stage(root, plan, output)
        raise ValueError('Unknown Heavy stage')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('stage', choices=('measure', 'seal-measurements', 'calibrate', 'apply', 'seal-predictions', 'evaluate'))
    parser.add_argument('--query', choices=NAMES)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.plan, args.stage, args.query), ensure_ascii=False), flush=True)
