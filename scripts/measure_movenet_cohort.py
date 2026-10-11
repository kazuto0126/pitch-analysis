"""One sealed full-frame MoveNet pass; no GT, subject selection or production edits."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import traceback

import numpy as np

from check_movenet_compatibility import (bound, sha, write, verify_model, verify_runtime,
                                        inspect_signature, prepare, native_slots)

SOURCE_ROLES = {'video', 'metadata', 'video_technical', 'export_receipt', 'frame_archive'}
APPROVED_CLIP_IDS = {f'pitch_{index:03d}' for index in range(1, 6)}
APPROVED_FRAME_BUDGET = 592


def validate_plan(root, plan):
    if (plan['status'] != 'frozen_before_measurement' or plan['synthetic_inference_budget'] != 0 or
            plan['formal_video_inference_budget'] != APPROVED_FRAME_BUDGET or
            {c['target']['pitch_id'] for c in plan['clips']} != APPROVED_CLIP_IDS or
            plan['formal_video_inference_budget'] != sum(c['target']['total_frames'] for c in plan['clips']) or
            len({c['target']['pitch_id'] for c in plan['clips']}) != len(plan['clips'])):
        raise ValueError('Unfrozen plan, changed budget or duplicate clip')
    for ref in plan['sources'].values():
        bound(root, ref)
    for clip in plan['clips']:
        if set(clip['sources']) != SOURCE_ROLES:
            raise ValueError('Producer permits only declared video/export inputs')
        for ref in clip['sources'].values():
            bound(root, ref)


def load_export(root, clip):
    sources, target = clip['sources'], clip['target']
    receipt = json.loads(bound(root, sources['export_receipt']).read_text(encoding='utf-8'))
    if (receipt['status'] != 'sealed_full_frame_rgb_inputs' or receipt['target'] != target or
            receipt['archive'] != sources['frame_archive'] or receipt['frame_key'] != 'rgb' or
            receipt['source_video'] != sources['video'] or receipt['pose_inference_calls'] != 0 or
            receipt['human_annotation_inputs'] or
            receipt['sources'] != {k: sources[k] for k in ('video', 'metadata', 'video_technical')} or
            [f['frame_index'] for f in receipt['frames']] != list(range(target['total_frames']))):
        raise ValueError('Changed, incomplete or annotated export receipt')
    technical = json.loads(bound(root, sources['video_technical']).read_text(encoding='utf-8'))
    if (technical['sha256'] != sources['video']['sha256'] or
            (technical['frame_count'], technical['width'], technical['height']) !=
            (target['total_frames'], target['width'], target['height']) or
            receipt['fps_float'] != technical['fps'] or not math.isfinite(receipt['fps_float']) or
            receipt['fps_float'] <= 0 or len(technical['timestamps_ms']) != target['total_frames']):
        raise ValueError('Export technical source mismatch')
    for index, frame in enumerate(receipt['frames']):
        native = frame['native_timestamp_ms']
        if (not math.isfinite(native) or not math.isclose(native, technical['timestamps_ms'][index],
                rel_tol=0, abs_tol=1e-6) or frame['timestamp_ms'] != round(native) or
                frame['frame_time_sec'] != index / receipt['fps_float']):
            raise ValueError('Export frame timeline mismatch')
    with np.load(bound(root, sources['frame_archive']), allow_pickle=False) as archive:
        if archive.files != ['rgb']:
            raise ValueError('Unexpected input archive fields')
        pixels = archive['rgb']
    if pixels.dtype != np.uint8 or pixels.shape != (target['total_frames'], target['height'], target['width'], 3):
        raise ValueError('Input archive dtype/shape mismatch')
    for index, rgb in enumerate(pixels):
        if hashlib.sha256(rgb.tobytes()).hexdigest() != receipt['frames'][index]['decoded_rgb_sha256']:
            raise ValueError('RGB bytes differ from sealed receipt')
    return receipt, pixels


def record_frame(receipt, geometry, raw, inference_seconds):
    slots = native_slots(raw, geometry)
    return {**receipt, 'input_geometry': geometry, 'native_output': raw.tolist(),
            'slots': slots, 'inference_seconds': inference_seconds}


def mark_attempt(stream, ordinal, pitch_id, frame_index, input_sha256):
    stream.write(json.dumps({'ordinal': ordinal, 'pitch_id': pitch_id, 'frame_index': frame_index,
                             'model_input_sha256': input_sha256}) + '\n')
    stream.flush()


def measure(root, plan_path):
    root, plan_path = root.resolve(), plan_path.resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError('Plan outside workspace')
    plan_sha = sha(plan_path)
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    validate_plan(root, plan)
    if sha(__file__) != plan['sources']['producer_code']['sha256']:
        raise ValueError('Unbound producer')
    if Path(sys.executable).resolve() != (root / plan['isolated_python']).resolve():
        raise ValueError('Use the frozen isolated runtime')
    model = (root / plan['model_directory']).resolve()
    output = (root / plan['output_directory']).resolve()
    if not model.is_relative_to(root) or not output.is_relative_to(root / 'analysis_results') or output.exists():
        raise ValueError('Existing or outside output; never retry a partial run')
    verify_model(root, model, plan['model_files'])
    verify_runtime(root, plan['sources']['runtime_lock'])
    # All five archives must be semantically valid before the first model call.
    prepared_inputs = [(clip, *load_export(root, clip)) for clip in plan['clips']]
    output.mkdir(parents=True)
    run = {'status': 'started', 'plan_sha256': plan_sha, 'producer_sha256': sha(__file__),
           'source_frames': 0, 'non_seed_frames': 0, 'inference_calls': 0, 'synthetic_inference_calls': 0,
           'clips': [], 'human_annotation_inputs': [], 'warning_policy': None,
           'phase2_automatic_reliability': 'NOT PASSED', 'subject_selection_performed': False}
    try:
        import tensorflow as tf
        if tf.__version__ != '2.21.0':
            raise ValueError('Frozen TensorFlow version mismatch')
        tf.config.set_visible_devices([], 'GPU')
        loaded = tf.saved_model.load(str(model))
        if set(loaded.signatures) != {'serving_default'}:
            raise ValueError('Changed model signatures')
        fn = loaded.signatures['serving_default']
        contract = inspect_signature(fn)
        run['contract'] = contract
        run['runtime'] = {'tensorflow': tf.__version__, 'numpy': np.__version__,
                          'python': sys.version, 'executable': sys.executable}
        with (output/'attempts.jsonl').open('x', encoding='utf-8', newline='\n') as attempts, \
                (output/'frame_measurements.jsonl').open('x', encoding='utf-8', newline='\n') as journal:
            for clip, receipt, pixels in prepared_inputs:
                target, frames = clip['target'], []
                calls_at_clip_start = run['inference_calls']
                try:
                    for index, rgb in enumerate(pixels):
                        tensor, geometry = prepare(tf, rgb)
                        if tensor.dtype != tf.int32 or tensor.shape.as_list() != [1, 256, 256, 3]:
                            raise ValueError('Changed model input contract')
                        input_sha = hashlib.sha256(tensor.numpy().tobytes()).hexdigest()
                        ordinal = run['inference_calls'] + 1
                        mark_attempt(attempts, ordinal, target['pitch_id'], index, input_sha)
                        run['inference_calls'] = ordinal
                        started = time.perf_counter()
                        raw = fn(**{contract['input_key']: tensor})['output_0'].numpy()
                        seconds = time.perf_counter() - started
                        # Keep invalid native output too; fail without replacing or retrying.
                        try:
                            frame = record_frame(receipt['frames'][index], geometry, raw, seconds)
                        except Exception:
                            np.save(output/(target['pitch_id']+f'_invalid_frame_{index}.npy'), raw, allow_pickle=False)
                            raise
                        frames.append(frame)
                        journal.write(json.dumps({'pitch_id': target['pitch_id'], **frame}, allow_nan=False)+'\n')
                        journal.flush()
                finally:
                    result = {'status': 'sealed_measurements_only' if len(frames)==target['total_frames'] else 'partial_stop_no_retry',
                              'target': target, 'plan_sha256': plan_sha, 'producer_sha256': sha(__file__),
                              'human_annotation_inputs': [], 'source_references': clip['sources'],
                              'inference_calls': run['inference_calls']-calls_at_clip_start,
                              'completed_frames': len(frames), 'total_frames': target['total_frames'], 'frames': frames}
                    path = output/(target['pitch_id']+'.json')
                    write(path, result)
                    run['clips'].append({'pitch_id':target['pitch_id'], 'path':path.relative_to(root).as_posix(),
                                         'sha256':sha(path)})
                    run['source_frames'] += len(frames)
                    run['non_seed_frames'] += max(0,len(frames)-1)
                print(json.dumps({'pitch_id':target['pitch_id'], 'frames':len(frames),
                                  'cumulative_inference_calls':run['inference_calls']}),flush=True)
        if run['inference_calls'] != plan['formal_video_inference_budget']:
            raise ValueError('Incomplete formal-frame denominator')
        run['status'] = 'sealed_movenet_cohort_measurements'
    except Exception as error:
        run['status'] = 'failed_stop_no_retry'
        run['error'] = type(error).__name__+': '+str(error)
        (output/'error.txt').write_text(traceback.format_exc(),encoding='utf-8')
    validate_plan(root,plan)
    verify_model(root,model,plan['model_files'])
    verify_runtime(root,plan['sources']['runtime_lock'])
    if sha(plan_path) != plan_sha:
        raise ValueError('Measurement plan changed during run')
    run['saved_files'] = [{'path':p.relative_to(root).as_posix(),'sha256':sha(p)}
                          for p in sorted(output.iterdir()) if p.is_file()]
    write(output/'measurement_run.json',run)
    return run


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan',type=Path)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    args=parser.parse_args()
    run=measure(args.root,args.plan)
    print(json.dumps({k:run[k] for k in ('status','source_frames','inference_calls')}))
    sys.exit(0 if run['status']=='sealed_movenet_cohort_measurements' else 1)
