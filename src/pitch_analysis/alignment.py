"""Masked, weighted and path-normalized DTW for already segmented pitch windows."""
from __future__ import annotations
import math
from typing import Mapping, Sequence
from .temporal import line_angle_delta


def frame_cost(
    left: Mapping[str, float | None],
    right: Mapping[str, float | None],
    weights: Mapping[str, float],
    *,
    min_shared_features: int = 1,
    circular_feature_scales: Mapping[str, float] | None = None,
) -> float | None:
    """Return masked weighted cost, preserving circular line orientation distance."""
    if min_shared_features < 1:
        raise ValueError("min_shared_features must be positive")
    circular_feature_scales = circular_feature_scales or {}
    total = weight_total = 0.0
    shared = 0
    for feature, weight in weights.items():
        a, b = left.get(feature), right.get(feature)
        if a is None or b is None:
            continue
        difference = (
            line_angle_delta(a, b) / circular_feature_scales[feature]
            if feature in circular_feature_scales
            else a - b
        )
        total += weight * difference ** 2
        weight_total += weight
        shared += 1
    return math.sqrt(total / weight_total) if weight_total and shared >= min_shared_features else None


def constrained_dtw(
    left: Sequence[Mapping[str, float | None]],
    right: Sequence[Mapping[str, float | None]],
    weights: Mapping[str, float],
    band_ratio: float = 0.15,
    *,
    min_shared_features: int = 1,
    circular_feature_scales: Mapping[str, float] | None = None,
) -> tuple[float, int] | None:
    """Return (mean path cost, path length); None when no valid alignment exists."""
    if not left or not right or not 0 <= band_ratio <= 1:
        raise ValueError("sequences must be non-empty and band_ratio must be in [0, 1]")
    width = max(abs(len(left) - len(right)), math.ceil(max(len(left), len(right)) * band_ratio))
    inf = float("inf")
    costs = [[inf] * (len(right) + 1) for _ in range(len(left) + 1)]
    paths = [[0] * (len(right) + 1) for _ in range(len(left) + 1)]
    costs[0][0] = 0.0
    for i in range(1, len(left) + 1):
        for j in range(max(1, i - width), min(len(right), i + width) + 1):
            cost = frame_cost(
                left[i-1],
                right[j-1],
                weights,
                min_shared_features=min_shared_features,
                circular_feature_scales=circular_feature_scales,
            )
            if cost is None:
                continue
            candidates = ((costs[i-1][j], paths[i-1][j]), (costs[i][j-1], paths[i][j-1]), (costs[i-1][j-1], paths[i-1][j-1]))
            previous_cost, previous_length = min(candidates, key=lambda item: item[0])
            if previous_cost != inf:
                costs[i][j], paths[i][j] = previous_cost + cost, previous_length + 1
    length = paths[-1][-1]
    return (costs[-1][-1] / length, length) if length else None
