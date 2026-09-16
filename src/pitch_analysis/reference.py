"""Build versioned, reference-only scalers from phase sequences."""
from __future__ import annotations
import csv
import json
from pathlib import Path
from collections import Counter
from typing import Mapping
from .comparison import FEATURE_SCALES
from .normalization import fit_scalers, fit_weighted_scalers, save_scalers


def fit_reference_scaler(
    phase_csvs: list[str | Path],
    output_json: str | Path,
    *,
    throws: str,
    provenance_context: Mapping | None = None,
) -> dict:
    rows = []
    sequence_summaries = []
    for path in phase_csvs:
        path = Path(path)
        row_count = 0
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                rows.append({feature: float(row[feature]) if row.get(feature, "") != "" else None for feature in FEATURE_SCALES})
                row_count += 1
        sequence_summaries.append({"phase_sequence": str(path), "row_count": row_count})
    scalers = fit_scalers(rows, FEATURE_SCALES)
    provenance = {
        "reference_sequences": sequence_summaries,
        "reference_sequence_count": len(sequence_summaries),
        "reference_rows": len(rows),
        "warning": "Rows are phase-resampled. Use a balanced reference set by throwing side and camera protocol before treating scores as production-quality.",
        **dict(provenance_context or {}),
    }
    save_scalers(output_json, scalers, schema_version="pitch-phase-v0.3-provisional", reference_scope={"throws": throws}, provenance=provenance)
    return {"reference_sequences": len(phase_csvs), "reference_rows": len(rows), "throws": throws, "output": str(output_json)}


def fit_registry_scaler(
    registry_json: str | Path,
    output_json: str | Path,
    *,
    throws: str,
) -> dict:
    """Fit a scaler from only the registry entries eligible for one throwing side."""
    registry_path = Path(registry_json)
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    selected = [
        (pitcher_id, entry)
        for pitcher_id, entries in (registry.get("pitchers") or {}).items()
        for entry in entries
        if entry.get("throws") == throws
    ]
    if not selected:
        raise ValueError(f"registry contains no eligible {throws} reference sequences")
    pitch_counts = Counter(pitcher_id for pitcher_id, _ in selected)
    rows = []
    weights = []
    sequence_summaries = []
    for pitcher_id, entry in selected:
        path = Path(entry["phase_sequence"])
        with path.open(encoding="utf-8-sig", newline="") as source:
            sequence_rows = list(csv.DictReader(source))
        if not sequence_rows:
            raise ValueError(f"phase sequence is empty: {path}")
        row_weight = 1.0 / (pitch_counts[pitcher_id] * len(sequence_rows))
        for row in sequence_rows:
            rows.append(
                {
                    feature: float(row[feature]) if row.get(feature, "") != "" else None
                    for feature in FEATURE_SCALES
                }
            )
            weights.append(row_weight)
        sequence_summaries.append(
            {
                "pitcher_id": pitcher_id,
                "phase_sequence": str(path),
                "row_count": len(sequence_rows),
                "row_weight": row_weight,
            }
        )
    scalers = fit_weighted_scalers(rows, FEATURE_SCALES, weights)
    save_scalers(
        output_json,
        scalers,
        schema_version="pitch-phase-v0.4-balanced-provisional",
        reference_scope={"throws": throws},
        provenance={
            "reference_sequences": sequence_summaries,
            "reference_sequence_count": len(selected),
            "reference_rows": len(rows),
            "registry": str(registry_path),
            "registry_schema_version": registry.get("schema_version"),
            "selection": "all eligible registry entries matching throwing side",
            "pitcher_sequence_counts": dict(sorted(pitch_counts.items())),
            "pitcher_balancing": "each pitcher has equal total scaler weight; each pitch and resampled row divide that pitcher's weight equally",
        },
        method="reference-z-score-equal-pitcher-weight",
    )
    return {
        "reference_sequences": len(selected),
        "reference_rows": len(rows),
        "pitcher_count": len(pitch_counts),
        "throws": throws,
        "output": str(output_json),
        "registry": str(registry_path),
    }
