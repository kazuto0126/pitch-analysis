from __future__ import annotations
import json
from pathlib import Path
from .config import FEATURE_COLUMNS, QualityConfig
from .features import extract_frame_features
from .io import coordinate_x_scale, load_pose_context, read_pose_csv, timeline_bounds, write_rows
from .segmentation import DEFAULT_ACTIVITY_SCALES, detect_activity_windows, detect_motion_window
from .temporal import (
    LINE_ORIENTATION_FEATURES,
    circular_smooth_line_angles,
    interpolate_short_gaps,
    interpolate_short_line_angle_gaps,
    median_smooth,
)


def _max_consecutive_missing(values: list[bool]) -> int:
    maximum = current = 0
    for value in values:
        if value:
            current = 0
        else:
            current += 1
            maximum = max(maximum, current)
    return maximum


def build_features(pose_csv: str | Path, output_csv: str | Path, *, throwing_side: str, quality: QualityConfig = QualityConfig()) -> dict:
    """Create an auditable feature table with raw and imputed coverage separated."""
    frames = read_pose_csv(pose_csv)
    if not frames:
        raise ValueError("pose CSV contains no landmarks; cannot calculate features")
    context = load_pose_context(pose_csv)
    first, last = timeline_bounds(frames, context)
    x_scale = coordinate_x_scale(context)
    interpolation_gap = quality.interpolation_gap_frames(context.get("fps"))
    smoothing_radius = quality.feature_smoothing_radius_frames(context.get("fps"))
    rows = []
    invalid = {name: 0 for name in FEATURE_COLUMNS}
    raw_invalid = {name: 0 for name in FEATURE_COLUMNS}
    coordinate_imputed = {name: 0 for name in FEATURE_COLUMNS}
    for frame_number in range(first, last + 1):
        frame = frames.get(frame_number, {})
        source_detected = bool(frame) and any(value.get("source_frame_detected", True) for value in frame.values())
        values = extract_frame_features(
            frame, throwing_side, quality.min_visibility, quality.min_presence, coordinate_x_scale=x_scale
        )
        raw_values = extract_frame_features(
            frame,
            throwing_side,
            quality.min_visibility,
            quality.min_presence,
            coordinate_x_scale=x_scale,
            require_raw=True,
        )
        row = {"frame": frame_number, "source_frame_detected": source_detected, **values}
        for name in FEATURE_COLUMNS:
            if values[name] is None:
                invalid[name] += 1
            if raw_values[name] is None:
                raw_invalid[name] += 1
            if values[name] is not None and raw_values[name] is None:
                coordinate_imputed[name] += 1
            row[f"{name}_raw_observed"] = raw_values[name] is not None
            row[f"{name}_coordinate_imputed"] = values[name] is not None and raw_values[name] is None
        rows.append(row)
    # There is deliberately one smoothing layer: feature values.  Landmark cleaning
    # only handles bounded coordinate gaps, retaining a mask for every imputation.
    for name in FEATURE_COLUMNS:
        if name in LINE_ORIENTATION_FEATURES:
            interpolated, imputed = interpolate_short_line_angle_gaps(
                [row[name] for row in rows], interpolation_gap
            )
            smoothed = circular_smooth_line_angles(interpolated, smoothing_radius)
        else:
            interpolated, imputed = interpolate_short_gaps([row[name] for row in rows], interpolation_gap)
            smoothed = median_smooth(interpolated, smoothing_radius)
        for row, value, was_imputed, smooth_value in zip(rows, interpolated, imputed, smoothed):
            row[f"{name}_interpolated"] = value
            row[f"{name}_imputed"] = was_imputed
            row[f"{name}_smoothed"] = smooth_value
    frame_numbers = [row["frame"] for row in rows]
    motion = detect_motion_window(frame_numbers, [row["lateral_foot_separation_smoothed"] for row in rows])
    activity_windows = detect_activity_windows(
        frame_numbers,
        {
            name: [row.get(name) for row in rows]
            for name in DEFAULT_ACTIVITY_SCALES
        },
    )
    fields = ["frame", "source_frame_detected", *FEATURE_COLUMNS]
    for name in FEATURE_COLUMNS:
        fields.extend((
            f"{name}_raw_observed",
            f"{name}_coordinate_imputed",
            f"{name}_interpolated",
            f"{name}_imputed",
            f"{name}_smoothed",
        ))
    write_rows(output_csv, fields, rows)
    source_detection = [bool(row["source_frame_detected"]) for row in rows]
    report = {
        "schema_version": "feature-quality-v0.3",
        "input_frames_detected": sum(source_detection),
        "timeline_frames": len(rows),
        "timeline_start_frame": first,
        "timeline_end_frame": last,
        "timeline_contract": "capture_requested_range" if context else "observed_csv_range_legacy",
        "missing_source_frames": [row["frame"] for row in rows if not row["source_frame_detected"]],
        "missing_source_frame_count": source_detection.count(False),
        "max_consecutive_missing_source_frames": _max_consecutive_missing(source_detection),
        "invalid_feature_frames": invalid,
        "raw_invalid_feature_frames": raw_invalid,
        "coordinate_imputed_feature_frames": coordinate_imputed,
        "feature_coverage": {name: (len(rows) - invalid[name]) / len(rows) for name in FEATURE_COLUMNS},
        "raw_feature_coverage": {name: (len(rows) - raw_invalid[name]) / len(rows) for name in FEATURE_COLUMNS},
        "coordinate_imputed_feature_fraction": {name: coordinate_imputed[name] / len(rows) for name in FEATURE_COLUMNS},
        "throwing_side": throwing_side,
        "min_visibility": quality.min_visibility,
        "min_presence": quality.min_presence,
        "coordinate_x_scale": x_scale,
        "coordinate_contract": context.get("coordinate_contract", "unverified legacy normalized x/y"),
        "capture_context": {key: context.get(key) for key in ("width", "height", "fps", "_context_path") if context.get(key) is not None},
        "smoothing": {
            "coordinate": "none",
            "feature_method": "median; doubled-angle circular mean for unoriented shoulder/hip lines",
            "radius_frames": smoothing_radius,
            "radius_seconds": quality.feature_smoothing_seconds,
            "max_interpolation_gap_frames": interpolation_gap,
            "max_interpolation_seconds": quality.max_interpolation_seconds,
        },
        "motion_window_proxy": vars(motion) if motion else None,
        "motion_candidates": {
            "status": "review_required",
            "method": "multi-feature-velocity-proxy",
            "candidate_count": len(activity_windows),
            "candidates": [vars(window) for window in activity_windows],
            "limitations": [
                "Broadcast cuts and pose-tracking errors may create false positives.",
                "Candidates are not biomechanical event labels and require visual review.",
            ],
        },
    }
    Path(output_csv).with_suffix(".quality.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
