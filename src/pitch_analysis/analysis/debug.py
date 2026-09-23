"""Auditable per-frame pose outputs for the rear-centerfield baseline."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean, median

from ..io import read_pose_csv
from ..pose_capture import LANDMARK_NAMES
from ..temporal import median_smooth
from ..contracts import write_contract


CONNECTIONS = ((11, 12), (11, 13), (13, 15), (12, 14), (14, 16),
               (11, 23), (12, 24), (23, 24), (23, 25), (25, 27),
               (24, 26), (26, 28), (27, 31), (28, 32))


def write_pose_debug(output: Path, video: dict, capture: dict, throwing_side: str,
                     quality_gate_passed: bool) -> dict:
    """Keep raw/cleaned traces and a diagnostic overlay, never infer events."""
    import cv2

    count = video["frame_count"]
    raw = read_pose_csv(output / "pose_raw.csv")
    cleaned: dict[int, dict[str, dict]] = {}
    clean_path = output / "pose_clean.csv"
    if clean_path.exists():
        with clean_path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                frame = int(row["frame"])
                cleaned.setdefault(frame, {})[row["landmark"]] = {
                    "x": float(row["x"]) if row["x"] else None,
                    "y": float(row["y"]) if row["y"] else None,
                    "usable": row["usable"].lower() == "true",
                    "interpolated": row["interpolated"].lower() == "true",
                    "quality_valid": row["quality_valid"].lower() == "true",
                }
        for name in LANDMARK_NAMES:
            for axis in ("x", "y"):
                values = [cleaned.get(frame, {}).get(name, {}).get(axis) for frame in range(count)]
                smoothed = median_smooth(values, radius=1)
                for frame in range(count):
                    point = cleaned.get(frame, {}).get(name)
                    if point is not None:
                        point[axis + "_smoothed"] = smoothed[frame] if point["usable"] else None
    selections = {entry["frame_index"]: entry for entry in capture.get("selection_frames", [])}
    raw_stream = output / "keypoints.jsonl"
    processed_stream = output / "processed_keypoints.jsonl"
    interpolated_frames = 0
    confidences = []
    with raw_stream.open("w", encoding="utf-8") as raw_sink, processed_stream.open("w", encoding="utf-8") as processed_sink:
        for frame in range(count):
            timestamp_ms = video["timestamps_ms"][frame]
            selected = selections.get(frame, {})
            raw_points = raw.get(frame, {})
            clean_points = cleaned.get(frame, {})
            if any(point["interpolated"] for point in clean_points.values()):
                interpolated_frames += 1
            for point in raw_points.values():
                if point.get("visibility") is not None:
                    confidences.append(point["visibility"])
            raw_record = {"frame_index": frame, "timestamp_ms": timestamp_ms,
                          "selection": selected.get("status", "unknown"),
                          "landmarks": raw_points}
            processed_record = {"frame_index": frame, "timestamp_ms": timestamp_ms,
                                "coordinate_processing": "confidence_presence_gate_and_short_gap_interpolation; three_frame_median_xy_is_visualization_only; feature_smoothing_is_downstream",
                                "landmarks": clean_points}
            raw_sink.write(json.dumps(raw_record, allow_nan=False) + "\n")
            processed_sink.write(json.dumps(processed_record, allow_nan=False) + "\n")
    wrist_name = throwing_side + "_WRIST"
    x_scale = video["width"] / video["height"]
    torso_sizes = []
    for pose in cleaned.values():
        joints = [pose.get(name) for name in ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP")]
        if all(joint and joint["usable"] and not joint["interpolated"] for joint in joints):
            shoulder_x = (joints[0]["x"] + joints[1]["x"]) / 2
            shoulder_y = (joints[0]["y"] + joints[1]["y"]) / 2
            hip_x = (joints[2]["x"] + joints[3]["x"]) / 2
            hip_y = (joints[2]["y"] + joints[3]["y"]) / 2
            torso_sizes.append(((shoulder_x - hip_x) ** 2 * x_scale ** 2 + (shoulder_y - hip_y) ** 2) ** .5)
    torso_scale = median(torso_sizes) if torso_sizes else None
    trajectory = []
    for frame in range(count):
        pose = cleaned.get(frame, {})
        wrist, left_hip, right_hip = (pose.get(name) for name in (wrist_name, "LEFT_HIP", "RIGHT_HIP"))
        if torso_scale and torso_scale > .01 and all(point and point["usable"] for point in (wrist, left_hip, right_hip)):
            hip_x = (left_hip["x"] + right_hip["x"]) / 2
            hip_y = (left_hip["y"] + right_hip["y"]) / 2
            direction = 1 if throwing_side == "RIGHT" else -1
            x = direction * (wrist["x"] - hip_x) * x_scale / torso_scale
            y = (wrist["y"] - hip_y) / torso_scale
            interpolated = any(point["interpolated"] for point in (wrist, left_hip, right_hip))
        else:
            x = y = None
            interpolated = False
        trajectory.append({"frame_index": frame, "timestamp_ms": video["timestamps_ms"][frame],
                           "x": x, "y": y, "interpolated": interpolated})
    (output / "wrist_trajectory.json").write_text(json.dumps({
        "schema_version": "wrist-trajectory-v1", "observability": "estimated_2d_body_relative",
        "coordinate_system": "hip-centered image plane; x aspect-corrected and mirrored for LEFT throws; median projected torso length = 1",
        "torso_scale_image_height": torso_scale, "throwing_side": throwing_side,
        "points": trajectory,
        "limitations": "Not a 3D arm path or release-position measurement; depends on view, occlusion and projected torso scale.",
    }, indent=2, allow_nan=False), encoding="utf-8")
    selected_count = sum(entry.get("status") == "selected" for entry in selections.values())
    rejected_count = count - selected_count
    missing = 0
    longest_missing = 0
    for frame in range(count):
        if selections.get(frame, {}).get("status") != "selected":
            missing += 1
            longest_missing = max(longest_missing, missing)
        else:
            missing = 0
    ratio = selected_count / count
    if quality_gate_passed and ratio >= .9:
        status, reason = "success", None
    elif selected_count and ratio >= .5:
        status, reason = "degraded", "pose coverage or existing quality gate did not pass"
    else:
        status, reason = "failed", "no sufficiently continuous selected pitcher pose"
    summary = {"schema_version": "keypoint-quality-v1", "status": status,
               "failure_reason": reason, "total_frames": count,
               "frames_with_valid_pitcher_pose": selected_count, "valid_pose_ratio": ratio,
               "interpolated_frame_count": interpolated_frames,
               "rejected_frame_count": rejected_count,
               "mean_landmark_confidence": mean(confidences) if confidences else None,
               "longest_missing_pose_gap": longest_missing,
               "existing_quality_gate_passed": quality_gate_passed,
               "selection_protocol": capture.get("subject_selection") or "rear_centerfield_broadcast",
               "selection_frames": capture.get("selection_frames", []),
               "notes": ["Confidence is MediaPipe visibility, not calibrated coordinate accuracy.",
                         "This summary does not establish correct pitcher identity; inspect overlay and human review."]}
    write_contract(output / "keypoint_quality.json", summary, "keypoint-quality-v1")

    source = Path(video["path"])
    reader = cv2.VideoCapture(str(source))
    overlay_path = output / "overlay.mp4"
    writer = cv2.VideoWriter(str(overlay_path), cv2.VideoWriter_fourcc(*"mp4v"),
                             video["fps"], (video["width"], video["height"]))
    if not reader.isOpened() or not writer.isOpened():
        reader.release()
        writer.release()
        raise ValueError("Could not create pose debug overlay")
    try:
        for frame in range(count):
            ok, image = reader.read()
            if not ok:
                raise ValueError("Overlay decode ended before validated frame count")
            pose = raw.get(frame, {})
            def point(name: str):
                item = pose.get(name)
                if not item or min(item.get("visibility", 0), item.get("presence", 0)) < .35:
                    return None
                return int(item["x"] * video["width"]), int(item["y"] * video["height"])
            for start, end in CONNECTIONS:
                first, second = point(LANDMARK_NAMES[start]), point(LANDMARK_NAMES[end])
                if first and second:
                    cv2.line(image, first, second, (0, 240, 80), 2)
            for name in LANDMARK_NAMES:
                location = point(name)
                if location:
                    cv2.circle(image, location, 3, (0, 255, 255), -1)
            choice = selections.get(frame, {})
            label = f"frame {frame}  {video['timestamps_ms'][frame]:.0f} ms  {choice.get('status', 'unknown')}"
            detail = f"pitcher conf {choice.get('mean_confidence') or 0:.2f}  throw {throwing_side}  lead {'LEFT' if throwing_side == 'RIGHT' else 'RIGHT'}"
            color = (0, 220, 0) if choice.get("status") == "selected" else (0, 0, 255)
            cv2.rectangle(image, (0, 0), (min(image.shape[1], 660), 55), (0, 0, 0), -1)
            cv2.putText(image, label, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, .48, color, 1)
            cv2.putText(image, detail, (6, 43), cv2.FONT_HERSHEY_SIMPLEX, .42, color, 1)
            writer.write(image)
    finally:
        reader.release()
        writer.release()
    review_dir = output / "review"
    review_dir.mkdir(exist_ok=True)
    (review_dir / "human_validation_template.json").write_text(json.dumps({
        "schema_version": "human-validation-v1", "review_status": "pending",
        "pitcher_skeleton_correct": None, "throwing_arm_correct": None,
        "lead_leg_correct": None, "major_keypoints_plausible": None,
        "identity_switch_observed": None, "complete_delivery": None,
        "reviewer_notes": "", "registry_approval": False,
    }, indent=2), encoding="utf-8")
    return summary
