"""Landmark-level cleaning before feature geometry is calculated."""
from __future__ import annotations
import json
from pathlib import Path
from .config import QualityConfig
from .io import coordinate_x_scale, load_pose_context, read_pose_csv, timeline_bounds, write_rows
from .temporal import interpolate_short_gaps


def clean_pose(
    pose_csv: str | Path,
    output_csv: str | Path,
    quality: QualityConfig = QualityConfig(),
    *,
    capture_context: dict | None = None,
) -> dict:
    frames = read_pose_csv(pose_csv)
    context = {**load_pose_context(pose_csv), **(capture_context or {})}
    first, last = timeline_bounds(frames, context)
    interpolation_gap = quality.interpolation_gap_frames(context.get("fps"))
    names = sorted({name for frame in frames.values() for name in frame})
    if not names:
        raise ValueError("pose CSV contains no landmarks; cannot create a cleaned pose table")
    rows = []
    for name in names:
        source = [frames.get(frame, {}).get(name) for frame in range(first, last + 1)]
        valid = [
            item is not None
            and "x" in item
            and "y" in item
            and item.get("quality_valid", True) is not False
            and item.get("visibility", 0.0) >= quality.min_visibility
            # Legacy pose CSVs do not carry MediaPipe presence; retain their
            # visibility-only behaviour rather than silently dropping all rows.
            and item.get("presence", 1.0) >= quality.min_presence
            for item in source
        ]
        xs, x_filled = interpolate_short_gaps([item["x"] if good else None for item, good in zip(source, valid)], interpolation_gap)
        ys, y_filled = interpolate_short_gaps([item["y"] if good else None for item, good in zip(source, valid)], interpolation_gap)
        for offset, frame in enumerate(range(first, last + 1)):
            item = source[offset] or {}
            source_detected = bool(frames.get(frame)) and any(
                value.get("source_frame_detected", True) is True for value in frames.get(frame, {}).values()
            )
            usable = xs[offset] is not None and ys[offset] is not None
            was_interpolated = usable and (
                x_filled[offset] or y_filled[offset] or item.get("interpolated", False) is True
            )
            rows.append({"frame": frame, "source_frame_detected": source_detected, "landmark": name, "x_raw": item.get("x"), "y_raw": item.get("y"), "z_raw": item.get("z"), "visibility": item.get("visibility"), "presence": item.get("presence"), "quality_valid": valid[offset], "interpolated": was_interpolated, "usable": usable, "x": xs[offset] if usable else None, "y": ys[offset] if usable else None})
    fields = ("frame", "source_frame_detected", "landmark", "x_raw", "y_raw", "z_raw", "visibility", "presence", "quality_valid", "interpolated", "usable", "x", "y")
    write_rows(output_csv, fields, rows)
    clean_context = {
        "schema_version": "pose-clean-v0.2",
        "source_pose_csv": str(pose_csv),
        "source_context": context.get("_context_path"),
        "timeline_start_frame": first,
        "timeline_end_frame": last,
        "requested_frames": last - first + 1,
        "width": context.get("width"),
        "height": context.get("height"),
        "fps": context.get("fps"),
        "coordinate_x_scale": coordinate_x_scale(context),
        "coordinate_contract": "height-normalized image plane: x_normalized * (width / height), y_normalized",
        "min_visibility": quality.min_visibility,
        "min_presence": quality.min_presence,
        "max_interpolation_gap_frames": interpolation_gap,
        "max_interpolation_seconds": quality.max_interpolation_seconds,
        "coordinate_smoothing": "none; feature-level smoothing is applied once downstream",
    }
    Path(output_csv).with_suffix(".clean.json").write_text(json.dumps(clean_context, indent=2), encoding="utf-8")
    return {"frame_range": [first, last], "landmarks": len(names), "rows": len(rows), "min_visibility": quality.min_visibility, "min_presence": quality.min_presence, "coordinate_x_scale": clean_context["coordinate_x_scale"], "context": str(Path(output_csv).with_suffix(".clean.json"))}
