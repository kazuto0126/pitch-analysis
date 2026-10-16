"""Pure fixed maximum-distance policy for the single Heavy information trial.

Calibration accepts four whole training clips only. Application reads only frame
indices and precomputed Full/Heavy distances; labels and model inference never
enter application. An absent warning is not an assertion of reliability.
"""
from __future__ import annotations

import math
from numbers import Real


PITCH_IDS = tuple(f"pitch_{i:03d}" for i in range(1, 6))
ROLES = ("throwing_elbow", "throwing_wrist")
LABELS = ("reliable", "unreliable", "not_observable", "uncertain")
_LIMITS = {
    "throwing_elbow": {
        "minimum_tp": 17, "maximum_fp": 1, "minimum_non003_tp": 10,
        "gate_passed_bad_hinted_must_exceed": 7,
        "score_only_tp": (1, 0, 7, 0, 1),
        "sample_maximum_tp": (6, 0, 2, 0, 0),
    },
    "throwing_wrist": {
        "minimum_tp": 27, "maximum_fp": 1, "minimum_non003_tp": 23,
        "gate_passed_bad_hinted_must_exceed": 8,
        "score_only_tp": (8, 2, 0, 8, 1),
        "sample_maximum_tp": (8, 0, 0, 0, 0),
    },
}


def _finite_nonnegative(value):
    return (isinstance(value, Real) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _indices(rows):
    """Validate frame identity without opening any annotation/context field."""
    seen = set()
    for row in rows:
        index = row["frame_index"]
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError("frame_index must be a unique nonnegative integer")
        seen.add(index)


def calibrate(training_clips, query_pitch_id, role):
    """Take the maximum measurable reliable nonseed training distance.

    Invalid cohorts are programming/input errors. A valid cohort with no usable
    reliable measurement instead returns an explicit failed calibration. No
    quantile, margin, replacement statistic, or query data is consulted.
    """
    if role not in ROLES or query_pitch_id not in PITCH_IDS:
        raise ValueError("unknown fixed role or query pitch_id")
    clips = list(training_clips)
    clip_ids = [clip["pitch_id"] for clip in clips]
    expected = set(PITCH_IDS) - {query_pitch_id}
    if len(clips) != 4 or len(set(clip_ids)) != 4 or set(clip_ids) != expected:
        raise ValueError("calibration requires exactly the four other whole clips")
    distances = []
    exclusions = {"seed": 0, "other_label": 0, "unmeasurable_reliable": 0}
    for clip in clips:
        rows = list(clip["rows"])
        _indices(rows)
        for row in rows:
            if row["frame_index"] == 0:
                exclusions["seed"] += 1
                continue
            label = row["canonical_label"]
            if label not in LABELS:
                raise ValueError("unknown canonical reliability label")
            if label != "reliable":
                exclusions["other_label"] += 1
                continue
            distance = row["distance_diagonal"]
            if not _finite_nonnegative(distance):
                exclusions["unmeasurable_reliable"] += 1
                continue
            distances.append(float(distance))
    return {
        "schema": "heavy_information_maximum_calibration_v1",
        "query_pitch_id": query_pitch_id,
        "role": role,
        "training_pitch_ids": sorted(clip_ids),
        "status": "calibrated" if distances else "failed",
        "reason": None if distances else "no_measurable_reliable_training_rows",
        "threshold_diagonal": max(distances) if distances else None,
        "used_reliable_rows": len(distances),
        "excluded_rows": exclusions,
        "comparison": "strictly_greater_than_training_maximum",
    }


def apply(rows, calibration):
    """Apply a sealed maximum using only query frame index and distance.

    ``review_required`` is null when no judgment can be made; the separate
    ``evaluated_warning=False`` keeps such rows in evaluation FN/TN denominators.
    Frame zero is retained but excluded from calibration and effectiveness.
    """
    if (calibration.get("schema") != "heavy_information_maximum_calibration_v1"
            or calibration.get("query_pitch_id") not in PITCH_IDS
            or calibration.get("role") not in ROLES
            or calibration.get("status") not in ("calibrated", "failed")
            or set(calibration.get("training_pitch_ids", [])) !=
                set(PITCH_IDS) - {calibration["query_pitch_id"]}
            or len(calibration["training_pitch_ids"]) != 4
            or calibration.get("comparison") != "strictly_greater_than_training_maximum"):
        raise ValueError("calibration does not match the fixed maximum policy")
    threshold = calibration["threshold_diagonal"]
    if (calibration["status"] == "calibrated" and not _finite_nonnegative(threshold)
            or calibration["status"] == "failed" and threshold is not None):
        raise ValueError("calibration threshold is inconsistent with its status")
    source_rows = list(rows)
    _indices(source_rows)
    result = []
    for row in source_rows:
        index, distance = row["frame_index"], row["distance_diagonal"]
        if distance is not None and not _finite_nonnegative(distance):
            raise ValueError("query distance must be finite nonnegative or null")
        distance = float(distance) if distance is not None else None
        warning = False
        if index == 0:
            status, review_required = "seed_excluded", False
        elif calibration["status"] != "calibrated":
            status, review_required = "calibration_failed", None
        elif distance is None:
            status, review_required = "insufficient_evidence", None
        else:
            warning = distance > threshold
            status = "warning" if warning else "no_warning"
            review_required = warning
        result.append({
            "frame_index": index,
            "distance_diagonal": distance,
            "threshold_diagonal": threshold,
            "status": status,
            "review_required": review_required,
            "evaluated_warning": warning,
            "effectiveness_eligible": index != 0,
        })
    return result


def decision(per_clip_role_stats):
    """Evaluate the frozen numbers for both roles, with all five folds present.

    Input is ``{role: [five stats dicts]}``; every stats dict contains pitch_id,
    calibration_status, tp/fn/fp/tn, and gate_passed_bad_hinted. A passing role is
    a proposal for supplementary review hints, never automatic core adoption.
    """
    if set(per_clip_role_stats) != set(ROLES):
        raise ValueError("decision requires both fixed roles")
    result = {}
    for role in ROLES:
        stats = list(per_clip_role_stats[role])
        ids = [row["pitch_id"] for row in stats]
        if len(stats) != 5 or len(set(ids)) != 5 or set(ids) != set(PITCH_IDS):
            raise ValueError("decision requires exactly five different original clips per role")
        for row in stats:
            for key in ("tp", "fn", "fp", "tn", "gate_passed_bad_hinted"):
                if type(row[key]) is not int or row[key] < 0:
                    raise ValueError("decision counts must be nonnegative integers")
            if row["gate_passed_bad_hinted"] > row["tp"]:
                raise ValueError("gate-passed bad hints must be a subset of true positives")
            if row["calibration_status"] not in ("calibrated", "failed"):
                raise ValueError("unknown calibration status")
        limits = _LIMITS[role]
        by_id = {row["pitch_id"]: row for row in stats}
        totals = {key: sum(row[key] for row in stats)
                  for key in ("tp", "fn", "fp", "tn", "gate_passed_bad_hinted")}
        non003 = sum(row["tp"] for row in stats if row["pitch_id"] != "pitch_003")
        improved = [pitch_id for i, pitch_id in enumerate(PITCH_IDS)
                    if pitch_id != "pitch_003" and by_id[pitch_id]["tp"] > max(
                        limits["score_only_tp"][i], limits["sample_maximum_tp"][i])]
        checks = {
            "five_folds_calibrated": all(row["calibration_status"] == "calibrated" for row in stats),
            "minimum_tp": totals["tp"] >= limits["minimum_tp"],
            "maximum_fp": totals["fp"] <= limits["maximum_fp"],
            "minimum_non003_tp": non003 >= limits["minimum_non003_tp"],
            "minimum_two_improved_non003_clips": len(improved) >= 2,
            "gate_passed_bad_hints_strictly_improve": totals["gate_passed_bad_hinted"] >
                limits["gate_passed_bad_hinted_must_exceed"],
        }
        result[role] = {
            "passed": all(checks.values()),
            "checks": checks,
            "totals": totals,
            "non003_tp": non003,
            "improved_non003_clips": improved,
            "frozen_limits": {key: list(value) if isinstance(value, tuple) else value
                              for key, value in limits.items()},
        }
    proposed = [role for role in ROLES if result[role]["passed"]]
    return {
        "schema": "heavy_information_fixed_decision_v1",
        "roles": result,
        "proposed_roles": proposed,
        "status": "propose_review_hint_scope" if proposed else "rejected",
        "next_action": "await_review_hint_scope_approval" if proposed else
            "stop_this_trial_need_better_images_or_model_information",
        "changes_formal_pose_tracking_or_gates": False,
        "automatically_passes_phase2": False,
    }
