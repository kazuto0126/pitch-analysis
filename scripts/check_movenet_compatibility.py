"""Isolated SavedModel compatibility gate: one synthetic attempt, no video input."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import sys
import time
import traceback

import numpy as np


JOINTS = ('NOSE', 'LEFT_EYE', 'RIGHT_EYE', 'LEFT_EAR', 'RIGHT_EAR',
          'LEFT_SHOULDER', 'RIGHT_SHOULDER', 'LEFT_ELBOW', 'RIGHT_ELBOW',
          'LEFT_WRIST', 'RIGHT_WRIST', 'LEFT_HIP', 'RIGHT_HIP',
          'LEFT_KNEE', 'RIGHT_KNEE', 'LEFT_ANKLE', 'RIGHT_ANKLE')
COORDINATE_CONVENTION = 'continuous pixel-edge XY: source [0,width] x [0,height]; no clipping'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def bound(root, ref):
    path = (root / ref['path']).resolve()
    if not path.is_relative_to(root) or sha(path) != ref['sha256']:
        raise ValueError('Changed or outside bound source: ' + ref['path'])
    return path


def verify_model(root, model, refs):
    expected = [bound(root, ref) for ref in refs]
    if len(set(expected)) != len(expected) or not expected:
        raise ValueError('Duplicate or absent model bindings')
    if any(not path.is_relative_to(model) for path in expected):
        raise ValueError('Model binding does not describe loaded directory')
    actual = []
    for path in model.rglob('*'):
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked model path is not frozen')
        if path.is_file():
            actual.append(path.resolve())
    if set(actual) != set(expected) or model / 'saved_model.pb' not in expected:
        raise ValueError('Loaded SavedModel file set differs from frozen bindings')


def verify_runtime(root, ref):
    locked = json.loads(bound(root, ref).read_text(encoding='utf-8'))
    current = sorted((d.metadata['Name'].lower().replace('_', '-'), d.version)
                     for d in importlib.metadata.distributions())
    expected = sorted((d['name'].lower().replace('_', '-'), d['version']) for d in locked['packages'])
    if current != expected or sys.version != locked['python']:
        raise ValueError('Installed runtime differs from frozen package/Python versions')
    if sha(sys.executable) != locked['executable_sha256']:
        raise ValueError('Isolated Python executable differs from frozen bytes')
    inventory = json.loads(bound(root, locked['installed_inventory']).read_text(encoding='utf-8'))
    for name, digest in inventory['files'].items():
        bound(root, {'path': name, 'sha256': digest})


def inspect_signature(signature):
    positional, keywords = signature.structured_input_signature
    if positional or len(keywords) != 1:
        raise ValueError('Expected exactly one named input')
    key, spec = next(iter(keywords.items()))
    if spec.dtype.name != 'int32' or spec.shape.as_list() != [1, None, None, 3]:
        raise ValueError('Input dtype/shape differs from fixed v1 contract')
    outputs = signature.structured_outputs
    if (set(outputs) != {'output_0'} or outputs['output_0'].dtype.name != 'float32' or
            outputs['output_0'].shape.as_list() != [1, 6, 56]):
        raise ValueError('Output key/dtype/shape differs from fixed v1 contract')
    return {'input_key': key, 'input_shape': spec.shape.as_list(), 'input_dtype': spec.dtype.name,
            'output_key': 'output_0', 'output_shape': [1, 6, 56], 'output_dtype': 'float32'}


def geometry_from_mask(mask, source_height, source_width):
    """Observe actual runtime resize/pad extent instead of guessing integer rounding."""
    if source_height <= 0 or source_width <= 0 or mask.shape != (256, 256):
        raise ValueError('Invalid source/mask dimensions')
    if not np.isfinite(mask).all() or not np.isin(mask, [0, 1]).all():
        raise ValueError('Expected a resized all-ones mask with zero padding')
    ys, xs = np.nonzero(mask)
    if not len(xs):
        raise ValueError('No source area remains after resize')
    left, top, right, bottom = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    if np.count_nonzero(mask) != (right - left) * (bottom - top):
        raise ValueError('Nonrectangular source support')
    return {'source_height': source_height, 'source_width': source_width,
            'target_height': 256, 'target_width': 256,
            'resized_height': bottom - top, 'resized_width': right - left,
            'pad_left': left, 'pad_top': top, 'pad_right': 256 - right, 'pad_bottom': 256 - bottom,
            'scale_x': (right - left) / source_width, 'scale_y': (bottom - top) / source_height,
            'coordinate_convention': COORDINATE_CONVENTION}


def to_source_xy(y_norm, x_norm, geometry):
    if not math.isfinite(y_norm) or not math.isfinite(x_norm):
        raise ValueError('Nonfinite native coordinate')
    return [(x_norm * 256 - geometry['pad_left']) / geometry['scale_x'],
            (y_norm * 256 - geometry['pad_top']) / geometry['scale_y']]


def to_target_yx(x, y, geometry):
    return [(y * geometry['scale_y'] + geometry['pad_top']) / 256,
            (x * geometry['scale_x'] + geometry['pad_left']) / 256]


def native_slots(raw, geometry):
    if raw.shape != (1, 6, 56) or raw.dtype != np.float32 or not np.isfinite(raw).all():
        raise ValueError('Invalid native output dtype/shape/nonfinite values')
    scores = np.concatenate((raw[0, :, :51].reshape(6, 17, 3)[:, :, 2].ravel(), raw[0, :, 55]))
    if np.any(scores < 0) or np.any(scores > 1):
        raise ValueError('Native confidence score outside [0,1]')
    slots = []
    for index, row in enumerate(raw[0]):
        points = row[:51].reshape(17, 3)
        slots.append({'slot_index': index, 'native_yx_score': points.tolist(),
                      'source_xy': [to_source_xy(float(y), float(x), geometry) for y, x, _ in points],
                      'native_box_ymin_xmin_ymax_xmax_score': row[51:].tolist(),
                      'joint_order': list(JOINTS), 'subject_identity': None,
                      'observability': None, 'reliability_status': None})
    return slots


def synthetic(height=720, width=1280):
    rgb = np.full((height, width, 3), 128, dtype=np.uint8)
    margin = max(1, min(height, width) // 8)
    colors = ([255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0])
    rgb[:margin, :margin] = colors[0]
    rgb[:margin, -margin:] = colors[1]
    rgb[-margin:, :margin] = colors[2]
    rgb[-margin:, -margin:] = colors[3]
    return rgb


def prepare(tf, rgb):
    if rgb.ndim != 3 or rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise ValueError('Expected synthetic RGB uint8')
    h, w = rgb.shape[:2]
    tensor = tf.cast(tf.image.resize_with_pad(rgb[None], 256, 256), tf.int32)
    mask = tf.image.resize_with_pad(tf.ones([1, h, w, 1]), 256, 256).numpy()[0, :, :, 0]
    return tensor, geometry_from_mask(mask, h, w)


def verify_preprocessing(tf):
    results = []
    for h, w in ((720, 1280), (1280, 720), (719, 1281), (257, 319), (256, 256), (127, 257)):
        tensor, geometry = prepare(tf, synthetic(h, w))
        image = tensor.numpy()[0]
        x, y = geometry['pad_left'], geometry['pad_top']
        x1, y1 = x + geometry['resized_width'] - 1, y + geometry['resized_height'] - 1
        actual = [image[y, x], image[y, x1], image[y1, x], image[y1, x1]]
        if not np.array_equal(actual, [[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 0]]):
            raise ValueError('Four source corners/RGB order were not retained')
        samples = [(px, py) for px in (0., w / 2., float(w)) for py in (0., h / 2., float(h))]
        errors = [math.dist([px, py], to_source_xy(*to_target_yx(px, py, geometry), geometry))
                  for px, py in samples]
        if max(errors) > 1e-9:
            raise ValueError('Recorded coordinate inverse differs')
        results.append({'geometry': geometry, 'four_corner_colors_retained': True,
                        'roundtrip_points': len(samples), 'max_algebraic_roundtrip_error_px': max(errors)})
    return results


def run(root, plan_path):
    if not plan_path.is_relative_to(root):
        raise ValueError('Plan outside workspace')
    plan_bytes = plan_path.read_bytes()
    plan_sha256 = hashlib.sha256(plan_bytes).hexdigest()
    plan = json.loads(plan_bytes)
    if (plan['status'] != 'frozen_before_synthetic_gate' or plan['synthetic_attempt_budget'] != 1 or
            plan['formal_video_inference_budget'] != 0):
        raise ValueError('Unfrozen or expanded gate')
    for ref in plan['sources'].values():
        bound(root, ref)
    if sha(__file__) != plan['sources']['gate_code']['sha256']:
        raise ValueError('Unbound gate code')
    expected_python = (root / plan['isolated_python']).resolve()
    if Path(sys.executable).resolve() != expected_python:
        raise ValueError('Must use frozen isolated Python')
    model = (root / plan['model_directory']).resolve()
    output = (root / plan['output_directory']).resolve()
    if not model.is_relative_to(root) or not output.is_relative_to(root) or output.exists():
        raise ValueError('Outside workspace or existing gate output; refuse rerun')
    verify_model(root, model, plan['model_files'])
    verify_runtime(root, plan['sources']['runtime_lock'])
    output.mkdir()
    report = {'status': 'started', 'synthetic_inference_attempts': 0, 'formal_video_inference_calls': 0,
              'plan_sha256': plan_sha256, 'gate_code_sha256': sha(__file__),
              'production_core_modified': None, 'production_integrity_assessment': 'external_before_after_audit_required',
              'phase2_automatic_reliability': 'NOT PASSED'}
    try:
        import tensorflow as tf
        if tf.__version__ != '2.21.0':
            raise ValueError('Different TensorFlow runtime')
        tf.config.set_visible_devices([], 'GPU')
        report['runtime'] = {'tensorflow': tf.__version__, 'numpy': np.__version__, 'python': sys.version,
                             'executable': sys.executable, 'platform': platform.platform(),
                             'cpu_devices': [d.name for d in tf.config.list_physical_devices('CPU')]}
        report['preprocessing_fixtures'] = verify_preprocessing(tf)
        started = time.perf_counter()
        loaded = tf.saved_model.load(str(model))
        report['load_seconds'] = time.perf_counter() - started
        if set(loaded.signatures) != {'serving_default'}:
            raise ValueError('Unexpected SavedModel signatures')
        fn = loaded.signatures['serving_default']
        report['contract'] = inspect_signature(fn)
        rgb = synthetic()
        tensor, geometry = prepare(tf, rgb)
        if tensor.dtype != tf.int32 or tensor.shape.as_list() != [1, 256, 256, 3]:
            raise ValueError('Prepared input does not match fixed contract')
        np.save(output / 'synthetic_rgb.npy', rgb, allow_pickle=False)
        np.save(output / 'model_input.npy', tensor.numpy(), allow_pickle=False)
        write(output / 'attempt_started.json', {'attempt': 1, 'model_input_sha256': sha(output / 'model_input.npy'),
              'rule': 'One attempt only, including a failing call. Never auto retry.'})
        report['synthetic_inference_attempts'] = 1
        started = time.perf_counter()
        result = fn(**{report['contract']['input_key']: tensor})
        raw = result['output_0'].numpy()
        report['first_inference_and_materialization_seconds'] = time.perf_counter() - started
        np.save(output / 'native_output.npy', raw, allow_pickle=False)
        report['slots'] = native_slots(raw, geometry)
        report['input_geometry'] = geometry
        report['output_shape'], report['output_dtype'] = list(raw.shape), str(raw.dtype)
        report['status'] = 'compatible_synthetic_only'
        report['accuracy'], report['subject_tracking_accuracy'] = None, None
        report['limits'] = ['Synthetic input has no people; six slots are not detections of six people.',
            'No anatomical accuracy, visibility, identity or pitching performance established.',
            'Coordinate fixtures check preprocessing and algebraic inverse under recorded edge convention.',
            'No MediaPipe33 conversion, confidence gate, interpolation or automatic winner.']
    except Exception as error:
        report['status'] = 'failed_stop_no_retry'
        report['error'] = type(error).__name__ + ': ' + str(error)
        (output / 'error.txt').write_text(traceback.format_exc(), encoding='utf-8')
    for ref in plan['sources'].values():
        bound(root, ref)
    verify_model(root, model, plan['model_files'])
    verify_runtime(root, plan['sources']['runtime_lock'])
    if sha(plan_path) != plan_sha256:
        raise ValueError('Execution plan changed during gate')
    report['saved_files'] = [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                             for p in sorted(output.iterdir()) if p.is_file()]
    write(output / 'compatibility.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run(args.root.resolve(), args.plan.resolve())
    print(json.dumps({k: result[k] for k in ('status', 'synthetic_inference_attempts', 'formal_video_inference_calls')}))
    sys.exit(0 if result['status'] == 'compatible_synthetic_only' else 1)
