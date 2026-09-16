"""Human-reviewable pitch event annotations and phase boundaries."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Mapping


EVENTS = ("pitch_start", "peak_leg_lift", "foot_strike", "release", "follow_through_end")


def make_annotation_template(*, video_id: str, quality_report: Mapping, event_candidates: Mapping[str, int] | None = None, reference_context: Mapping | None = None) -> dict:
    proxy = quality_report.get("motion_window_proxy") or {}
    motion_candidates = quality_report.get("motion_candidates") or {}
    return {
        "schema_version": "1.0",
        "video_id": video_id,
        "throws": quality_report.get("throwing_side"),
        "reference_context": dict(reference_context or {}),
        "review_status": "needs_human_review",
        "annotation": {
            "source": "human_review_required",
            "confidence": None,
            "notes": None,
        },
        "events": {name: None for name in EVENTS},
        "automatic_candidates": {
            "motion_start_proxy": proxy.get("start_frame"),
            "peak_lateral_foot_separation_proxy": proxy.get("peak_separation_frame"),
            "motion_end_proxy": proxy.get("end_frame"),
            **(dict(event_candidates) if event_candidates else {}),
        },
        "automatic_motion_windows": list(motion_candidates.get("candidates") or []),
        "notes": "Fill event frames after reviewing the video. Proxy values are not biomechanical labels.",
    }


def validate_events(
    annotation: Mapping,
    *,
    frame_range: tuple[int, int] | None = None,
    min_phase_frames: int = 2,
) -> dict[str, int]:
    """Validate label type, strict ordering, and optional feature-timeline bounds."""
    if min_phase_frames < 2:
        raise ValueError("min_phase_frames must be at least two")
    events = annotation.get("events", {})
    result = {name: events.get(name) for name in EVENTS}
    if any(type(frame) is not int for frame in result.values()):
        raise ValueError("all event frames must be integer values before phase alignment")
    values = list(result.values())
    if any(right - left < min_phase_frames - 1 for left, right in zip(values, values[1:])):
        raise ValueError("each adjacent event pair must span at least two source frames")
    if frame_range is not None:
        first, last = frame_range
        if last < first:
            raise ValueError("event frame range is invalid")
        if any(frame < first or frame > last for frame in values):
            raise ValueError(f"event frames must fall inside feature timeline [{first}, {last}]")
    return result


def write_template(report_path: str | Path, output_path: str | Path, video_id: str, event_candidates: Mapping[str, int] | None = None, reference_context: Mapping | None = None) -> dict:
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    template = make_annotation_template(video_id=video_id, quality_report=report, event_candidates=event_candidates, reference_context=reference_context)
    Path(output_path).write_text(json.dumps(template, indent=2), encoding="utf-8")
    return template
