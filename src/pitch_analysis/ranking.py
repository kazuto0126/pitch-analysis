"""Pitcher-level ranking over every eligible reference in a registry."""
from __future__ import annotations
import json
from pathlib import Path
from statistics import median
from .camera import compare_camera_contexts
from .comparison import compare_phase_sequences
from .registry import ACCEPTED_STATUSES, discover_references


def _check_query_readiness(query_csv: str | Path) -> dict:
    quality_path = Path(query_csv).with_suffix(".quality.json")
    try:
        quality = json.loads(quality_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {
            "ready": False,
            "quality_report": str(quality_path),
            "review_status": None,
            "reasons": ["query_phase_quality_missing"],
        }
    except (OSError, json.JSONDecodeError):
        return {
            "ready": False,
            "quality_report": str(quality_path),
            "review_status": None,
            "reasons": ["query_phase_quality_invalid"],
        }
    review_status = quality.get("event_review_status")
    reasons = []
    if quality.get("schema_version") != "phase-quality-v0.1":
        reasons.append("query_phase_quality_schema_unsupported")
    if review_status not in ACCEPTED_STATUSES:
        reasons.append("query_event_review_status_not_accepted")
    return {
        "ready": not reasons,
        "quality_report": str(quality_path),
        "review_status": review_status,
        "reasons": reasons,
    }


def _load_references(reference_root: str | Path, registry_json: str | Path | None) -> tuple[dict, dict | None]:
    if registry_json:
        registry = json.loads(Path(registry_json).read_text(encoding="utf-8"))
        return registry.get("pitchers", {}), registry
    return discover_references(reference_root), None


def _load_query_context(query_context_json: str | Path | None, query_throws: str) -> dict:
    if not query_context_json:
        return {"throws": query_throws, "reference_context": {}}
    payload = json.loads(Path(query_context_json).read_text(encoding="utf-8"))
    if payload.get("throws") and payload["throws"] != query_throws:
        raise ValueError(f"Query context throws {payload['throws']}, but --query-throws is {query_throws}")
    return payload


def _check_scaler_registry(
    scaler_payload: dict,
    registry_payload: dict | None,
    registry_json: str | Path | None,
) -> dict:
    if registry_payload is None or registry_json is None:
        return {"status": "not_applicable", "warnings": []}
    provenance = scaler_payload.get("provenance") or {}
    recorded_registry = provenance.get("registry")
    if not recorded_registry:
        return {
            "status": "legacy_unverified",
            "warnings": ["scaler provenance does not identify its source registry"],
        }
    if Path(recorded_registry).resolve() != Path(registry_json).resolve():
        raise ValueError(
            f"Scaler was fitted from registry {recorded_registry}, not {registry_json}"
        )
    recorded_schema = provenance.get("registry_schema_version")
    current_schema = registry_payload.get("schema_version")
    if recorded_schema != current_schema:
        raise ValueError(
            f"Scaler registry schema is {recorded_schema}, but current registry schema is {current_schema}"
        )
    return {
        "status": "verified",
        "registry": str(registry_json),
        "registry_schema_version": current_schema,
        "warnings": [],
    }


def rank_pitchers(
    query_csv: str | Path,
    reference_root: str | Path,
    scaler_json: str | Path,
    output_json: str | Path,
    query_throws: str,
    *,
    registry_json: str | Path | None = None,
    query_context_json: str | Path | None = None,
    camera_mode: str = "exploratory",
) -> dict:
    scaler_payload = json.loads(Path(scaler_json).read_text(encoding="utf-8"))
    scaler_throws = (scaler_payload.get("reference_scope") or {}).get("throws")
    if scaler_throws and scaler_throws != query_throws:
        raise ValueError(f"Scaler is scoped to {scaler_throws}, but query throws {query_throws}")
    references_by_pitcher, registry_payload = _load_references(reference_root, registry_json)
    scaler_registry_check = _check_scaler_registry(scaler_payload, registry_payload, registry_json)
    query_readiness = _check_query_readiness(query_csv)
    query_payload = _load_query_context(query_context_json, query_throws)
    query_camera = query_payload.get("reference_context") or query_payload.get("camera_context") or {}
    rankings = []
    excluded_references = []
    for pitcher_id, references in references_by_pitcher.items():
        compatible = [reference for reference in references if reference.get("throws") == query_throws]
        if not compatible:
            continue
        distances = []
        by_season = {}
        used_references = []
        for reference in compatible:
            camera = compare_camera_contexts(query_camera, reference.get("camera_context") or reference.get("context"), mode=camera_mode)
            if not camera["compatible"]:
                excluded_references.append({
                    "pitcher_id": pitcher_id,
                    "video_id": reference.get("video_id"),
                    "phase_sequence": reference["phase_sequence"],
                    "reasons": camera["reasons"],
                })
                continue
            if not query_readiness["ready"]:
                excluded_references.append({
                    "pitcher_id": pitcher_id,
                    "video_id": reference.get("video_id"),
                    "phase_sequence": reference["phase_sequence"],
                    "reasons": query_readiness["reasons"],
                })
                continue
            comparison = compare_phase_sequences(query_csv, reference["phase_sequence"], scaler_json)
            if comparison["overall_mean_phase_distance"] is not None:
                distances.append(comparison["overall_mean_phase_distance"])
                by_season.setdefault(reference["context"]["season"], []).append(comparison["overall_mean_phase_distance"])
                used_references.append({
                    "video_id": reference.get("video_id"),
                    "phase_sequence": reference["phase_sequence"],
                    "distance": comparison["overall_mean_phase_distance"],
                    "camera_warnings": camera["warnings"],
                })
        if distances:
            rankings.append({"pitcher_id": pitcher_id, "distance": median(distances), "reference_count": len(distances), "season_contributions": {season: {"reference_count": len(values), "distance": median(values)} for season, values in by_season.items()}, "confidence": "provisional" if len(distances) < 5 else "limited", "references": used_references})
    rankings.sort(key=lambda row: row["distance"])
    result = {
        "schema_version": "0.3-provisional-camera-aware",
        "result_status": (
            "ranked"
            if rankings
            else "query_not_ready"
            if not query_readiness["ready"]
            else "no_compatible_references"
        ),
        "query_throws": query_throws,
        "query_context": query_payload,
        "ranking_method": "median of phase-aware DTW distances; references and scaler restricted to matching throwing side",
        "camera_compatibility_mode": camera_mode,
        "reference_root": str(reference_root),
        "registry": str(registry_json) if registry_json else None,
        "registry_schema_version": registry_payload.get("schema_version") if registry_payload else None,
        "scaler": str(scaler_json),
        "scaler_registry_check": scaler_registry_check,
        "query_readiness": query_readiness,
        "rankings": [{"rank": index + 1, **row} for index, row in enumerate(rankings)],
        "excluded_references": excluded_references,
        "warning": (
            "Ranking is diagnostic only until every pitcher has at least 5 reviewed, camera-compatible reference pitches."
            if rankings
            else "No ranking was issued because the query event annotation has not passed review."
            if not query_readiness["ready"]
            else "No ranking was issued because no eligible reference passed the throwing-side and camera-compatibility gates."
        ),
    }
    Path(output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
