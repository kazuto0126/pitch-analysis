"""Evidence-based, provisional pose reliability diagnostics for one pitch.

This module reads existing pose outputs. It does not change pose estimation,
quality gates, interpolation, or raw predictions. A reliability label here
describes *observability and temporal continuity*, not ground-truth accuracy.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import mean, median


_RELIABILITY_ORDER = {"reliable": 0, "partially_reliable": 1, "unreliable": 2}
_BODY_PAIRS = ("SHOULDER", "HIP", "KNEE", "ANKLE")


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _longest_run(states: list[str], predicate) -> int:
    longest = current = 0
    for state in states:
        current = current + 1 if predicate(state) else 0
        longest = max(longest, current)
    return longest


def _visibility(values: list[float]) -> dict:
    return {
        "sample_count": len(values),
        "mean": mean(values) if values else None,
        "median": median(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def _jump_diagnostics(states: list[str], points: list[tuple[float, float] | None],
                      frame_indices: list[int], x_scale: float) -> dict:
    # Only consecutive *observed* samples count. Crossing an occlusion or an
    # interpolation is not a measured one-frame displacement.
    steps = []
    for i in range(1, len(states)):
        if states[i - 1] != "observed" or states[i] != "observed":
            continue
        if frame_indices[i] - frame_indices[i - 1] != 1:
            continue
        previous, current = points[i - 1], points[i]
        if previous is None or current is None:
            continue
        distance = math.hypot((current[0] - previous[0]) * x_scale,
                              current[1] - previous[1])
        steps.append((frame_indices[i], distance))
    distances = [distance for _, distance in steps]
    typical = median(distances) if distances else None
    mad = median([abs(value - typical) for value in distances]) if distances else None
    # A review candidate, not a declaration of incorrect keypoints. Fast arm
    # motion can also produce a large image-plane displacement.
    threshold = max(0.05, typical + 6 * mad) if distances else None
    candidates = [frame for frame, value in steps if value > threshold] if threshold is not None else []
    return {
        "unit": "image_height_per_adjacent_frame",
        "observed_adjacent_pairs": len(steps),
        "median": typical,
        "median_absolute_deviation": mad,
        "max": max(distances) if distances else None,
        "candidate_threshold": threshold,
        "candidate_frames": candidates,
        "candidate_count": len(candidates),
        "interpretation": "Review candidates only; genuine fast motion may exceed the heuristic threshold.",
    }


def _classify_joint(report: dict, total_frames: int) -> tuple[str, list[str]]:
    coverage = report["raw_coverage"]
    missing = report["longest_missing_span_frames"]
    interpolation = report["interpolation_usage"]["fraction_of_frames"]
    jumps = report["frame_to_frame_jump"]["candidate_count"]
    unobserved_limit = max(5, math.ceil(0.10 * total_frames))
    reasons = []
    if coverage < 0.50:
        reasons.append(f"Quality-gated raw coverage {coverage:.1%} is below the provisional 50% evidence floor.")
    if missing > unobserved_limit:
        reasons.append(f"Longest missing span {missing} frames exceeds the provisional {unobserved_limit}-frame review limit.")
    if reasons:
        return "unreliable", reasons
    if coverage >= 0.85 and missing <= 2 and interpolation <= 0.10 and jumps == 0:
        return "reliable", [
            f"Quality-gated raw coverage {coverage:.1%}; longest missing span {missing} frames; "
            f"interpolation {interpolation:.1%}; no jump candidates."
        ]
    if coverage < 0.85:
        reasons.append(f"Quality-gated raw coverage {coverage:.1%} is below the provisional 85% reliable band.")
    if missing > 2:
        reasons.append(f"Longest missing span is {missing} frames.")
    if interpolation > 0.10:
        reasons.append(f"Interpolated frames account for {interpolation:.1%} of this joint's timeline.")
    if jumps:
        reasons.append(f"{jumps} observed-frame jump candidate(s) need visual review.")
    return "partially_reliable", reasons


def _left_right_consistency(joints: dict, frame_indices: list[int], x_scale: float) -> dict:
    pairs = {}
    for part in _BODY_PAIRS:
        left, right = joints.get(f"LEFT_{part}"), joints.get(f"RIGHT_{part}")
        if left is None or right is None:
            continue
        orientation = []
        for i, frame in enumerate(frame_indices):
            if left["frame_states"][i] != "observed" or right["frame_states"][i] != "observed":
                continue
            left_x, right_x = left["_points"][i], right["_points"][i]
            if left_x is None or right_x is None:
                continue
            delta = (right_x[0] - left_x[0]) * x_scale
            if abs(delta) < 0.01:
                continue
            orientation.append((frame, 1 if delta > 0 else -1))
        flips = [orientation[i][0] for i in range(1, len(orientation))
                 if orientation[i][0] - orientation[i - 1][0] == 1
                 and orientation[i][1] != orientation[i - 1][1]]
        transient = [orientation[i][0] for i in range(1, len(orientation) - 1)
                     if orientation[i][0] - orientation[i - 1][0] == 1
                     and orientation[i + 1][0] - orientation[i][0] == 1
                     and orientation[i - 1][1] == orientation[i + 1][1] != orientation[i][1]]
        pairs[part.lower()] = {
            "observed_pair_frames": len(orientation),
            "image_order_sign_change_frames": flips,
            "single_frame_reversal_candidates": transient,
        }
    return {
        "pairs": pairs,
        "interpretation": "Image ordering can change with body rotation; a sign change alone is not an anatomical swap or identity switch.",
    }


def evaluate_pose_reliability(analysis_dir: str | Path) -> dict:
    """Evaluate one existing analysis directory without modifying its artifacts.

    The per-frame ``frame_states`` arrays align with ``frame_indices``. Raw
    coverage counts only quality-gated, directly observed coordinates; raw
    coordinates rejected for visibility/presence are not credited as observed.
    """
    source = Path(analysis_dir)
    clean_path = source / "pose_clean.csv"
    context = _load_json(source / "pose_clean.clean.json")
    quality = _load_json(source / "keypoint_quality.json")
    manifest = _load_json(source / "input_manifest.json")
    throwing_side = str(manifest["pitcher"]["throws"]).upper()
    if throwing_side not in {"LEFT", "RIGHT"}:
        raise ValueError("Pitcher throwing side must be LEFT or RIGHT")
    lead_side = "LEFT" if throwing_side == "RIGHT" else "RIGHT"
    first = int(context["timeline_start_frame"])
    last = int(context["timeline_end_frame"])
    if last < first:
        raise ValueError("Invalid pose timeline")
    frame_indices = list(range(first, last + 1))
    total_frames = len(frame_indices)
    if total_frames != int(quality["total_frames"]):
        raise ValueError("Pose timeline differs from keypoint quality total_frames")
    x_scale = float(context["coordinate_x_scale"])
    if not math.isfinite(x_scale) or x_scale <= 0:
        raise ValueError("Invalid coordinate scale")

    rows: dict[str, dict[int, dict]] = {}
    with clean_path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            frame = int(row["frame"])
            if frame < first or frame > last:
                raise ValueError(f"Pose row outside declared timeline: {frame}")
            name = row["landmark"]
            if frame in rows.setdefault(name, {}):
                raise ValueError(f"Duplicate pose row: {name} frame {frame}")
            rows[name][frame] = row
    important = {
        "throwing_shoulder": f"{throwing_side}_SHOULDER",
        "throwing_elbow": f"{throwing_side}_ELBOW",
        "throwing_wrist": f"{throwing_side}_WRIST",
        "lead_hip": f"{lead_side}_HIP",
        "lead_knee": f"{lead_side}_KNEE",
        "lead_ankle": f"{lead_side}_ANKLE",
    }
    for name in important.values():
        rows.setdefault(name, {})

    joints = {}
    for name in sorted(rows):
        states, points, raw_vis, observed_vis = [], [], [], []
        raw_predictions = 0
        for frame in frame_indices:
            row = rows[name].get(frame)
            if row is None:
                states.append("missing")
                points.append(None)
                continue
            x_raw, y_raw = _float(row.get("x_raw")), _float(row.get("y_raw"))
            x, y = _float(row.get("x")), _float(row.get("y"))
            visibility = _float(row.get("visibility"))
            if x_raw is not None and y_raw is not None and _bool(row.get("source_frame_detected")):
                raw_predictions += 1
                if visibility is not None:
                    raw_vis.append(visibility)
            if x is None or y is None or not _bool(row.get("usable")):
                state = "missing"
                point = None
            elif _bool(row.get("interpolated")):
                state = "interpolated"
                point = (x, y)
            elif (_bool(row.get("quality_valid")) and
                  _bool(row.get("source_frame_detected")) and
                  x_raw is not None and y_raw is not None):
                state = "observed"
                point = (x, y)
                if visibility is not None:
                    observed_vis.append(visibility)
            else:
                state = "missing"
                point = None
            states.append(state)
            points.append(point)
        observed = states.count("observed")
        interpolated = states.count("interpolated")
        missing = states.count("missing")
        report = {
            "raw_prediction_coverage": raw_predictions / total_frames,
            "raw_coverage": observed / total_frames,
            "observed_frames": observed,
            "interpolated_frames": interpolated,
            "missing_frames": missing,
            "frame_states": states,
            "visibility_statistics": {
                "raw_prediction": _visibility(raw_vis),
                "quality_gated_observed": _visibility(observed_vis),
            },
            "longest_missing_span_frames": _longest_run(states, lambda state: state == "missing"),
            "longest_not_observed_span_frames": _longest_run(states, lambda state: state != "observed"),
            "interpolation_usage": {
                "frames": interpolated,
                "fraction_of_frames": interpolated / total_frames,
            },
            "frame_to_frame_jump": _jump_diagnostics(states, points, frame_indices, x_scale),
            "_points": points,
        }
        report["status"], report["reasons"] = _classify_joint(report, total_frames)
        joints[name] = report

    left_right = _left_right_consistency(joints, frame_indices, x_scale)
    for report in joints.values():
        del report["_points"]
    critical = [joints[name]["status"] for name in important.values()]
    clip_status = max(critical, key=_RELIABILITY_ORDER.__getitem__)
    throwing_status = max((joints[important[role]]["status"] for role in
                           ("throwing_shoulder", "throwing_elbow", "throwing_wrist")),
                          key=_RELIABILITY_ORDER.__getitem__)
    return {
        "schema_version": "pose-reliability-v1",
        "pitch_id": manifest["pitch_id"],
        "pitcher_id": manifest["pitcher"]["id"],
        "source_artifacts": {
            "pose_clean_csv": "pose_clean.csv",
            "pose_clean_sha256": hashlib.sha256(clean_path.read_bytes()).hexdigest(),
            "keypoint_quality_json": "keypoint_quality.json",
            "input_manifest_json": "input_manifest.json",
        },
        "scope": "provisional image-plane signal quality; not ground-truth keypoint accuracy or pitcher identity",
        "ground_truth_evaluated": False,
        "policy": {
            "status": "provisional; requires calibration against human ground truth",
            "raw_coverage_definition": "quality-gated direct observations divided by declared clip frames",
            "reliable": "raw coverage >= 85%, longest missing <= 2 frames, interpolation <= 10%, no jump candidates",
            "unreliable": "raw coverage < 50% or longest missing span > max(5 frames, 10% of clip)",
            "partially_reliable": "between reliable and unreliable bands",
            "jump_candidate": "adjacent observed displacement > max(0.05 image heights, median + 6 median absolute deviations)",
        },
        "frame_indices": frame_indices,
        "total_frames": total_frames,
        "valid_pose_ratio": quality["valid_pose_ratio"],
        "longest_missing_pose_gap_frames": quality["longest_missing_pose_gap"],
        "important_joints": important,
        "joints": joints,
        "left_right_consistency": left_right,
        "throwing_side_reliability": {
            "status": throwing_status,
            "joint_statuses": {role: joints[important[role]]["status"] for role in
                               ("throwing_shoulder", "throwing_elbow", "throwing_wrist")},
            "reason": "Conservative worst status among throwing shoulder, elbow, and wrist; not a biomechanical accuracy claim.",
        },
        "status": clip_status,
        "reasons": [f"{role}: {joints[name]['status']}; {joints[name]['reasons'][0]}"
                    for role, name in important.items() if joints[name]["status"] != "reliable"]
                   or ["All six important joints meet the provisional signal-quality band."],
    }


def write_pose_reliability(analysis_dir: str | Path, output_path: str | Path | None = None) -> Path:
    """Write diagnostics, optionally outside the immutable source analysis."""
    target = Path(output_path) if output_path is not None else Path(analysis_dir) / "pose_reliability.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evaluate_pose_reliability(analysis_dir), indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")
    return target
