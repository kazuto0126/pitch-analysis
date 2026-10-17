"""Pure evaluation of the one sealed Full/RTMPose native-response experiment.

No file IO, pose inference, selection, calibration writes or data repair occurs
here. Canonical reviews describe original Full predictions, never RTMPose labels.
Visible manual XY is an auxiliary paired comparison on pitch_003 only.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math
from numbers import Real
import statistics

import numpy as np

from heavy_information_policy import decision


PITCH_IDS = tuple(f"pitch_{i:03d}" for i in range(1, 6))
ROLES = ("throwing_elbow", "throwing_wrist")
LABELS = ("reliable", "unreliable", "not_observable", "uncertain")
HISTORICAL_SCREENS = ("score_only", "sample_maximum", "classifier")
SCREENS = ("rtmpose_response", *HISTORICAL_SCREENS)
LANDMARK_INDEX = {"RIGHT_ELBOW": 8, "RIGHT_WRIST": 10}
COCO_NAMES = ("NOSE", "LEFT_EYE", "RIGHT_EYE", "LEFT_EAR", "RIGHT_EAR",
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST",
    "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE")


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


def _list_close(actual, expected, message):
    if expected is None:
        if actual is not None:
            raise ValueError(message)
    elif not isinstance(actual, list) or len(actual) != len(expected):
        raise ValueError(message)
    else:
        for value, reference in zip(actual, expected, strict=True):
            _close(value, reference, message)


def _native(frame, width, height):
    """Independently audit native vectors, ROI affine and all 17 argmax points."""
    geometry = frame["geometry"]
    fixed = {"source_size": [width, height], "input_size": [192, 256],
        "simcc_split_ratio": 2, "padding": 1.25, "rotation": 0, "color_order": "RGB",
        "mean": [123.675, 116.28, 103.53], "std": [58.395, 57.12, 57.375],
        "interpolation": "INTER_LINEAR", "border_mode": "BORDER_CONSTANT", "border_value": 0,
        "normalize_simcc": False, "use_dark": False, "flip_test": False}
    if any(geometry.get(key) != value for key, value in fixed.items()):
        raise ValueError("Geometry differs from the fixed native SDK contract")
    roi = geometry["roi_xywh"]
    if (not isinstance(roi, list) or len(roi) != 4 or not all(_finite(value) for value in roi)
            or roi[2] <= 0 or roi[3] <= 0):
        raise ValueError("Invalid original CSRT ROI")
    x, y, w, h = roi
    cx, cy = x + w / 2, y + h / 2
    if w > h * .75:
        h = w / .75
    else:
        w = h * .75
    scale_w, scale_h = w * 1.25, h * 1.25
    _list_close(geometry["center_xy"], [cx, cy], "Changed ROI center")
    _list_close(geometry["scale_wh"], [scale_w, scale_h], "Changed ROI scale")
    sx, sy = 192 / scale_w, 256 / scale_h
    expected_forward = [[sx, 0, 96 - cx * sx], [0, sy, 128 - cy * sy]]
    expected_inverse = [[1 / sx, 0, cx - 96 / sx], [0, 1 / sy, cy - 128 / sy]]
    matrices = []
    for name, expected in (("affine_src_to_input", expected_forward), ("affine_input_to_src", expected_inverse)):
        actual = geometry[name]
        if not isinstance(actual, list) or len(actual) != 2:
            raise ValueError("Invalid affine matrix")
        for row, reference in zip(actual, expected, strict=True):
            _list_close(row, reference, "Changed SDK affine matrix")
        matrices.append(np.asarray(actual, dtype=np.float64))
    vectors = []
    for key, shape in (("native_simcc_x", (1, 17, 384)), ("native_simcc_y", (1, 17, 512))):
        values = frame[key]
        if not isinstance(values, np.ndarray) or values.dtype != np.float32 or values.shape != shape:
            raise ValueError("Native SimCC must keep exact float32 COCO17 axis shape")
        vectors.append(values[0])
    xs, ys = vectors
    contract = frame["native_contract"]
    if (contract.get("landmark_count") != 17 or contract.get("input_size") != [192, 256] or
            contract.get("simcc_split_ratio") != 2 or contract.get("simcc_x_shape") != [1, 17, 384] or
            contract.get("simcc_y_shape") != [1, 17, 512] or contract.get("response_normalized") is not False or
            contract.get("score") != "minimum_of_native_axis_maxima" or contract.get("decoded_nonpositive_score_xy") is not None):
        raise ValueError("Changed native COCO17 output contract")
    points = frame["native_keypoints"]
    if not isinstance(points, list) or len(points) != 17:
        raise ValueError("Preserve native COCO17; do not fabricate a 33-point estimate")
    forward, inverse = matrices
    for index, (name, point) in enumerate(zip(COCO_NAMES, points, strict=True)):
        if (point["name"] != name or point["index"] != index or
                any(key in point for key in ("z", "visibility", "presence"))):
            raise ValueError("Native landmark names/order or score-only contract changed")
        finite = bool(np.isfinite(xs[index]).all() and np.isfinite(ys[index]).all())
        arg_x = arg_y = max_x = max_y = score = decoded_input = source = None
        if finite:
            arg_x, arg_y = int(np.argmax(xs[index])), int(np.argmax(ys[index]))
            max_x, max_y = float(xs[index, arg_x]), float(ys[index, arg_y])
            score, decoded_input = min(max_x, max_y), [arg_x / 2, arg_y / 2]
            if score > 0:
                converted = inverse @ np.asarray([*decoded_input, 1.], dtype=np.float64)
                if np.isfinite(converted).all():
                    source = converted.tolist()
        state = "nonfinite_response" if not finite else (
            "nonpositive_score" if score <= 0 else "decoded" if source is not None else "nonfinite_inverse_coordinate")
        if (point["finite_response"] is not finite or point["argmax_x_bin"] != arg_x or
                point["argmax_y_bin"] != arg_y or point["decode_status"] != state):
            raise ValueError("Changed native response decoding")
        for key, expected in (("response_x_max", max_x), ("response_y_max", max_y), ("score", score),
                ("x_px", source[0] if source is not None else None), ("y_px", source[1] if source is not None else None)):
            _close(point[key], expected, "Changed raw SimCC argmax or native score")
        _list_close(point["argmax_input_xy"], decoded_input, "Changed native argmax input coordinate")
    return forward, xs, ys, points


def _measurement_row(pid, clip, frame, role, baseline, label, major, native):
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
    forward, xs, ys, points = native
    native_index = LANDMARK_INDEX[landmark]
    point = points[native_index]
    native_xy = [point["x_px"], point["y_px"]] if point["x_px"] is not None else None
    native_finite = native_xy is not None
    input_xy = bins = deficit = None
    reason = None
    if not raw_finite:
        reason = "missing_or_nonfinite_full_point"
    else:
        converted = forward @ np.asarray([*raw_xy, 1.], dtype=np.float64)
        if not np.isfinite(converted).all():
            reason = "nonfinite_full_input_coordinate"
        else:
            input_xy = converted.tolist()
            bins = [math.floor(2 * value + .5) for value in input_xy]
            if not point["finite_response"]:
                reason = "nonfinite_native_response"
            elif not (0 <= bins[0] < 384 and 0 <= bins[1] < 512):
                reason = "full_point_outside_simcc_bins"
            else:
                deficit = ((point["response_x_max"] - float(xs[native_index, bins[0]])) +
                           (point["response_y_max"] - float(ys[native_index, bins[1]])))
                if not _finite(deficit):
                    deficit, reason = None, "nonfinite_response_deficit"
    if (source["native_joint_index"] != native_index or source["native_vector_finite"] is not point["finite_response"] or
            source["bins"] != bins or source["reason"] != reason):
        raise ValueError("Changed native joint mapping, nearest bin or response insufficiency")
    _list_close(source["full_xy_px"], raw_xy, "Changed Full source coordinate")
    _list_close(source["full_input_xy"], input_xy, "Changed Full affine coordinate")
    _list_close(source["native_xy_px"], native_xy, "Changed native diagnostic coordinate")
    _close(source["native_score"], point["score"], "Changed native diagnostic score")
    _close(source["response_deficit"], deficit, "Changed raw SimCC response deficit")
    if source["evidence_status"] != ("measured" if deficit is not None else "insufficient_evidence"):
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
        "native_decoded_finite": native_finite, "native_xy_px": deepcopy(native_xy),
        "native_score": point["score"], "native_joint_index": native_index,
        "native_positive_score_diagnostic_only": bool(native_finite),
        "full_input_xy": deepcopy(input_xy), "bins": deepcopy(bins), "response_deficit": deficit,
        "evidence_status": source["evidence_status"],
        "evidence_reason": reason, "native_decode": deepcopy(point),
        "existing_major_review_required": major,
        "original_context": deepcopy(baseline["original_context"]), "screens": screens}


def _validate_prediction(predicted, row, fold_status, expected_threshold):
    if type(predicted["frame_index"]) is not int or predicted["frame_index"] != row["frame_index"]:
        raise ValueError("Changed prediction frame identity")
    _close(predicted["response_deficit"], row["response_deficit"], "Prediction response deficit changed")
    _close(predicted["threshold"], expected_threshold, "Prediction training maximum changed")
    warning = False
    if row["frame_index"] == 0:
        status, review = "seed_excluded", False
    elif fold_status != "calibrated":
        status, review = "calibration_failed", None
    elif row["response_deficit"] is None:
        status, review = "insufficient_evidence", None
    else:
        warning = row["response_deficit"] > expected_threshold
        status, review = ("warning" if warning else "no_warning"), warning
    if (predicted["status"] != status or predicted["review_required"] is not review or
            predicted["evaluated_warning"] is not warning or
            predicted["effectiveness_eligible"] is not row["effectiveness_eligible"]):
        raise ValueError("Prediction is not the frozen strict-maximum/abstention decision")


def _warning(row, screen):
    value = row["screens"][screen]
    return value["evaluated_warning"] if screen == "rtmpose_response" else value["warning"]


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
        "native_decoded_finite_frames": sum(row["native_decoded_finite"] for row in rows),
        "native_decoded_missing_frames": sum(not row["native_decoded_finite"] for row in rows),
        "native_vector_finite_frames": sum(row["native_decode"]["finite_response"] for row in rows),
        "nonpositive_native_score_frames": sum(row["native_score"] is not None and row["native_score"] <= 0 for row in rows),
        "measurable_response_deficit_frames": sum(row["response_deficit"] is not None for row in rows),
        "full_point_outside_simcc_bins_frames": sum(row["evidence_reason"] == "full_point_outside_simcc_bins" for row in rows),
        "evidence_status_counts": _counts(row["evidence_status"] for row in rows),
        "evidence_reason_counts": _counts(row["evidence_reason"] or "measured" for row in rows),
        "native_decode_status_counts": _counts(row["native_decode"]["decode_status"] for row in rows),
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
        state = "status" if screen == "rtmpose_response" else "state"
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
    rtmpose = [row for row in rows if _warning(row, "rtmpose_response")]
    increment = [row for row in rtmpose if not row["existing_major_review_required"]]
    result["existing_major_hint_overlap"] = {
        "existing_major_hint_frames": len(major), "rtmpose_hint_frames": len(rtmpose),
        "overlap_frames": len(rtmpose) - len(increment),
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
        "rtmpose": _error_stats(pair["rtmpose_error_px"] for pair in pairs),
        "difference_rtmpose_minus_original": _error_stats(pair["rtmpose_error_px"] - pair["original_full_error_px"] for pair in pairs)}


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
                    ("rtmpose", row["native_decoded_finite"], row["native_xy_px"])):
                errors[name] = math.hypot(predicted_xy[0] - xy[0], predicted_xy[1] - xy[1]) if finite else None
            single_rows.append({"frame_index": row["frame_index"], "original_full_error_px": errors["original_full"],
                "rtmpose_error_px": errors["rtmpose"], "raw_gate_pass": row["raw_gate_pass"],
                "native_positive_score_diagnostic_only": row["native_positive_score_diagnostic_only"]})
            if None in errors.values():
                continue
            pairs.append({**single_rows[-1], "canonical_label_of_original_full": row["canonical_label"],
                "manual_xy_px": xy, "original_full_xy_px": deepcopy(row["raw_xy_px"]),
                "native_xy_px": deepcopy(row["native_xy_px"]),
                "rtmpose_hint": deepcopy(row["screens"]["rtmpose_response"])})
        reports[role] = {"manual_status_counts_non_seed": dict(statuses),
            "visible_reference_frames": len(single_rows),
            "original_full_missing_visible_frames": sum(row["original_full_error_px"] is None for row in single_rows),
            "rtmpose_decoded_missing_visible_frames": sum(row["rtmpose_error_px"] is None for row in single_rows),
            "original_full_gate_pass_visible_frames": sum(row["raw_gate_pass"] for row in single_rows),
            "rtmpose_decoded_positive_score_visible_frames_diagnostic_only": sum(row["native_positive_score_diagnostic_only"] for row in single_rows),
            "same_frame_same_joint_paired_errors": _paired_stats(pairs),
            "paired_original_gate_pass_errors": _paired_stats([pair for pair in pairs if pair["raw_gate_pass"]]),
            "paired_native_decoded_errors_diagnostic_only": _paired_stats([pair for pair in pairs if pair["native_positive_score_diagnostic_only"]]),
            "visible_reference_continuous_errors": single_rows, "pairs": pairs}
    return {"purpose": "Auxiliary continuous XY comparison only; no labels, calibration, cutoff or adoption criterion.",
        "scope": "pitch_003 visible manual joints only; paired model errors use exactly the same frames and joints.",
        "rtmpose_quality_labelled": False, "roles": reports}


def evaluate_clips(measurements, predictions, ground_truths, baseline_evaluation, major_hints, manual_xy=None, visibility_audit=None):
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
            (clip, "RTMPose measurement"), (prediction, "RTMPose prediction"), (hints, "major hints")))
        fold_status[pid] = prediction["fold_status"]
        if set(fold_status[pid]) != set(ROLES) or any(value not in ("calibrated", "failed") for value in fold_status[pid].values()):
            raise ValueError("Invalid RTMPose fold status")
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
            native = _native(measurement, clip["width"], clip["height"])
            for role in ROLES:
                key = pid, index, role
                if key not in historical or historical[key]["timestamp_ms"] != timestamp:
                    raise ValueError("Historical frame timeline incomplete or changed")
                rows.append(_measurement_row(pid, clip, measurement, role, historical[key],
                    timelines[role][index], major["review_required"], native))
        totals[pid] = total
    if len(historical) != len(rows):
        raise ValueError("Unexpected historical rows outside the complete measurement timeline")
    for row in rows:
        pid, role, index = row["pitch_id"], row["role"], row["frame_index"]
        eligible_training = [source["response_deficit"] for source in rows if source["pitch_id"] != pid and
            source["role"] == role and source["effectiveness_eligible"] and source["canonical_label"] == "reliable" and
            source["response_deficit"] is not None]
        expected_threshold = max(eligible_training) if eligible_training else None
        expected_status = "calibrated" if eligible_training else "failed"
        if fold_status[pid][role] != expected_status:
            raise ValueError("Fold calibration status disagrees with four training clips")
        predicted = predictions[pid]["frames"][index]["roles"][role]
        _validate_prediction(predicted, row, expected_status, expected_threshold)
        row["screens"]["rtmpose_response"] = deepcopy(predicted)
    clips = [{"pitch_id": pid, "source_frames": totals[pid], "non_seed_frames": totals[pid] - 1,
        "fold_status": deepcopy(fold_status[pid]), "precise_accuracy": None,
        "roles": {role: _summarize([row for row in rows if row["pitch_id"] == pid and row["role"] == role]) for role in ROLES}}
        for pid in PITCH_IDS]
    aggregate = {role: _summarize([row for row in rows if row["role"] == role]) for role in ROLES}
    stats = {role: [{"pitch_id": clip["pitch_id"], "calibration_status": fold_status[clip["pitch_id"]][role],
        **{key: clip["roles"][role]["screens"]["rtmpose_response"][key] for key in ("tp", "fn", "fp", "tn")},
        "gate_passed_bad_hinted": clip["roles"][role]["screens"]["rtmpose_response"]["retention_on_original_raw_gate_pass"]["newly_caught_gate_pass_wrong_points"]}
        for clip in clips] for role in ROLES}
    auxiliary = _manual_auxiliary(manual_xy, measurements["pitch_003"], rows)
    clips[2]["precise_accuracy"] = auxiliary
    held_out = deepcopy(clips[2])
    held_out["training_clip_ids"] = [pid for pid in PITCH_IDS if pid != "pitch_003"]
    held_out["known_major_miss_frame_104_context"] = [deepcopy(row) for row in rows if row["pitch_id"] == "pitch_003" and row["frame_index"] == 104]
    held_out["interpretation"] = "Whole-clip held-out predictions. Frame 104 and original major holds are not repaired using known answers."
    return {"status": "complete_single_fixed_rtmpose_response_evaluation", "source_frames": sum(totals.values()),
        "non_seed_frames": sum(total - 1 for total in totals.values()), "source_joint_rows": len(rows),
        "non_seed_joint_rows": sum(row["effectiveness_eligible"] for row in rows), "clips": clips,
        "aggregate": aggregate,
        "non003_aggregate": {role: _summarize([row for row in rows if row["pitch_id"] != "pitch_003" and row["role"] == role]) for role in ROLES},
        "held_out_pitch_003": held_out, "decision": decision(stats), "frame_joint_rows": rows,
        "visibility_audit_existing_sources_only": deepcopy(visibility_audit),
        "visibility_audit_effect_on_labels_denominators_or_decision": "none",
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "One developmental five-video screening comparison. Canonical labels target original Full raw predictions, not RTMPose. No hint is not reliability. Unknown and missing stay in denominators. No data, coordinates, gate or existing use disposition changed."}
