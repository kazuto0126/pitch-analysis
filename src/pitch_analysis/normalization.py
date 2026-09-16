"""Reference-fitted scaling. Never fit a scaler separately for each query pitch."""
from __future__ import annotations
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
from statistics import fmean, stdev
from typing import Iterable, Mapping


@dataclass(frozen=True)
class FeatureScaler:
    feature: str
    mean: float
    standard_deviation: float
    sample_count: int

    def transform(self, value: float | None) -> float | None:
        return None if value is None else (value - self.mean) / self.standard_deviation


def fit_scalers(rows: Iterable[Mapping[str, float | None]], features: Iterable[str]) -> dict[str, FeatureScaler]:
    rows = list(rows)
    result = {}
    for feature in features:
        values = [float(row[feature]) for row in rows if row.get(feature) is not None]
        if len(values) < 2:
            raise ValueError(f"{feature} needs at least two reference values")
        deviation = stdev(values)
        if deviation == 0:
            raise ValueError(f"{feature} has no reference variation")
        result[feature] = FeatureScaler(feature, fmean(values), deviation, len(values))
    return result


def fit_weighted_scalers(
    rows: Iterable[Mapping[str, float | None]],
    features: Iterable[str],
    weights: Iterable[float],
) -> dict[str, FeatureScaler]:
    """Fit unbiased weighted scalers while retaining observed sample counts."""
    rows = list(rows)
    weights = [float(weight) for weight in weights]
    if len(rows) != len(weights):
        raise ValueError("rows and weights must have the same length")
    if any(not math.isfinite(weight) or weight <= 0 for weight in weights):
        raise ValueError("all scaler weights must be positive finite values")
    result = {}
    for feature in features:
        observed = [
            (float(row[feature]), weight)
            for row, weight in zip(rows, weights)
            if row.get(feature) is not None
        ]
        if len(observed) < 2:
            raise ValueError(f"{feature} needs at least two reference values")
        weight_sum = sum(weight for _, weight in observed)
        weight_square_sum = sum(weight * weight for _, weight in observed)
        denominator = weight_sum - weight_square_sum / weight_sum
        if denominator <= 0:
            raise ValueError(f"{feature} has insufficient effective reference weight")
        mean = sum(value * weight for value, weight in observed) / weight_sum
        variance = (
            sum(weight * (value - mean) ** 2 for value, weight in observed)
            / denominator
        )
        deviation = math.sqrt(variance)
        if deviation == 0:
            raise ValueError(f"{feature} has no reference variation")
        result[feature] = FeatureScaler(feature, mean, deviation, len(observed))
    return result


def save_scalers(path: str | Path, scalers: Mapping[str, FeatureScaler], *, schema_version: str, reference_scope: Mapping | None = None, provenance: Mapping | None = None, method: str = "reference-z-score") -> None:
    payload = {"schema_version": schema_version, "method": method, "scalers": {name: asdict(scaler) for name, scaler in scalers.items()}}
    if reference_scope:
        payload["reference_scope"] = dict(reference_scope)
    if provenance:
        payload["provenance"] = dict(provenance)
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")
