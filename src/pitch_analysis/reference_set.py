"""Aggregate query-to-pitch comparisons into a pitcher-level diagnostic score."""
from __future__ import annotations
import json
from pathlib import Path
from statistics import median
from .comparison import compare_phase_sequences


def compare_reference_set(query_csv: str | Path, reference_csvs: list[str | Path], output_json: str | Path, scaler_json: str | Path | None = None) -> dict:
    comparisons = []
    for reference in reference_csvs:
        result = compare_phase_sequences(query_csv, reference, scaler_json)
        comparisons.append({"reference_sequence": str(reference), "distance": result["overall_mean_phase_distance"], "phase_distances": {name: value.get("distance") for name, value in result["phases"].items()}})
    valid = [item["distance"] for item in comparisons if item["distance"] is not None]
    summary = {"schema_version": "0.1-provisional", "aggregation": "median per-reference phase-DTW distance", "reference_count": len(comparisons), "pitcher_distance": median(valid) if valid else None, "reference_comparisons": comparisons, "warning": "Diagnostic only: references share one pitcher and the sample is too small for pitcher ranking."}
    Path(output_json).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
