"""Diagnostic phase-aware comparison before a multi-pitch reference scaler exists."""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from .alignment import constrained_dtw

FEATURE_SCALES = {"throwing_knee_angle_smoothed": 180.0, "lead_knee_angle_smoothed": 180.0, "shoulder_line_angle_smoothed": 90.0, "throwing_elbow_angle_smoothed": 180.0, "hip_line_angle_smoothed": 90.0}
FEATURE_WEIGHTS = {"throwing_knee_angle_smoothed": 1.0, "lead_knee_angle_smoothed": 1.0, "shoulder_line_angle_smoothed": 0.6, "throwing_elbow_angle_smoothed": 0.3, "hip_line_angle_smoothed": 0.6}
LINE_ORIENTATION_FEATURES = frozenset({"shoulder_line_angle_smoothed", "hip_line_angle_smoothed"})
CIRCULAR_FEATURE_SCALES = {name: FEATURE_SCALES[name] for name in LINE_ORIENTATION_FEATURES}
MIN_PHASE_COVERAGE = {
    "throwing_knee_angle_smoothed": 0.6,
    "lead_knee_angle_smoothed": 0.6,
    "shoulder_line_angle_smoothed": 0.6,
    "throwing_elbow_angle_smoothed": 0.35,
    "hip_line_angle_smoothed": 0.6,
}
MIN_SHARED_FEATURES = 3
EXPECTED_PHASES = ("windup", "stride", "arm_acceleration", "follow_through")
MIN_SCORED_PHASES = 3
REQUIRED_SCORED_PHASES = frozenset({"stride", "arm_acceleration"})


def _load(path: str | Path, scalers: dict | None = None) -> dict[str, list[dict[str, float | None]]]:
    phases: dict[str, list[dict[str, float | None]]] = defaultdict(list)
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            values = {}
            for feature, scale in FEATURE_SCALES.items():
                if row.get(feature, "") == "":
                    values[feature] = None
                elif feature in LINE_ORIENTATION_FEATURES:
                    # The phase CSV stores real angles.  Keep them in degrees so
                    # alignment can use the shortest 180-degree orientation path.
                    values[feature] = float(row[feature])
                elif scalers:
                    config = scalers[feature]
                    values[feature] = (float(row[feature]) - config["mean"]) / config["standard_deviation"]
                else:
                    values[feature] = float(row[feature]) / scale
            phases[row["phase"]].append(values)
    return dict(phases)


def _coverage(rows: list[dict[str, float | None]]) -> dict[str, float]:
    return {
        feature: sum(row[feature] is not None for row in rows) / len(rows)
        for feature in FEATURE_SCALES
    }


def _load_phase_quality(path: str | Path) -> dict | None:
    quality_path = Path(path).with_suffix(".quality.json")
    if not quality_path.exists():
        return None
    try:
        payload = json.loads(quality_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != "phase-quality-v0.1":
        return None
    return payload


def _phase_coverage(
    rows: list[dict[str, float | None]],
    quality: Mapping | None,
    phase: str,
) -> tuple[dict[str, float], dict[str, str]]:
    """Prefer source-frame raw coverage over resampled non-missing values.

    The phase CSV contains smoothed/resampled values and can therefore look
    complete even when a landmark was not observed.  Legacy sequences without
    a valid quality sidecar retain an explicit CSV fallback.
    """
    csv_coverage = _coverage(rows)
    phase_report = ((quality or {}).get("phases") or {}).get(phase) or {}
    raw_coverage = phase_report.get("raw_feature_coverage") or {}
    coverage: dict[str, float] = {}
    sources: dict[str, str] = {}
    for feature in FEATURE_SCALES:
        raw_value = raw_coverage.get(feature)
        if isinstance(raw_value, (int, float)) and 0.0 <= float(raw_value) <= 1.0:
            coverage[feature] = float(raw_value)
            sources[feature] = "phase_quality_raw_feature_coverage"
        else:
            coverage[feature] = csv_coverage[feature]
            sources[feature] = "resampled_csv_non_missing_fallback"
    return coverage, sources


def _phase_eligibility(
    query_coverage: dict[str, float],
    reference_coverage: dict[str, float],
) -> tuple[bool, list[str], list[str], list[str]]:
    coverage_notes = []
    shared = []
    for feature, minimum in MIN_PHASE_COVERAGE.items():
        query_value, reference_value = query_coverage[feature], reference_coverage[feature]
        if query_value >= minimum and reference_value >= minimum:
            shared.append(feature)
        else:
            if query_value < minimum:
                coverage_notes.append(f"query {feature} coverage below {minimum:.0%}")
            if reference_value < minimum:
                coverage_notes.append(f"reference {feature} coverage below {minimum:.0%}")
    failures = []
    if len(shared) < MIN_SHARED_FEATURES:
        failures.append(f"fewer than {MIN_SHARED_FEATURES} key features meet coverage in both sequences")
    return not failures, failures, shared, coverage_notes


def compare_phase_sequences(
    query_csv: str | Path,
    reference_csv: str | Path,
    scaler_json: str | Path | Mapping | None = None,
) -> dict:
    scaler_payload = (
        dict(scaler_json)
        if isinstance(scaler_json, Mapping)
        else json.loads(Path(scaler_json).read_text(encoding="utf-8"))
        if scaler_json
        else None
    )
    scalers = scaler_payload["scalers"] if scaler_payload else None
    query, reference = _load(query_csv, scalers), _load(reference_csv, scalers)
    query_quality = _load_phase_quality(query_csv)
    reference_quality = _load_phase_quality(reference_csv)
    result, scores = {}, []
    for phase in EXPECTED_PHASES:
        if phase not in query or phase not in reference:
            result[phase] = {"distance": None, "reason": "phase missing"}
            continue
        query_coverage, query_coverage_source = _phase_coverage(
            query[phase], query_quality, phase
        )
        reference_coverage, reference_coverage_source = _phase_coverage(
            reference[phase], reference_quality, phase
        )
        eligible, failures, shared, coverage_notes = _phase_eligibility(query_coverage, reference_coverage)
        phase_weights = {feature: FEATURE_WEIGHTS[feature] for feature in shared}
        phase_circular_scales = {
            feature: CIRCULAR_FEATURE_SCALES[feature]
            for feature in shared
            if feature in CIRCULAR_FEATURE_SCALES
        }
        distance = (
            constrained_dtw(
                query[phase],
                reference[phase],
                phase_weights,
                min_shared_features=MIN_SHARED_FEATURES,
                circular_feature_scales=phase_circular_scales,
            )
            if eligible
            else None
        )
        result[phase] = {
            "distance": distance[0] if distance else None,
            "path_length": distance[1] if distance else 0,
            "query_coverage": {name: round(value, 3) for name, value in query_coverage.items()},
            "reference_coverage": {name: round(value, 3) for name, value in reference_coverage.items()},
            "query_coverage_source": query_coverage_source,
            "reference_coverage_source": reference_coverage_source,
            "shared_key_features": shared,
            "excluded_low_coverage_features": [feature for feature in FEATURE_SCALES if feature not in shared],
            "coverage_notes": coverage_notes,
            "eligibility_failures": failures,
            "reason": None if distance else ("alignment unavailable after coverage gate" if eligible else "coverage gate failed"),
        }
        if distance:
            scores.append(distance[0])
    scored_phases = [
        phase for phase in EXPECTED_PHASES if result.get(phase, {}).get("distance") is not None
    ]
    overall_failures = []
    if len(scored_phases) < MIN_SCORED_PHASES:
        overall_failures.append(
            f"fewer than {MIN_SCORED_PHASES} phases produced valid distances"
        )
    missing_required = sorted(REQUIRED_SCORED_PHASES.difference(scored_phases))
    if missing_required:
        overall_failures.append(
            "required phases unavailable: " + ", ".join(missing_required)
        )
    overall_distance = sum(scores) / len(scores) if scores and not overall_failures else None
    return {
        "schema_version": "0.4-raw-phase-quality-aware",
        "normalization": "reference-z-score for joint angles; fixed circular scale for shoulder/hip line orientation" if scalers else "fixed feature ranges; no per-video Min-Max",
        "excluded_features": ["lateral_foot_separation_smoothed"],
        "circular_line_orientation": "shoulder/hip use a 180-degree wrap-aware difference, so +89 and -89 degrees are close",
        "minimum_shared_features": MIN_SHARED_FEATURES,
        "minimum_scored_phases": MIN_SCORED_PHASES,
        "required_scored_phases": sorted(REQUIRED_SCORED_PHASES),
        "scored_phase_count": len(scored_phases),
        "scored_phases": scored_phases,
        "overall_eligibility_failures": overall_failures,
        "overall_mean_phase_distance": overall_distance,
        "phases": result,
        "warning": "Diagnostic comparison only; phase feature eligibility uses raw source-frame coverage when a valid phase-quality sidecar is available.",
    }


def write_comparison(query_csv: str | Path, reference_csv: str | Path, output_json: str | Path, scaler_json: str | Path | None = None) -> dict:
    result = compare_phase_sequences(query_csv, reference_csv, scaler_json)
    Path(output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
