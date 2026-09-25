"""Manual, video-bound ground truth that never modifies pose predictions.

An unreviewed template is a request for human annotation, not ground truth.
The review status and nullable labels make that distinction machine-readable.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


EVENT_NAMES = (
    "preparation_start",
    "leg_lift",
    "foot_plant",
    "approximate_release",
    "follow_through_end",
)
INTERVAL_LABELS = (
    "identity_switch_intervals",
    "major_pose_failure_intervals",
    "throwing_elbow_reliability",
    "lead_knee_reliability",
)
JOINT_LABELS = ("throwing_elbow_reliability", "lead_knee_reliability")


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(
        files("pitch_analysis.contracts")
        .joinpath("schemas", "ground-truth-v1.json")
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


def _check_intervals(name: str, intervals: list[dict], total_frames: int, *, complete: bool) -> None:
    previous_end = -1
    for index, interval in enumerate(intervals):
        start, end = interval["start_frame"], interval["end_frame"]
        if end < start or end >= total_frames:
            raise ValueError(f"{name}[{index}] is outside the video timeline")
        if start <= previous_end:
            raise ValueError(f"{name}[{index}] overlaps or is out of order")
        if complete and start != previous_end + 1:
            raise ValueError(f"{name} leaves unlabeled frames before {start}")
        if name not in JOINT_LABELS and not interval["reason"].strip():
            raise ValueError(f"{name}[{index}] needs a reason")
        if name in JOINT_LABELS and interval["status"] != "reliable" and not interval["reason"].strip():
            raise ValueError(f"{name}[{index}] needs a reason for {interval['status']}")
        previous_end = end
    if complete and previous_end != total_frames - 1:
        raise ValueError(f"{name} must cover every frame, including the final frame")


def validate_ground_truth(payload: dict, *, source_video_path: str | Path | None = None) -> None:
    """Validate shape, frame bounds, review completeness, and optional source hash.

    A reviewed annotation may explicitly mark an event or joint *uncertain*;
    uncertainty is retained rather than filled with model output.
    """
    errors = sorted(_validator().iter_errors(payload), key=lambda error: str(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "$"
        raise ValueError(f"ground-truth-v1 at {location}: {error.message}")

    status = payload["annotation_status"]
    labels = payload["labels"]
    provenance = payload["provenance"]
    total_frames = payload["source_video"]["total_frames"]

    if status == "unreviewed":
        if provenance["reviewer"] is not None or provenance["reviewed_at_utc"] is not None:
            raise ValueError("unreviewed ground truth cannot have reviewer or review time")
        if labels["pitcher_correctly_selected"] is not None or any(
            labels[name] is not None for name in INTERVAL_LABELS
        ) or any(labels["events"][name] is not None for name in EVENT_NAMES):
            raise ValueError("unreviewed ground truth cannot contain human labels")
    else:
        if not provenance["reviewer"] or not provenance["reviewer"].strip():
            raise ValueError(f"{status} ground truth requires a reviewer")
        if status == "in_progress" and provenance["reviewed_at_utc"] is not None:
            raise ValueError("in_progress ground truth cannot have a completed review time")
        if status == "reviewed":
            if provenance["reviewed_at_utc"] is None:
                raise ValueError("reviewed ground truth requires reviewed_at_utc")
            if labels["pitcher_correctly_selected"] is None:
                raise ValueError("reviewed ground truth requires pitcher_correctly_selected")
            missing = [name for name in INTERVAL_LABELS if labels[name] is None]
            missing += [name for name in EVENT_NAMES if labels["events"][name] is None]
            if missing:
                raise ValueError("reviewed ground truth has unannotated labels: " + ", ".join(missing))

    for name in INTERVAL_LABELS:
        intervals = labels[name]
        if intervals is not None:
            _check_intervals(name, intervals, total_frames, complete=status == "reviewed" and name in JOINT_LABELS)

    previous_event_frame = -1
    for name in EVENT_NAMES:
        event = labels["events"][name]
        if event is None or event["frame_index"] is None:
            if event is not None and not event["note"].strip():
                raise ValueError(f"{name} needs a note when not visible or uncertain")
            continue
        frame = event["frame_index"]
        if frame >= total_frames:
            raise ValueError(f"{name} is outside the video timeline")
        if frame < previous_event_frame:
            raise ValueError("annotated pitch events must be in timeline order")
        previous_event_frame = frame

    if source_video_path is not None:
        video = Path(source_video_path).resolve(strict=True)
        if video.name != payload["source_video"]["filename"]:
            raise ValueError("ground truth source filename does not match the video")
        if _sha256(video) != payload["source_video"]["sha256"]:
            raise ValueError("ground truth source SHA-256 does not match the video")


def blank_ground_truth(video_path: str | Path, pitch_id: str, total_frames: int) -> dict:
    """Build a blank human-review template bound to a specific MP4.

    The frame count must come from independently decoded video metadata. It is
    deliberately not inferred from pose results, which can omit frames.
    """
    video = Path(video_path).resolve(strict=True)
    if video.suffix.lower() != ".mp4":
        raise ValueError("ground truth source must be an MP4")
    if not isinstance(total_frames, int) or isinstance(total_frames, bool) or total_frames < 2:
        raise ValueError("total_frames must be an integer of at least two")
    payload = {
        "schema_version": "ground-truth-v1",
        "annotation_status": "unreviewed",
        "source_video": {
            "pitch_id": pitch_id,
            "filename": video.name,
            "sha256": _sha256(video),
            "total_frames": total_frames,
            "frame_index_base": 0,
        },
        "provenance": {
            "reviewer": None,
            "reviewed_at_utc": None,
            "method": "manual_video_review",
            "guidelines_version": "ground-truth-guidelines-v1",
        },
        "labels": {
            "pitcher_correctly_selected": None,
            "identity_switch_intervals": None,
            "major_pose_failure_intervals": None,
            "throwing_elbow_reliability": None,
            "lead_knee_reliability": None,
            "events": {name: None for name in EVENT_NAMES},
        },
        "notes": [],
    }
    validate_ground_truth(payload)
    return payload


def create_blank_ground_truth(
    video_path: str | Path,
    pitch_id: str,
    total_frames: int,
    ground_truth_root: str | Path,
) -> Path:
    """Create `<ground_truth_root>/<pitch_id>/ground_truth.json` exactly once.

    Existing human annotations are never replaced, even by another template.
    Keep ``ground_truth_root`` outside model prediction directories.
    """
    payload = blank_ground_truth(video_path, pitch_id, total_frames)
    output = Path(ground_truth_root) / pitch_id / "ground_truth.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as target:
        json.dump(payload, target, indent=2, ensure_ascii=False, allow_nan=False)
        target.write("\n")
    return output


def load_ground_truth(path: str | Path, *, source_video_path: str | Path | None = None) -> dict:
    """Load and validate an annotation, optionally checking the actual MP4."""
    with Path(path).open(encoding="utf-8-sig") as source:
        payload = json.load(source)
    validate_ground_truth(payload, source_video_path=source_video_path)
    return payload
