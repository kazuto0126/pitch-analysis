"""Quality-preserving operations for regularly sampled feature sequences."""
from __future__ import annotations
import math
from statistics import median
from typing import Sequence


LINE_ORIENTATION_FEATURES = frozenset({"shoulder_line_angle", "hip_line_angle"})


def interpolate_short_gaps(values: Sequence[float | None], max_gap: int = 2) -> tuple[list[float | None], list[bool]]:
    """Linearly fill only bounded internal gaps; return values and an imputation mask."""
    output = list(values)
    imputed = [False] * len(output)
    index = 0
    while index < len(output):
        if output[index] is not None:
            index += 1
            continue
        start = index
        while index < len(output) and output[index] is None:
            index += 1
        end = index
        if start == 0 or end == len(output) or end - start > max_gap:
            continue
        left, right = output[start - 1], output[end]
        assert left is not None and right is not None
        for position in range(start, end):
            fraction = (position - start + 1) / (end - start + 1)
            output[position] = left + fraction * (right - left)
            imputed[position] = True
    return output, imputed


def median_smooth(values: Sequence[float | None], radius: int = 2) -> list[float | None]:
    """Centered median. Missing values remain missing when no valid neighbour exists."""
    smoothed: list[float | None] = []
    for index in range(len(values)):
        window = [value for value in values[max(0, index-radius):index+radius+1] if value is not None]
        smoothed.append(float(median(window)) if window else None)
    return smoothed


def wrap_line_angle(angle: float) -> float:
    """Wrap an unoriented line angle to ``[-90, 90)`` degrees."""
    return ((float(angle) + 90.0) % 180.0) - 90.0


def line_angle_delta(start: float, end: float) -> float:
    """Return the shortest signed orientation change from ``start`` to ``end``."""
    return wrap_line_angle(end - start)


def interpolate_short_line_angle_gaps(
    values: Sequence[float | None], max_gap: int = 2
) -> tuple[list[float | None], list[bool]]:
    """Interpolate line orientation across the 180-degree wrap safely."""
    output = list(values)
    imputed = [False] * len(output)
    index = 0
    while index < len(output):
        if output[index] is not None:
            index += 1
            continue
        start = index
        while index < len(output) and output[index] is None:
            index += 1
        end = index
        if start == 0 or end == len(output) or end - start > max_gap:
            continue
        left, right = output[start - 1], output[end]
        assert left is not None and right is not None
        delta = line_angle_delta(left, right)
        for position in range(start, end):
            fraction = (position - start + 1) / (end - start + 1)
            output[position] = wrap_line_angle(left + delta * fraction)
            imputed[position] = True
    return output, imputed


def circular_smooth_line_angles(values: Sequence[float | None], radius: int = 2) -> list[float | None]:
    """Smooth unoriented line angles with a doubled-angle circular mean."""
    smoothed: list[float | None] = []
    for index in range(len(values)):
        window = [value for value in values[max(0, index-radius):index+radius+1] if value is not None]
        if not window:
            smoothed.append(None)
            continue
        radians = [math.radians(2.0 * value) for value in window]
        sin_mean = sum(math.sin(value) for value in radians) / len(radians)
        cos_mean = sum(math.cos(value) for value in radians) / len(radians)
        if math.hypot(sin_mean, cos_mean) < 1e-12:
            smoothed.append(wrap_line_angle(window[len(window) // 2]))
        else:
            smoothed.append(wrap_line_angle(math.degrees(math.atan2(sin_mean, cos_mean)) / 2.0))
    return smoothed
