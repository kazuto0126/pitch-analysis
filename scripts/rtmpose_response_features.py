"""Pure SDK-matched input geometry and native RTMPose SimCC response features.

No model execution, file access, human labels, response normalization, confidence
filter or coordinate correction occurs here. Native COCO17 output remains native;
the primary response deficit tests an original Full point without repairing it.
"""
from __future__ import annotations

from copy import deepcopy
import math
from numbers import Real

import cv2
import numpy as np


INPUT_SIZE = (192, 256)
SPLIT_RATIO = 2
PADDING = 1.25
MEAN = (123.675, 116.28, 103.53)
STD = (58.395, 57.12, 57.375)
COCO_NAMES = (
    "NOSE", "LEFT_EYE", "RIGHT_EYE", "LEFT_EAR", "RIGHT_EAR",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE",
    "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
)
ROLES = {"throwing_elbow": ("RIGHT_ELBOW", 8), "throwing_wrist": ("RIGHT_WRIST", 10)}


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and math.isfinite(value)


def _positive_dimension(value):
    return isinstance(value, (int, np.integer)) and not isinstance(value, (bool, np.bool_)) and value > 0


def _geometry(roi_xywh, width, height):
    roi = list(roi_xywh)
    if len(roi) != 4 or not all(_finite(v) for v in roi) or roi[2] <= 0 or roi[3] <= 0:
        raise ValueError("ROI must contain finite x/y and positive width/height")
    x, y, w, h = (float(v) for v in roi)
    cx, cy = x + w * .5, y + h * .5
    if w > h * .75:
        h = w / .75
    else:
        w = h * .75
    scale_w, scale_h = w * PADDING, h * PADDING
    if not all(math.isfinite(v) and v > 0 for v in (scale_w, scale_h)):
        raise ValueError("ROI scale is not finite positive")
    sx, sy = 192. / scale_w, 256. / scale_h
    forward = np.array([[sx, 0., 96. - cx * sx], [0., sy, 128. - cy * sy]], dtype=np.float64)
    if not np.isfinite(forward).all() or not all(math.isfinite(v) for v in (cx, cy)):
        raise ValueError("ROI affine geometry is nonfinite")
    inverse = cv2.invertAffineTransform(forward)
    if not np.isfinite(inverse).all():
        raise ValueError("ROI inverse geometry is nonfinite")
    return {
        "schema": "rtmpose_body7_sdk_geometry_v1",
        "source_size": [int(width), int(height)],
        "input_size": list(INPUT_SIZE), "simcc_split_ratio": SPLIT_RATIO,
        "roi_xywh": [float(v) for v in roi], "center_xy": [cx, cy],
        "scale_wh": [scale_w, scale_h], "padding": PADDING, "rotation": 0,
        "affine_src_to_input": forward.tolist(), "affine_input_to_src": inverse.tolist(),
        "color_order": "RGB", "mean": list(MEAN), "std": list(STD),
        "interpolation": "INTER_LINEAR", "border_mode": "BORDER_CONSTANT", "border_value": 0,
        "normalize_simcc": False, "use_dark": False, "flip_test": False,
    }


def preprocess(frame_bgr, roi_xywh):
    """Return RGB-normalized float32 NCHW [1,3,256,192] and exact affine data.

    The original ROI is neither clipped to the source image nor rounded. Outside
    source pixels receive the SDK's zero border before mean/std normalization.
    """
    if (not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8
            or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3
            or frame_bgr.shape[0] <= 0 or frame_bgr.shape[1] <= 0):
        raise ValueError("source must be a nonempty uint8 BGR HWC image with three channels")
    height, width = frame_bgr.shape[:2]
    geometry = _geometry(roi_xywh, width, height)
    affine = np.asarray(geometry["affine_src_to_input"], dtype=np.float64)
    warped = cv2.warpAffine(frame_bgr, affine, INPUT_SIZE, flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0))
    rgb = warped[:, :, ::-1].astype(np.float32)
    normalized = (rgb - np.asarray(MEAN, dtype=np.float32)) / np.asarray(STD, dtype=np.float32)
    tensor = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None, ...], dtype=np.float32)
    return tensor, geometry


def _validated_geometry(geometry, width, height):
    if not _positive_dimension(width) or not _positive_dimension(height):
        raise ValueError("original image dimensions must be positive integers")
    try:
        expected = _geometry(geometry["roi_xywh"], width, height)
        if set(geometry) != set(expected):
            raise ValueError("geometry header keys differ from the fixed SDK contract")
        for key, value in expected.items():
            if key.startswith("affine_"):
                array = np.asarray(geometry[key], dtype=np.float64)
                if array.shape != (2, 3) or not np.isfinite(array).all() or not np.array_equal(array, value):
                    raise ValueError("affine matrix differs from the fixed ROI geometry")
            elif geometry[key] != value:
                raise ValueError("geometry field differs from the fixed SDK contract: " + key)
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError("invalid geometry contract") from error
    return (np.asarray(geometry["affine_src_to_input"], dtype=np.float64),
            np.asarray(geometry["affine_input_to_src"], dtype=np.float64))


def _simcc(values, shape):
    if not isinstance(values, np.ndarray) or values.dtype != np.float32 or values.shape != shape:
        raise ValueError("native SimCC tensor must have the exact float32 SDK output shape")
    return values[0]


def build_frame(original_raw_dict, native_simcc_x, native_simcc_y, geometry, width, height, gate):
    """Decode COCO17 diagnostics and sample raw axis responses at Full locations.

    Every finite vector is used at its original values, including nonpositive
    maxima. The SDK's score<=0 decoding convention makes native XY null, while
    the independently defined response deficit remains measurable. Nonfinite
    vectors affect their own joint only; missing/outside Full bins remain null.
    """
    forward, inverse = _validated_geometry(geometry, width, height)
    xs = _simcc(native_simcc_x, (1, 17, 384))
    ys = _simcc(native_simcc_y, (1, 17, 512))
    if not isinstance(original_raw_dict, dict):
        raise ValueError("original raw landmarks must be a mapping")
    for key in ("min_visibility", "min_presence"):
        if not _finite(gate.get(key)) or not 0 <= gate[key] <= 1:
            raise ValueError("original gate must supply finite confidence bounds")
    native = []
    for index, name in enumerate(COCO_NAMES):
        finite_response = bool(np.isfinite(xs[index]).all() and np.isfinite(ys[index]).all())
        max_x = max_y = score = arg_x = arg_y = decoded_input = source = None
        if finite_response:
            arg_x, arg_y = int(np.argmax(xs[index])), int(np.argmax(ys[index]))
            max_x, max_y = float(xs[index, arg_x]), float(ys[index, arg_y])
            score = min(max_x, max_y)
            decoded_input = [arg_x / SPLIT_RATIO, arg_y / SPLIT_RATIO]
            if score > 0:
                source_array = inverse @ np.asarray([*decoded_input, 1.], dtype=np.float64)
                if np.isfinite(source_array).all():
                    source = source_array.tolist()
        state = "nonfinite_response" if not finite_response else (
            "nonpositive_score" if score <= 0 else ("decoded" if source is not None else "nonfinite_inverse_coordinate"))
        native.append({
            "index": index, "name": name,
            "x_px": source[0] if source is not None else None,
            "y_px": source[1] if source is not None else None,
            "score": score, "argmax_x_bin": arg_x, "argmax_y_bin": arg_y,
            "argmax_input_xy": decoded_input,
            "response_x_max": max_x, "response_y_max": max_y,
            "finite_response": finite_response, "decode_status": state,
        })
    roles = {}
    for role, (name, index) in ROLES.items():
        point = original_raw_dict.get(name)
        raw_finite = isinstance(point, dict) and all(_finite(point.get(key))
            for key in ("x", "y", "visibility", "presence"))
        full_xy = [float(point["x"]) * width, float(point["y"]) * height] if raw_finite else None
        if full_xy is not None and not all(math.isfinite(v) for v in full_xy):
            raw_finite, full_xy = False, None
        raw_gate = bool(raw_finite and point["visibility"] >= gate["min_visibility"]
                        and point["presence"] >= gate["min_presence"])
        input_xy = bins = deficit = None
        reason = None
        if not raw_finite:
            reason = "missing_or_nonfinite_full_point"
        else:
            transformed = forward @ np.asarray([*full_xy, 1.], dtype=np.float64)
            if not np.isfinite(transformed).all():
                reason = "nonfinite_full_input_coordinate"
            else:
                input_xy = transformed.tolist()
                bins = [math.floor(SPLIT_RATIO * coordinate + .5) for coordinate in input_xy]
                if not native[index]["finite_response"]:
                    reason = "nonfinite_native_response"
                elif not (0 <= bins[0] < 384 and 0 <= bins[1] < 512):
                    reason = "full_point_outside_simcc_bins"
                else:
                    deficit = ((native[index]["response_x_max"] - float(xs[index, bins[0]]))
                               + (native[index]["response_y_max"] - float(ys[index, bins[1]])))
                    if not math.isfinite(deficit):
                        deficit, reason = None, "nonfinite_response_deficit"
        roles[role] = {
            "original_point": deepcopy(point), "raw_finite": bool(raw_finite), "raw_gate_pass": raw_gate,
            "full_xy_px": full_xy, "full_input_xy": input_xy, "bins": bins,
            "native_joint_index": index, "native_score": native[index]["score"],
            "native_xy_px": [native[index]["x_px"], native[index]["y_px"]]
                if native[index]["x_px"] is not None else None,
            "native_vector_finite": native[index]["finite_response"],
            "response_deficit": deficit,
            "evidence_status": "measured" if deficit is not None else "insufficient_evidence",
            "reason": reason,
        }
    return {
        "native_contract": {"schema": "rtmpose_body7_coco17_simcc_v1", "landmark_count": 17,
            "input_size": list(INPUT_SIZE), "simcc_split_ratio": SPLIT_RATIO,
            "simcc_x_shape": [1, 17, 384], "simcc_y_shape": [1, 17, 512],
            "score": "minimum_of_native_axis_maxima", "response_normalized": False,
            "decoded_nonpositive_score_xy": None},
        "native_keypoints": native, "roles": roles,
    }
