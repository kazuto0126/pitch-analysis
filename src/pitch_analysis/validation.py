"""Leave-one-reference-out checks for provisional pitcher identification."""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import median

from .camera import compare_camera_contexts
from .comparison import FEATURE_SCALES, compare_phase_sequences
from .normalization import fit_weighted_scalers


def _scaler_payload(references: list[dict], throws: str) -> dict:
    rows: list[dict[str, float | None]] = []
    weights: list[float] = []
    pitch_counts = {
        pitcher_id: sum(reference["pitcher_id"] == pitcher_id for reference in references)
        for pitcher_id in {reference["pitcher_id"] for reference in references}
    }
    for reference in references:
        with Path(reference["phase_sequence"]).open(encoding="utf-8-sig", newline="") as source:
            sequence_rows = list(csv.DictReader(source))
        if not sequence_rows:
            raise ValueError(f"phase sequence is empty: {reference['phase_sequence']}")
        row_weight = 1.0 / (
            pitch_counts[reference["pitcher_id"]] * len(sequence_rows)
        )
        for row in sequence_rows:
            rows.append(
                {
                    feature: float(row[feature]) if row.get(feature, "") != "" else None
                    for feature in FEATURE_SCALES
                }
            )
            weights.append(row_weight)
    scalers = fit_weighted_scalers(rows, FEATURE_SCALES, weights)
    return {
        "schema_version": "pitch-phase-loo-v0.2-balanced",
        "method": "reference-z-score-equal-pitcher-weight",
        "reference_scope": {"throws": throws},
        "scalers": {name: asdict(scaler) for name, scaler in scalers.items()},
    }


def leave_one_reference_out(
    registry_json: str | Path,
    output_json: str | Path,
    *,
    throws: str,
    camera_mode: str = "exploratory",
) -> dict:
    """Evaluate whether each held-out pitch retrieves its own pitcher first."""
    registry = json.loads(Path(registry_json).read_text(encoding="utf-8"))
    references: list[dict] = []
    for pitcher_id, entries in (registry.get("pitchers") or {}).items():
        for entry in entries:
            if entry.get("throws") == throws:
                references.append({"pitcher_id": pitcher_id, **entry})

    folds = []
    for query in references:
        training = [reference for reference in references if reference["phase_sequence"] != query["phase_sequence"]]
        expected_available = any(reference["pitcher_id"] == query["pitcher_id"] for reference in training)
        if not expected_available:
            folds.append(
                {
                    "query_video_id": query.get("video_id"),
                    "expected_pitcher_id": query["pitcher_id"],
                    "status": "not_scored",
                    "reason": "held-out pitcher has no remaining reference",
                }
            )
            continue

        scaler = _scaler_payload(training, throws)
        by_pitcher: dict[str, list[float]] = defaultdict(list)
        excluded = []
        for reference in training:
            camera = compare_camera_contexts(
                query.get("camera_context") or query.get("context"),
                reference.get("camera_context") or reference.get("context"),
                mode=camera_mode,
            )
            if not camera["compatible"]:
                excluded.append(
                    {
                        "video_id": reference.get("video_id"),
                        "pitcher_id": reference["pitcher_id"],
                        "reasons": camera["reasons"],
                    }
                )
                continue
            comparison = compare_phase_sequences(query["phase_sequence"], reference["phase_sequence"], scaler)
            distance = comparison["overall_mean_phase_distance"]
            if distance is not None:
                by_pitcher[reference["pitcher_id"]].append(distance)

        ranking = sorted(
            (
                {
                    "pitcher_id": pitcher_id,
                    "distance": median(distances),
                    "reference_count": len(distances),
                }
                for pitcher_id, distances in by_pitcher.items()
            ),
            key=lambda row: row["distance"],
        )
        expected_rank = next(
            (index + 1 for index, row in enumerate(ranking) if row["pitcher_id"] == query["pitcher_id"]),
            None,
        )
        folds.append(
            {
                "query_video_id": query.get("video_id"),
                "query_phase_sequence": query["phase_sequence"],
                "expected_pitcher_id": query["pitcher_id"],
                "status": "scored" if expected_rank is not None else "not_scored",
                "expected_rank": expected_rank,
                "top1_correct": expected_rank == 1,
                "ranking": [{"rank": index + 1, **row} for index, row in enumerate(ranking)],
                "excluded_references": excluded,
            }
        )

    scored = [fold for fold in folds if fold["status"] == "scored"]
    unscored = [fold for fold in folds if fold["status"] != "scored"]
    top1_correct = sum(bool(fold["top1_correct"]) for fold in scored)
    reciprocal_ranks = [1.0 / fold["expected_rank"] for fold in scored]
    per_pitcher = {}
    for pitcher_id in sorted({fold["expected_pitcher_id"] for fold in folds}):
        pitcher_folds = [fold for fold in folds if fold["expected_pitcher_id"] == pitcher_id]
        pitcher_scored = [fold for fold in pitcher_folds if fold["status"] == "scored"]
        pitcher_correct = sum(bool(fold["top1_correct"]) for fold in pitcher_scored)
        per_pitcher[pitcher_id] = {
            "reference_count": len(pitcher_folds),
            "scored_fold_count": len(pitcher_scored),
            "unscored_fold_count": len(pitcher_folds) - len(pitcher_scored),
            "top1_correct_count": pitcher_correct,
            "top1_accuracy": pitcher_correct / len(pitcher_scored) if pitcher_scored else None,
        }
    result = {
        "schema_version": "leave-one-reference-out-v0.1",
        "registry": str(registry_json),
        "registry_schema_version": registry.get("schema_version"),
        "throws": throws,
        "camera_compatibility_mode": camera_mode,
        "reference_count": len(references),
        "scored_fold_count": len(scored),
        "unscored_fold_count": len(unscored),
        "validation_coverage": len(scored) / len(folds) if folds else None,
        "top1_correct_count": top1_correct,
        "top1_accuracy": top1_correct / len(scored) if scored else None,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else None,
        "per_pitcher": per_pitcher,
        "folds": folds,
        "warning": (
            "Small-sample diagnostic only; each fold fits its scaler without the held-out pitch. "
            "Pitchers with only one reference are reported but cannot be scored."
        ),
    }
    Path(output_json).write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
