"""GT-blind, pure feature extraction for the frozen joint quality experiment.

The caller owns the explicit source allowlist, hash verification and exclusive
output writes. This module opens no files and performs no model inference.
Original pose states are context only, never classifier features.
"""
from __future__ import annotations

import math
from pathlib import PureWindowsPath


ROLES = ("throwing_elbow", "throwing_wrist")
FEATURE_NAMES = (
    "raw_visibility", "raw_presence", "raw_in_source",
    "speed_diagonal_per_second", "acceleration_diagonal_per_second_squared",
    "compatible_distance_diagonal_min", "compatible_distance_diagonal_max",
    "compatible_distance_diagonal_range", "native_joint_score_min",
    "native_joint_score_max", "compatible_candidate_count",
    "no_compatible_candidates", "candidate_ambiguity",
)
CONTINUOUS_INDICES = [0, 1, 3, 4, 5, 6, 7, 8, 9]
NATIVE_JOINTS = (
    "NOSE", "LEFT_EYE", "RIGHT_EYE", "LEFT_EAR", "RIGHT_EAR",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
)
JOINTS = NATIVE_JOINTS[5:]
COORDINATE_CONVENTION = "continuous pixel-edge XY: source [0,width] x [0,height]; no clipping"


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _inside(xy, width, height):
    return 0 <= xy[0] < width and 0 <= xy[1] < height


def _close(actual, expected, message):
    if actual is None or expected is None:
        valid = actual is expected
    else:
        valid = _finite(actual) and _finite(expected) and math.isclose(
            actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    if not valid:
        raise ValueError(message)


def _path_matches(actual, relative):
    """Compare saved absolute Windows paths with repository-relative refs."""
    actual = PureWindowsPath(actual).as_posix().casefold().rstrip("/")
    relative = PureWindowsPath(relative).as_posix().casefold().rstrip("/")
    return actual == relative or actual.endswith("/" + relative)


def _raw_point(point, target):
    finite = point is not None and all(_finite(point.get(key)) for key in (
        "x", "y", "visibility", "presence"))
    xy = [point["x"] * target["width"], point["y"] * target["height"]] if finite else None
    finite = finite and all(_finite(value) for value in xy)
    return {"finite": finite, "xy_px": xy if finite else None,
            "visibility": point["visibility"] if finite else None,
            "presence": point["presence"] if finite else None,
            "in_source": _inside(xy, target["width"], target["height"]) if finite else None}


def _native_slots(frame, target):
    """Reproduce sealed six-slot coordinates without reading evaluation code."""
    geom = frame["input_geometry"]
    if (geom["source_width"] != target["width"] or geom["source_height"] != target["height"] or
            geom["target_width"] != 256 or geom["target_height"] != 256 or
            geom["coordinate_convention"] != COORDINATE_CONVENTION):
        raise ValueError("Native geometry source identity differs")
    for axis, before, after in (("width", "left", "right"), ("height", "top", "bottom")):
        extent = geom["resized_" + axis]
        pads = [geom["pad_" + part] for part in (before, after)]
        if (any(type(value) is not int for value in [extent, *pads]) or extent <= 0 or
                any(value < 0 for value in pads) or extent + sum(pads) != 256 or
                not _finite(geom["scale_x" if axis == "width" else "scale_y"]) or
                geom["scale_x" if axis == "width" else "scale_y"] != extent / target[axis]):
            raise ValueError("Native resize/padding inverse differs")
    output = frame["native_output"]
    if (len(output) != 1 or len(output[0]) != 6 or
            any(len(row) != 56 or not all(_finite(value) for value in row) for row in output[0])):
        raise ValueError("Native six-slot shape or finite values differ")
    slots = []
    for index, row in enumerate(output[0]):
        points = [list(row[start:start + 3]) for start in range(0, 51, 3)]
        if any(not 0 <= point[2] <= 1 for point in points) or not 0 <= row[55] <= 1:
            raise ValueError("Native score is outside its contract")
        slots.append({"slot_index": index, "native_yx_score": points,
            "source_xy": [[(x * 256 - geom["pad_left"]) / geom["scale_x"],
                           (y * 256 - geom["pad_top"]) / geom["scale_y"]] for y, x, _ in points],
            "native_box_ymin_xmin_ymax_xmax_score": list(row[51:]),
            "joint_order": list(NATIVE_JOINTS), "subject_identity": None,
            "observability": None, "reliability_status": None})
    if slots != frame["slots"]:
        raise ValueError("Native slot coordinates/scores do not reproduce")
    return slots


def _mapping(disagreement):
    mapping = disagreement["important_joints"]
    throwing = mapping["throwing_shoulder"].split("_")[0]
    if throwing not in {"LEFT", "RIGHT"}:
        raise ValueError("Invalid throwing side mapping")
    lead = "LEFT" if throwing == "RIGHT" else "RIGHT"
    expected = {role: (throwing if role.startswith("throwing_") else lead) + "_" + role.split("_")[1].upper()
                for role in ("throwing_shoulder", *ROLES, "lead_hip", "lead_knee", "lead_ankle")}
    if mapping != expected:
        raise ValueError("Inconsistent throwing/lead role mapping")
    return dict(mapping)


def _verify_sources(raw, capture, config, disagreement, native):
    target = disagreement["target"]
    if (set(target) != {"pitch_id", "total_frames", "width", "height"} or
            not isinstance(target["pitch_id"], str) or not target["pitch_id"] or
            any(type(target[key]) is not int or target[key] <= 0 for key in ("total_frames", "width", "height"))):
        raise ValueError("Invalid feature source target")
    total = target["total_frames"]
    if (disagreement["status"] != "sealed_joint_disagreement_only" or
            disagreement["human_annotation_inputs"] != [] or
            native["status"] != "sealed_measurements_only" or native["human_annotation_inputs"] != [] or
            native["target"] != target or
            any(native[key] != total for key in ("total_frames", "completed_frames", "inference_calls")) or
            disagreement["source_frames"] != total or disagreement["non_seed_frames"] != total - 1 or
            any(len(data) != total for data in (raw, capture["selection_frames"], disagreement["frames"], native["frames"]))):
        raise ValueError("Incomplete or contaminated feature source")
    if ((capture["width"], capture["height"], capture["start_frame"], capture["end_frame"],
         capture["requested_frames"], capture["processed_frames"]) !=
            (target["width"], target["height"], 0, total - 1, total, total) or
            (config["width"], config["height"], config["timeline_start_frame"], config["timeline_end_frame"],
             config["requested_frames"]) != (target["width"], target["height"], 0, total - 1, total)):
        raise ValueError("Capture/config source dimensions or range differ")
    refs = disagreement["source_references"]
    if (not _path_matches(capture["video"], native["source_references"]["video"]["path"]) or
            not _path_matches(config["source_pose_csv"], refs["original_raw"]["path"]) or
            not _path_matches(config["source_context"], refs["capture"]["path"])):
        raise ValueError("Capture/config source path differs")
    if not all(_finite(config[key]) for key in ("min_visibility", "min_presence")):
        raise ValueError("Nonfinite original gate")
    previous = None
    for index, (cap, measured, original) in enumerate(zip(
            capture["selection_frames"], disagreement["frames"], native["frames"], strict=True)):
        timestamps = [cap["timestamp_ms"], measured["capture_timestamp_ms"],
                      measured["native_timestamp_ms"], original["native_timestamp_ms"]]
        if (any(row["frame_index"] != index for row in (cap, measured, original)) or
                not all(_finite(value) for value in timestamps) or timestamps[0] != timestamps[1] or
                abs(timestamps[0] - timestamps[2]) > 1 or timestamps[2] != timestamps[3] or
                original["timestamp_ms"] != round(timestamps[3]) or
                measured["decoded_bgr_sha256"] != original["decoded_bgr_sha256"] or
                measured["effectiveness_eligible"] is not (index != 0) or
                (previous is not None and timestamps[0] <= previous)):
            raise ValueError("Capture/native/disagreement frame timeline differs")
        if index == 0 and timestamps[0] != 0:
            raise ValueError("Frame zero capture time must be zero")
        previous = timestamps[0]
    return dict(target)


def _verified_frame(points, measured, native_frame, target):
    slots = _native_slots(native_frame, target)
    candidates = measured["candidate_slot_indices"]
    if (not isinstance(candidates, list) or candidates != sorted(set(candidates)) or
            any(type(value) is not int or not 0 <= value < 6 for value in candidates)):
        raise ValueError("Invalid compatible candidate slots")
    expected_status = "none" if not candidates else "unique_geometric_candidate" if len(candidates) == 1 else "ambiguous"
    if measured["association_status"] != expected_status:
        raise ValueError("Candidate ambiguity context differs")
    diagonal = math.hypot(target["width"], target["height"])
    verified = {}
    for name in JOINTS:
        joint = measured["joints"][name]
        raw = _raw_point(points.get(name), target)
        if raw != joint["raw"] or joint["baseline_model_state"] not in {"observed", "interpolated", "missing"}:
            raise ValueError("Original raw point/score or state differs")
        expected_rows = []
        native_index = NATIVE_JOINTS.index(name)
        for slot in slots:
            xy = slot["source_xy"][native_index]
            distance = math.dist(raw["xy_px"], xy) if raw["finite"] else None
            expected_rows.append({"slot_index": slot["slot_index"],
                "geometric_candidate": slot["slot_index"] in candidates,
                "native_xy_px": xy, "native_joint_score": slot["native_yx_score"][native_index][2],
                "native_in_source": _inside(xy, target["width"], target["height"]),
                "distance_px": distance, "distance_diagonal": distance / diagonal if distance is not None else None})
        if joint["slot_distances"] != expected_rows:
            raise ValueError("Sealed same-joint native distance/score differs")
        compatible = [row for row in expected_rows if row["geometric_candidate"]]
        if joint["candidate_distances"] != compatible:
            raise ValueError("Compatible candidate list does not retain every slot")
        for units, field in (("px", "distance_px"), ("diagonal", "distance_diagonal")):
            values = [row[field] for row in compatible if row[field] is not None]
            for key, expected in (("min", min(values) if values else None), ("max", max(values) if values else None)):
                _close(joint["distance_range_" + units][key], expected, "Sealed distance range differs")
        verified[name] = {"raw": raw, "model_state": joint["baseline_model_state"], "compatible": compatible}
    return verified


def build_clip(raw, capture, config, disagreement, native):
    """Return all source rows; consume no GT, labels, manual XY or future frames."""
    target = _verify_sources(raw, capture, config, disagreement, native)
    mapping = _mapping(disagreement)
    verified = [_verified_frame(points, measured, original, target) for points, measured, original in zip(
        raw, disagreement["frames"], native["frames"], strict=True)]
    diagonal = math.hypot(target["width"], target["height"])
    times = [frame["timestamp_ms"] / 1000 for frame in capture["selection_frames"]]
    frames = []
    for index, joints in enumerate(verified):
        roles = {}
        for role in ROLES:
            name = mapping[role]
            joint, point = joints[name], joints[name]["raw"]
            compatible = joint["compatible"]
            count = len(compatible)
            features = [None] * len(FEATURE_NAMES)
            reasons = {}
            if point["finite"]:
                features[:3] = [float(point["visibility"]), float(point["presence"]), float(point["in_source"])]
            else:
                for feature in FEATURE_NAMES[:3]:
                    reasons[feature] = "raw_missing_or_nonfinite"
            velocities = []
            for current in (index, index - 1):
                if current > 0 and all(verified[pos][name]["raw"]["finite"] for pos in (current - 1, current)):
                    before, after = (verified[pos][name]["raw"]["xy_px"] for pos in (current - 1, current))
                    dt = times[current] - times[current - 1]
                    velocities.append([(after[axis] - before[axis]) / diagonal / dt for axis in (0, 1)])
                else:
                    velocities.append(None)
            if velocities[0] is not None:
                features[3] = math.hypot(*velocities[0])
            else:
                reasons[FEATURE_NAMES[3]] = "continuous_current_and_previous_raw_required"
            if all(velocity is not None for velocity in velocities):
                midpoint_dt = (times[index] - times[index - 2]) / 2
                features[4] = math.hypot(*(velocities[0][axis] - velocities[1][axis] for axis in (0, 1))) / midpoint_dt
            else:
                reasons[FEATURE_NAMES[4]] = "continuous_current_and_two_previous_raw_required"
            distances = [row["distance_diagonal"] for row in compatible]
            if count and point["finite"]:
                features[5:8] = [min(distances), max(distances), max(distances) - min(distances)]
            else:
                for feature in FEATURE_NAMES[5:8]:
                    reasons[feature] = "no_compatible_candidates" if not count else "raw_missing_or_nonfinite"
            if count:
                scores = [row["native_joint_score"] for row in compatible]
                features[8:10] = [min(scores), max(scores)]
            else:
                for feature in FEATURE_NAMES[8:10]:
                    reasons[feature] = "no_compatible_candidates"
            features[10:13] = [float(count), float(count == 0), float(count > 1)]
            if any(value is not None and not _finite(value) for value in features):
                raise ValueError("Nonfinite derived feature")
            roles[role] = {"landmark": name, "raw_finite": point["finite"],
                "raw_gate_pass": point["finite"] and point["visibility"] >= config["min_visibility"] and point["presence"] >= config["min_presence"],
                "model_state": joint["model_state"], "raw_xy_px": point["xy_px"],
                "evidence_status": "available" if point["finite"] else "insufficient_evidence",
                "features": [float(value) if value is not None else None for value in features],
                "missing_reasons": reasons,
                "compatible_candidates": [dict(row) for row in compatible]}
        frames.append({"frame_index": index, "timestamp_ms": capture["selection_frames"][index]["timestamp_ms"],
                       "effectiveness_eligible": index != 0, "roles": roles})
    return {"status": "sealed_gt_blind_joint_quality_features", "target": target,
        "important_joints": mapping, "feature_names": list(FEATURE_NAMES),
        "continuous_indices": list(CONTINUOUS_INDICES), "source_frames": target["total_frames"],
        "non_seed_frames": target["total_frames"] - 1, "human_annotation_inputs": [],
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "frames": frames}
