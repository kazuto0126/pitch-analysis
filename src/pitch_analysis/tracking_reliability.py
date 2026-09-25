"""Diagnostic continuity audit of the selected skeleton in one prepared pitch.

This module does not identify a named player. A discontinuity is a warning for
human review, never a confirmed identity switch. All geometry comes from raw
landmarks; interpolated or smoothed coordinates cannot hide a track break.
"""
from __future__ import annotations

import csv
import json
from math import hypot, isfinite
from pathlib import Path
from statistics import median


# Diagnostic warning bounds, independent of the Phase 1 quality gate. The
# centre bound mirrors the selector's conservative continuity radius. These
# deliberately identify conspicuous discontinuities rather than fine motion.
MIN_GEOMETRY_CONFIDENCE = 0.35
CENTER_JUMP_BODY_HEIGHTS = 0.45
SCALE_JUMP_RATIO = 1.6
MOTION_ACCELERATION_BODY_HEIGHTS = 0.45
ROI_X = (0.15, 0.85)
ROI_Y = (0.12, 0.85)
LANDMARKS = (
    "LEFT_HIP", "RIGHT_HIP", "LEFT_SHOULDER", "RIGHT_SHOULDER",
    "LEFT_ANKLE", "RIGHT_ANKLE",
)


def _point(row: dict | None) -> tuple[float, float] | None:
    if not row:
        return None
    try:
        x, y = float(row["x"]), float(row["y"])
        visibility = float(row["visibility"])
        presence = float(row["presence"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(isfinite(value) for value in (x, y, visibility, presence)):
        return None
    if min(visibility, presence) < MIN_GEOMETRY_CONFIDENCE:
        return None
    return x, y


def _raw_geometry(path: Path) -> dict[int, dict[str, tuple[float, float]]]:
    frames: dict[int, dict[str, tuple[float, float]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            name = row.get("landmark")
            if name not in LANDMARKS:
                continue
            point = _point(row)
            if point is not None:
                frames.setdefault(int(row["frame"]), {})[name] = point
    return frames


def _frame_geometry(points: dict[str, tuple[float, float]]) -> tuple[tuple[float, float] | None, float | None]:
    hips = [points.get(name) for name in ("LEFT_HIP", "RIGHT_HIP")]
    if any(point is None for point in hips):
        return None, None
    center = ((hips[0][0] + hips[1][0]) / 2, (hips[0][1] + hips[1][1]) / 2)
    shoulders = [points.get(name) for name in ("LEFT_SHOULDER", "RIGHT_SHOULDER")]
    ankles = [points.get(name) for name in ("LEFT_ANKLE", "RIGHT_ANKLE")]
    if any(point is None for point in shoulders + ankles):
        return center, None
    shoulder_y = (shoulders[0][1] + shoulders[1][1]) / 2
    ankle_y = (ankles[0][1] + ankles[1][1]) / 2
    height = ankle_y - shoulder_y
    return center, height if height > 0 else None


def _breaks(frames: list[dict]) -> list[dict]:
    breaks = []
    start = None
    for frame in frames:
        if frame["selection_status"] != "selected":
            if start is None:
                start = frame["frame_index"]
        elif start is not None:
            breaks.append({"start_frame": start, "end_frame": frame["frame_index"] - 1,
                           "length_frames": frame["frame_index"] - start})
            start = None
    if start is not None:
        end = frames[-1]["frame_index"]
        breaks.append({"start_frame": start, "end_frame": end,
                       "length_frames": end - start + 1})
    return breaks


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def evaluate_tracking_reliability(analysis_dir: Path) -> dict:
    """Assess raw selected-skeleton continuity in one analysis output folder.

    The output distinguishes an observed selector rejection, a geometry jump,
    and a possible identity change. Neither the model's pose index nor the
    continuity heuristic is ground truth for the pitcher's real identity.
    """
    analysis_dir = Path(analysis_dir)
    capture = json.loads((analysis_dir / "pose_raw.capture.json").read_text(encoding="utf-8"))
    video = json.loads((analysis_dir / "video_metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((analysis_dir / "analysis.json").read_text(encoding="utf-8"))
    total = int(video["frame_count"])
    if total <= 0 or video["height"] <= 0:
        raise ValueError("Video frame count and height must be positive")
    selections = capture.get("selection_frames")
    if not isinstance(selections, list) or len(selections) != total:
        raise ValueError("Complete per-frame subject selection trace is required")
    selected_by_frame = {int(entry["frame_index"]): entry for entry in selections}
    if len(selected_by_frame) != total or set(selected_by_frame) != set(range(total)):
        raise ValueError("Selection trace must contain exactly one entry per video frame")
    raw = _raw_geometry(analysis_dir / "pose_raw.csv")
    aspect = float(video["width"]) / float(video["height"])

    frames = []
    for index in range(total):
        selection = selected_by_frame[index]
        status = selection.get("status", "unknown")
        center, height = _frame_geometry(raw.get(index, {})) if status == "selected" else (None, None)
        frames.append({
            "frame_index": index,
            "selection_status": status,
            "candidate_count": selection.get("candidate_count"),
            "center_xy": list(center) if center is not None else None,
            "projected_body_height": height,
            "warnings": [],
        })

    breaks = _breaks(frames)
    events = []
    center_steps = []
    scale_ratios = []
    accelerations = []
    roi_outside = []
    for frame in frames:
        center = frame["center_xy"]
        if frame["selection_status"] == "selected" and center is None:
            frame["warnings"].append("raw_hip_center_unavailable")
            events.append({"type": "raw_hip_center_unavailable", "frame_index": frame["frame_index"]})
        elif frame["selection_status"] == "selected" and frame["projected_body_height"] is None:
            frame["warnings"].append("raw_body_scale_unavailable")
        if center is not None and not (ROI_X[0] <= center[0] <= ROI_X[1] and ROI_Y[0] <= center[1] <= ROI_Y[1]):
            frame["warnings"].append("outside_pitcher_roi")
            roi_outside.append(frame["frame_index"])
            events.append({"type": "outside_pitcher_roi", "frame_index": frame["frame_index"],
                           "center_xy": center})

    previous = None
    for frame in frames:
        if frame["selection_status"] != "selected" or frame["center_xy"] is None:
            continue
        if previous is not None:
            gap = frame["frame_index"] - previous["frame_index"]
            last_height = previous["projected_body_height"]
            current_height = frame["projected_body_height"]
            reference_height = last_height or current_height
            if reference_height:
                dx = (frame["center_xy"][0] - previous["center_xy"][0]) * aspect
                dy = frame["center_xy"][1] - previous["center_xy"][1]
                step = hypot(dx, dy) / reference_height
                # A longer loss permits genuine body travel, but a large jump
                # immediately after a short loss still deserves review.
                limit = CENTER_JUMP_BODY_HEIGHTS * max(1.0, gap / 2)
                center_steps.append(step)
                if step > limit:
                    frame["warnings"].append("body_center_jump")
                    events.append({"type": "body_center_jump", "frame_index": frame["frame_index"],
                                   "previous_frame_index": previous["frame_index"],
                                   "gap_frames": gap - 1, "step_body_heights": step,
                                   "warning_limit_body_heights": limit})
            if last_height and current_height:
                ratio = max(last_height, current_height) / min(last_height, current_height)
                scale_ratios.append(ratio)
                if ratio > SCALE_JUMP_RATIO:
                    frame["warnings"].append("skeleton_scale_jump")
                    events.append({"type": "skeleton_scale_jump", "frame_index": frame["frame_index"],
                                   "previous_frame_index": previous["frame_index"],
                                   "gap_frames": gap - 1, "scale_ratio": ratio,
                                   "warning_limit_ratio": SCALE_JUMP_RATIO})
        previous = frame

    for index in range(1, total - 1):
        before, current, after = frames[index - 1:index + 2]
        if not all(item["selection_status"] == "selected" and item["center_xy"] is not None and
                   item["projected_body_height"] for item in (before, current, after)):
            continue
        x = (after["center_xy"][0] - 2 * current["center_xy"][0] + before["center_xy"][0]) * aspect
        y = after["center_xy"][1] - 2 * current["center_xy"][1] + before["center_xy"][1]
        acceleration = hypot(x, y) / current["projected_body_height"]
        accelerations.append(acceleration)
        if acceleration > MOTION_ACCELERATION_BODY_HEIGHTS:
            current["warnings"].append("motion_discontinuity")
            events.append({"type": "motion_discontinuity", "frame_index": index,
                           "center_acceleration_body_heights_per_frame2": acceleration,
                           "warning_limit": MOTION_ACCELERATION_BODY_HEIGHTS})

    selected_count = sum(frame["selection_status"] == "selected" for frame in frames)
    center_count = sum(frame["center_xy"] is not None for frame in frames)
    scale_count = sum(frame["projected_body_height"] is not None for frame in frames)
    switch_events = [item for item in events if item["type"] in {
        "body_center_jump", "skeleton_scale_jump", "motion_discontinuity"}]
    reasons = []
    if selected_count == 0:
        reasons.append("no_selected_pitcher_skeleton")
    if selected_count < total:
        reasons.append("selector_track_break")
    if center_count < selected_count:
        reasons.append("raw_hip_center_unavailable_in_selected_frames")
    if selected_count and scale_count / selected_count < 0.9:
        reasons.append("raw_body_scale_unavailable_in_selected_frames")
    if roi_outside:
        reasons.append("selected_center_outside_pitcher_roi")
    if switch_events:
        reasons.append("possible_identity_or_pose_discontinuity_requires_review")
    if not center_steps and selected_count > 1:
        reasons.append("insufficient_center_continuity_evidence")
    if not scale_ratios and selected_count > 1:
        reasons.append("insufficient_scale_continuity_evidence")
    if selected_count == 0 or selected_count / total < 0.5 or center_count == 0:
        status = "unreliable"
    elif reasons:
        status = "partially_reliable"
    else:
        status = "reliable"

    return {
        "schema_version": "tracking-reliability-v1",
        "pitch_id": manifest.get("pitch_id"),
        "pitcher_id": manifest.get("pitcher_id"),
        "status": status,
        "reasons": reasons,
        "scope": "single known-pitcher clip; selected skeleton continuity, not player re-identification",
        "source": {"selection": "pose_raw.capture.json", "geometry": "pose_raw.csv",
                   "geometry_processing": "raw observed landmarks only; no interpolation or smoothing"},
        "total_frames": total,
        "selected_frames": selected_count,
        "selected_frame_ratio": selected_count / total,
        "track_breaks": breaks,
        "longest_track_break_frames": max((item["length_frames"] for item in breaks), default=0),
        "raw_geometry_evidence": {"hip_center_frames": center_count,
                                  "projected_body_scale_frames": scale_count,
                                  "selected_frames": selected_count},
        "roi_continuity": {"hip_center_roi_normalized_xy": {"x": list(ROI_X), "y": list(ROI_Y)},
                           "evaluated_frames": center_count, "outside_roi_frames": roi_outside,
                           "inside_roi_ratio": (center_count - len(roi_outside)) / center_count if center_count else None},
        "body_center_continuity": {"evaluated_transitions": len(center_steps),
                                   "median_step_body_heights": median(center_steps) if center_steps else None,
                                   "p95_step_body_heights": _percentile(center_steps, .95),
                                   "max_step_body_heights": max(center_steps, default=None)},
        "skeleton_scale_continuity": {"evaluated_transitions": len(scale_ratios),
                                      "median_ratio": median(scale_ratios) if scale_ratios else None,
                                      "p95_ratio": _percentile(scale_ratios, .95),
                                      "max_ratio": max(scale_ratios, default=None)},
        "motion_continuity": {"evaluated_triplets": len(accelerations),
                              "p95_center_acceleration_body_heights_per_frame2": _percentile(accelerations, .95),
                              "max_center_acceleration_body_heights_per_frame2": max(accelerations, default=None)},
        "identity_switch_warning": bool(switch_events),
        "identity_switch_confirmed": None,
        "identity_switch_warning_basis": "body-center, scale or motion discontinuity; requires human ground truth",
        "warning_events": events,
        "frames": frames,
        "limitations": [
            "A stable skeleton can still belong to the wrong person; human subject ground truth is required.",
            "A warning can be caused by pose jitter, perspective or genuine pitching motion, not an identity change.",
            "Pose-array selected_index is not a persistent identity and is not used as a switch detector.",
        ],
    }


def write_tracking_reliability(analysis_dir: Path, output_path: Path | None = None) -> dict:
    """Write the independent tracking audit next to an existing analysis."""
    analysis_dir = Path(analysis_dir)
    report = evaluate_tracking_reliability(analysis_dir)
    target = Path(output_path) if output_path is not None else analysis_dir / "tracking_reliability.json"
    target.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
