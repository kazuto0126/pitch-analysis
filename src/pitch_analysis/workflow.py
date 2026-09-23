"""Safe, reusable preparation of one candidate pitch segment.

Preparation stops before event approval.  A prepared segment is evidence for
review, not an automatically valid reference pitch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from .clean_pose import clean_pose
from .config import QualityConfig
from .events import make_annotation_template
from .phases import build_phase_sequence
from .pipeline import build_features
from .pose_capture import extract_pose


PHASE_FEATURES = (
    "throwing_knee_angle_smoothed",
    "lead_knee_angle_smoothed",
    "shoulder_line_angle_smoothed",
    "throwing_elbow_angle_smoothed",
    "hip_line_angle_smoothed",
    "lateral_foot_separation_smoothed",
)
ACCEPTED_EVENT_STATUSES = {"human_reviewed", "provisional_candidates_accepted"}


def quality_gate(report: Mapping) -> dict:
    """Apply transparent minimum coverage checks before a human spends time labelling.

    This is intentionally a triage rule, not a claim that passing footage is a
    valid biomechanics reference. The throwing elbow threshold is lower because
    rear broadcast footage commonly occludes it, but it must still be observed
    through at least half of the segment.
    """
    timeline = report["timeline_frames"]
    if timeline <= 0:
        return {"passed": False, "feature_coverage": {}, "failures": ["empty feature timeline"]}
    detected = report["input_frames_detected"]
    usable_invalid = report["invalid_feature_frames"]
    raw_invalid = report.get("raw_invalid_feature_frames", usable_invalid)
    coverage = {name: (timeline - invalid) / timeline for name, invalid in raw_invalid.items()}
    usable_coverage = {name: (timeline - invalid) / timeline for name, invalid in usable_invalid.items()}
    coordinate_imputed = report.get("coordinate_imputed_feature_fraction", {})
    failures = []
    if detected / timeline < 0.9:
        failures.append("pose detection below 90% of segment timeline")
    if report.get("max_consecutive_missing_source_frames", 0) > 2:
        failures.append("more than 2 consecutive frames have no source pose")
    for feature in ("throwing_knee_angle", "lead_knee_angle", "shoulder_line_angle", "hip_line_angle"):
        if coverage[feature] < 0.8:
            failures.append(f"{feature} raw coverage below 80%")
        if coordinate_imputed.get(feature, 0.0) > 0.2:
            failures.append(f"{feature} coordinate interpolation exceeds 20%")
    if coverage["throwing_elbow_angle"] < 0.5:
        failures.append("throwing_elbow_angle raw coverage below 50%")
    if coordinate_imputed.get("throwing_elbow_angle", 0.0) > 0.35:
        failures.append("throwing_elbow_angle coordinate interpolation exceeds 35%")
    return {
        "passed": not failures,
        "feature_coverage": coverage,
        "usable_feature_coverage": usable_coverage,
        "coordinate_imputed_feature_fraction": coordinate_imputed,
        "detection_coverage": detected / timeline,
        "max_consecutive_missing_source_frames": report.get("max_consecutive_missing_source_frames", 0),
        "failures": failures,
    }


def prepare_segment(
    video_path: str | Path,
    output_dir: str | Path,
    *,
    video_id: str,
    throwing_side: str,
    model_path: str | Path,
    start_second: float,
    end_second: float | None,
    reference_context: Mapping[str, str] | None = None,
    quality: QualityConfig = QualityConfig(),
    subject_selection: str | None = None,
) -> dict:
    """Extract, clean and featurize one bounded delivery without overwriting review.

    The output directory must be new. This avoids replacing event annotations or
    phase sequences that a reviewer has already approved.
    """
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    raw = output / "pose_raw.csv"
    clean = output / "pose_clean.csv"
    features = output / "features.csv"
    capture = extract_pose(video_path, model_path, raw, start_second=start_second, end_second=end_second, subject_selection=subject_selection)
    if capture["detected_frames"] == 0:
        metadata = {
            "schema_version": "0.2",
            "status": "prepared_capture_failed_no_pose",
            "source_video": str(video_path),
            "segment_seconds": {"start": start_second, "end": end_second},
            "capture": capture,
            "reference_context": dict(reference_context or {}),
            "failure": "MediaPipe detected no pose; no clean/features/events artifacts were generated.",
        }
        (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return {
            "output_dir": str(output),
            "status": metadata["status"],
            "detected_frames": 0,
            "quality_gate_passed": False,
            "event_review": None,
        }
    clean_report = clean_pose(raw, clean, quality)
    feature_report = build_features(clean, features, throwing_side=throwing_side, quality=quality)
    gate = quality_gate(feature_report)
    annotation = make_annotation_template(
        video_id=video_id,
        quality_report=feature_report,
        reference_context=reference_context,
    )
    (output / "events.json").write_text(json.dumps(annotation, indent=2), encoding="utf-8")
    metadata = {
        "schema_version": "0.1",
        "status": "prepared_needs_event_review" if gate["passed"] else "prepared_quality_gate_failed",
        "source_video": str(video_path),
        "segment_seconds": {"start": start_second, "end": end_second},
        "capture": capture,
        "cleaning": clean_report,
        "feature_quality": feature_report,
        "quality_gate": gate,
        "reference_context": dict(reference_context or {}),
    }
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {"output_dir": str(output), "status": metadata["status"], "detected_frames": capture["detected_frames"], "quality_gate_passed": gate["passed"], "event_review": str(output / "events.json")}


def _read_json_if_present(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def rebuild_segment(segment_dir: str | Path, quality: QualityConfig = QualityConfig()) -> dict:
    """Rebuild derived artifacts from an existing raw capture without touching labels.

    This is the migration path after a feature-contract change.  It preserves raw
    pose files and ``events.json`` exactly, refreshes clean/features/quality
    metadata, and rebuilds phase sequences only after their existing human event
    boundaries pass validation.
    """
    segment = Path(segment_dir)
    raw, clean, features = segment / "pose_raw.csv", segment / "pose_clean.csv", segment / "features.csv"
    if not raw.exists():
        raise FileNotFoundError(f"missing raw pose capture: {raw}")
    existing = _read_json_if_present(segment / "metadata.json")
    capture = _read_json_if_present(raw.with_suffix(".capture.json"))
    events_path = segment / "events.json"
    events = _read_json_if_present(events_path)

    clean_report = clean_pose(raw, clean, quality)
    throwing_side = events.get("throws") or (existing.get("feature_quality") or {}).get("throwing_side")
    if throwing_side not in {"LEFT", "RIGHT"}:
        raise ValueError(f"{segment} has no valid throwing side in events.json or metadata.json")
    feature_report = build_features(clean, features, throwing_side=throwing_side, quality=quality)
    gate = quality_gate(feature_report)

    phase_rebuild: dict[str, object] = {"attempted": False, "rebuilt": False}
    if events.get("review_status") in ACCEPTED_EVENT_STATUSES:
        phase_rebuild["attempted"] = True
        temporary_phase = segment / "phase_sequence.rebuild.tmp.csv"
        temporary_quality = temporary_phase.with_suffix(".quality.json")
        final_phase = segment / "phase_sequence.csv"
        final_quality = final_phase.with_suffix(".quality.json")
        try:
            build_phase_sequence(features, events, temporary_phase, PHASE_FEATURES)
            temporary_phase.replace(final_phase)
            if temporary_quality.exists():
                temporary_quality.replace(final_quality)
            phase_rebuild["rebuilt"] = True
            phase_rebuild["quality_report"] = str(final_quality) if final_quality.exists() else None
        except (OSError, ValueError) as error:
            if temporary_phase.exists():
                temporary_phase.unlink()
            if temporary_quality.exists():
                temporary_quality.unlink()
            phase_rebuild["error"] = str(error)

    fps = capture.get("fps")
    derived_seconds = None
    if isinstance(fps, (int, float)) and fps > 0:
        derived_seconds = {
            "start": capture.get("start_frame", 0) / fps,
            "end": capture.get("end_frame", 0) / fps,
        }
    if not gate["passed"]:
        status = "revalidated_quality_gate_failed"
    elif events.get("review_status") in ACCEPTED_EVENT_STATUSES:
        status = "revalidated_reference_candidate"
    elif events.get("review_status") == "rejected":
        status = "revalidated_quality_passed_event_rejected"
    else:
        status = "revalidated_needs_event_review"
    metadata = {
        **existing,
        "schema_version": "0.2-quality-aware",
        "status": status,
        "source_video": existing.get("source_video", capture.get("video")),
        "segment_seconds": existing.get("segment_seconds", derived_seconds),
        "capture": capture,
        "cleaning": clean_report,
        "feature_quality": feature_report,
        "quality_gate": gate,
        "reference_context": existing.get("reference_context", events.get("reference_context", {})),
        "revalidation": {
            "method": "rebuild-derived-artifacts-from-existing-pose-raw",
            "phase_sequence": phase_rebuild,
        },
    }
    (segment / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return {
        "segment": str(segment),
        "quality_gate_passed": gate["passed"],
        "throwing_side": throwing_side,
        "phase_sequence": phase_rebuild,
        "status": metadata["status"],
    }


def rebuild_library(reference_root: str | Path, output_json: str | Path, quality: QualityConfig = QualityConfig()) -> dict:
    """Apply ``rebuild_segment`` to every existing raw-pose capture under a root."""
    root = Path(reference_root)
    results = []
    for raw in sorted(root.rglob("pose_raw.csv")):
        try:
            results.append(rebuild_segment(raw.parent, quality))
        except (OSError, ValueError) as error:
            results.append({"segment": str(raw.parent), "status": "revalidation_failed", "error": str(error)})
    report = {
        "schema_version": "revalidation-v0.2",
        "reference_root": str(root),
        "segment_count": len(results),
        "passed_quality_gate_count": sum(result.get("quality_gate_passed") is True for result in results),
        "failed_or_rejected_count": sum(result.get("quality_gate_passed") is not True for result in results),
        "results": results,
        "note": "Raw pose and event annotations were preserved. Derived clean/features/phases were rebuilt under the current quality contract.",
    }
    Path(output_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
