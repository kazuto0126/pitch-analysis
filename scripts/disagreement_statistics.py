"""Threshold-free descriptive statistics for sealed disagreement measurements.

Missing values remain in the human-scorable denominator; AUROC is conditional
on finite values and never replaces availability reporting. Larger distances
always rank toward ``unreliable``. No predictions or human annotations are
created or changed here.
"""
from __future__ import annotations

import math
from numbers import Real
from typing import Iterable, Mapping, Sequence


LABELS = ("reliable", "unreliable", "uncertain", "not_observable")
SCORABLE = ("reliable", "unreliable")


def _finite_number(value: object, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError("Values must be finite numbers, not booleans")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError("Values must be finite numbers") from error
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ValueError("Values must be finite and nonnegative" if nonnegative
                         else "Values must be finite numbers")
    return number


def _ranks(values: Sequence[float]) -> list[float]:
    """Return one-based ranks with exact-value ties receiving average ranks."""
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2
        for index in order[start:end]:
            result[index] = average
        start = end
    return result


def _quantile(ordered: Sequence[float], probability: float) -> float | None:
    """Linear type-7 quantile; avoid overflowing the mean of large positives."""
    if not ordered:
        return None
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _describe(values: Sequence[float]) -> dict:
    ordered = sorted(values)
    count = len(ordered)
    # Scale before summation to avoid both overflow for large positives and
    # premature underflow when every observation is a tiny positive number.
    maximum = ordered[-1] if count else None
    average = (maximum * math.fsum(value / maximum / count for value in ordered)
               if maximum else (0.0 if count else None))
    return {
        "count": count,
        "mean": average,
        "median": _quantile(ordered, 0.5),
        "p90": _quantile(ordered, 0.9),
        "max": maximum,
    }


def _auroc(negative: Sequence[float], positive: Sequence[float]) -> float | None:
    if not negative or not positive:
        return None
    ranks = _ranks(list(negative) + list(positive))
    positive_rank_sum = math.fsum(ranks[len(negative):])
    positives = len(positive)
    return ((positive_rank_sum - positives * (positives + 1) / 2)
            / (len(negative) * positives))


def summarize_labeled(rows: Iterable[Mapping]) -> dict:
    """Describe human labels and conditional distance ranking without a gate.

Each row has ``label`` in LABELS and ``value`` as a finite nonnegative number or
None. Uncertain/not_observable rows are counted, excluded from the scorable
denominator, and validated even though their values do not enter the metrics.
``value_coverage`` measures numerical availability, not decisions or accuracy.
AUROC gives exact-value ties half credit and returns None without both classes.
"""
    labels = dict.fromkeys(LABELS, 0)
    values: dict[str, list[float]] = {label: [] for label in SCORABLE}
    for row in rows:
        if not isinstance(row, Mapping) or "label" not in row or "value" not in row:
            raise ValueError("Each row must contain label and value")
        label = row["label"]
        if not isinstance(label, str) or label not in labels:
            raise ValueError("Unknown human reliability label")
        value = row["value"]
        number = None if value is None else _finite_number(value, nonnegative=True)
        labels[label] += 1
        if label in values and number is not None:
            values[label].append(number)

    scorable = {label: labels[label] for label in SCORABLE}
    paired = {label: len(values[label]) for label in SCORABLE}
    unavailable = {label: scorable[label] - paired[label] for label in SCORABLE}
    for counts in (scorable, paired, unavailable):
        counts["total"] = sum(counts.values())
    coverage = {
        label: paired[label] / scorable[label] if scorable[label] else None
        for label in (*SCORABLE, "total")
    }
    coverage["overall"] = coverage.pop("total")
    return {
        "label_counts": labels,
        "human_excluded_count": labels["uncertain"] + labels["not_observable"],
        "scorable_counts": scorable,
        "paired_counts": paired,
        "unavailable_counts": unavailable,
        "value_coverage": coverage,
        "conditional_auroc": _auroc(values["reliable"], values["unreliable"]),
        "auroc_direction": "larger_value_ranks_toward_unreliable",
        "auroc_scope": "conditional_on_numerically_available_human_scorable_rows",
        "descriptive": {label: _describe(values[label]) for label in SCORABLE},
        "quantile_method": "linear_type_7",
    }


def spearman(pairs: Iterable[Sequence[float]]) -> float | None:
    """Rank correlation with average ties; fewer than two/constant => None.

Pairs must each contain exactly two finite numbers. Neither None nor invalid
values are silently removed, and zero is an ordinary numerical observation.
"""
    x, y = [], []
    for pair in pairs:
        if (not isinstance(pair, Sequence) or isinstance(pair, (str, bytes))
                or len(pair) != 2):
            raise ValueError("Each pair must contain exactly two finite numbers")
        x.append(_finite_number(pair[0]))
        y.append(_finite_number(pair[1]))
    count = len(x)
    if count < 2:
        return None
    rx, ry = _ranks(x), _ranks(y)
    center = (count + 1) / 2
    dx = [value - center for value in rx]
    dy = [value - center for value in ry]
    xx = math.fsum(value * value for value in dx)
    yy = math.fsum(value * value for value in dy)
    if xx == 0 or yy == 0:
        return None
    correlation = math.fsum(a * b for a, b in zip(dx, dy)) / math.sqrt(xx * yy)
    return max(-1.0, min(1.0, correlation))
