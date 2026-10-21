"""Native RTMPose geometry and decoding, with no model runtime dependency.

The caller supplies a transport that evaluates one prepared tensor.  This
module neither selects a subject nor applies the production confidence gates.
Its preprocessing follows the sealed OpenMMLab ONNX example: BGR channels are
unchanged, the box is padded by 1.25, and the input size is 192 by 256 pixels.
"""
from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral, Real
from typing import Protocol

import cv2
import numpy as np

from .native_pose import TOPOLOGIES


_INPUT_SIZE = (192, 256)
_PADDING = 1.25
_SIMCC_SPLIT_RATIO = 2.0
_MEAN = np.array([123.675, 116.28, 103.53], dtype=np.float64)
_STD = np.array([58.395, 57.12, 57.375], dtype=np.float64)


@dataclass(frozen=True)
class NativePoseEstimate:
    """One model's native landmarks and their source-image transformation."""

    landmarks: list[dict]
    input_geometry: dict


class NativePoseEstimator(Protocol):
    """Explicit live estimation, separate from a cached NativePoseSource."""

    backend_name: str

    def estimate(self, frame_bgr: np.ndarray) -> NativePoseEstimate: ...


class RTMPoseTransport(Protocol):
    """Evaluate one float32 NCHW tensor without implicit retries."""

    def run(self, tensor: np.ndarray) -> tuple[np.ndarray, np.ndarray]: ...


def _crop_bounds(frame_bgr: np.ndarray, crop_xyxy) -> tuple[int, int, int, int]:
    if (not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8
            or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3
            or frame_bgr.shape[0] == 0 or frame_bgr.shape[1] == 0):
        raise ValueError("RTMPose requires a nonempty uint8 BGR image")
    if (not isinstance(crop_xyxy, (tuple, list)) or len(crop_xyxy) != 4
            or any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral)
                   for value in crop_xyxy)):
        raise ValueError("RTMPose crop must contain four integer pixel coordinates")
    left, top, right, bottom = map(int, crop_xyxy)
    height, width = frame_bgr.shape[:2]
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError("RTMPose crop must be nonempty and inside the source image")
    return left, top, right, bottom


def prepare_rtmpose_input(frame_bgr: np.ndarray, crop_xyxy, *,
                          person_bbox_xyxy=None) -> tuple[np.ndarray, dict]:
    """Crop first, then apply the official zero-rotation affine and normalization.

    Padding samples black outside the already extracted crop.  It cannot expose
    pixels outside the caller's fixed crop even if they exist in the full frame.
    The saved affine matrices map original-image pixels, including crop offset.
    An optional person box chooses the affine center/scale, while the sampling
    canvas remains the approved crop. Its padding may see crop-local context.
    """
    left, top, right, bottom = _crop_bounds(frame_bgr, crop_xyxy)
    crop = frame_bgr[top:bottom, left:right]
    crop_width, crop_height = right - left, bottom - top
    input_width, input_height = _INPUT_SIZE
    person_box = None
    if person_bbox_xyxy is None:
        center = np.array([crop_width, crop_height], dtype=np.float64) * .5
        padded_scale = np.array([crop_width, crop_height], dtype=np.float64) * _PADDING
    else:
        if (not isinstance(person_bbox_xyxy, (tuple, list)) or len(person_bbox_xyxy) != 4
                or any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real)
                       or not np.isfinite(value) for value in person_bbox_xyxy)):
            raise ValueError("Person box requires four finite original-image coordinates")
        person_box = np.asarray(person_bbox_xyxy, dtype=np.float64)
        x1, y1, x2, y2 = person_box
        if x2 <= x1 or y2 <= y1:
            raise ValueError("Person box must have positive dimensions")
        if max(x1, left) >= min(x2, right) or max(y1, top) >= min(y2, bottom):
            raise ValueError("Person box has no intersection with the approved crop")
        with np.errstate(over="ignore", invalid="ignore"):
            center = np.array([x1 * .5 + x2 * .5 - left, y1 * .5 + y2 * .5 - top])
            padded_scale = np.array([x2 - x1, y2 - y1]) * _PADDING
        if not np.isfinite(center).all() or not np.isfinite(padded_scale).all():
            raise ValueError("Person box exceeds the affine numeric range")
    scale = padded_scale.copy()
    aspect_ratio = input_width / input_height
    if scale[0] > scale[1] * aspect_ratio:
        scale[1] = scale[0] / aspect_ratio
    else:
        scale[0] = scale[1] * aspect_ratio
    if (not np.isfinite(scale).all() or
            np.any(np.abs(center) + scale > np.finfo(np.float32).max * .5)):
        raise ValueError("Person box exceeds the affine numeric range")

    # These three control points are the official get_warp_matrix at rot=0.
    # Its vertical direction uses scale width; the adjusted aspect supplies Y.
    source = np.zeros((3, 2), dtype=np.float32)
    source[0] = center
    source[1] = center + [0, -.5 * scale[0]]
    direction = source[0] - source[1]
    source[2] = source[1] + [-direction[1], direction[0]]
    target = np.zeros((3, 2), dtype=np.float32)
    target[0] = [input_width * .5, input_height * .5]
    target[1] = target[0] + [0, -.5 * input_width]
    direction = target[0] - target[1]
    target[2] = target[1] + [-direction[1], direction[0]]
    crop_to_input = cv2.getAffineTransform(source, target)
    warped = cv2.warpAffine(crop, crop_to_input, _INPUT_SIZE,
                            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                            borderValue=(0, 0, 0))
    normalized = (warped - _MEAN) / _STD
    tensor = np.ascontiguousarray(normalized.transpose(2, 0, 1)[None], dtype=np.float32)

    original_to_crop = np.array([[1., 0., -left], [0., 1., -top], [0., 0., 1.]])
    source_to_input = crop_to_input @ original_to_crop
    input_to_source = cv2.invertAffineTransform(source_to_input)
    geometry = {
        "input_mode": "roi_affine",
        "roi_xywh": [left, top, crop_width, crop_height],
        "affine_src_to_input": source_to_input.tolist(),
        "affine_input_to_src": input_to_source.tolist(),
        "sdk_geometry": {
            "preprocessing": "openmmlab_sealed_onnx_example_crop_then_affine",
            "source_size": [int(frame_bgr.shape[1]), int(frame_bgr.shape[0])],
            "crop_xyxy": [left, top, right, bottom],
            "crop_origin_px": [left, top],
            "crop_size": [crop_width, crop_height],
            "center_crop_px": center.tolist(),
            "center_source_px": (center + [left, top]).tolist(),
            "scale_before_aspect": padded_scale.tolist(),
            "scale": scale.tolist(),
            "padding": _PADDING,
            "aspect_ratio": aspect_ratio,
            "rotation_degrees": 0,
            "input_size": list(_INPUT_SIZE),
            "affine_crop_to_input": crop_to_input.tolist(),
            "color_order": "BGR_unchanged",
            "mean": _MEAN.tolist(),
            "std": _STD.tolist(),
            "interpolation": "cv2.INTER_LINEAR",
            "border": {"mode": "constant", "bgr": [0, 0, 0],
                       "source": "padding_outside_extracted_crop"},
            "simcc_split_ratio": _SIMCC_SPLIT_RATIO,
            "coordinate_clamping": False,
        },
    }
    if person_box is not None:
        sdk = geometry["sdk_geometry"]
        sdk.update({
            "preprocessing": "openmmlab_person_bbox_affine_on_approved_crop",
            "person_bbox_xyxy_px": person_box.tolist(),
            "person_bbox_clamped": False,
            "person_bbox_outside_approved_crop": bool(person_box[0] < left or person_box[1] < top
                                                      or person_box[2] > right or person_box[3] > bottom),
            "person_bbox_crop_intersection_xyxy_px": [max(float(person_box[0]), left),
                                                       max(float(person_box[1]), top),
                                                       min(float(person_box[2]), right),
                                                       min(float(person_box[3]), bottom)],
            "sampling_canvas": "approved_motion_crop_only",
            "person_bbox_padding_context": "pixels_inside_approved_crop_allowed",
        })
    return tensor, geometry


def _axis_record(axis: np.ndarray) -> tuple[int, float | None, dict]:
    maximum = float(np.max(axis))
    details = {
        "nan": int(np.isnan(axis).sum()),
        "positive_infinity": int(np.isposinf(axis).sum()),
        "negative_infinity": int(np.isneginf(axis).sum()),
    }
    return int(np.argmax(axis)), maximum if np.isfinite(maximum) else None, details


def decode_rtmpose_outputs(outputs, geometry: dict) -> list[dict]:
    """Decode native SimCC maxima and return COCO17 in original image pixels.

    The native score is min(max(X), max(Y)), not a probability or a visibility.
    The official decoder's nonpositive response is missing.  Any nonfinite
    response in a joint also stays missing, with JSON-safe diagnostic details.
    No confidence cutoff, coordinate clipping, interpolation or 33-point fill
    is applied.
    """
    if not isinstance(outputs, (tuple, list)) or len(outputs) != 2:
        raise ValueError("RTMPose transport must return two SimCC arrays")
    simcc_x, simcc_y = (np.asarray(value) for value in outputs)
    if (simcc_x.shape != (1, 17, 384) or simcc_y.shape != (1, 17, 512)
            or any(not np.issubdtype(value.dtype, np.floating) for value in (simcc_x, simcc_y))):
        raise ValueError("RTMPose requires floating SimCC shapes (1,17,384) and (1,17,512)")
    inverse = np.asarray(geometry.get("affine_input_to_src"), dtype=np.float64)
    if (geometry.get("input_mode") != "roi_affine" or inverse.shape != (2, 3)
            or not np.isfinite(inverse).all()):
        raise ValueError("RTMPose decode requires a finite inverse ROI affine")

    landmarks = []
    for index, name in enumerate(TOPOLOGIES["coco_17"]["names"]):
        x_index, x_max, x_nonfinite = _axis_record(simcc_x[0, index])
        y_index, y_max, y_nonfinite = _axis_record(simcc_y[0, index])
        score = min(x_max, y_max) if x_max is not None and y_max is not None else None
        has_nonfinite = any(x_nonfinite.values()) or any(y_nonfinite.values())
        input_xy = [x_index / _SIMCC_SPLIT_RATIO, y_index / _SIMCC_SPLIT_RATIO]
        reason = ("nonfinite_native_response" if has_nonfinite else
                  "nonpositive_native_response" if score is None or score <= 0 else None)
        original_xy = None
        if reason is None:
            original_xy = inverse @ [*input_xy, 1.]
            if not np.isfinite(original_xy).all():
                original_xy = None
                reason = "nonfinite_inverse_affine_xy"
        landmarks.append({
            "name": name, "index": index,
            "x_px": float(original_xy[0]) if original_xy is not None else None,
            "y_px": float(original_xy[1]) if original_xy is not None else None,
            "z": None, "visibility": None, "presence": None, "native_score": score,
            "coordinate_state": "model_observed" if reason is None else "missing",
            "missing_reason": reason,
            "source_record": {
                "simcc_argmax_xy": [x_index, y_index],
                "simcc_axis_maxima": [x_max, y_max],
                "native_score": score,
                "simcc_nonfinite_values": {"x": x_nonfinite, "y": y_nonfinite},
                "simcc_split_ratio": _SIMCC_SPLIT_RATIO,
                "native_input_xy_px": input_xy if reason is None else None,
                "decode_status": "decoded" if reason is None else reason,
                "score_semantics": "minimum_of_native_axis_maxima_not_probability",
            },
        })
    return landmarks


class RTMPoseNativeEstimator:
    """Run one explicit transport call for each requested source BGR frame."""

    backend_name = "rtmpose"

    def __init__(self, transport: RTMPoseTransport, *, crop_xyxy: tuple[int, int, int, int]):
        self.transport = transport
        self.crop_xyxy = tuple(crop_xyxy)

    def estimate(self, frame_bgr: np.ndarray, *, person_bbox_xyxy=None) -> NativePoseEstimate:
        tensor, geometry = prepare_rtmpose_input(frame_bgr, self.crop_xyxy,
                                                person_bbox_xyxy=person_bbox_xyxy)
        outputs = self.transport.run(tensor)
        landmarks = decode_rtmpose_outputs(outputs, geometry)
        return NativePoseEstimate(landmarks, geometry)
