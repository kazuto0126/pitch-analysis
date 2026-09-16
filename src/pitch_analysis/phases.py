"""Phase-aware resampling after human event review."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import Sequence
from .events import EVENTS, validate_events
from .io import write_rows
from .temporal import LINE_ORIENTATION_FEATURES, line_angle_delta, wrap_line_angle


def _interpolate(values: Sequence[float | None], position: float) -> float | None:
    left = int(position)
    right = min(left + 1, len(values) - 1)
    a, b = values[left], values[right]
    if a is None or b is None:
        return None
    return a + (position - left) * (b - a)


def _interpolate_line_orientation(
    values: Sequence[float | None], position: float
) -> float | None:
    """Interpolate an unoriented line on its shortest 180-degree path."""
    left = int(position)
    right = min(left + 1, len(values) - 1)
    a, b = values[left], values[right]
    if a is None or b is None:
        return None
    return wrap_line_angle(a + (position - left) * line_angle_delta(a, b))


def _is_line_orientation_feature(feature: str) -> bool:
    return feature.removesuffix("_smoothed") in LINE_ORIENTATION_FEATURES


def resample_phase(rows: Sequence[dict], features: Sequence[str], start: int, end: int, points: int) -> list[dict]:
    selected = [row for row in rows if start <= int(row["frame"]) <= end]
    if len(selected) < 2 or points < 2:
        raise ValueError("each phase needs at least two source frames and two target points")
    output = []
    source = {feature: [float(row[feature]) if row.get(feature, "") != "" else None for row in selected] for feature in features}
    for index in range(points):
        position = index * (len(selected) - 1) / (points - 1)
        output.append(
            {
                "phase_index": index,
                "source_frame_float": start
                + position * (end - start) / (len(selected) - 1),
                **{
                    feature: (
                        _interpolate_line_orientation(source[feature], position)
                        if _is_line_orientation_feature(feature)
                        else _interpolate(source[feature], position)
                    )
                    for feature in features
                },
            }
        )
    return output


def _is_true(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _coverage_report(rows: Sequence[dict], features: Sequence[str]) -> dict:
    if not rows:
        return {"source_frames": 0, "feature_coverage": {}, "raw_feature_coverage": {}}
    usable = {
        feature: sum(row.get(feature, "") != "" for row in rows) / len(rows)
        for feature in features
    }
    raw = {}
    for feature in features:
        base = feature.removesuffix("_smoothed")
        raw_column = f"{base}_raw_observed"
        if any(raw_column in row for row in rows):
            raw[feature] = sum(_is_true(row.get(raw_column)) for row in rows) / len(rows)
    detection_values = [
        _is_true(row.get("source_frame_detected"))
        for row in rows
        if "source_frame_detected" in row
    ]
    max_missing = current_missing = 0
    for detected in detection_values:
        if detected:
            current_missing = 0
        else:
            current_missing += 1
            max_missing = max(max_missing, current_missing)
    return {
        "source_frames": len(rows),
        "source_detection_coverage": (
            sum(detection_values) / len(detection_values) if detection_values else None
        ),
        "max_consecutive_missing_source_frames": max_missing if detection_values else None,
        "feature_coverage": usable,
        "raw_feature_coverage": raw,
    }


def build_phase_sequence(
    features_csv: str | Path,
    annotation: dict,
    output_csv: str | Path,
    features: Sequence[str],
    points_per_phase: int = 25,
) -> dict:
    with Path(features_csv).open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError("features CSV contains no rows")
    timeline = (min(int(row["frame"]) for row in rows), max(int(row["frame"]) for row in rows))
    events = validate_events(annotation, frame_range=timeline)
    output = []
    phase_quality = {}
    for phase, start_name, end_name in zip(("windup", "stride", "arm_acceleration", "follow_through"), EVENTS, EVENTS[1:]):
        start, end = events[start_name], events[end_name]
        source_rows = [row for row in rows if start <= int(row["frame"]) <= end]
        phase_quality[phase] = {
            "frame_range": [start, end],
            **_coverage_report(source_rows, features),
        }
        for row in resample_phase(rows, features, start, end, points_per_phase):
            output.append({"phase": phase, **row})
    write_rows(output_csv, ("phase", "phase_index", "source_frame_float", *features), output)
    event_rows = [
        row
        for row in rows
        if events["pitch_start"] <= int(row["frame"]) <= events["follow_through_end"]
    ]
    report = {
        "schema_version": "phase-quality-v0.1",
        "source_features_csv": str(features_csv),
        "source_video_id": annotation.get("video_id"),
        "event_review_status": annotation.get("review_status"),
        "event_frame_range": [events["pitch_start"], events["follow_through_end"]],
        "event_window": _coverage_report(event_rows, features),
        "phases": phase_quality,
        "points_per_phase": points_per_phase,
        "note": "Event-window coverage, not full-video coverage, describes the frames used for comparison.",
    }
    Path(output_csv).with_suffix(".quality.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    return report
