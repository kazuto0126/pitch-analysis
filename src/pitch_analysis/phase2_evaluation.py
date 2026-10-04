"""Compare reliability warnings with independent human labels when available.

This is diagnostic agreement, not calibrated identity or 2-D coordinate
accuracy. Empty ground-truth templates never become negative labels.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy

from pitch_analysis.ground_truth import FULL_JOINT_LABELS, validate_ground_truth


_SWITCH_WARNINGS = {"body_center_jump", "skeleton_scale_jump", "motion_discontinuity"}
_HUMAN_STATES = ("reliable", "unreliable", "uncertain", "not_observable")
_MODEL_STATES = ("observed", "interpolated", "missing")


def frame_ranges(frames) -> list[dict]:
    """Lossless, inclusive ranges; no tolerance or extension around warnings."""
    result = []
    for frame in sorted(set(frames)):
        if result and frame == result[-1]["end_frame"] + 1:
            result[-1]["end_frame"] = frame
        else:
            result.append({"start_frame": frame, "end_frame": frame})
    return result


def _screening(intervals: list[dict], predicted: set[int], total: int) -> dict:
    # The original frame-interval contract omitted status for confirmed spans.
    positive = _interval_frames([i for i in intervals if i.get("status", "confirmed") == "confirmed"])
    excluded = {status: _interval_frames([i for i in intervals if i.get("status", "confirmed") == status])
                for status in ("uncertain", "not_observable")}
    unknown = set().union(*excluded.values())
    negative = set(range(total)) - positive - unknown
    cells = {
        "true_positive": predicted & positive,
        "false_negative": positive - predicted,
        "false_positive": predicted & negative,
        "true_negative": negative - predicted,
    }
    tp, fp = len(cells["true_positive"]), len(cells["false_positive"])
    interval_results = []
    for item in intervals:
        span = set(range(item["start_frame"], item["end_frame"] + 1))
        interval_results.append({
            "human_interval": deepcopy(item),
            "screened_frames": len(span & predicted),
            "screened_ranges": frame_ranges(span & predicted),
            "scored": item.get("status", "confirmed") == "confirmed",
        })
    return {
        "human_positive_frames": len(positive),
        "human_negative_frames": len(negative),
        "excluded_frames_by_status": {s: len(f) for s, f in excluded.items()},
        "screened_frames_total": len(predicted),
        "screened_excluded_frames": len(predicted & unknown),
        **{name + "_frames": len(frames) for name, frames in cells.items()},
        "recall_on_confirmed_frames": tp / len(positive) if positive else None,
        "precision_on_scorable_frames": tp / (tp + fp) if tp + fp else None,
        "false_positive_rate_on_known_negative_frames": fp / len(negative) if negative else None,
        "ranges": {name: frame_ranges(frames) for name, frames in cells.items()},
        "excluded_ranges_by_status": {s: frame_ranges(f) for s, f in excluded.items()},
        "human_intervals": interval_results,
        "confirmed_interval_count": sum(i.get("status", "confirmed") == "confirmed" for i in intervals),
        "confirmed_intervals_with_any_screen": sum(
            i["scored"] and i["screened_frames"] > 0 for i in interval_results),
        "interpretation": (
            "Exact frame overlap with this specified screening cue, not a calibrated detector. "
            "Uncertain/unobservable frames are excluded, not negatives. A boundary cue need not "
            "cover an entire interval; any-overlap interval counts are reported separately. "
            "A false positive here can still be a useful warning for a different problem."
        ),
    }


def _checked_indices(values: list[int], total: int, label: str) -> set[int]:
    if any(type(i) is not int or not 0 <= i < total for i in values):
        raise ValueError(f"{label} has an invalid frame index")
    if len(set(values)) != len(values):
        raise ValueError(f"{label} has duplicate frame indices")
    return set(values)


def _full_joint_agreement(intervals: list[dict], joint: dict, total: int) -> dict:
    states = joint["frame_states"]
    if len(states) != total or any(s not in _MODEL_STATES for s in states):
        raise ValueError("Joint frame-state timeline is incomplete or invalid")
    human = [None] * total
    for item in intervals:
        human[item["start_frame"]:item["end_frame"] + 1] = [item["status"]] * (
            item["end_frame"] - item["start_frame"] + 1)
    counts = {h: {m: sum(a == h and b == m for a, b in zip(human, states))
                  for m in _MODEL_STATES} for h in _HUMAN_STATES}
    contrasts = {
        "observed_but_human_unreliable": {i for i in range(total)
                                            if human[i] == "unreliable" and states[i] == "observed"},
        "observed_but_human_not_observable": {i for i in range(total)
                                                if human[i] == "not_observable" and states[i] == "observed"},
        "human_reliable_but_model_unobserved": {i for i in range(total)
                                                 if human[i] == "reliable" and states[i] != "observed"},
    }
    jump_frames = _checked_indices(joint["frame_to_frame_jump"]["candidate_frames"], total, "Joint jump")
    # The jump marks the current endpoint of an adjacent-frame transition.
    # It is not an interval-wide error prediction or a new reliability gate.
    screening_labels = [{**item, "status": "confirmed" if item["status"] == "unreliable" else item["status"]}
                        for item in intervals if item["status"] != "reliable"]
    return {
        "model_joint_status": joint["status"],
        "model_joint_reasons": deepcopy(joint["reasons"]),
        "human_label_by_model_state": counts,
        "human_frame_counts": {h: sum(row.values()) for h, row in counts.items()},
        **{name + "_frames": len(frames) for name, frames in contrasts.items()},
        "contrast_ranges": {name: frame_ranges(frames) for name, frames in contrasts.items()},
        "joint_jump_endpoint_screening": _screening(screening_labels, jump_frames, total),
        "interpretation": (
            "Human labels judge source imagery and the raw overlay; model states describe processed "
            "quality-gated availability. This cross-tab is not processed-coordinate accuracy. "
            "Observed does not prove correct position; interpolated does not prove wrong position. "
            "Human not_observable is not a model error or a confirmed occlusion cause. "
            "Clip-level model flags are retained, not converted into invented per-frame predictions."
        ),
    }


def _evaluate_full_review(ground_truth: dict, pose: dict, tracking: dict) -> dict:
    validate_ground_truth(ground_truth)
    total = ground_truth["source_video"]["total_frames"]
    pitch_id = ground_truth["source_video"]["pitch_id"]
    if any(report.get("pitch_id") != pitch_id or report.get("total_frames") != total
           for report in (pose, tracking)):
        raise ValueError("Human annotation pitch/timeline differs from model output")
    if (not isinstance(pose.get("pitcher_id"), str) or not pose["pitcher_id"].strip()
            or pose["pitcher_id"] != tracking.get("pitcher_id")):
        raise ValueError("Pose and tracking subject identifiers differ or are missing")
    if pose.get("frame_indices") != list(range(total)):
        raise ValueError("Pose frame indices do not align with the human timeline")
    _checked_indices(pose["frame_indices"], total, "Pose timeline")
    frames = tracking["frames"]
    if [f["frame_index"] for f in frames] != list(range(total)):
        raise ValueError("Tracking frame indices do not align with the human timeline")
    _checked_indices([f["frame_index"] for f in frames], total, "Tracking timeline")
    if any(f["selection_status"] not in ("selected", "rejected") or not isinstance(f["warnings"], list)
           for f in frames):
        raise ValueError("Invalid tracking selection state or warnings")
    warning_frames = {e["frame_index"] for e in tracking["warning_events"] if e["type"] in _SWITCH_WARNINGS}
    for event in tracking["warning_events"]:
        _checked_indices([event["frame_index"]], total, "Tracking warning")
    if warning_frames != {f["frame_index"] for f in frames if _SWITCH_WARNINGS.intersection(f["warnings"])}:
        raise ValueError("Tracking warning events disagree with frame warnings")
    breaks = {f["frame_index"] for f in frames if f["selection_status"] != "selected"}
    if _interval_frames(tracking["track_breaks"]) != breaks:
        raise ValueError("Tracking break intervals disagree with selection states")
    screen = {f["frame_index"] for f in frames if f["selection_status"] != "selected" or f["warnings"]}
    labels = ground_truth["labels"]
    joints = {}
    all_jump_frames = set()
    for name in FULL_JOINT_LABELS:
        role = name.removesuffix("_reliability")
        landmark = pose["important_joints"][role]
        joint = pose["joints"][landmark]
        joints[role] = {"landmark": landmark, **_full_joint_agreement(labels[name], joint, total)}
        all_jump_frames.update(joint["frame_to_frame_jump"]["candidate_frames"])
    return {
        "status": "human_comparison_available",
        "ground_truth_status": "reviewed",
        "review_profile": "phase2_full_review",
        "correct_pitcher": labels["pitcher_correctly_selected"],
        "human_pitcher_selection_review": deepcopy(labels["pitcher_selection_review"]),
        "model_tracking_status": tracking["status"],
        "model_tracking_reasons": deepcopy(tracking["reasons"]),
        "identity_switch_warning_agreement": _screening(labels["identity_switch_intervals"], warning_frames, total),
        "track_break_screening": _screening(labels["track_break_intervals"], breaks, total),
        "major_pose_failure_screening": _screening(labels["major_pose_failure_intervals"], screen, total),
        "major_pose_failure_with_joint_jump_cues": _screening(
            labels["major_pose_failure_intervals"], screen | all_jump_frames, total),
        "screen_definitions": {
            "identity_switch": sorted(_SWITCH_WARNINGS),
            "track_break": "selection_status != selected",
            "major_pose_failure": "selection rejection or any existing per-frame tracking warning",
            "major_pose_failure_with_joint_jump_cues": (
                "Diagnostic union of the preceding tracking screen and six existing joint jump endpoints; "
                "not a new detector and not used to change baseline flags."),
        },
        "joint_reliability_agreement": joints,
        "human_arm_occlusion": {
            "intervals": deepcopy(labels["throwing_arm_occlusion_intervals"]),
            "frame_counts_by_status": {s: len(_interval_frames([i for i in labels["throwing_arm_occlusion_intervals"]
                                                               if i.get("status", "confirmed") == s]))
                                       for s in ("confirmed", "uncertain", "not_observable")},
            "accuracy": None,
            "reason": "The baseline has no occlusion-cause detector. Missing pose is not proof of occlusion; use joint-specific observability labels.",
        },
        "human_events": deepcopy(labels["events"]),
        "event_accuracy": None,
        "keypoint_coordinate_accuracy": None,
        "unmeasured_reasons": [
            "No automatic event estimates exist; human exact/range/uncertain events are preserved without a timing score.",
            "Qualitative review contains no reference X/Y coordinates; coordinate accuracy remains unmeasured.",
            "Single-reviewer judgments on five clips are not independent multi-reviewer validation or evidence of generalization.",
            "Zero confirmed identity switches cannot establish switch-detection sensitivity.",
        ],
    }


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

    if ground_truth.get("review_profile") == "phase2_full_review":
        return _evaluate_full_review(ground_truth, pose, tracking)

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
