"""Conservative, camera-protocol-specific input triage.

Video-only preflight runs before pose inference. Pose evidence may later refine
the same report; it never overrides a definite camera cut or repairs a clip.
Thresholds are generic image/pose heuristics, not pitcher-specific rules or
calibrated probabilities. Human review remains required for semantic validity.
"""
from __future__ import annotations

from copy import deepcopy
from math import hypot
from pathlib import Path
from statistics import median


def scan_input_quality(video: dict) -> dict:
    """Decode frames to flag hard cuts and long freezes before MediaPipe runs."""
    import cv2
    import numpy as np

    capture = cv2.VideoCapture(str(video["path"]))
    if not capture.isOpened():
        raise ValueError("Cannot open prepared MP4 for input-quality scan")
    previous_image = previous_histogram = None
    boundaries: list[dict] = []
    freeze_run = longest_freeze = 0
    count = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            image = cv2.resize(frame, (96, 96), interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            histogram = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
            cv2.normalize(histogram, histogram)
            if previous_image is not None:
                pixel_change = float(np.mean(cv2.absdiff(image, previous_image)) / 255)
                color_change = float(cv2.compareHist(histogram, previous_histogram, cv2.HISTCMP_BHATTACHARYYA))
                freeze_run = freeze_run + 1 if pixel_change < .001 else 0
                longest_freeze = max(longest_freeze, freeze_run)
                if pixel_change >= .11 and color_change >= .12:
                    strength = "high" if pixel_change >= .12 and color_change >= .35 else "medium"
                    boundaries.append({"frame_index": count, "timestamp_ms": video["timestamps_ms"][count],
                                       "pixel_change": pixel_change, "color_histogram_change": color_change,
                                       "strength": strength})
            previous_image, previous_histogram = image, histogram
            count += 1
    finally:
        capture.release()
    if count != video["frame_count"]:
        raise ValueError("Input-quality scan decoded a different frame count from MP4 validation")
    strong = any(item["strength"] == "high" for item in boundaries)
    freeze_suspected = longest_freeze >= max(round(video["fps"]), round(count * .2))
    reasons = []
    if strong:
        reasons.append("high_confidence_shot_change")
    elif boundaries:
        reasons.append("possible_shot_change")
    if freeze_suspected:
        reasons.append("long_near_duplicate_frame_run")
    status = "rejected" if strong else "degraded" if reasons else "accepted"
    return {
        "schema_version": "input-quality-v1", "stage": "video_preflight", "status": status,
        "video_sha256": video["sha256"], "frame_count": count, "fps": video["fps"],
        "detected_shot_boundaries": boundaries,
        "camera_continuity": "discontinuous" if strong else "suspect" if boundaries else "no_cut_detected",
        "camera_view_consistency": "suspected_mixed_shots" if boundaries else "declared_unverified",
        "longest_invalid_span_frames": None, "pose_selection_ratio": None,
        "possible_identity_switch": None, "identity_transitions": [],
        "start_completeness": "unknown", "followthrough_completeness": "unknown",
        "slow_motion_replay": "freeze_or_replay_suspected" if freeze_suspected else "not_detected_not_excluded",
        "longest_near_duplicate_run_frames": longest_freeze,
        "reasons": reasons,
        "confidence": {"level": "high" if strong else "low", "calibrated": False,
                       "basis": "frame-difference and color-histogram heuristics; not a trained camera/replay classifier"},
        "uncertainties": ["No semantic camera-view classifier: rear-centerfield declaration still needs visual review.",
                          "CFR and duplicate-frame checks cannot prove normal playback speed or exclude replay.",
                          "Start, follow-through, subject identity and pose-invalid spans require later pose/manual evidence."],
    }


def _knee_height_ratio(pose: dict, lead_side: str) -> float | None:
    names = (lead_side + "_KNEE", ("LEFT" if lead_side == "RIGHT" else "RIGHT") + "_KNEE",
             "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ANKLE", "RIGHT_ANKLE")
    if not all(name in pose and pose[name].get("visibility", 0) >= .5 and pose[name].get("presence", 0) >= .5 for name in names):
        return None
    shoulder_y = (pose["LEFT_SHOULDER"]["y"] + pose["RIGHT_SHOULDER"]["y"]) / 2
    ankle_y = (pose["LEFT_ANKLE"]["y"] + pose["RIGHT_ANKLE"]["y"]) / 2
    body_height = ankle_y - shoulder_y
    return (pose[names[0]]["y"] - pose[names[1]]["y"]) / body_height if body_height > .1 else None


def refine_input_quality(preflight: dict, capture: dict, pose_frames: dict[int, dict],
                         *, throwing_side: str, quality_gate_passed: bool) -> dict:
    """Add selected-subject continuity and conservative delivery completeness cues."""
    report = deepcopy(preflight)
    report["stage"] = "post_pose"
    count, fps = report["frame_count"], report["fps"]
    selections = {row["frame_index"]: row for row in capture.get("selection_frames", [])}
    selected = [frame for frame in range(count) if selections.get(frame, {}).get("status") == "selected"]
    selected_set = set(selected)
    report["pose_selection_ratio"] = len(selected) / count
    longest = run = 0
    for frame in range(count):
        run = 0 if frame in pose_frames and frame in selected_set else run + 1
        longest = max(longest, run)
    report["longest_invalid_span_frames"] = longest

    transitions = []
    for earlier, later in zip(selected, selected[1:]):
        if not 1 < later - earlier <= max(2, round(.5 * fps)):
            continue
        first, second = pose_frames.get(earlier, {}), pose_frames.get(later, {})
        if not all(name in first and name in second for name in ("LEFT_HIP", "RIGHT_HIP")):
            continue
        if not all(pose[name].get("visibility", 0) >= .5 and pose[name].get("presence", 0) >= .5
                   for pose in (first, second) for name in ("LEFT_HIP", "RIGHT_HIP")):
            continue
        a = ((first["LEFT_HIP"]["x"] + first["RIGHT_HIP"]["x"]) / 2,
             (first["LEFT_HIP"]["y"] + first["RIGHT_HIP"]["y"]) / 2)
        b = ((second["LEFT_HIP"]["x"] + second["RIGHT_HIP"]["x"]) / 2,
             (second["LEFT_HIP"]["y"] + second["RIGHT_HIP"]["y"]) / 2)
        distance = hypot(a[0] - b[0], a[1] - b[1])
        if distance > .3:
            transitions.append({"last_frame_before_gap": earlier, "first_frame_after_gap": later,
                                "hip_center_jump_normalized_image": distance})
    report["identity_transitions"] = transitions
    report["possible_identity_switch"] = bool(transitions)

    lead_side = "LEFT" if throwing_side == "RIGHT" else "RIGHT"
    knee = {frame: value for frame in selected if (value := _knee_height_ratio(pose_frames.get(frame, {}), lead_side)) is not None}
    initial = [value for frame, value in knee.items() if frame < max(6, round(.2 * fps))]
    final = [value for frame, value in knee.items() if frame >= count - max(6, round(.2 * fps))]
    if selected and selected[0] > max(6, round(.2 * fps)):
        start = "incomplete"
    elif len(initial) >= 3:
        start = "incomplete" if median(initial) < -.15 else "plausible"
    else:
        start = "unknown"
    if selected and count - 1 - selected[-1] > max(6, round(.2 * fps)):
        follow = "incomplete"
    elif final and min(knee.values(), default=0) < -.15 and median(final) > -.1:
        follow = "plausible"
    else:
        follow = "unknown"
    report["start_completeness"], report["followthrough_completeness"] = start, follow

    reasons = report["reasons"]
    if transitions:
        reasons.append("possible_subject_identity_switch")
    if longest > max(round(fps), round(.25 * count)):
        reasons.append("long_pose_invalid_span")
    elif longest > max(2, round(.2 * fps)):
        reasons.append("pose_invalid_span_requires_review")
    if len(selected) / count < .5:
        reasons.append("low_pitcher_pose_coverage")
    if start == "incomplete":
        reasons.append("missing_preparation_phase")
    elif start == "unknown":
        reasons.append("preparation_phase_unverified")
    if follow == "incomplete":
        reasons.append("missing_followthrough_or_trailing_pose")
    elif follow == "unknown":
        reasons.append("followthrough_unverified")
    if not quality_gate_passed:
        reasons.append("existing_pose_feature_quality_gate_failed")
    hard_reject = (preflight["status"] == "rejected" or bool(transitions)
                   or longest > max(round(fps), round(.25 * count)) or len(selected) / count < .5)
    report["status"] = "rejected" if hard_reject else "degraded" if reasons else "accepted"
    report["confidence"] = {"level": "high" if preflight["status"] == "rejected" or transitions else "moderate" if report["status"] == "accepted" else "low",
                            "calibrated": False,
                            "basis": "video cuts, selected-pose spans, projected hip continuity and knee-height cues; not player ReID or event ground truth"}
    report["uncertainties"] = [
        "A selected skeleton is not verified MLB identity; overlay review is required.",
        "Knee-height start/follow-through cues are projected 2D proxies, not event annotation.",
        "No semantic camera or slow-motion classifier is available; human review remains required.",
    ]
    return report
