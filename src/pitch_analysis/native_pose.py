"""Native pose contracts, independent of the production quality gates.

Coordinates describe model output in original image pixels.  Neither a finite
coordinate nor a native model score is a claim of visibility or accuracy.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from fractions import Fraction
from functools import lru_cache
from importlib.resources import files
import json
import math
from pathlib import PurePosixPath
from typing import Protocol

from jsonschema import Draft202012Validator


_MP_NAMES = (
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER", "RIGHT_EYE_INNER",
    "RIGHT_EYE", "RIGHT_EYE_OUTER", "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT",
    "MOUTH_RIGHT", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY", "LEFT_INDEX",
    "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB", "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL",
    "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
)
_COCO_NAMES = (
    "NOSE", "LEFT_EYE", "RIGHT_EYE", "LEFT_EAR", "RIGHT_EAR", "LEFT_SHOULDER",
    "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST",
    "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
)
TOPOLOGIES = {
    "mediapipe_33": {
        "names": _MP_NAMES,
        "connections": ((11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
                        (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
                        (24, 26), (26, 28), (27, 31), (28, 32)),
    },
    "coco_17": {
        "names": _COCO_NAMES,
        "connections": ((5, 6), (5, 7), (7, 9), (6, 8), (8, 10), (5, 11),
                        (6, 12), (11, 12), (11, 13), (13, 15), (12, 14), (14, 16)),
    },
}
COMMON_JOINTS = tuple(f"{side}_{joint}" for joint in
                      ("SHOULDER", "ELBOW", "WRIST", "HIP", "KNEE", "ANKLE")
                      for side in ("LEFT", "RIGHT"))
CAPABILITIES = {
    "mediapipe_33": {"z": True, "visibility": True, "presence": True, "native_score": False},
    "coco_17": {"z": False, "visibility": False, "presence": False, "native_score": True},
}


def _finite_json(value: object, location: str = "$") -> None:
    """Reject non-JSON objects and nonfinite numbers even in source metadata."""
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Nonfinite JSON number at {location}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _finite_json(item, f"{location}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"JSON keys must be strings at {location}")
            _finite_json(item, f"{location}.{key}")
        return
    raise ValueError(f"Unsupported JSON value at {location}: {type(value).__name__}")


@lru_cache(maxsize=1)
def _schema() -> dict:
    return json.loads(files("pitch_analysis.contracts").joinpath(
        "schemas", "native-keypoints-v1.json").read_text(encoding="utf-8"))


def _validate_schema(payload: dict, definition: str) -> None:
    _finite_json(payload)
    schema = {"$schema": _schema()["$schema"], "$defs": _schema()["$defs"],
              "$ref": f"#/$defs/{definition}"}
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: str(e.path))
    if errors:
        error = errors[0]
        location = ".".join(map(str, error.path)) or "$"
        raise ValueError(f"Native pose {definition} at {location}: {error.message}")


def _validate_reference(ref: dict) -> None:
    path = ref["path"]
    parts = PurePosixPath(path).parts
    if (not parts or path.startswith("/") or "\\" in path or ":" in path or
            any(part in (".", "..") for part in path.split("/")) or
            PurePosixPath(path).as_posix() != path):
        raise ValueError("Source reference must use a normalized root-relative POSIX path")


def validate_manifest(payload: dict) -> None:
    """Validate a source envelope without touching files or invoking a model.

    Cached manifests retain their original contract.  The opt-in live mode also
    binds its model, video, operation configuration, and human input review.
    """
    _validate_schema(payload, "manifest")
    topology = payload["topology"]
    if payload["capabilities"] != CAPABILITIES[topology]:
        raise ValueError("Native capabilities do not match topology")
    for ref in payload["source_refs"]:
        _validate_reference(ref)
    if payload["original_overlay"] is not None:
        _validate_reference(payload["original_overlay"])
    if payload["inference_mode"] == "live_stateless_roi":
        _validate_live_manifest(payload)


def _validate_live_manifest(payload: dict) -> None:
    if payload["topology"] != "coco_17" or "rtmpose" not in payload["backend"]["name"].lower():
        raise ValueError("Live native mode requires RTMPose COCO17")
    refs = payload["source_refs"]
    video_ref = {"path": payload["video"]["path"], "sha256": payload["video"]["sha256"]}
    if video_ref not in refs:
        raise ValueError("Live native video must be declared in source_refs")
    if not any(ref["sha256"] == payload["backend"]["model_sha256"] for ref in refs):
        raise ValueError("Live native model must be declared in source_refs")
    provenance = payload["roi_provenance"]
    for key in ("config_ref", "review_ref"):
        ref = provenance.get(key)
        if not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or ref not in refs:
            raise ValueError(f"Live native ROI {key} must match a declared source reference")
    for key in ("reviewer", "roi_source"):
        if not isinstance(provenance.get(key), str) or not provenance[key].strip():
            raise ValueError(f"Live native ROI requires explicit {key}")
    reviewed = provenance.get("reviewed_at_utc")
    try:
        if not isinstance(reviewed, str):
            raise ValueError
        parsed = datetime.fromisoformat(reviewed.replace("Z", "+00:00"))
        if parsed.utcoffset() != timedelta(0):
            raise ValueError
    except (ValueError, TypeError):
        raise ValueError("Live native ROI requires reviewed_at_utc with a UTC timezone") from None
    fps_text = payload["timebase"].get("fps_fraction")
    if fps_text is None:
        raise ValueError("Live native timebase requires fps_fraction")
    fps = Fraction(fps_text)
    if fps <= 0 or not math.isclose(float(fps), payload["video"]["fps"], rel_tol=0, abs_tol=1e-9):
        raise ValueError("Live native FPS must preserve its declared fractional source FPS")


def validate_frame(payload: dict) -> None:
    """Validate native order/capabilities without applying confidence gates."""
    _validate_schema(payload, "frame")
    topology = payload["topology"]
    names = TOPOLOGIES[topology]["names"]
    points = payload["landmarks"]
    if len(points) != len(names):
        raise ValueError("Native landmark count differs from declared topology")
    for index, (name, point) in enumerate(zip(names, points, strict=True)):
        if point["index"] != index or point["name"] != name:
            raise ValueError("Native landmark name/index/order differs from topology")
        for capability, supported in CAPABILITIES[topology].items():
            if not supported and point[capability] is not None:
                raise ValueError(f"Unsupported {capability} must remain null")
        if point["coordinate_state"] == "model_observed":
            if point["x_px"] is None or point["y_px"] is None or point["missing_reason"] is not None:
                raise ValueError("Observed native point needs finite XY and null missing_reason")
        elif point["x_px"] is not None or point["y_px"] is not None or not point["missing_reason"]:
            raise ValueError("Missing native point needs null XY and an explicit missing_reason")
    geometry = payload["input_geometry"]
    if topology == "mediapipe_33":
        if geometry["input_mode"] != "full_frame" or any(geometry[key] is not None for key in
                ("roi_xywh", "affine_src_to_input", "affine_input_to_src", "sdk_geometry")):
            raise ValueError("MediaPipe cached source must preserve full-frame input geometry")
    else:
        if geometry["input_mode"] != "roi_affine" or any(geometry[key] is None for key in
                ("roi_xywh", "affine_src_to_input", "affine_input_to_src", "sdk_geometry")):
            raise ValueError("RTMPose native source requires its saved ROI and affine geometry")
        if geometry["roi_xywh"][2] <= 0 or geometry["roi_xywh"][3] <= 0:
            raise ValueError("Native ROI dimensions must be positive")


@dataclass(frozen=True, init=False)
class NativePoseFrame:
    """Validated frame whose exported dictionaries cannot mutate its snapshot."""

    _payload: dict = field(repr=False)

    def __init__(self, payload: dict) -> None:
        snapshot = deepcopy(payload)
        validate_frame(snapshot)
        object.__setattr__(self, "_payload", snapshot)

    @property
    def payload(self) -> dict:
        return self.to_dict()

    def to_dict(self) -> dict:
        return deepcopy(self._payload)


class NativePoseSource(Protocol):
    """A cached source, never an implicit model estimator."""

    manifest: dict

    def read_frame(self, index: int) -> NativePoseFrame: ...

    def __len__(self) -> int: ...
