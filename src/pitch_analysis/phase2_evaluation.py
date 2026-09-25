"""Compare reliability warnings with independent human labels when available.

This is diagnostic agreement, not calibrated identity or 2-D coordinate
accuracy. Empty ground-truth templates never become negative labels.
"""
from __future__ import annotations

from collections import Counter


_SWITCH_WARNINGS = {"body_center_jump", "skeleton_scale_jump", "motion_discontinuity"}


def _interval_frames(intervals: list[dict]) -> set[int]:
    return {frame for item in intervals
            for frame in range(item["start_frame"], item["end_frame"] + 1)}


def _joint_agreement(intervals: list[dict], states: list[str], total: int) -> dict:
    labels = [None] * total
    for item in intervals:
        for frame in range(item["start_frame"], item["end_frame"] + 1):
            labels[frame] = item["status"]
    counts = {label: dict(Counter(states[i] for i in range(total) if labels[i] == label))
              for label in ("reliable", "unreliable", "uncertain")}
    unsafe_observed = counts["unreliable"].get("observed", 0)
    reliable_unobserved = (counts["reliable"].get("interpolated", 0) +
                           counts["reliable"].get("missing", 0))
    return {
        "human_label_by_model_state": counts,
        "observed_but_human_unreliable_frames": unsafe_observed,
        "human_reliable_but_model_unobserved_frames": reliable_unobserved,
        "interpretation": "Observed means a quality-gated model coordinate exists; it does not establish location accuracy.",
    }


def evaluate_against_ground_truth(ground_truth: dict, pose: dict, tracking: dict) -> dict:
    """Score only reviewed labels; otherwise return explicit unmeasured fields."""
    status = ground_truth["annotation_status"]
    if status != "reviewed":
        return {
            "status": "pending_human_ground_truth",
            "ground_truth_status": status,
            "correct_pitcher": None,
            "identity_switch_warning_agreement": None,
            "major_pose_failure_screening": None,
            "joint_reliability_agreement": None,
            "event_accuracy": None,
            "keypoint_coordinate_accuracy": None,
            "reason": "Human labels are incomplete; model predictions cannot serve as ground truth.",
        }

    labels = ground_truth["labels"]
    total = ground_truth["source_video"]["total_frames"]
    if total != pose["total_frames"] or total != tracking["total_frames"]:
        raise ValueError("Human annotation timeline differs from model output")
    throwing_elbow = pose["important_joints"]["throwing_elbow"]
    lead_knee = pose["important_joints"]["lead_knee"]
    for name in (throwing_elbow, lead_knee):
        if len(pose["joints"][name]["frame_states"]) != total:
            raise ValueError("Joint frame-state timeline is incomplete")
    if len(tracking["frames"]) != total:
        raise ValueError("Tracking frame-state timeline is incomplete")

    human_switch = _interval_frames(labels["identity_switch_intervals"])
    warning = {event["frame_index"] for event in tracking["warning_events"]
               if event["type"] in _SWITCH_WARNINGS}
    human_failure = _interval_frames(labels["major_pose_failure_intervals"])
    model_failure_screen = {entry["frame_index"] for entry in tracking["frames"]
                            if entry["selection_status"] != "selected" or entry["warnings"]}
    events = {name: value["frame_index"] if value["status"] == "annotated" else None
              for name, value in labels["events"].items()}
    return {
        "status": "human_comparison_available",
        "ground_truth_status": "reviewed",
        "correct_pitcher": labels["pitcher_correctly_selected"],
        "identity_switch_warning_agreement": {
            "human_switch_frames": len(human_switch),
            "warning_frames": len(warning),
            "warning_on_human_switch_frames": len(warning & human_switch),
            "unwarned_human_switch_frames": len(human_switch - warning),
            "warning_outside_human_switch_frames": len(warning - human_switch),
            "interpretation": "Frame-level screening comparison; a warning can mark only a switch boundary, not its full interval.",
        },
        "major_pose_failure_screening": {
            "human_failure_frames": len(human_failure),
            "screened_human_failure_frames": len(model_failure_screen & human_failure),
            "unscreened_human_failure_frames": len(human_failure - model_failure_screen),
            "screened_other_frames": len(model_failure_screen - human_failure),
        },
        "joint_reliability_agreement": {
            "throwing_elbow": _joint_agreement(labels["throwing_elbow_reliability"],
                                                pose["joints"][throwing_elbow]["frame_states"], total),
            "lead_knee": _joint_agreement(labels["lead_knee_reliability"],
                                          pose["joints"][lead_knee]["frame_states"], total),
        },
        "human_event_frames": events,
        "event_accuracy": None,
        "keypoint_coordinate_accuracy": None,
        "unmeasured_reasons": [
            "No automatic Phase 2 event estimates are produced for timing-error measurement.",
            "Human joint reliability intervals do not contain reference X/Y coordinates for localization error.",
        ],
    }
