"""Pure evaluation of the one sealed Full/Heavy disagreement experiment.

No file IO, pose inference, selection, calibration writes or data repair occurs
here. Canonical reviews describe original Full predictions, never Heavy labels.
Visible manual XY is an auxiliary paired comparison on pitch_003 only.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from numbers import Real
import statistics

from heavy_information_policy import decision


PITCH_IDS = tuple(f"pitch_{i:03d}" for i in range(1, 6))
ROLES = ("throwing_elbow", "throwing_wrist")
LABELS = ("reliable", "unreliable", "not_observable", "uncertain")
HISTORICAL_SCREENS = ("score_only", "sample_maximum", "classifier")
SCREENS = ("heavy_disagreement", *HISTORICAL_SCREENS)
LANDMARK_INDEX = {"LEFT_ELBOW": 13, "RIGHT_ELBOW": 14,
                  "LEFT_WRIST": 15, "RIGHT_WRIST": 16}


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value)


def _close(actual, expected, message):
    if actual is None or expected is None:
        matches = actual is expected
    else:
        matches = (_finite(actual) and _finite(expected) and
                   math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12))
    if not matches:
        raise ValueError(message)


def _frames(source, total, name):
    frames = source.get("frames")
    if (not isinstance(frames, list) or len(frames) != total or any(
            type(frame.get("frame_index")) is not int or frame["frame_index"] != i
            for i, frame in enumerate(frames))):
        raise ValueError(f"Incomplete or reordered {name} frames")
    return frames


def _timeline(gt, role, total):
    labels = [None] * total
    for interval in gt["labels"][role + "_reliability"]:
        start, end, label = (interval[key] for key in ("start_frame", "end_frame", "status"))
        if (type(start) is not int or type(end) is not int or
                not 0 <= start <= end < total or label not in LABELS):
            raise ValueError("Invalid canonical interval")
        for index in range(start, end + 1):
            if labels[index] is not None:
                raise ValueError("Overlapping canonical intervals")
            labels[index] = label
    if None in labels:
        raise ValueError("Incomplete canonical timeline")
    return labels


def _point(point, width, height):
    finite = isinstance(point, dict) and all(_finite(point.get(k)) for k in (
        "x", "y", "visibility", "presence"))
    xy = [point["x"] * width, point["y"] * height] if finite else None
    finite = finite and all(_finite(v) for v in xy)
    return finite, xy if finite else None, bool(
        finite and point["visibility"] >= .5 and point["presence"] >= .5)


def _baseline_rows(baseline):
    source = baseline["frame_joint_rows"]
    rows = {}
    for row in source:
        key = row["pitch_id"], row["frame_index"], row["role"]
        if key in rows or key[0] not in PITCH_IDS or key[2] not in ROLES:
            raise ValueError("Repeated or unexpected historical evaluation row")
        rows[key] = row
    return rows


def _selection(frame):
    candidates, selected = frame["heavy_candidates"], frame["heavy_selection"]
    if (not isinstance(candidates, list) or len(candidates) > 4 or any(
            not isinstance(pose, list) or len(pose) != 33 or
            any(not isinstance(point, dict) for point in pose) for pose in candidates)):
        raise ValueError("Heavy must preserve every native 33-point candidate")
    index, status = selected["index"], selected["status"]
    if (type(selected["candidate_count"]) is not int or
            selected["candidate_count"] != len(candidates)):
        raise ValueError("Heavy candidate count changed")
    if status == "selected":
        if type(index) is not int or not 0 <= index < len(candidates):
            raise ValueError("Invalid native Heavy selected index")
    elif status in ("rejected", "ambiguous", "failed"):
        if index is not None:
            raise ValueError("Unselected Heavy result cannot supply an index")
    else:
        raise ValueError("Unknown Heavy selection status")
    return candidates[index] if status == "selected" else None


def _measurement_row(pid, clip, frame, role, baseline, label, major):
    width, height = clip["width"], clip["height"]
    source, index = frame["roles"][role], frame["frame_index"]
    original = source["original_point"]
    raw_finite, raw_xy, raw_gate = _point(original, width, height)
    if (type(source["raw_finite"]) is not bool or type(source["raw_gate_pass"]) is not bool or
            source["raw_finite"] != raw_finite or source["raw_gate_pass"] != raw_gate or
            baseline["raw_finite"] != raw_finite or baseline["raw_gate_pass"] != raw_gate):
        raise ValueError("Changed original finite flag or 0.5 raw gate")
    if baseline["canonical_label"] != label:
        raise ValueError("Historical label disagrees with independently expanded canonical GT")
    if baseline["effectiveness_eligible"] is not (index != 0):
        raise ValueError("Historical seed eligibility changed")
    landmark = baseline["landmark"]
    if landmark not in LANDMARK_INDEX or (role == "throwing_elbow") != landmark.endswith("ELBOW"):
        raise ValueError("Historical throwing-side landmark differs")
    if raw_xy is None:
        if baseline["raw_xy_px"] is not None:
            raise ValueError("Historical missing raw coordinates changed")
    else:
        if not isinstance(baseline["raw_xy_px"], list) or len(baseline["raw_xy_px"]) != 2:
            raise ValueError("Historical raw coordinate shape changed")
        for actual, expected in zip(raw_xy, baseline["raw_xy_px"], strict=True):
            _close(actual, expected, "Historical raw coordinates changed")
    selected = _selection(frame)
    heavy = source["heavy_point"]
    expected_heavy = selected[LANDMARK_INDEX[landmark]] if selected is not None else None
    if heavy != expected_heavy:
        raise ValueError("Heavy role does not equal the selected native same-name point")
    heavy_finite, heavy_xy, heavy_gate = _point(heavy, width, height)
    paired = raw_finite and heavy_finite
    distance = math.hypot(raw_xy[0] - heavy_xy[0], raw_xy[1] - heavy_xy[1]) if paired else None
    diagonal_distance = distance / math.hypot(width, height) if paired else None
    _close(source["distance_px"], distance, "Changed Full/Heavy pixel distance")
    _close(source["distance_diagonal"], diagonal_distance, "Changed Full/Heavy diagonal distance")
    if source["evidence_status"] != ("measured" if paired else "insufficient_evidence"):
        raise ValueError("Changed measurable/insufficient evidence status")
    screens = {}
    for screen in HISTORICAL_SCREENS:
        value = deepcopy(baseline["screens"][screen])
        if type(value["warning"]) is not bool or index == 0 and value["warning"]:
            raise ValueError("Invalid historical screening warning")
        screens[screen] = value
    expected_score = index != 0 and raw_finite and not raw_gate
    if screens["score_only"]["warning"] != expected_score:
        raise ValueError("Historical score-only warning disagrees with original gate")
    return {"pitch_id": pid, "role": role, "landmark": landmark, "frame_index": index,
        "timestamp_ms": frame["timestamp_ms"], "effectiveness_eligible": index != 0,
        "canonical_label": label, "label_target": "original_full_raw_overlay_only",
        "raw_finite": raw_finite, "raw_gate_pass": raw_gate, "raw_xy_px": deepcopy(raw_xy),
        "heavy_selected_finite": heavy_finite, "heavy_xy_px": deepcopy(heavy_xy),
        "heavy_gate_pass_diagnostic_only": heavy_gate,
        "distance_px": distance, "distance_diagonal": diagonal_distance,
        "evidence_status": source["evidence_status"],
        "heavy_selection": deepcopy(frame["heavy_selection"]),
        "existing_major_review_required": major,
        "original_context": deepcopy(baseline["original_context"]), "screens": screens}


def _validate_prediction(predicted, row, fold_status, expected_threshold):
    if type(predicted["frame_index"]) is not int or predicted["frame_index"] != row["frame_index"]:
        raise ValueError("Changed prediction frame identity")
    _close(predicted["distance_diagonal"], row["distance_diagonal"], "Prediction distance changed")
    _close(predicted["threshold_diagonal"], expected_threshold, "Prediction training maximum changed")
    warning = False
    if row["frame_index"] == 0:
        status, review = "seed_excluded", False
    elif fold_status != "calibrated":
        status, review = "calibration_failed", None
    elif row["distance_diagonal"] is None:
        status, review = "insufficient_evidence", None
    else:
        warning = row["distance_diagonal"] > expected_threshold
        status, review = ("warning" if warning else "no_warning"), warning
    if (predicted["status"] != status or predicted["review_required"] is not review or
            predicted["evaluated_warning"] is not warning or
            predicted["effectiveness_eligible"] is not row["effectiveness_eligible"]):
        raise ValueError("Prediction is not the frozen strict-maximum/abstention decision")


def _warning(row, screen):
    value = row["screens"][screen]
    return value["evaluated_warning"] if screen == "heavy_disagreement" else value["warning"]


def _class(row, screen):
    warning, label = _warning(row, screen), row["canonical_label"]
    if label == "unreliable":
        return "tp" if warning else "fn"
    if label == "reliable":
        return "fp" if warning else "tn"
    return None


def _refs(rows):
    return [{"pitch_id": row["pitch_id"], "frame_index": row["frame_index"]} for row in rows]


def _counts(values):
    return dict(sorted(Counter(values).items()))


def _summarize(source_rows):
    rows = [row for row in source_rows if row["effectiveness_eligible"]]
    labels = {label: sum(row["canonical_label"] == label for row in rows) for label in LABELS}
    result = {"non_seed_frames": len(rows), "canonical_label_counts": labels,
        "binary_label_frames": labels["reliable"] + labels["unreliable"],
        "raw_missing_frames": sum(not row["raw_finite"] for row in rows),
        "heavy_selected_finite_frames": sum(row["heavy_selected_finite"] for row in rows),
        "heavy_selected_missing_frames": sum(not row["heavy_selected_finite"] for row in rows),
        "measurable_distance_frames": sum(row["distance_diagonal"] is not None for row in rows),
        "evidence_status_counts": _counts(row["evidence_status"] for row in rows),
        "heavy_selection_status_counts": _counts(row["heavy_selection"]["status"] for row in rows),
        "heavy_candidate_count_histogram": _counts(row["heavy_selection"]["candidate_count"] for row in rows),
        "heavy_no_candidates_frames": sum(row["heavy_selection"]["candidate_count"] == 0 for row in rows),
        "original_model_state_counts": _counts(row["original_context"]["model_state"] for row in rows),
        "original_use_disposition_counts": _counts(row["original_context"]["use_disposition"]["status"] for row in rows),
        "original_restriction_counts": _counts(restriction for row in rows for restriction in
            row["original_context"]["use_disposition"].get("restrictions", [])),
        "existing_major_hold_frames": sum(row["original_context"]["major_hold"] for row in rows),
        "original_processed_usable_frames": sum(row["original_context"]["processed_usable"] for row in rows),
        "raw_gate_pass_frames": sum(row["raw_gate_pass"] for row in rows), "screens": {}}
    for screen in SCREENS:
        warned = [row for row in rows if _warning(row, screen)]
        gate = [row for row in rows if row["raw_gate_pass"]]
        kept = [row for row in gate if not _warning(row, screen)]
        state = "status" if screen == "heavy_disagreement" else "state"
        stats = {key: sum(_class(row, screen) == key for row in rows) for key in ("tp", "fn", "fp", "tn")}
        stats.update({"warning_total": len(warned),
            "unknown_label_warning_counts": {label: sum(row["canonical_label"] == label for row in warned)
                for label in ("not_observable", "uncertain")},
            "state_counts": _counts(row["screens"][screen][state] for row in rows),
            "abstain_frames": sum(row["screens"][screen][state] in
                ("insufficient_evidence", "calibration_failed", "fold_failed") for row in rows),
            "warning_frames": _refs(warned),
            "missed_wrong_point_frames": _refs(row for row in rows if _class(row, screen) == "fn"),
            "false_positive_frames": _refs(row for row in rows if _class(row, screen) == "fp"),
            "retention_on_original_raw_gate_pass": {
                "original_support": len(gate), "newly_flagged": len(gate) - len(kept),
                "remaining_without_this_hint": len(kept),
                "reliable_remaining": sum(row["canonical_label"] == "reliable" for row in kept),
                "unreliable_remaining_unflagged": sum(row["canonical_label"] == "unreliable" for row in kept),
                "not_observable_remaining": sum(row["canonical_label"] == "not_observable" for row in kept),
                "uncertain_remaining": sum(row["canonical_label"] == "uncertain" for row in kept),
                "newly_caught_gate_pass_wrong_points": sum(row["canonical_label"] == "unreliable" for row in gate if _warning(row, screen)),
                "newly_flagged_gate_pass_good_points": sum(row["canonical_label"] == "reliable" for row in gate if _warning(row, screen)),
                "duplicate_hint_on_gate_blocked_finite_raw": sum(row["raw_finite"] and not row["raw_gate_pass"] for row in warned)},
            "original_gate_plus_hint_union_estimate": {
                "original_processed_support_without_hint": sum(row["original_context"]["processed_usable"] and not _warning(row, screen) for row in rows),
                "original_reviewed_support_without_hint": sum(row["original_context"]["processed_usable"] and
                    row["original_context"]["use_disposition"]["status"] == "reviewed_raw_observation" and
                    not row["original_context"]["use_disposition"].get("restrictions") and
                    not row["original_context"]["major_hold"] and not _warning(row, screen) for row in rows),
                "existing_major_hold_frames_preserved": result["existing_major_hold_frames"],
                "interpretation": "Hypothetical support only; all original gates, holds and use dispositions remain unchanged."}})
        if sum(stats[key] for key in ("tp", "fn", "fp", "tn")) != result["binary_label_frames"]:
            raise ValueError("Lost canonical binary denominator")
        result["screens"][screen] = stats
    major = [row for row in rows if row["existing_major_review_required"]]
    heavy = [row for row in rows if _warning(row, "heavy_disagreement")]
    increment = [row for row in heavy if not row["existing_major_review_required"]]
    result["existing_major_hint_overlap"] = {
        "existing_major_hint_frames": len(major), "heavy_hint_frames": len(heavy),
        "overlap_frames": len(heavy) - len(increment),
        "union_frames": len(major) + len(increment), "new_hint_union_increment": len(increment),
        "new_hint_union_increment_by_canonical_label": {label: sum(row["canonical_label"] == label for row in increment) for label in LABELS},
        "new_gate_pass_bad_hint_beyond_major": sum(row["raw_gate_pass"] and row["canonical_label"] == "unreliable" for row in increment),
        "new_gate_pass_good_hint_beyond_major": sum(row["raw_gate_pass"] and row["canonical_label"] == "reliable" for row in increment),
        "increment_frames": _refs(increment)}
    return result


def _error_stats(source):
    values = sorted(source)
    if not values:
        return {"n": 0, "mean_px": None, "median_px": None, "p95_px": None, "maximum_px": None}
    position = .95 * (len(values) - 1)
    lower, upper = math.floor(position), math.ceil(position)
    p95 = values[lower] + (values[upper] - values[lower]) * (position - lower)
    return {"n": len(values), "mean_px": statistics.mean(values),
        "median_px": statistics.median(values), "p95_px": p95, "maximum_px": max(values)}


def _paired_stats(pairs):
    return {"original_full": _error_stats(pair["original_full_error_px"] for pair in pairs),
        "heavy": _error_stats(pair["heavy_error_px"] for pair in pairs),
        "difference_heavy_minus_original": _error_stats(pair["heavy_error_px"] - pair["original_full_error_px"] for pair in pairs)}


def _manual_auxiliary(manual, clip, rows):
    if manual is None:
        return None
    source = manual["source_video"]
    if (source["pitch_id"] != "pitch_003" or source["total_frames"] != clip["total_frames"] or
            source["sha256"] != clip["video_sha256"] or
            manual.get("coordinate_system") != "original_image_pixels_xy" or
            manual.get("image_size") != {"width": clip["width"], "height": clip["height"]}):
        raise ValueError("Auxiliary XY source or coordinate system differs")
    frames = _frames(manual, clip["total_frames"], "manual XY")
    reports = {}
    for role in ROLES:
        statuses, pairs, single_rows = Counter(), [], []
        for row in rows:
            if row["pitch_id"] != "pitch_003" or row["role"] != role or not row["effectiveness_eligible"]:
                continue
            matches = [point for point in frames[row["frame_index"]]["joints"] if point["name"] == row["landmark"]]
            if len(matches) != 1:
                raise ValueError("Missing or repeated auxiliary manual joint")
            point = matches[0]
            status = point["status"]
            if status not in ("visible", "not_observable", "uncertain"):
                raise ValueError("Auxiliary manual review is incomplete")
            statuses[status] += 1
            xy = [point["x_px"], point["y_px"]]
            if status != "visible":
                if xy != [None, None]:
                    raise ValueError("Unobservable or uncertain XY cannot become visible truth")
                continue
            if not all(_finite(value) for value in xy):
                raise ValueError("Visible auxiliary XY must be finite")
            errors = {}
            for name, finite, predicted_xy in (("original_full", row["raw_finite"], row["raw_xy_px"]),
                    ("heavy", row["heavy_selected_finite"], row["heavy_xy_px"])):
                errors[name] = math.hypot(predicted_xy[0] - xy[0], predicted_xy[1] - xy[1]) if finite else None
            single_rows.append({"frame_index": row["frame_index"], "original_full_error_px": errors["original_full"],
                "heavy_error_px": errors["heavy"], "raw_gate_pass": row["raw_gate_pass"],
                "heavy_gate_pass_diagnostic_only": row["heavy_gate_pass_diagnostic_only"]})
            if None in errors.values():
                continue
            pairs.append({**single_rows[-1], "canonical_label_of_original_full": row["canonical_label"],
                "manual_xy_px": xy, "original_full_xy_px": deepcopy(row["raw_xy_px"]),
                "heavy_xy_px": deepcopy(row["heavy_xy_px"]),
                "heavy_hint": deepcopy(row["screens"]["heavy_disagreement"])})
        reports[role] = {"manual_status_counts_non_seed": dict(statuses),
            "visible_reference_frames": len(single_rows),
            "original_full_missing_visible_frames": sum(row["original_full_error_px"] is None for row in single_rows),
            "heavy_selected_missing_visible_frames": sum(row["heavy_error_px"] is None for row in single_rows),
            "original_full_gate_pass_visible_frames": sum(row["raw_gate_pass"] for row in single_rows),
            "heavy_gate_pass_visible_frames_diagnostic_only": sum(row["heavy_gate_pass_diagnostic_only"] for row in single_rows),
            "same_frame_same_joint_paired_errors": _paired_stats(pairs),
            "paired_original_gate_pass_errors": _paired_stats([pair for pair in pairs if pair["raw_gate_pass"]]),
            "paired_heavy_gate_pass_errors_diagnostic_only": _paired_stats([pair for pair in pairs if pair["heavy_gate_pass_diagnostic_only"]]),
            "paired_both_gates_pass_errors": _paired_stats([pair for pair in pairs if pair["raw_gate_pass"] and pair["heavy_gate_pass_diagnostic_only"]]),
            "visible_reference_continuous_errors": single_rows, "pairs": pairs}
    return {"purpose": "Auxiliary continuous XY comparison only; no labels, calibration, cutoff or adoption criterion.",
        "scope": "pitch_003 visible manual joints only; paired model errors use exactly the same frames and joints.",
        "heavy_quality_labelled": False, "roles": reports}


def evaluate_clips(measurements, predictions, ground_truths, baseline_evaluation, major_hints, manual_xy=None):
    """Evaluate sealed fivefold hints without mutating any borrowed source.

    Recomputing training maxima here is an integrity audit of the sealed thresholds,
    not another calibration attempt. Query GT enters only this evaluation stage.
    """
    if any(set(mapping) != set(PITCH_IDS) for mapping in (measurements, predictions, ground_truths, major_hints)):
        raise ValueError("Require exactly the five formal clips in every source map")
    historical = _baseline_rows(baseline_evaluation)
    rows, totals, fold_status = [], {}, {}
    for pid in PITCH_IDS:
        clip, prediction, gt, hints = measurements[pid], predictions[pid], ground_truths[pid], major_hints[pid]
        total = clip["total_frames"]
        if (clip["pitch_id"] != pid or prediction["pitch_id"] != pid or type(total) is not int or total < 2 or
                any(not _finite(clip[key]) or clip[key] <= 0 for key in ("width", "height"))):
            raise ValueError("Wrong measurement or prediction target")
        source = gt["source_video"]
        if (source["pitch_id"] != pid or source["total_frames"] != total or gt.get("annotation_status") != "reviewed" or
                source.get("sha256") is not None and source["sha256"] != clip["video_sha256"] or
                hints["pitch_id"] != pid or hints.get("status") != "evaluated_development_evidence"):
            raise ValueError("Wrong or incomplete canonical/major source")
        timelines = {role: _timeline(gt, role, total) for role in ROLES}
        mf, pf, hf = (_frames(data, total, name) for data, name in (
            (clip, "Heavy measurement"), (prediction, "Heavy prediction"), (hints, "major hints")))
        fold_status[pid] = prediction["fold_status"]
        if set(fold_status[pid]) != set(ROLES) or any(value not in ("calibrated", "failed") for value in fold_status[pid].values()):
            raise ValueError("Invalid Heavy fold status")
        previous_time = None
        for measurement, predicted, major in zip(mf, pf, hf, strict=True):
            index, timestamp = measurement["frame_index"], measurement["timestamp_ms"]
            if (not _finite(timestamp) or timestamp < 0 or index == 0 and timestamp != 0 or
                    previous_time is not None and timestamp <= previous_time or
                    not _finite(major["timestamp_ms"]) or abs(major["timestamp_ms"] - timestamp) > 1 or
                    type(major["review_required"]) is not bool):
                raise ValueError("Changed frame timeline or unavailable major evidence")
            previous_time = timestamp
            if "timestamp_ms" in predicted and predicted["timestamp_ms"] != timestamp:
                raise ValueError("Changed prediction timestamp")
            for role in ROLES:
                key = pid, index, role
                if key not in historical or historical[key]["timestamp_ms"] != timestamp:
                    raise ValueError("Historical frame timeline incomplete or changed")
                rows.append(_measurement_row(pid, clip, measurement, role, historical[key],
                    timelines[role][index], major["review_required"]))
        totals[pid] = total
    if len(historical) != len(rows):
        raise ValueError("Unexpected historical rows outside the complete measurement timeline")
    for row in rows:
        pid, role, index = row["pitch_id"], row["role"], row["frame_index"]
        eligible_training = [source["distance_diagonal"] for source in rows if source["pitch_id"] != pid and
            source["role"] == role and source["effectiveness_eligible"] and source["canonical_label"] == "reliable" and
            source["distance_diagonal"] is not None]
        expected_threshold = max(eligible_training) if eligible_training else None
        expected_status = "calibrated" if eligible_training else "failed"
        if fold_status[pid][role] != expected_status:
            raise ValueError("Fold calibration status disagrees with four training clips")
        predicted = predictions[pid]["frames"][index]["roles"][role]
        _validate_prediction(predicted, row, expected_status, expected_threshold)
        row["screens"]["heavy_disagreement"] = deepcopy(predicted)
    clips = [{"pitch_id": pid, "source_frames": totals[pid], "non_seed_frames": totals[pid] - 1,
        "fold_status": deepcopy(fold_status[pid]), "precise_accuracy": None,
        "roles": {role: _summarize([row for row in rows if row["pitch_id"] == pid and row["role"] == role]) for role in ROLES}}
        for pid in PITCH_IDS]
    aggregate = {role: _summarize([row for row in rows if row["role"] == role]) for role in ROLES}
    stats = {role: [{"pitch_id": clip["pitch_id"], "calibration_status": fold_status[clip["pitch_id"]][role],
        **{key: clip["roles"][role]["screens"]["heavy_disagreement"][key] for key in ("tp", "fn", "fp", "tn")},
        "gate_passed_bad_hinted": clip["roles"][role]["screens"]["heavy_disagreement"]["retention_on_original_raw_gate_pass"]["newly_caught_gate_pass_wrong_points"]}
        for clip in clips] for role in ROLES}
    auxiliary = _manual_auxiliary(manual_xy, measurements["pitch_003"], rows)
    clips[2]["precise_accuracy"] = auxiliary
    held_out = deepcopy(clips[2])
    held_out["training_clip_ids"] = [pid for pid in PITCH_IDS if pid != "pitch_003"]
    held_out["known_major_miss_frame_104_context"] = [deepcopy(row) for row in rows if row["pitch_id"] == "pitch_003" and row["frame_index"] == 104]
    held_out["interpretation"] = "Whole-clip held-out predictions. Frame 104 and original major holds are not repaired using known answers."
    return {"status": "complete_single_fixed_heavy_information_evaluation", "source_frames": sum(totals.values()),
        "non_seed_frames": sum(total - 1 for total in totals.values()), "source_joint_rows": len(rows),
        "non_seed_joint_rows": sum(row["effectiveness_eligible"] for row in rows), "clips": clips,
        "aggregate": aggregate,
        "non003_aggregate": {role: _summarize([row for row in rows if row["pitch_id"] != "pitch_003" and row["role"] == role]) for role in ROLES},
        "held_out_pitch_003": held_out, "decision": decision(stats), "frame_joint_rows": rows,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "One developmental five-video screening comparison. Canonical labels target original Full raw predictions, not Heavy. No hint is not reliability. Unknown and missing stay in denominators. No data, coordinates, gate or existing use disposition changed."}
