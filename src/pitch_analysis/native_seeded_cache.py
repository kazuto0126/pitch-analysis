"""Exact reuse checks for previously executed person-box native predictions.

This module reads no files and invokes no model. A match allows the caller to
copy the already saved native output, including any genuinely missing points;
it does not upgrade its uncalibrated status or establish human visibility.
"""
from __future__ import annotations

from fractions import Fraction
import json
import math
import re

from .native_pose import _finite_json, validate_frame, validate_manifest


def _canonical(value) -> str:
    """Distinguish JSON types (including bool/int/float), without tolerances."""
    _finite_json(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _exact(first, second) -> bool:
    try:
        return _canonical(first) == _canonical(second)
    except (TypeError, ValueError):
        return False


def _sha(value) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _number(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _bbox(value) -> bool:
    return (isinstance(value, list) and len(value) == 4
            and all(_number(item) for item in value)
            and value[2] > value[0] and value[3] > value[1])


def cache_geometry_matches(manifest: dict, cached_record: dict, *, model_sha256: str,
                           source_video_sha256: str, frame_index: int,
                           timestamp_ms: float, decoded_bgr_sha256: str,
                           person_bbox_xyxy: list, input_geometry: dict) -> tuple[bool, list[str]]:
    """Return whether all source and geometry facts permit exact cache reuse.

    Native numeric JSON types and all saved SDK geometry fields must match.
    There is no coordinate tolerance, alternate-cache search, inference or
    mutation. Source-file SHA verification remains the producer's job.
    """
    if (not all(_sha(value) for value in (model_sha256, source_video_sha256, decoded_bgr_sha256))
            or type(frame_index) is not int or frame_index < 0
            or not _number(timestamp_ms)
            or timestamp_ms < 0 or not _bbox(person_bbox_xyxy)
            or not isinstance(input_geometry, dict)):
        return False, ["invalid_expected_reuse_facts"]
    try:
        _canonical(input_geometry)
    except (TypeError, ValueError):
        return False, ["invalid_expected_reuse_facts"]
    if not isinstance(manifest, dict) or not isinstance(cached_record, dict):
        return False, ["invalid_cached_contract"]
    try:
        validate_manifest(manifest)
        validate_frame(cached_record)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False, ["invalid_cached_contract"]

    reasons = []
    if (manifest["topology"] != "coco_17" or cached_record["topology"] != "coco_17"
            or manifest["inference_mode"] != "live_stateless_roi"
            or "rtmpose" not in manifest["backend"]["name"].lower()):
        reasons.append("not_live_rtmpose_coco17")
    if manifest["backend"]["model_sha256"] != model_sha256:
        reasons.append("source_model_mismatch")
    if (manifest["video"]["sha256"] != source_video_sha256
            or cached_record["source_video_sha256"] != source_video_sha256):
        reasons.append("source_video_mismatch")
    if (cached_record["pitch_id"] != manifest["pitch_id"]
            or cached_record["backend"] != manifest["backend"]["name"]
            or not _exact(cached_record["image_size"], manifest["image_size"])):
        reasons.append("cached_envelope_mismatch")
    if cached_record["frame_index"] != frame_index or frame_index >= manifest["video"]["frame_count"]:
        reasons.append("frame_index_mismatch")
    try:
        fps = Fraction(manifest["timebase"]["fps_fraction"])
        expected_time = float(Fraction(frame_index * 1000, 1) / fps)
    except (KeyError, ValueError, ZeroDivisionError):
        expected_time = None
    if (not _exact(cached_record["timestamp_ms"], timestamp_ms)
            or not _exact(timestamp_ms, expected_time)):
        reasons.append("timestamp_mismatch")
    if cached_record["decoded_bgr_sha256"] != decoded_bgr_sha256:
        reasons.append("decoded_pixels_mismatch")
    if (manifest["quality_status"] != "not_calibrated"
            or cached_record["quality_status"] != "not_calibrated"
            or manifest["usable_for_analysis"] is not None
            or cached_record["usable_for_analysis"] is not None):
        reasons.append("quality_not_compatible")

    selection = cached_record["model_selection"]
    geometry = cached_record["input_geometry"]
    attempt = selection.get("isolated_worker_attempt_index")
    if (selection.get("pose_not_run") is not False
            or selection.get("inference_mode") != "live_stateless_roi"
            or geometry["input_mode"] != "roi_affine"
            or type(attempt) is not int or attempt < 1):
        reasons.append("cached_pose_not_executed")
    box_selection = selection.get("person_box_selection", {})
    if (not isinstance(box_selection, dict) or box_selection.get("status") != "selected"
            or not _exact(box_selection.get("selected_bbox_xyxy_px"), person_bbox_xyxy)):
        reasons.append("selected_bbox_mismatch")
    sdk = geometry.get("sdk_geometry")
    if (not isinstance(sdk, dict)
            or not _exact(sdk.get("person_bbox_xyxy_px"), person_bbox_xyxy)):
        reasons.append("saved_person_bbox_mismatch")
    if not _exact(geometry, input_geometry):
        reasons.append("input_geometry_mismatch")
    return not reasons, reasons
