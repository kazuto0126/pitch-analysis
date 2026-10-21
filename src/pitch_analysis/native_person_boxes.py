"""Fixed, uncalibrated person-box conditioning; no GT or model runtime reads."""
from __future__ import annotations

from math import isfinite

import cv2
import numpy as np

from .native_pose_estimator import _crop_bounds

FINAL_SCORE_THRESHOLD = 0.7
INPUT_SIZE = 640
POLICY = 'unique_person_box_center_in_operator_roi_v1'


def prepare_detector_input(frame_bgr: np.ndarray, crop_xyxy) -> tuple[np.ndarray, dict]:
    """Upstream BGR resize, bottom/right 114 padding and float32 NCHW."""
    left, top, right, bottom = _crop_bounds(frame_bgr, crop_xyxy)
    image = frame_bgr[top:bottom, left:right]
    height, width = image.shape[:2]
    ratio = min(INPUT_SIZE / height, INPUT_SIZE / width)
    resized = (int(width * ratio), int(height * ratio))
    canvas = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
    canvas[:resized[1], :resized[0]] = cv2.resize(image, resized, interpolation=cv2.INTER_LINEAR)
    tensor = np.ascontiguousarray(canvas.transpose(2, 0, 1)[None], dtype=np.float32)
    return tensor, {
        'crop_xyxy_px': [left, top, right, bottom],
        'source_size': [int(frame_bgr.shape[1]), int(frame_bgr.shape[0])],
        'resized_size': list(resized), 'resize_ratio': ratio,
        'input_size': [INPUT_SIZE, INPUT_SIZE], 'padding_bgr': [114, 114, 114],
        'padding_alignment': 'top_left_image_bottom_right_padding',
        'channel_order': 'BGR', 'normalization': 'mean0_std1',
        'source_pixels_outside_operator_crop': False,
    }


def select_person_box(outputs, geometry: dict, subject_roi) -> dict:
    """Use every emitted detection; ambiguity never picks a highest-score person.

    The exact model has baked NMS. Its raw tensors are retained by the worker;
    internally suppressed proposals cannot be recovered here. No second NMS.
    """
    if not isinstance(outputs, (tuple, list)) or len(outputs) != 2:
        raise ValueError('Detector must return dets and labels')
    dets, labels = (np.asarray(value) for value in outputs)
    if (dets.ndim != 3 or dets.shape[0] != 1 or dets.shape[2] != 5
            or labels.shape != dets.shape[:2] or dets.dtype != np.float32
            or labels.dtype != np.int64 or dets.shape[1] > 10000):
        raise ValueError('Expected native float32[1,N,5] and int64[1,N] detector outputs')
    if (not isinstance(subject_roi, (list, tuple)) or len(subject_roi) != 4
            or any(isinstance(v, (bool, np.bool_)) or not isfinite(float(v)) for v in subject_roi)):
        raise ValueError('Explicit finite operator ROI required')
    xmin, ymin, xmax, ymax = map(float, subject_roi)
    if not 0 <= xmin < xmax <= 1 or not 0 <= ymin < ymax <= 1:
        raise ValueError('Invalid normalized operator ROI')
    left, top, right, bottom = geometry['crop_xyxy_px']
    width, height = geometry['source_size']
    ratio = geometry['resize_ratio']
    if not isfinite(ratio) or ratio <= 0:
        raise ValueError('Positive detector resize ratio required')
    candidates = []
    for index, (row, label) in enumerate(zip(dets[0], labels[0], strict=True)):
        finite = np.isfinite(row)
        safe = [float(v) if okay else None for v, okay in zip(row, finite, strict=True)]
        reasons = []
        bbox = None
        if not finite.all():
            reasons.append('nonfinite_detector_output')
        else:
            x1, y1, x2, y2, score = map(float, row)
            bbox = [x1 / ratio + left, y1 / ratio + top, x2 / ratio + left, y2 / ratio + top]
            if x2 <= x1 or y2 <= y1:
                reasons.append('nonpositive_box')
            if min(bbox[2], right) <= max(bbox[0], left) or min(bbox[3], bottom) <= max(bbox[1], top):
                reasons.append('no_operator_crop_intersection')
            center_x, center_y = (bbox[0] + bbox[2]) / (2 * width), (bbox[1] + bbox[3]) / (2 * height)
            if not xmin <= center_x <= xmax or not ymin <= center_y <= ymax:
                reasons.append('box_center_outside_operator_roi')
            if score < FINAL_SCORE_THRESHOLD:
                reasons.append('below_fixed_detector_score')
        if int(label) != 0:
            reasons.append('not_person_class')
        candidates.append({
            'output_index': index, 'class_id': int(label), 'person_class_id': 0,
            'native_dets_row_json_safe': safe,
            'nonfinite_native_output': not bool(finite.all()),
            'bbox_original_xyxy_px': bbox,
            'native_score': safe[4],
            'bbox_extends_outside_operator_crop': (None if bbox is None else
                bbox[0] < left or bbox[1] < top or bbox[2] > right or bbox[3] > bottom),
            'eligible': not reasons, 'rejection_reasons': reasons,
        })
    eligible = [candidate for candidate in candidates if candidate['eligible']]
    selected = eligible[0] if len(eligible) == 1 else None
    return {
        'policy': POLICY, 'status': ('selected' if selected else
            'no_subject_box' if not eligible else 'ambiguous_subject_boxes'),
        'eligible_count': len(eligible), 'emitted_detection_count': len(candidates),
        'selected_output_index': selected['output_index'] if selected else None,
        'selected_bbox_xyxy_px': selected['bbox_original_xyxy_px'] if selected else None,
        'selected_bbox_extends_outside_operator_crop': selected['bbox_extends_outside_operator_crop'] if selected else None,
        'operator_roi': list(subject_roi), 'final_score_threshold': FINAL_SCORE_THRESHOLD,
        'second_nms': False, 'pre_nms_suppressed_proposals_available': False,
        'identity_confirmed': None, 'candidates': candidates,
    }
