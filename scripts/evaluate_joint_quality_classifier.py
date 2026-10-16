"""Pure, fixed-rule evaluation of sealed out-of-fold elbow/wrist hints.

Inputs are already loaded by the source-bound execution driver.  This module
does no FIT, APPLY, inference, file IO, threshold search, or coordinate repair.
Canonical raw-overlay reviews remain the classification target.  Human XY is
only an auxiliary continuous-error description for pitch_003.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from numbers import Real
import statistics


ROLES = ("throwing_elbow", "throwing_wrist")
SCREENS = ("classifier", "score_only", "sample_maximum")
LABELS = ("reliable", "unreliable", "not_observable", "uncertain")
RULES = {
    "throwing_elbow": {"minimum_tp": 17, "maximum_fp": 1, "minimum_non003_tp": 10},
    "throwing_wrist": {"minimum_tp": 27, "maximum_fp": 1, "minimum_non003_tp": 23},
}


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def _xy(value):
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(_finite(v) for v in value)


def _frames(data, total, name):
    frames = data.get("frames")
    if not isinstance(frames, list) or len(frames) != total or any(
            type(f.get("frame_index")) is not int or f["frame_index"] != i
            for i, f in enumerate(frames)):
        raise ValueError(f"Incomplete or reordered {name} frames")
    return frames


def _timeline(gt, role, total):
    """Require exhaustive, nonoverlapping original canonical intervals."""
    labels = [None] * total
    for interval in gt["labels"][role + "_reliability"]:
        start, end, status = (interval[k] for k in ("start_frame", "end_frame", "status"))
        if (type(start) is not int or type(end) is not int or
                not 0 <= start <= end < total or status not in LABELS):
            raise ValueError("Invalid canonical joint interval")
        for frame in range(start, end + 1):
            if labels[frame] is not None:
                raise ValueError("Overlapping canonical joint intervals")
            labels[frame] = status
    if None in labels:
        raise ValueError("Incomplete canonical joint timeline")
    return labels


def _fold_status(prediction, role):
    value = prediction["fold_status"][role]
    return value["status"] if isinstance(value, dict) else value


def _prediction(data, feature, frame_index, fold_status):
    state, warning, probability = (data[k] for k in ("state", "warning", "probability"))
    if type(warning) is not bool:
        raise ValueError("Classifier warning must be a boolean")
    if frame_index == 0:
        if (state, warning, probability) != ("seed_excluded", False, None):
            raise ValueError("Seed must be excluded from application and effectiveness")
        return
    if not feature["raw_finite"]:
        if (state, warning, probability) != ("insufficient_evidence", False, None):
            raise ValueError("Missing raw cannot produce a coordinate warning or probability")
    elif fold_status != "converged":
        if (state, warning, probability) != ("fold_failed", False, None):
            raise ValueError("Unconverged fold cannot silently supply classifier predictions")
    elif (not _finite(probability) or not 0 <= probability <= 1 or
          warning != (probability >= 0.5) or
          state != ("warning" if warning else "no_warning")):
        raise ValueError("Finite query must receive its fixed 0.5 decision, without abstention")


def _screen(row, screen):
    warning = row["screens"][screen]["warning"]
    label = row["canonical_label"]
    return ("tp" if warning else "fn") if label == "unreliable" else (
        ("fp" if warning else "tn") if label == "reliable" else None)


def _counts(values):
    return dict(sorted(Counter(values).items()))


def _summarize(rows):
    rows = [r for r in rows if r["effectiveness_eligible"]]
    labels = {label: sum(r["canonical_label"] == label for r in rows) for label in LABELS}
    result = {
        "non_seed_frames": len(rows),
        "canonical_label_counts": labels,
        "binary_label_frames": labels["reliable"] + labels["unreliable"],
        "raw_missing_frames": sum(not r["raw_finite"] for r in rows),
        "feature_missing_frames": sum(r["feature_missing_count"] > 0 for r in rows),
        "feature_missing_value_count": sum(r["feature_missing_count"] for r in rows),
        "original_model_state_counts": _counts(r["original_context"]["model_state"] for r in rows),
        "original_use_disposition_counts": _counts(
            r["original_context"]["use_disposition"]["status"] for r in rows),
        "original_restriction_counts": _counts(
            restriction for r in rows for restriction in r["original_context"]["use_disposition"].get("restrictions", [])),
        "existing_major_hold_frames": sum(r["original_context"]["major_hold"] for r in rows),
        "original_processed_usable_frames": sum(r["original_context"]["processed_usable"] for r in rows),
        "raw_gate_pass_frames": sum(r["raw_gate_pass"] for r in rows),
        "screens": {},
    }
    for screen in SCREENS:
        counts = {k: sum(_screen(r, screen) == k for r in rows) for k in ("tp", "fn", "fp", "tn")}
        warnings = [r for r in rows if r["screens"][screen]["warning"]]
        gate = [r for r in rows if r["raw_gate_pass"]]
        kept = [r for r in gate if not r["screens"][screen]["warning"]]
        states = _counts(r["screens"][screen]["state"] for r in rows)
        counts.update({
            "warning_total": len(warnings),
            "unknown_label_warning_counts": {
                label: sum(r["canonical_label"] == label for r in warnings)
                for label in ("not_observable", "uncertain")},
            "state_counts": states,
            "abstain_frames": sum(r["screens"][screen]["state"] in
                ("insufficient_evidence", "fold_failed") for r in rows),
            "fold_failed_frames": states.get("fold_failed", 0),
            "warning_frames": _frame_refs(warnings),
            "missed_wrong_point_frames": _frame_refs(r for r in rows if _screen(r, screen) == "fn"),
            "false_positive_frames": _frame_refs(r for r in rows if _screen(r, screen) == "fp"),
            "retention_on_original_raw_gate_pass": {
                "original_support": len(gate),
                "newly_flagged": len(gate) - len(kept),
                "remaining_without_this_hint": len(kept),
                "reliable_remaining": sum(r["canonical_label"] == "reliable" for r in kept),
                "unreliable_remaining_unflagged": sum(r["canonical_label"] == "unreliable" for r in kept),
                "not_observable_remaining": sum(r["canonical_label"] == "not_observable" for r in kept),
                "uncertain_remaining": sum(r["canonical_label"] == "uncertain" for r in kept),
                "newly_caught_gate_pass_wrong_points": sum(
                    r["canonical_label"] == "unreliable" for r in gate if r["screens"][screen]["warning"]),
                "newly_flagged_gate_pass_good_points": sum(
                    r["canonical_label"] == "reliable" for r in gate if r["screens"][screen]["warning"]),
                "duplicate_hint_on_gate_blocked_finite_raw": sum(
                    r["raw_finite"] and not r["raw_gate_pass"] for r in warnings),
            },
            "original_gate_plus_hint_union_estimate": {
                "raw_gate_supported_without_hint": len(kept),
                "original_processed_support_without_hint": sum(
                    r["original_context"]["processed_usable"] and not r["screens"][screen]["warning"] for r in rows),
                "original_reviewed_support_without_hint": sum(
                    r["original_context"]["processed_usable"] and
                    r["original_context"]["use_disposition"]["status"] == "reviewed_raw_observation" and
                    not r["original_context"]["use_disposition"].get("restrictions") and
                    not r["original_context"]["major_hold"] and
                    not r["screens"][screen]["warning"] for r in rows),
                "existing_major_hold_frames_preserved": result["existing_major_hold_frames"],
                "existing_use_disposition_counts_preserved": result["original_use_disposition_counts"],
                "interpretation": "Support and review-burden estimate only; no original gate, hold or use state is changed.",
            },
        })
        if sum(counts[k] for k in ("tp", "fn", "fp", "tn")) != result["binary_label_frames"]:
            raise ValueError("Lost binary denominator")
        result["screens"][screen] = counts
    return result


def _frame_refs(rows):
    return [{"pitch_id": r["pitch_id"], "frame_index": r["frame_index"]} for r in rows]


def _decision(clips, aggregate, folds):
    output = {}
    for role in ROLES:
        overall = aggregate[role]["screens"]
        prediction = overall["classifier"]
        other = [c for c in clips if c["pitch_id"] != "pitch_003"]
        non003_tp = sum(c["roles"][role]["screens"]["classifier"]["tp"] for c in other)
        improved = [c["pitch_id"] for c in other if
            c["roles"][role]["screens"]["classifier"]["tp"] > max(
                c["roles"][role]["screens"][b]["tp"] for b in ("score_only", "sample_maximum"))]
        rule = RULES[role]
        checks = {
            "all_five_folds_converged": all(folds[p][role] == "converged" for p in folds),
            "tp_minimum": prediction["tp"] >= rule["minimum_tp"],
            "fp_at_most_one_and_no_higher_than_either_baseline": prediction["fp"] <= min(
                rule["maximum_fp"], overall["score_only"]["fp"], overall["sample_maximum"]["fp"]),
            "non003_tp_minimum": non003_tp >= rule["minimum_non003_tp"],
            "at_least_two_non003_clips_improve_both_baselines": len(improved) >= 2,
        }
        output[role] = {"fixed_rule": deepcopy(rule), "checks": checks,
            "non003_tp": non003_tp, "improved_non003_clips": improved,
            "meets_proposal_rule": all(checks.values()),
            "action": "propose_review_hint_scope_await_user_approval" if all(checks.values()) else
                      "do_not_propose_adoption_stop_adjusting_these_signals"}
    proposed = [role for role in ROLES if output[role]["meets_proposal_rule"]]
    return {"roles": output, "proposed_roles": proposed, "automatic_adoption": False,
        "next_action": "await_user_approval_of_proposed_hint_scope" if proposed else
            "stop_signal_adjustment_need_better_images_or_model_information",
        "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "This fixed developmental screening decision does not replace existing Phase 2 acceptance criteria."}


def _error_stats(values):
    values = sorted(values)
    return {"n": len(values), "mean_px": statistics.mean(values) if values else None,
        "median_px": statistics.median(values) if values else None,
        "maximum_px": max(values) if values else None}


def _manual_auxiliary(manual, features, rows):
    if manual is None:
        return None
    clip = next(c for c in features if c["target"]["pitch_id"] == "pitch_003")
    target = clip["target"]
    if (manual["source_video"]["pitch_id"] != "pitch_003" or
            manual["source_video"]["total_frames"] != target["total_frames"]):
        raise ValueError("Auxiliary XY belongs to a different clip")
    if manual.get("coordinate_system") != "original_image_pixels_xy":
        raise ValueError("Auxiliary XY must use original image pixels")
    frames = _frames(manual, target["total_frames"], "manual XY")
    reports = {}
    for role in ROLES:
        pairs, missing_raw = [], 0
        statuses = Counter()
        role_rows = [r for r in rows if r["pitch_id"] == "pitch_003" and r["role"] == role and r["effectiveness_eligible"]]
        for row in role_rows:
            matches = [j for j in frames[row["frame_index"]]["joints"] if j["name"] == row["landmark"]]
            if len(matches) != 1:
                raise ValueError("Missing or repeated manual joint")
            point = matches[0]
            statuses[point["status"]] += 1
            if point["status"] != "visible":
                continue
            if not _xy([point["x_px"], point["y_px"]]):
                raise ValueError("Visible auxiliary point is not finite")
            if not row["raw_finite"]:
                missing_raw += 1
                continue
            xy = row["raw_xy_px"]
            distance = math.hypot(xy[0] - point["x_px"], xy[1] - point["y_px"])
            pairs.append({"frame_index": row["frame_index"], "canonical_label": row["canonical_label"],
                "manual_xy_px": [point["x_px"], point["y_px"]], "raw_xy_px": deepcopy(xy),
                "error_px": distance, "raw_gate_pass": row["raw_gate_pass"],
                "warnings": {s: row["screens"][s]["warning"] for s in SCREENS}})
        reports[role] = {"manual_status_counts_non_seed": dict(statuses),
            "visible_reference_raw_missing": missing_raw,
            "all_finite_raw_visible_pairs": _error_stats(p["error_px"] for p in pairs),
            "by_screen": {s: {"warning": _error_stats(p["error_px"] for p in pairs if p["warnings"][s]),
                "no_warning": _error_stats(p["error_px"] for p in pairs if not p["warnings"][s])} for s in SCREENS},
            "by_canonical_label": {label: _error_stats(p["error_px"] for p in pairs if p["canonical_label"] == label)
                for label in LABELS}, "pairs": pairs}
    return {"purpose": "Continuous auxiliary XY check only; never training labels, features, cutoffs or adoption criteria.",
        "source_scope": "pitch_003 visible manual points only; finite raw outside the image is retained.",
        "roles": reports}


def evaluate_clips(features, predictions, ground_truths, baseline_hints, reviewed_views, manual_xy=None):
    """Evaluate once using complete per-clip rows and fixed preapproved rules.

    All inputs are borrowed, never mutated. The caller is responsible for SHA
    binding and sealing predictions before supplying query annotations here.
    """
    names = [f"pitch_{i:03d}" for i in range(1, 6)]
    if ([c["target"]["pitch_id"] for c in features] != names or
            [c["target"]["pitch_id"] for c in predictions] != names or
            any(set(mapping) != set(names) for mapping in (ground_truths, baseline_hints, reviewed_views))):
        raise ValueError("Require original five clips in fixed order and complete source maps")
    rows, reports, folds = [], [], {}
    for clip, prediction in zip(features, predictions, strict=True):
        target = clip["target"]
        pid, total = target["pitch_id"], target["total_frames"]
        if (type(total) is not int or total < 2 or prediction["target"] != target or
                any(not _finite(target[k]) or target[k] <= 0 for k in ("width", "height"))):
            raise ValueError("Wrong prediction target")
        gt, baseline, view = ground_truths[pid], baseline_hints[pid], reviewed_views[pid]
        if (gt["source_video"]["pitch_id"] != pid or gt["source_video"]["total_frames"] != total or
                gt.get("annotation_status") != "reviewed" or view.get("pitch_id") != pid or baseline["target"] != target):
            raise ValueError("Wrong or incomplete human/baseline source")
        timelines = {role: _timeline(gt, role, total) for role in ROLES}
        ff, pf, bf, vf = (_frames(data, total, name) for data, name in (
            (clip, "features"), (prediction, "prediction"), (baseline, "sample maximum"), (view, "reviewed view")))
        folds[pid] = {role: _fold_status(prediction, role) for role in ROLES}
        clip_rows = []
        previous_time = None
        for f, p, b, v in zip(ff, pf, bf, vf, strict=True):
            index, timestamp = f["frame_index"], f["timestamp_ms"]
            if (not _finite(timestamp) or p["timestamp_ms"] != timestamp or
                    not _finite(v["timestamp_ms"]) or abs(v["timestamp_ms"] - timestamp) > 1 or
                    (previous_time is not None and timestamp <= previous_time)):
                raise ValueError("Changed or incomplete frame timeline")
            baseline_timestamp = b.get("capture_timestamp_ms", b.get("timestamp_ms"))
            if baseline_timestamp != timestamp:
                raise ValueError("Changed sample-maximum timeline")
            previous_time = timestamp
            for role in ROLES:
                source, predicted, original = f["roles"][role], p["roles"][role], v["focus_joints"][role]
                if (type(source["raw_finite"]) is not bool or type(source["raw_gate_pass"]) is not bool or
                        source["raw_gate_pass"] and not source["raw_finite"] or
                        source["landmark"] != original["landmark"] or source["model_state"] != original["model_state"]):
                    raise ValueError("Changed raw finite/gate or original model context")
                if source["raw_finite"] != _xy(source["raw_xy_px"]):
                    raise ValueError("Raw coordinate presence differs from finite flag")
                feature_values = source["features"]
                if isinstance(feature_values, dict):
                    feature_values = list(feature_values.values())
                if (len(feature_values) != 13 or any(value is not None and not _finite(value) for value in feature_values)):
                    raise ValueError("Expected 13 finite-or-null frozen features")
                _prediction(predicted, source, index, folds[pid][role])
                sample = b["joints"][role]
                if type(sample["warning"]) is not bool or index == 0 and sample["warning"]:
                    raise ValueError("Invalid sample-maximum warning")
                score_warning = index != 0 and source["raw_finite"] and not source["raw_gate_pass"]
                state = "seed_excluded" if index == 0 else (
                    "insufficient_evidence" if not source["raw_finite"] else ("warning" if score_warning else "no_warning"))
                processed = original["processed_landmark"]
                row = {"pitch_id": pid, "role": role, "landmark": source["landmark"],
                    "frame_index": index, "timestamp_ms": timestamp, "effectiveness_eligible": index != 0,
                    "canonical_label": timelines[role][index], "raw_finite": source["raw_finite"],
                    "raw_gate_pass": source["raw_gate_pass"], "raw_xy_px": deepcopy(source["raw_xy_px"]),
                    "feature_missing_count": sum(value is None for value in feature_values),
                    "feature_missing_reasons": deepcopy(source["missing_reasons"]),
                    "original_context": {"model_state": original["model_state"],
                        "use_disposition": deepcopy(original["use_disposition"]),
                        "major_hold": bool(v["human_review"].get("major_pose_failure")),
                        "major_pose_failure": deepcopy(v["human_review"].get("major_pose_failure", [])),
                        "processed_usable": processed.get("usable") is True,
                        "processed_landmark": deepcopy(processed)},
                    "screens": {"classifier": deepcopy(predicted),
                        "score_only": {"state": state, "warning": score_warning},
                        "sample_maximum": {"state": sample["evidence_state"], "warning": sample["warning"]}}}
                rows.append(row)
                clip_rows.append(row)
        reports.append({"pitch_id": pid, "source_frames": total, "non_seed_frames": total - 1,
            "fold_status": deepcopy(folds[pid]), "precise_accuracy": None,
            "roles": {role: _summarize([r for r in clip_rows if r["role"] == role]) for role in ROLES}})
    aggregate = {role: _summarize([r for r in rows if r["role"] == role]) for role in ROLES}
    auxiliary = _manual_auxiliary(manual_xy, features, rows)
    if auxiliary is not None:
        next(c for c in reports if c["pitch_id"] == "pitch_003")["precise_accuracy"] = auxiliary
    held_out = deepcopy(next(c for c in reports if c["pitch_id"] == "pitch_003"))
    held_out["training_clip_ids"] = [name for name in names if name != "pitch_003"]
    held_out["interpretation"] = "Out-of-fold query only; no fit on pitch_003 labels. Canonical, XY and major context are separate. Local hints do not certify or repair tracking."
    held_out["known_major_miss_frame_104_context"] = [deepcopy(r) for r in rows if
        r["pitch_id"] == "pitch_003" and r["frame_index"] == 104]
    return {"status": "complete_single_fixed_joint_quality_evaluation", "source_frames": sum(c["source_frames"] for c in reports),
        "non_seed_frames": sum(c["non_seed_frames"] for c in reports), "source_joint_rows": len(rows),
        "non_seed_joint_rows": sum(r["effectiveness_eligible"] for r in rows),
        "clips": reports, "aggregate": aggregate,
        "non003_aggregate": {role: _summarize([r for r in rows if r["role"] == role and r["pitch_id"] != "pitch_003"]) for role in ROLES},
        "held_out_pitch_003": held_out, "decision": _decision(reports, aggregate, folds), "frame_joint_rows": rows,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "interpretation": "Screening hints developed on five reviewed Yamamoto clips. No hint is not proof of reliability; unknown labels and raw missing remain in full denominators. No data, gate, coordinates or existing use status changed."}
