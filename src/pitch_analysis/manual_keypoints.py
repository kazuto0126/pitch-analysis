"""Validate independent, manually placed skeleton coordinates from CVAT.

These annotations are a separate sidecar from model predictions and from
qualitative event/reliability review. Hidden or uncertain joints have no XY
position; an unfinished annotation cannot become completed ground truth merely
by changing its review status.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timedelta
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


JOINT_NAMES = (
    "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST",
    "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE",
    "LEFT_ANKLE", "RIGHT_ANKLE",
)


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(
        files("pitch_analysis.contracts")
        .joinpath("schemas", "manual-keypoints-v1.json")
        .read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_finite(value: int | float | None, location: str) -> None:
    # Integers are finite even when they are too large to convert to a float.
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"manual-keypoints-v1 at {location}: must be finite")


def _check_review_time(value: str) -> None:
    # jsonschema's RFC 3339 checker is optional; validate without extra packages.
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|\+00:00)", value,
    ):
        raise ValueError("manual keypoints reviewed_at_utc must be a UTC date-time")
    try:
        completed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("manual keypoints reviewed_at_utc must be a valid UTC date-time") from error
    if completed.utcoffset() != timedelta(0):
        raise ValueError("manual keypoints reviewed_at_utc must use UTC")


def validate_manual_keypoints(
    payload: dict, source_video_path: str | Path | None = None,
) -> None:
    """Check the sidecar, full frame/joint coverage, and optional source video.

    Coordinates use the original decoded image in pixels, with the origin at
    its top left. Each source frame appears once in ascending zero-based order.
    Image hashes and timestamps are checked against the export manifest by the
    importer; this validator checks their shape and timeline consistency.
    """
    errors = sorted(_validator().iter_errors(payload), key=lambda error: str(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "$"
        raise ValueError(f"manual-keypoints-v1 at {location}: {error.message}")

    status = payload["annotation_status"]
    provenance = payload["provenance"]
    if provenance["reviewed_at_utc"] is not None:
        _check_review_time(provenance["reviewed_at_utc"])
    if status == "in_progress" and provenance["reviewed_at_utc"] is not None:
        raise ValueError("in_progress manual keypoints cannot have a completed review time")
    if status == "reviewed":
        if provenance["reviewer"] is None or not provenance["reviewer"].strip():
            raise ValueError("reviewed manual keypoints require a reviewer")
        if provenance["reviewed_at_utc"] is None:
            raise ValueError("reviewed manual keypoints require reviewed_at_utc")

    frames = payload["frames"]
    total_frames = payload["source_video"]["total_frames"]
    if len(frames) != total_frames:
        raise ValueError("manual keypoints must include every source frame exactly once")

    width, height = payload["image_size"]["width"], payload["image_size"]["height"]
    previous_timestamp = -1
    image_names = set()
    for expected_index, frame in enumerate(frames):
        if frame["frame_index"] != expected_index:
            raise ValueError("manual keypoint frames must be in zero-based source timeline order without gaps")
        timestamp = frame["timestamp_ms"]
        _check_finite(timestamp, f"frames.{expected_index}.timestamp_ms")
        if timestamp < previous_timestamp:
            raise ValueError("manual keypoint timestamps must be in source timeline order")
        previous_timestamp = timestamp
        if frame["image_name"] in image_names:
            raise ValueError("manual keypoint image_name must identify a distinct image for each frame")
        image_names.add(frame["image_name"])

        names = [joint["name"] for joint in frame["joints"]]
        if len(names) != len(JOINT_NAMES) or set(names) != set(JOINT_NAMES):
            raise ValueError(f"frame {expected_index} must contain each of the twelve joints exactly once")
        for joint in frame["joints"]:
            location = f"frame {expected_index} joint {joint['name']}"
            _check_finite(joint["confidence"], f"{location}.confidence")
            if joint["status"] == "visible":
                x, y = joint["x_px"], joint["y_px"]
                _check_finite(x, f"{location}.x_px")
                _check_finite(y, f"{location}.y_px")
                if not 0 <= x < width or not 0 <= y < height:
                    raise ValueError(f"{location} coordinates must be inside the original image bounds")
            elif joint["x_px"] is not None or joint["y_px"] is not None:
                raise ValueError(f"{location} must have null coordinates for {joint['status']}")
            if joint["status"] in {"uncertain", "not_observable"} and not joint["note"].strip():
                raise ValueError(f"{location} needs a note explaining {joint['status']}")
            if status == "reviewed" and joint["status"] == "unreviewed":
                raise ValueError(f"reviewed manual keypoints contain an unreviewed joint at {location}")

    if source_video_path is not None:
        video = Path(source_video_path)
        if video.name != payload["source_video"]["filename"]:
            raise ValueError("manual keypoints source filename does not match the video")
        if _sha256(video) != payload["source_video"]["sha256"]:
            raise ValueError("manual keypoints source SHA-256 does not match the video")


def load_manual_keypoints(
    path: str | Path, source_video_path: str | Path | None = None,
) -> dict:
    """Load a manual coordinate sidecar, validating its optional source MP4."""
    with Path(path).open(encoding="utf-8-sig") as source:
        payload = json.load(source)
    validate_manual_keypoints(payload, source_video_path=source_video_path)
    return payload
