"""Discover only auditable pitch references and build a reproducible registry.

The registry is deliberately stricter than the event-review UI. A sequence is
eligible for comparison only when its event review, capture metadata, quality
gate, and phase CSV can all be checked together. Older artefacts are retained
on disk; they are reported as requiring revalidation instead of being silently
included in rankings.
"""
from __future__ import annotations

import csv
import json
import math
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from .camera import camera_context


ACCEPTED_STATUSES = {"human_reviewed", "provisional_candidates_accepted"}
EXPECTED_PHASES = ("windup", "stride", "arm_acceleration", "follow_through")
EXPECTED_FEATURE_COLUMNS = (
    "throwing_knee_angle_smoothed",
    "lead_knee_angle_smoothed",
    "shoulder_line_angle_smoothed",
    "throwing_elbow_angle_smoothed",
    "hip_line_angle_smoothed",
    "lateral_foot_separation_smoothed",
)
EXPECTED_PHASE_COLUMNS = (
    "phase",
    "phase_index",
    "source_frame_float",
    *EXPECTED_FEATURE_COLUMNS,
)
EVENT_NAMES = ("pitch_start", "peak_leg_lift", "foot_strike", "release", "follow_through_end")


def _context(events: dict, relative: Path) -> dict:
    explicit = events.get("reference_context") or {}
    collection = relative.parts[1] if len(relative.parts) > 1 else "unknown"
    inferred_season = collection[:4] if len(collection) >= 4 and collection[:4].isdigit() else "unknown"
    context = {
        "season": explicit.get("season", inferred_season),
        "team": explicit.get("team", "unknown"),
        "view": explicit.get("view", "unknown"),
        "collection": collection,
    }
    for field in ("horizontal_mirror", "subject_framing"):
        if field in explicit:
            context[field] = explicit[field]
    return context


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _has_valid_capture_range(capture: Mapping | None) -> bool:
    return bool(
        isinstance(capture, Mapping)
        and _is_int(capture.get("start_frame"))
        and _is_int(capture.get("end_frame"))
        and capture["end_frame"] >= capture["start_frame"]
    )


def _read_json(path: Path) -> tuple[dict | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "missing"
    except (OSError, json.JSONDecodeError):
        return None, "invalid"
    if not isinstance(value, dict):
        return None, "invalid"
    return value, None


def _validate_events(events: Mapping, capture: Mapping) -> list[str]:
    reasons: list[str] = []
    if events.get("review_status") not in ACCEPTED_STATUSES:
        reasons.append("event_review_status_not_accepted")
    if events.get("throws") not in {"LEFT", "RIGHT"}:
        reasons.append("event_throwing_side_missing_or_invalid")

    annotation = events.get("events")
    if not isinstance(annotation, Mapping):
        return [*reasons, "events_missing_or_invalid"]
    values = [annotation.get(name) for name in EVENT_NAMES]
    if not all(_is_int(value) for value in values):
        return [*reasons, "events_must_contain_all_integer_boundaries"]
    if any(left >= right for left, right in zip(values, values[1:])):
        return [*reasons, "event_boundaries_not_strictly_chronological"]

    start, end = capture["start_frame"], capture["end_frame"]
    if values[0] < start or values[-1] > end:
        reasons.append("event_boundaries_outside_capture_range")
    return reasons


def _validate_capture(metadata: Mapping) -> tuple[Mapping | None, list[str]]:
    capture = metadata.get("capture")
    if not isinstance(capture, Mapping):
        return None, ["capture_metadata_missing_or_invalid"]

    reasons: list[str] = []
    start, end = capture.get("start_frame"), capture.get("end_frame")
    requested, detected = capture.get("requested_frames"), capture.get("detected_frames")
    if not _is_int(start) or not _is_int(end) or end < start:
        reasons.append("capture_frame_range_missing_or_invalid")
    if not _is_int(requested) or not _is_int(detected):
        reasons.append("capture_frame_counts_missing_or_invalid")
    elif _is_int(start) and _is_int(end):
        expected = end - start + 1
        if requested != expected:
            reasons.append("capture_requested_frame_count_does_not_match_range")
        if not 0 < detected <= requested:
            reasons.append("capture_detected_frame_count_out_of_range")

    # Width, height and FPS make the capture contract inspectable. A blank or
    # non-positive value means normalized coordinates cannot be interpreted
    # reliably across videos.
    for field in ("width", "height", "fps"):
        value = capture.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            reasons.append(f"capture_{field}_missing_or_invalid")
    if not isinstance(capture.get("video"), str) or not capture["video"].strip():
        reasons.append("capture_video_missing_or_invalid")
    return capture, reasons


def _validate_phase_sequence(path: Path, capture: Mapping) -> list[str]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            fields = reader.fieldnames or []
            missing = [name for name in EXPECTED_PHASE_COLUMNS if name not in fields]
            if missing:
                return ["phase_schema_missing_required_columns:" + ",".join(missing)]
            rows = list(reader)
    except (OSError, csv.Error, UnicodeError):
        return ["phase_sequence_unreadable"]

    if not rows:
        return ["phase_sequence_empty"]

    phase_rows: dict[str, int] = {name: 0 for name in EXPECTED_PHASES}
    start, end = capture["start_frame"], capture["end_frame"]
    reasons: list[str] = []
    for row in rows:
        phase = row.get("phase")
        if phase not in phase_rows:
            reasons.append("phase_schema_contains_unknown_phase")
            break
        phase_rows[phase] += 1
        try:
            phase_index = float(row.get("phase_index", ""))
            source_frame = float(row.get("source_frame_float", ""))
        except (TypeError, ValueError):
            reasons.append("phase_schema_contains_invalid_index_or_frame")
            break
        if not math.isfinite(phase_index) or not math.isfinite(source_frame):
            reasons.append("phase_schema_contains_invalid_index_or_frame")
            break
        if source_frame < start or source_frame > end:
            reasons.append("phase_source_frame_outside_capture_range")
            break
    if not reasons and any(count < 2 for count in phase_rows.values()):
        reasons.append("phase_schema_requires_at_least_two_rows_per_phase")
    return reasons


def _validate_phase_quality(quality: Mapping, events: Mapping) -> list[str]:
    reasons: list[str] = []
    if quality.get("schema_version") != "phase-quality-v0.1":
        reasons.append("phase_quality_schema_missing_or_unsupported")
    event_values = events.get("events") if isinstance(events.get("events"), Mapping) else {}
    expected_range = [event_values.get("pitch_start"), event_values.get("follow_through_end")]
    if quality.get("event_frame_range") != expected_range:
        reasons.append("phase_quality_event_range_mismatch")
    phases = quality.get("phases")
    if not isinstance(phases, Mapping):
        reasons.append("phase_quality_phases_missing_or_invalid")
        return reasons
    for phase in EXPECTED_PHASES:
        phase_report = phases.get(phase)
        if not isinstance(phase_report, Mapping):
            reasons.append(f"phase_quality_missing_phase:{phase}")
            continue
        if not isinstance(phase_report.get("source_frames"), int) or phase_report["source_frames"] < 2:
            reasons.append(f"phase_quality_insufficient_source_frames:{phase}")
        coverage = phase_report.get("feature_coverage")
        if not isinstance(coverage, Mapping):
            reasons.append(f"phase_quality_feature_coverage_missing:{phase}")
            continue
        if any(feature not in coverage for feature in EXPECTED_FEATURE_COLUMNS):
            reasons.append(f"phase_quality_feature_coverage_incomplete:{phase}")
    return reasons


def _event_window_quality_gate(quality: Mapping | None) -> dict:
    window = quality.get("event_window") if isinstance(quality, Mapping) else None
    if not isinstance(window, Mapping):
        return {"passed": False, "failures": ["event_window_quality_missing"]}
    failures: list[str] = []
    detection = window.get("source_detection_coverage")
    max_missing = window.get("max_consecutive_missing_source_frames")
    if not isinstance(detection, (int, float)) or detection < 0.9:
        failures.append("event-window pose detection below 90%")
    if not isinstance(max_missing, int) or max_missing > 2:
        failures.append("event-window has more than 2 consecutive missing source frames")
    raw = window.get("raw_feature_coverage")
    if not isinstance(raw, Mapping):
        return {"passed": False, "failures": [*failures, "event-window raw feature coverage missing"]}
    for feature in (
        "throwing_knee_angle_smoothed",
        "lead_knee_angle_smoothed",
        "shoulder_line_angle_smoothed",
        "hip_line_angle_smoothed",
    ):
        value = raw.get(feature)
        if not isinstance(value, (int, float)) or value < 0.8:
            failures.append(f"{feature} event-window raw coverage below 80%")
    elbow = raw.get("throwing_elbow_angle_smoothed")
    if not isinstance(elbow, (int, float)) or elbow < 0.5:
        failures.append("throwing_elbow_angle_smoothed event-window raw coverage below 50%")
    return {"passed": not failures, "failures": failures}


def validate_reference(sequence: str | Path) -> dict:
    """Return a non-mutating eligibility audit for one phase sequence.

    ``reasons`` are stable machine-readable codes so callers can keep a clear
    revalidation queue. This function never edits a candidate's artefacts.
    """
    sequence = Path(sequence)
    events_path = sequence.with_name("events.json")
    metadata_path = sequence.with_name("metadata.json")
    phase_quality_path = sequence.with_suffix(".quality.json")
    input_quality_path = sequence.with_name("input_quality.json")
    events, events_error = _read_json(events_path)
    metadata, metadata_error = _read_json(metadata_path)
    phase_quality, phase_quality_error = _read_json(phase_quality_path)
    input_quality, input_quality_error = _read_json(input_quality_path)
    reasons: list[str] = []

    # Legacy references have no input-quality report. New analyses must not
    # enter the registry when their input remains degraded or rejected.
    if input_quality_error and input_quality_error != "missing":
        reasons.append("input_quality_json_invalid")
    elif input_quality is not None and (input_quality.get("schema_version") != "input-quality-v1"
                                        or input_quality.get("stage") != "post_pose"
                                        or input_quality.get("status") != "accepted"):
        reasons.append("input_quality_not_accepted")

    if events_error:
        reasons.append(f"events_json_{events_error}")
    if metadata_error == "missing":
        reasons.append("metadata_missing_requires_revalidation")
    elif metadata_error:
        reasons.append("metadata_json_invalid_requires_revalidation")
    if phase_quality_error == "missing":
        reasons.append("phase_quality_missing_requires_revalidation")
    elif phase_quality_error:
        reasons.append("phase_quality_json_invalid_requires_revalidation")

    capture: Mapping | None = None
    quality_basis: str | None = None
    if metadata is not None:
        gate = metadata.get("quality_gate")
        event_gate = _event_window_quality_gate(phase_quality)
        if isinstance(gate, Mapping) and gate.get("passed") is True:
            quality_basis = "segment_quality_gate"
        elif event_gate["passed"]:
            quality_basis = "reviewed_event_window_quality_gate"
        else:
            reasons.append("quality_gate_not_passed")
        capture, capture_reasons = _validate_capture(metadata)
        reasons.extend(capture_reasons)

    if events is not None and _has_valid_capture_range(capture):
        reasons.extend(_validate_events(events, capture))
    elif events is not None:
        # Status can still be reported even when a legacy entry lacks capture
        # evidence, but no phase/capture validation is possible.
        if events.get("review_status") not in ACCEPTED_STATUSES:
            reasons.append("event_review_status_not_accepted")
        if events.get("throws") not in {"LEFT", "RIGHT"}:
            reasons.append("event_throwing_side_missing_or_invalid")

    if _has_valid_capture_range(capture):
        reasons.extend(_validate_phase_sequence(sequence, capture))
    if phase_quality is not None and events is not None:
        reasons.extend(_validate_phase_quality(phase_quality, events))

    # Keep ordering deterministic while avoiding duplicate reasons caused by a
    # malformed entry satisfying several failed checks.
    reasons = list(dict.fromkeys(reasons))
    return {
        "accepted": not reasons,
        "phase_sequence": str(sequence),
        "events_path": str(events_path),
        "metadata_path": str(metadata_path),
        "phase_quality_path": str(phase_quality_path),
        "events": events,
        "metadata": metadata,
        "quality_basis": quality_basis,
        "reasons": reasons,
    }


def audit_references(root: str | Path) -> tuple[dict[str, list[dict]], list[dict]]:
    """Discover eligible sequences and separately retain an exclusion audit."""
    root = Path(root)
    grouped: dict[str, list[dict]] = defaultdict(list)
    exclusions: list[dict] = []
    for sequence in sorted(root.rglob("phase_sequence.csv")):
        try:
            relative = sequence.relative_to(root)
            pitcher_id = relative.parts[0]
        except (ValueError, IndexError):
            # This should not occur for an rglob result, but retain evidence if
            # a caller passes an unusual path implementation.
            exclusions.append({
                "phase_sequence": str(sequence),
                "relative_path": str(sequence),
                "pitcher_id": "unknown",
                "reasons": ["phase_sequence_outside_reference_root"],
                "action": "requires_revalidation",
            })
            continue

        audit = validate_reference(sequence)
        if not audit["accepted"]:
            exclusions.append({
                "phase_sequence": str(sequence),
                "relative_path": str(relative),
                "pitcher_id": pitcher_id,
                "reasons": audit["reasons"],
                "action": "requires_revalidation" if any("revalidation" in reason for reason in audit["reasons"]) else "not_eligible",
            })
            continue

        events = audit["events"]
        metadata = audit["metadata"]
        assert events is not None and metadata is not None  # implied by acceptance
        grouped[pitcher_id].append({
            "phase_sequence": str(sequence),
            "video_id": events.get("video_id"),
            "throws": events.get("throws"),
            "review_status": events.get("review_status"),
                "context": _context(events, relative),
                "camera_context": camera_context(_context(events, relative)),
                "validation": {
                "quality_gate": audit.get("quality_basis") or "passed",
                "capture_range": [metadata["capture"]["start_frame"], metadata["capture"]["end_frame"]],
                "phase_schema": "validated",
                "phase_quality_schema": "validated",
            },
        })
    return dict(grouped), exclusions


def discover_references(root: str | Path) -> dict[str, list[dict]]:
    """Return only current, independently auditable reference sequences.

    The return type matches the original public API. Use ``audit_references``
    or ``write_registry`` when the exclusion/revalidation queue is needed.
    """
    return audit_references(root)[0]


def write_registry(root: str | Path, output_json: str | Path) -> dict:
    pitchers, exclusions = audit_references(root)
    season_counts = {
        pitcher: dict(Counter(entry["context"]["season"] for entry in sequences))
        for pitcher, sequences in pitchers.items()
    }
    warnings = {
        pitcher: "below recommended 5 reference pitches"
        for pitcher, sequences in pitchers.items()
        if len(sequences) < 5
    }
    revalidation_warnings = [
        exclusion for exclusion in exclusions
        if exclusion["action"] == "requires_revalidation"
    ]
    registry = {
        "schema_version": "0.5-reviewed-event-window-provisional",
        "reference_root": str(root),
        "pitchers": pitchers,
        "season_counts": season_counts,
        "accepted_reference_count": sum(len(sequences) for sequences in pitchers.values()),
        "excluded_reference_count": len(exclusions),
        "warnings": warnings,
        "exclusions": exclusions,
        "revalidation_warnings": revalidation_warnings,
        "eligibility_policy": {
            "accepted_event_statuses": sorted(ACCEPTED_STATUSES),
            "requires": [
                "passed segment quality gate, or passed reviewed event-window quality gate",
                "complete capture metadata and in-range event boundaries",
                "expected phase sequence schema",
                "event-window phase quality sidecar matching reviewed boundaries",
            ],
            "legacy_behavior": "missing metadata is excluded and retained for revalidation; no artefacts are deleted",
        },
    }
    Path(output_json).write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return registry
