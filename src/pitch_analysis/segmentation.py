"""Conservative 2-D motion-window detection; not a biomechanics event labeller."""
from __future__ import annotations
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping, Sequence


DEFAULT_ACTIVITY_SCALES = {
    "throwing_knee_angle_smoothed": 30.0,
    "lead_knee_angle_smoothed": 30.0,
    "shoulder_line_angle_smoothed": 30.0,
    "throwing_elbow_angle_smoothed": 30.0,
    "hip_line_angle_smoothed": 30.0,
    "lateral_foot_separation_smoothed": 0.10,
}
CIRCULAR_ACTIVITY_FEATURES = {"shoulder_line_angle_smoothed", "hip_line_angle_smoothed"}


@dataclass(frozen=True)
class MotionWindow:
    start_frame: int
    end_frame: int
    peak_separation_frame: int
    confidence: float
    method: str = "lateral-foot-separation-proxy"


def detect_motion_windows(
    frames: Sequence[int],
    separation: Sequence[float | None],
    baseline_frames: int = 15,
    threshold_ratio: float = 0.2,
    merge_gap_frames: int = 3,
    min_window_frames: int = 5,
    pre_roll_frames: int = 0,
    post_roll_frames: int = 0,
) -> list[MotionWindow]:
    """Return multiple conservative motion candidates from foot separation.

    The candidates are broad activity windows only. They are intended to help a
    reviewer locate pitches in a longer clip; they do not assert biomechanical
    events such as foot strike or ball release.

    ``merge_gap_frames`` bridges short dips below the activity threshold. The
    optional pre/post roll expands each candidate without exceeding the supplied
    frame range.
    """
    if len(frames) != len(separation):
        raise ValueError("frames and separation must have the same length")
    if baseline_frames < 1:
        raise ValueError("baseline_frames must be positive")
    if not 0.0 < threshold_ratio < 1.0:
        raise ValueError("threshold_ratio must be between 0 and 1")
    if merge_gap_frames < 0 or min_window_frames < 1:
        raise ValueError("gap and window sizes must be non-negative/positive")
    if pre_roll_frames < 0 or post_roll_frames < 0:
        raise ValueError("pre/post roll must be non-negative")

    valid = [(int(frame), float(value)) for frame, value in zip(frames, separation) if value is not None]
    if len(valid) < max(5, baseline_frames):
        return []

    baseline = sum(value for _, value in valid[:baseline_frames]) / baseline_frames
    global_peak = max(value for _, value in valid)
    amplitude = global_peak - baseline
    if amplitude <= 0:
        return []

    threshold = baseline + amplitude * threshold_ratio
    active = [(frame, value) for frame, value in valid if value >= threshold]
    if not active:
        return []

    groups: list[list[tuple[int, float]]] = [[active[0]]]
    for point in active[1:]:
        previous_frame = groups[-1][-1][0]
        inactive_gap = point[0] - previous_frame - 1
        if inactive_gap <= merge_gap_frames:
            groups[-1].append(point)
        else:
            groups.append([point])

    first_frame = min(int(frame) for frame in frames)
    last_frame = max(int(frame) for frame in frames)
    windows: list[MotionWindow] = []
    for group in groups:
        start_frame = group[0][0]
        end_frame = group[-1][0]
        if end_frame - start_frame + 1 < min_window_frames:
            continue

        peak_frame, peak = max(group, key=lambda pair: pair[1])
        local_amplitude = peak - baseline
        if local_amplitude <= 0:
            continue
        confidence = min(1.0, local_amplitude / max(abs(peak), 1e-9))
        windows.append(
            MotionWindow(
                start_frame=max(first_frame, start_frame - pre_roll_frames),
                end_frame=min(last_frame, end_frame + post_roll_frames),
                peak_separation_frame=peak_frame,
                confidence=confidence,
                method="lateral-foot-separation-proxy-multi",
            )
        )

    return windows


def _quantile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a quantile from no values")
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _line_delta_degrees(current: float, previous: float) -> float:
    delta = abs(current - previous) % 180.0
    return min(delta, 180.0 - delta)


def detect_activity_windows(
    frames: Sequence[int],
    features: Mapping[str, Sequence[float | None]],
    *,
    feature_scales: Mapping[str, float] | None = None,
    activity_quantile: float = 0.70,
    smoothing_radius: int = 2,
    merge_gap_frames: int = 12,
    min_window_frames: int = 3,
    pre_roll_frames: int = 15,
    post_roll_frames: int = 20,
    min_shared_features: int = 3,
) -> list[MotionWindow]:
    """Locate motion bursts using normalized frame-to-frame feature velocity.

    This is less dependent on stance width than ``detect_motion_windows``. It is
    still only a candidate generator: broadcast cuts, tracking swaps, and warm-up
    movements can create false positives and therefore require visual review.
    """
    if not 0.0 < activity_quantile < 1.0:
        raise ValueError("activity_quantile must be between 0 and 1")
    if smoothing_radius < 0 or merge_gap_frames < 0 or min_window_frames < 1:
        raise ValueError("invalid activity window size")
    if pre_roll_frames < 0 or post_roll_frames < 0 or min_shared_features < 1:
        raise ValueError("invalid activity detection parameter")
    if not frames:
        return []
    if any(len(values) != len(frames) for values in features.values()):
        raise ValueError("every feature sequence must match the frame sequence")

    scales = dict(feature_scales or DEFAULT_ACTIVITY_SCALES)
    selected = {name: values for name, values in features.items() if name in scales and scales[name] > 0}
    if len(selected) < min_shared_features:
        return []

    raw_scores: list[float | None] = [None]
    for index in range(1, len(frames)):
        normalized_deltas: list[float] = []
        for name, values in selected.items():
            previous, current = values[index - 1], values[index]
            if previous is None or current is None:
                continue
            if name in CIRCULAR_ACTIVITY_FEATURES:
                delta = _line_delta_degrees(float(current), float(previous))
            else:
                delta = abs(float(current) - float(previous))
            # Capping limits the influence of one-frame landmark swaps.
            normalized_deltas.append(min(3.0, delta / scales[name]))
        raw_scores.append(
            sum(normalized_deltas) / len(normalized_deltas)
            if len(normalized_deltas) >= min_shared_features
            else None
        )

    smoothed_scores: list[float | None] = []
    for index in range(len(raw_scores)):
        start = max(0, index - smoothing_radius)
        end = min(len(raw_scores), index + smoothing_radius + 1)
        local = [score for score in raw_scores[start:end] if score is not None]
        smoothed_scores.append(sum(local) / len(local) if local else None)

    valid_scores = [score for score in smoothed_scores if score is not None]
    if len(valid_scores) < 5 or max(valid_scores) <= 0:
        return []
    threshold = _quantile(valid_scores, activity_quantile)
    if threshold <= 0:
        positive = [score for score in valid_scores if score > 0]
        if not positive:
            return []
        threshold = _quantile(positive, 0.5)

    active = [
        (int(frame), float(score))
        for frame, score in zip(frames, smoothed_scores)
        if score is not None and score >= threshold
    ]
    if not active:
        return []

    groups: list[list[tuple[int, float]]] = [[active[0]]]
    for point in active[1:]:
        inactive_gap = point[0] - groups[-1][-1][0] - 1
        if inactive_gap <= merge_gap_frames:
            groups[-1].append(point)
        else:
            groups.append([point])

    first_frame, last_frame = min(frames), max(frames)
    windows: list[MotionWindow] = []
    for group in groups:
        if group[-1][0] - group[0][0] + 1 < min_window_frames:
            continue
        peak_frame, peak_score = max(group, key=lambda pair: pair[1])
        windows.append(
            MotionWindow(
                start_frame=max(first_frame, group[0][0] - pre_roll_frames),
                end_frame=min(last_frame, group[-1][0] + post_roll_frames),
                peak_separation_frame=peak_frame,
                confidence=min(1.0, peak_score / max(threshold * 2.0, 1e-9)),
                method="multi-feature-velocity-proxy",
            )
        )
    return windows


def write_motion_candidates(
    features_csv: str | Path,
    output_json: str | Path,
    *,
    method: str = "multi-feature-velocity",
    feature_column: str = "lateral_foot_separation_smoothed",
    baseline_frames: int = 15,
    threshold_ratio: float = 0.2,
    merge_gap_frames: int = 12,
    min_window_frames: int = 3,
    pre_roll_frames: int = 15,
    post_roll_frames: int = 20,
    activity_quantile: float = 0.70,
    smoothing_radius: int = 2,
) -> dict:
    """Detect broad candidates from a feature table and write an audit file."""
    source_path = Path(features_csv)
    with source_path.open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or "frame" not in reader.fieldnames:
            raise ValueError("feature CSV must contain a frame column")
        fieldnames = list(reader.fieldnames)
        if method == "foot-separation" and feature_column not in fieldnames:
            raise ValueError(f"feature CSV does not contain {feature_column!r}")
        rows = list(reader)

    frames = [int(row["frame"]) for row in rows]
    if method == "foot-separation":
        separation = [float(row[feature_column]) if row.get(feature_column, "") != "" else None for row in rows]
        windows = detect_motion_windows(
            frames,
            separation,
            baseline_frames=baseline_frames,
            threshold_ratio=threshold_ratio,
            merge_gap_frames=merge_gap_frames,
            min_window_frames=min_window_frames,
            pre_roll_frames=pre_roll_frames,
            post_roll_frames=post_roll_frames,
        )
    elif method == "multi-feature-velocity":
        available = {
            name: [float(row[name]) if row.get(name, "") != "" else None for row in rows]
            for name in DEFAULT_ACTIVITY_SCALES
            if name in fieldnames
        }
        windows = detect_activity_windows(
            frames,
            available,
            activity_quantile=activity_quantile,
            smoothing_radius=smoothing_radius,
            merge_gap_frames=merge_gap_frames,
            min_window_frames=min_window_frames,
            pre_roll_frames=pre_roll_frames,
            post_roll_frames=post_roll_frames,
        )
    else:
        raise ValueError(f"unknown motion candidate method: {method}")
    payload = {
        "schema": "motion-candidates-v0.1",
        "status": "review_required",
        "source_features_csv": str(source_path),
        "method": method,
        "feature_column": feature_column,
        "parameters": {
            "baseline_frames": baseline_frames,
            "threshold_ratio": threshold_ratio,
            "merge_gap_frames": merge_gap_frames,
            "min_window_frames": min_window_frames,
            "pre_roll_frames": pre_roll_frames,
            "post_roll_frames": post_roll_frames,
            "activity_quantile": activity_quantile,
            "smoothing_radius": smoothing_radius,
        },
        "candidate_count": len(windows),
        "candidates": [
            {
                **asdict(window),
                **(
                    {"peak_activity_frame": window.peak_separation_frame}
                    if method == "multi-feature-velocity"
                    else {}
                ),
            }
            for window in windows
        ],
        "limitations": (
            [
                "Candidates use normalized velocity from multiple 2-D pose features.",
                "Broadcast cuts and pose-tracking errors may create false positives.",
                "Each candidate must be visually reviewed before event annotation.",
            ]
            if method == "multi-feature-velocity"
            else [
                "Candidates are based on rear-view lateral foot separation only.",
                "Each candidate must be visually reviewed before event annotation.",
            ]
        ),
    }
    target = Path(output_json)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def detect_motion_window(frames: Sequence[int], separation: Sequence[float | None], baseline_frames: int = 15) -> MotionWindow | None:
    """Find a broad activity window from rear-view foot separation.

    This deliberately does not claim foot-strike or ball-release: those events need
    validated landmarks/camera geometry or manual labels.
    """
    valid = [(frame, value) for frame, value in zip(frames, separation) if value is not None]
    if len(valid) < max(5, baseline_frames):
        return None
    baseline = sum(value for _, value in valid[:baseline_frames]) / baseline_frames
    peak_frame, peak = max(valid, key=lambda pair: pair[1])
    amplitude = peak - baseline
    if amplitude <= 0:
        return None
    threshold = baseline + amplitude * 0.2
    active = [frame for frame, value in valid if value >= threshold]
    if not active:
        return None
    # Confidence only describes signal contrast, not biomechanical correctness.
    confidence = min(1.0, amplitude / max(peak, 1e-9))
    return MotionWindow(min(active), max(active), peak_frame, confidence)
