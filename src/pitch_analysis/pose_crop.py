"""Optional image crop geometry; native and original-image points stay separate.

MediaPipe Z uses an image-width-relative scale. Rescaling it restores the
original image-width convention, not calibrated three-dimensional geometry.
"""
from __future__ import annotations

from math import ceil, floor, isfinite
from numbers import Integral, Real
from types import SimpleNamespace


def validate_input_crop(input_crop) -> tuple[float, float, float, float] | None:
    """Validate an optional normalized original-image XYXY crop."""
    if input_crop is None:
        return None
    if not isinstance(input_crop, (tuple, list)) or len(input_crop) != 4:
        raise ValueError("input_crop must contain four normalized image coordinates")
    if any(isinstance(value, bool) or not isinstance(value, Real)
           or not isfinite(float(value)) for value in input_crop):
        raise ValueError("input_crop coordinates must be finite numbers, not booleans")
    xmin, ymin, xmax, ymax = (float(value) for value in input_crop)
    if not (0 <= xmin < xmax <= 1 and 0 <= ymin < ymax <= 1):
        raise ValueError("input_crop must satisfy 0 <= min < max <= 1 on both axes")
    return xmin, ymin, xmax, ymax


def build_input_transform(input_crop, width: int, height: int) -> dict:
    """Describe the exact unresized pixel slice and inverse landmark mapping."""
    crop = validate_input_crop(input_crop)
    if crop is None:
        raise ValueError("input_crop is required to build a crop transform")
    if any(isinstance(value, bool) or not isinstance(value, Integral) or value <= 0
           for value in (width, height)):
        raise ValueError("input_crop requires positive integer original image dimensions")
    left, top = floor(crop[0] * width), floor(crop[1] * height)
    right, bottom = ceil(crop[2] * width), ceil(crop[3] * height)
    crop_width, crop_height = right - left, bottom - top
    return {
        "schema_version": "pose-input-crop-v1",
        "operation": "axis_aligned_crop_without_resize",
        "requested_bounds_normalized_xyxy": list(crop),
        "pixel_bounds_xyxy": [left, top, right, bottom],
        "pixel_bound_rounding": "floor_left_top_ceil_right_bottom; right_bottom_exclusive",
        "original_image_size_px": [width, height],
        "model_input_size_px": [crop_width, crop_height],
        "native_coordinate_system": "crop_image_normalized_xy",
        "output_coordinate_system": "original_image_normalized_xy",
        "x_mapping": "(left + native_x * crop_width) / original_width",
        "y_mapping": "(top + native_y * crop_height) / original_height",
        "z_mapping": "native_z * crop_width / original_width",
        "z_scale": crop_width / width,
        "z_semantics": "MediaPipe model-relative depth in original-image-width units; not calibrated metric 3D",
        "confidence_mapping": "visibility and presence unchanged; missing presence remains missing",
        "coordinate_clamping": False,
    }


def map_crop_candidates(poses, transform: dict) -> list[list]:
    """Return new mapped points while preserving every native input object."""
    left, top, right, bottom = transform["pixel_bounds_xyxy"]
    width, height = transform["original_image_size_px"]
    crop_width, crop_height = right - left, bottom - top
    mapped = []
    for pose in poses:
        points = []
        for point in pose:
            converted = SimpleNamespace(
                x=(left + point.x * crop_width) / width,
                y=(top + point.y * crop_height) / height,
                z=point.z * crop_width / width,
                visibility=point.visibility,
            )
            if hasattr(point, "presence"):
                converted.presence = point.presence
            points.append(converted)
        mapped.append(points)
    return mapped
