"""Source-bound evaluation of sealed mode sensitivity, never fit a warning policy."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean, median
from types import SimpleNamespace

import cv2
import numpy as np

from pitch_analysis.ground_truth import validate_ground_truth, FULL_JOINT_LABELS
from pitch_analysis.manual_keypoints import validate_manual_keypoints
from pitch_analysis.subject import PitcherSelector
import measure_pose_mode_countercheck as measure


def describe(values):
    values = [v for v in values if v is not None]
    return {"count": len(values), "mean": mean(values) if values else None,
            "median": median(values) if values else None,
            "p95": float(np.percentile(values, 95)) if values else None,
            "max": max(values) if values else None}


def rank_auc(positive, negative):
    if not positive or not negative:
        return None
    differences = np.asarray(positive)[:, None] - np.asarray(negative)[None, :]
    return float(np.mean((differences > 0) + .5 * (differences == 0)))


def compare_distributions(values, labels, positive="confirmed", negative="known_negative"):
    p = [v for v, label in zip(values, labels, strict=True) if label == positive and v is not None]
    n = [v for v, label in zip(values, labels, strict=True) if label == negative and v is not None]
    return {"positive_label": positive, "negative_label": negative,
            "positive_total": labels.count(positive), "negative_total": labels.count(negative),
            "positive_measured": describe(p), "negative_measured": describe(n),
            "positive_unmeasured": labels.count(positive) - len(p),
            "negative_unmeasured": labels.count(negative) - len(n),
            "excluded_labels": dict(Counter(x for x in labels if x not in (positive, negative))),
            "conditional_rank_auc_higher_is_positive": rank_auc(p, n),
            "interpretation": "Known development data, measured subset only; not warning recall or IMAGE accuracy."}


def major_timeline(intervals, total):
    values = ["known_negative"] * total
    for interval in intervals:
        start, end = interval["start_frame"], interval["end_frame"]
        if not 0 <= start <= end < total:
            raise ValueError("Major interval outside original timeline")
        values[start:end + 1] = [interval["status"]] * (end - start + 1)
    return values


def joint_timeline(intervals, total):
    values = [None] * total
    for interval in intervals:
        start, end = interval["start_frame"], interval["end_frame"]
        if not 0 <= start <= end < total or any(value is not None for value in values[start:end + 1]):
            raise ValueError("Invalid or overlapping joint interval")
        values[start:end + 1] = [interval["status"]] * (end - start + 1)
    if any(value is None for value in values):
        raise ValueError("Incomplete human joint timeline")
    return values


def coordinate_rows(manual, raw, frames, width, height, config, major):
    rows = []
    for reference, before, frame in zip(manual["frames"], raw, frames, strict=True):
        after = measure.selected_points(frame["image_candidates"], frame["image_selection"])
        for joint in reference["joints"]:
            name, status = joint["name"], joint["status"]
            item = {"frame_index": frame["frame_index"], "landmark": name, "human_status": status,
                    "major_reference": major[frame["frame_index"]], "video_error_px": None, "image_error_px": None,
                    "video_gate_pass": measure.gate(before.get(name), config),
                    "image_gate_pass": measure.gate(after.get(name), config)}
            # Hidden inferred coordinates cannot become an accuracy target.
            if status == "visible":
                for label, pose in (("video", before), ("image", after)):
                    if measure.finite_point(pose.get(name)):
                        point = pose[name]
                        item[label + "_error_px"] = math.hypot(point["x"] * width - joint["x_px"],
                                                               point["y"] * height - joint["y_px"])
            rows.append(item)
    return rows


def coordinate_summary(rows):
    visible = [r for r in rows if r["human_status"] == "visible"]
    common = [r for r in visible if r["video_error_px"] is not None and r["image_error_px"] is not None]
    gated = [r for r in common if r["video_gate_pass"] and r["image_gate_pass"]]
    return {"all_reference_rows": len(rows), "human_status_counts": dict(Counter(r["human_status"] for r in rows)),
            "visible_reference_denominator": len(visible),
            "video_finite": describe([r["video_error_px"] for r in visible]),
            "image_finite": describe([r["image_error_px"] for r in visible]),
            "video_existing_gate_points": sum(r["video_gate_pass"] for r in visible),
            "image_existing_gate_points": sum(r["image_gate_pass"] for r in visible),
            "common_finite": {"count": len(common), "video": describe([r["video_error_px"] for r in common]),
                              "image": describe([r["image_error_px"] for r in common])},
            "common_existing_gate": {"count": len(gated), "video": describe([r["video_error_px"] for r in gated]),
                                     "image": describe([r["image_error_px"] for r in gated]),
                                     "image_error_lower": sum(r["image_error_px"] < r["video_error_px"] for r in gated),
                                     "image_error_higher": sum(r["image_error_px"] > r["video_error_px"] for r in gated),
                                     "equal": sum(r["image_error_px"] == r["video_error_px"] for r in gated)},
            "hidden_coordinates_evaluated": 0}


def validate_binding(gt, clip, data):
    validate_ground_truth(gt)
    if gt["annotation_status"] != "reviewed" or gt["review_profile"] != "phase2_full_review":
        raise ValueError("Completed canonical full review required")
    source = gt["source_video"]
    if (source["pitch_id"], source["sha256"], source["total_frames"], source["frame_index_base"]) != (clip["pitch_id"], data["video_sha256"], data["total_frames"], 0):
        raise ValueError("Human/video binding mismatch")


def replay_and_verify(data, raw, context, capture, config):
    selector = PitcherSelector()
    total = data["total_frames"]
    if [f["frame_index"] for f in data["frames"]] != list(range(total)):
        raise ValueError("Incomplete countercheck denominator")
    for index, frame in enumerate(data["frames"]):
        ok, pixels = capture.read()
        if not ok:
            raise ValueError("Missing source image")
        import hashlib
        if hashlib.sha256(pixels.tobytes()).hexdigest() != frame["decoded_bgr_sha256"]:
            raise ValueError("Countercheck source pixels changed")
        poses = [[SimpleNamespace(**point) for point in candidate] for candidate in frame["image_candidates"]]
        if measure.serialize_candidates(poses) != frame["image_candidates"]:
            raise ValueError("Invalid saved experimental candidates")
        from dataclasses import asdict
        choice = asdict(selector.select(poses))
        reproduced = measure.frame_measurement(index, context["selection_frames"][index]["timestamp_ms"], capture.get(cv2.CAP_PROP_POS_MSEC),
            frame["decoded_bgr_sha256"], frame["image_candidates"], choice, raw[index],
            context["selection_frames"][index], data["width"], data["height"], config)
        if frame != reproduced:
            raise ValueError("Saved selection/disagreement does not reproduce")
    if capture.read()[0]:
        raise ValueError("Extra source frames")


def evaluate(root, plan_path, measurement_root, output):
    root, output = root.resolve(), output.resolve()
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Fresh evaluator output required inside analysis_results")
    plan = measure.read(plan_path)
    measure.validate_plan(plan)
    reference_paths = {clip["ground_truth"] for clip in plan["clips"]}
    reference_paths.update(clip["manual_reference"] for clip in plan["clips"] if clip.get("manual_reference"))
    if reference_paths != plan["evaluator_only_source_hashes"].keys():
        raise ValueError("Unbound/unexpected evaluator human input")
    run = measure.read(measurement_root / "measurement_run.json")
    if run["status"] != "measurements_only" or run["human_annotation_inputs"] or run["warning_predictions_generated"]:
        raise ValueError("Expected sealed GT-blind measurements only")
    if run["plan_sha256"] != measure.sha(plan_path) or plan["producer_sha256"] != measure.sha(measure.__file__) or plan["evaluator_sha256"] != measure.sha(__file__):
        raise ValueError("Plan/runner receipt mismatch")
    if run["parameters"] != measure.PARAMETERS or plan["parameters"] != measure.PARAMETERS or run["options"] != measure.OPTIONS or plan["options"] != measure.OPTIONS or run["runtime"] != plan["runtime"] or plan["runtime"] != measure.runtime():
        raise ValueError("Runtime/parameters changed")
    if run["measurement_source_hashes"] != plan["measurement_source_hashes"] or run["producer_sha256"] != plan["producer_sha256"]:
        raise ValueError("Producer/source receipts changed")
    for hashes in (plan["measurement_source_hashes"], plan["evaluator_only_source_hashes"], plan["protected_source_hashes"]):
        measure.verify_hashes(root, hashes)
    if [r["pitch_id"] for r in run["clips"]] != [c["pitch_id"] for c in plan["clips"]]:
        raise ValueError("Changed clip denominator")
    clips, coordinate_results, all_major_values, all_major_labels = [], {}, [], []
    files = {}
    for clip, receipt in zip(plan["clips"], run["clips"], strict=True):
        name = clip["pitch_id"]
        if receipt["path"] != name + ".json" or measure.sha(measurement_root / receipt["path"]) != receipt["sha256"]:
            raise ValueError("Experimental output receipt mismatch")
        files[receipt["path"]] = receipt["sha256"]
        data = measure.read(measurement_root / receipt["path"])
        native_metadata = measure.read(root / clip["video_metadata"])
        if (data["width"], data["height"], data["total_frames"], data["pitch_id"]) != (native_metadata["width"], native_metadata["height"], clip["total_frames"], name):
            raise ValueError("Changed source dimensions/timeline/identity")
        context = measure.read(root / clip["capture"])
        config = measure.read(root / clip["clean_config"])
        gt = measure.read(root / clip["ground_truth"])
        validate_binding(gt, clip, data)
        raw = measure.load_video_raw(root / clip["raw_csv"], context, data["total_frames"])
        capture = cv2.VideoCapture(str(root / clip["video"]))
        try:
            if not capture.isOpened():
                raise ValueError("Cannot verify original pixels")
            replay_and_verify(data, raw, context, capture, config)
        finally:
            capture.release()
        frames, total = data["frames"], data["total_frames"]
        labels = major_timeline(gt["labels"]["major_pose_failure_intervals"], total)
        values = [f["torso_median_distance_px"] / data["height"] if f["torso_median_distance_px"] is not None else None for f in frames]
        all_major_values.extend(values)
        all_major_labels.extend(labels)
        metadata = measure.read(root / clip["metadata"])
        throws = metadata["pitcher"]["throws"].upper()
        if throws not in ("LEFT", "RIGHT"):
            raise ValueError("Unknown handedness cannot be mapped to a joint role")
        lead = "LEFT" if throws == "RIGHT" else "RIGHT"
        roles = {"throwing_shoulder": throws + "_SHOULDER", "throwing_elbow": throws + "_ELBOW",
                 "throwing_wrist": throws + "_WRIST", "lead_hip": lead + "_HIP",
                 "lead_knee": lead + "_KNEE", "lead_ankle": lead + "_ANKLE"}
        joint_groups = {}
        for field in FULL_JOINT_LABELS:
            role = field.removesuffix("_reliability")
            landmark = roles[role]
            human = joint_timeline(gt["labels"][field], total)
            joint_groups[role] = {"landmark": landmark,
                "disagreement_vs_original_overlay_review": compare_distributions(
                    [f["joint_disagreement"][landmark]["gated_distance_image_height"] for f in frames], human, "unreliable", "reliable"),
                "unmeasured_reason_counts": dict(Counter(reason for f in frames for reason in f["joint_disagreement"][landmark]["unmeasured_reasons"]))}
        clips.append({"pitch_id": name, "total_frames": total,
            "image_selection_counts": dict(Counter(f["image_selection"]["status"] for f in frames)),
            "image_candidate_counts": dict(Counter(len(f["image_candidates"]) for f in frames)),
            "video_selection_counts": dict(Counter(f["video_selection"]["status"] for f in frames)),
            "torso_disagreement_vs_major_reference": compare_distributions(values, labels),
            "joint_disagreement": joint_groups, "image_localization_accuracy": None,
            "identity_accuracy": None, "warning_tp_fn_fp": None})
        if clip.get("manual_reference"):
            manual = measure.read(root / clip["manual_reference"])
            validate_manual_keypoints(manual)
            if manual["annotation_status"] != "reviewed" or manual["source_video"] != gt["source_video"] or manual["image_size"] != {"width": data["width"], "height": data["height"]}:
                raise ValueError("Manual coordinate binding mismatch")
            if any(not math.isclose(reference["timestamp_ms"], f["native_timestamp_ms"], abs_tol=1e-6)
                   for reference, f in zip(manual["frames"], frames, strict=True)):
                raise ValueError("Manual/native frame timestamp mismatch")
            rows = coordinate_rows(manual, raw, frames, data["width"], data["height"], config, labels)
            coordinate_results[name] = {"all": coordinate_summary(rows),
                "confirmed_major": coordinate_summary([r for r in rows if r["major_reference"] == "confirmed"]),
                "other_frames": coordinate_summary([r for r in rows if r["major_reference"] == "known_negative"]),
                "by_joint": {joint: coordinate_summary([r for r in rows if r["landmark"] == joint]) for joint in sorted({r["landmark"] for r in rows})},
                "rows": rows}
    output.mkdir(parents=True)
    report = {"status": "development_countercheck_complete", "plan_sha256": measure.sha(plan_path),
        "measurement_run_sha256": measure.sha(measurement_root / "measurement_run.json"),
        "experimental_output_hashes": files, "total_frames": sum(c["total_frames"] for c in clips),
        "clips": clips, "combined_disagreement_vs_major": compare_distributions(all_major_values, all_major_labels),
        "coordinate_results": coordinate_results, "warning_policy": None, "warning_tp_fn_fp": None,
        "phase2_automatic_reliability": "NOT PASSED", "production_adoption": False,
        "limitations": ["Same model: agreement does not prove subject identity or accurate keypoints.",
                        "Mode change includes scheduling/temporal processing; does not isolate an internal failure cause.",
                        "Original selector remains temporal; candidate index is not a cross-arm identity.",
                        "Qualitative GT describes original VIDEO overlay, not IMAGE localization accuracy.",
                        "Only reviewed visible XY in the one coordinate-labelled clip measures IMAGE error.",
                        "No threshold fitting, holdout/generalization claim, hidden-point scoring or event detection."]}
    measure.write(output / "comparison.json", report)
    for hashes in (plan["measurement_source_hashes"], plan["evaluator_only_source_hashes"], plan["protected_source_hashes"]):
        measure.verify_hashes(root, hashes)
    measure.write(output / "evidence_integrity_check.json", {
        "source_inventories_unchanged": {key: len(plan[key]) for key in ("measurement_source_hashes", "evaluator_only_source_hashes", "protected_source_hashes")},
        "native_frames_verified": report["total_frames"], "selection_and_disagreement_rows_reproduced": report["total_frames"],
        "inference_reproduced": False, "warning_policy": None, "human_annotations_modified": False})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("measurement_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = evaluate(args.root, args.plan, args.measurement_root, args.output)
    print(json.dumps({"frames": result["total_frames"], "clips": len(result["clips"]), "phase2": result["phase2_automatic_reliability"]}))
