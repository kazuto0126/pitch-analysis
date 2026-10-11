"""Offline, source-bound comparison of sealed native MoveNet measurements.

No model is loaded. Geometry is a descriptive association aid, never identity
truth, and native scores have no availability or warning cutoff.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from check_movenet_compatibility import (COORDINATE_CONVENTION, JOINTS,
                                        native_slots, sha, to_source_xy)
import measure_pose_mode_countercheck as baseline
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints
from pitch_analysis.subject import PitcherSelector


EXPECTED = {"source_frames": 592, "non_seed_frames": 587}
PITCH_IDS = tuple(f"pitch_{index:03d}" for index in range(1, 6))
TORSO = ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP")
BASELINE_ARMS = ("video", "image")
ASSOCIATION = {
    "rule": "unique_positive_box_intersection_and_all_four_torso_inside_source_and_csrt",
    "candidate_requirements": ["native_box_has_positive_width_and_height",
        "native_box_has_positive_area_intersection_with_sealed_csrt",
        "all_four_native_torso_points_inside_half_open_source_image",
        "all_four_native_torso_points_inside_half_open_sealed_csrt"],
    "one_candidate": "unique_geometric_candidate",
    "zero_candidates": "none", "multiple_candidates": "ambiguous",
    "native_score_cutoff": None, "iou_resolves_ambiguity": False,
    "temporal_slot_identity": False, "subject_alignment_verified": False,
}
INVENTORY = {"path": "docs/evaluation_plans/phase2_pose_mode_countercheck_20261009.json",
    "sha256": "587d7df4e91e279262be408607c8bdc13d73b6f11c1a28e5f874ab0af3c3bb69",
    "key": "protected_source_hashes", "physical_files": 374}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def bound_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Bound input outside workspace")
    return path


def verify_ref(root, ref):
    path = bound_path(root, ref["path"])
    if sha(path) != ref["sha256"]:
        raise ValueError("Frozen source changed: " + ref["path"])
    return path


def describe(values):
    values = sorted(value for value in values if value is not None)
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    if not all(math.isfinite(value) for value in values):
        raise ValueError("Nonfinite descriptive statistic")
    def percentile(q):
        position = (len(values) - 1) * q
        low, high = math.floor(position), math.ceil(position)
        return values[low] + (values[high] - values[low]) * (position - low)
    return {"count": len(values), "mean": sum(values) / len(values),
        "median": percentile(.5), "p90": percentile(.9), "max": values[-1]}


def validate_geometry(geometry, target):
    """Check the recorded inverse; this does not rerun TensorFlow resizing."""
    if (geometry["source_width"] != target["width"] or
            geometry["source_height"] != target["height"] or
            geometry["target_width"] != 256 or geometry["target_height"] != 256 or
            geometry["coordinate_convention"] != COORDINATE_CONVENTION):
        raise ValueError("Recorded source/target geometry differs")
    for axis, before, after in (("width", "left", "right"), ("height", "top", "bottom")):
        resized = geometry["resized_" + axis]
        pads = [geometry["pad_" + part] for part in (before, after)]
        if (any(isinstance(value, bool) or not isinstance(value, int) for value in (resized, *pads)) or
                resized <= 0 or any(value < 0 for value in pads) or resized + sum(pads) != 256):
            raise ValueError("Invalid recorded resize/padding extent")
        scale = geometry["scale_x" if axis == "width" else "scale_y"]
        if not math.isfinite(scale) or scale != resized / target[axis]:
            raise ValueError("Recorded inverse scale differs")


def derive_slots(frame, target):
    geometry = frame["input_geometry"]
    validate_geometry(geometry, target)
    raw = np.asarray(frame["native_output"], dtype=np.float32)
    if raw.tolist() != frame["native_output"]:
        raise ValueError("Native output is not an exact serialized float32 array")
    slots = native_slots(raw, geometry)
    if slots != frame["slots"]:
        raise ValueError("Native slots, scores, source XY or semantics do not reproduce")
    result = []
    for slot in slots:
        ymin, xmin, ymax, xmax, _ = slot["native_box_ymin_xmin_ymax_xmax_score"]
        x0, y0 = to_source_xy(ymin, xmin, geometry)
        x1, y1 = to_source_xy(ymax, xmax, geometry)
        result.append({**slot, "source_box_xyxy": [x0, y0, x1, y1]})
    return result


def inside(xy, box):
    return box[0] <= xy[0] < box[2] and box[1] <= xy[1] < box[3]


def geometric_association(slots, rectangle, width, height):
    """Retain every competitor. IoU/score never resolves a candidate ambiguity."""
    if len(slots) != 6 or [slot["slot_index"] for slot in slots] != list(range(6)):
        raise ValueError("All six native slots in order are required")
    if rectangle is not None and (len(rectangle) != 4 or
            not all(math.isfinite(value) for value in rectangle) or rectangle[2] <= 0 or rectangle[3] <= 0):
        raise ValueError("Invalid sealed CSRT rectangle")
    roi = None if rectangle is None else [rectangle[0], rectangle[1],
        rectangle[0] + rectangle[2], rectangle[1] + rectangle[3]]
    diagnostics = []
    for slot in slots:
        box = slot["source_box_xyxy"]
        x0, y0, x1, y1 = box
        positive = x1 > x0 and y1 > y0
        area = (x1 - x0) * (y1 - y0) if positive else 0.
        points = dict(zip(JOINTS, slot["source_xy"], strict=True))
        source_torso = all(inside(points[name], [0, 0, width, height]) for name in TORSO)
        roi_torso = roi is not None and all(inside(points[name], roi) for name in TORSO)
        intersection = (max(0., min(x1, roi[2]) - max(x0, roi[0])) *
            max(0., min(y1, roi[3]) - max(y0, roi[1]))) if positive and roi else 0.
        roi_area = rectangle[2] * rectangle[3] if roi else None
        union = area + roi_area - intersection if roi else None
        iou = intersection / union if union and union > 0 else 0. if roi else None
        center = [(x0 + x1) / 2, (y0 + y1) / 2]
        hip = [(points["LEFT_HIP"][axis] + points["RIGHT_HIP"][axis]) / 2 for axis in (0, 1)]
        candidate = bool(positive and intersection > 0 and source_torso and roi_torso)
        diagnostics.append({"slot_index": slot["slot_index"], "source_box_xyxy": box,
            "instance_score": slot["native_box_ymin_xmin_ymax_xmax_score"][4],
            "positive_box_area": positive, "box_intersection_px2": intersection,
            "box_iou": iou, "box_coverage_by_csrt": intersection / area if area else None,
            "csrt_coverage_by_box": intersection / roi_area if roi_area else None,
            "box_center_distance_to_csrt_center_px": math.dist(center,
                [(roi[0] + roi[2]) / 2, (roi[1] + roi[3]) / 2]) if roi else None,
            "all_four_torso_inside_source": source_torso, "all_four_torso_inside_csrt": roi_torso,
            "hip_midpoint_xy": hip, "hip_midpoint_inside_csrt": inside(hip, roi) if roi else None,
            "geometric_candidate": candidate})
    candidates = [row["slot_index"] for row in diagnostics if row["geometric_candidate"]]
    ranking = sorted(diagnostics, key=lambda row: (-(row["box_iou"] or 0), row["slot_index"])) if roi else []
    return {"rule": ASSOCIATION["rule"], "status": "unique_geometric_candidate" if len(candidates) == 1
            else "ambiguous" if len(candidates) > 1 else "none",
        "candidate_slot_indices": candidates,
        "descriptive_slot_index": candidates[0] if len(candidates) == 1 else None,
        "reason": "missing_sealed_csrt" if roi is None else "geometry_only_unverified_identity",
        "csrt_rectangle_xywh": rectangle, "competitors": diagnostics,
        "box_iou_ranking_slot_indices": [row["slot_index"] for row in ranking],
        "top_minus_runner_up_box_iou": ranking[0]["box_iou"] - ranking[1]["box_iou"] if ranking else None,
        "subject_alignment_verified": False, "ground_truth_used": False, "score_cutoff": None}


def baseline_state(point, target, config):
    finite = baseline.finite_point(point)
    xy = [point["x"] * target["width"], point["y"] * target["height"]] if finite else None
    return {"selected_raw": point is not None, "finite": finite, "missing": point is None,
        "existing_gate_pass": baseline.gate(point, config),
        "xy_px": xy, "outside_image": not inside(xy, [0, 0, target["width"], target["height"]]) if xy else None,
        "visibility": point["visibility"] if finite else None, "presence": point["presence"] if finite else None}


def joint_diagnostics(slots, association, arms, target, config):
    rows = {}
    for joint_index, name in enumerate(JOINTS):
        states = {arm: baseline_state(arms[arm].get(name), target, config) for arm in BASELINE_ARMS}
        predictions = []
        for slot in slots:
            xy = slot["source_xy"][joint_index]
            comparisons = {}
            for arm, state in states.items():
                distance = math.dist(xy, state["xy_px"]) if state["finite"] else None
                comparisons[arm] = {"both_finite_distance_px": distance,
                    "mediapipe_existing_gate_distance_px": distance if state["existing_gate_pass"] else None,
                    "distance_image_height": distance / target["height"] if distance is not None else None}
            predictions.append({"slot_index": slot["slot_index"], "xy_px": xy,
                "native_score": slot["native_yx_score"][joint_index][2], "finite": True,
                "outside_image": not inside(xy, [0, 0, target["width"], target["height"]]),
                "prediction_differences": comparisons})
        index = association["descriptive_slot_index"]
        rows[name] = {"mediapipe": states, "native_slots": predictions,
            "descriptive_association": predictions[index] if index is not None else None,
            "anatomical_accuracy": None, "observability": None, "movenet_gate": None}
    return rows


def verify_frame(frame, tracked, image, pixels, native_ms, technical_ms, target):
    """Independently bind source pixels and original PTS before any human read."""
    if pixels.dtype != np.uint8 or pixels.shape != (target["height"], target["width"], 3):
        raise ValueError("Independent source dimensions/type mismatch")
    rgb = cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB)
    if (frame["frame_index"] != tracked["frame_index"] or frame["frame_index"] != image["frame_index"] or
            frame["decoded_bgr_sha256"] != hashlib.sha256(pixels.tobytes()).hexdigest() or
            frame["decoded_rgb_sha256"] != hashlib.sha256(rgb.tobytes()).hexdigest() or
            any(frame["decoded_bgr_sha256"] != data["decoded_bgr_sha256"] for data in (tracked, image)) or
            not math.isfinite(native_ms) or any(not math.isclose(native_ms, value, rel_tol=0, abs_tol=1e-6)
                for value in (technical_ms, frame["native_timestamp_ms"], tracked["native_timestamp_ms"], image["native_timestamp_ms"])) or
            frame["timestamp_ms"] != round(native_ms)):
        raise ValueError("Independent source pixel/color/PTS binding mismatch")
    return derive_slots(frame, target), rgb


def load_export(root, clip, data, technical):
    """Validate the separate, GT-blind decode archive and its complete receipts."""
    sources, target = clip["sources"], clip["target"]
    if set(sources) != {"video", "metadata", "video_technical", "export_receipt", "frame_archive"}:
        raise ValueError("Changed exported source roles")
    receipt = read(verify_ref(root, sources["export_receipt"]))
    decode_sources = {key: sources[key] for key in ("video", "metadata", "video_technical")}
    if (receipt["status"] != "sealed_full_frame_rgb_inputs" or receipt["target"] != target or
            receipt["sources"] != decode_sources or receipt["source_video"] != sources["video"] or
            receipt["archive"] != sources["frame_archive"] or receipt["frame_key"] != "rgb" or
            receipt["human_annotation_inputs"] != [] or receipt["pose_inference_calls"] != 0 or
            receipt["fps_float"] != technical["fps"] or not math.isfinite(receipt["fps_float"]) or
            receipt["fps_float"] <= 0 or len(receipt["frames"]) != target["total_frames"]):
        raise ValueError("Changed or unsealed full-frame export")
    fields = ("frame_index", "native_timestamp_ms", "timestamp_ms", "frame_time_sec",
        "decoded_bgr_sha256", "decoded_rgb_sha256")
    for index, (exported, measured) in enumerate(zip(receipt["frames"], data["frames"], strict=True)):
        if (set(exported) != set(fields) or exported["frame_index"] != index or
                exported != {key: measured[key] for key in fields} or
                exported["frame_time_sec"] != index / receipt["fps_float"] or
                exported["timestamp_ms"] != round(exported["native_timestamp_ms"])):
            raise ValueError("Changed exported RGB timeline/measurement binding")
    with np.load(verify_ref(root, sources["frame_archive"]), allow_pickle=False) as archive:
        if archive.files != ["rgb"]:
            raise ValueError("Unexpected exported archive arrays")
        rgb = archive["rgb"]
    if rgb.dtype != np.uint8 or rgb.shape != (target["total_frames"], target["height"], target["width"], 3):
        raise ValueError("Exported archive dimensions/type differ")
    return receipt, rgb


def replay_image(image, pixels, native_ms, original, raw, target, config, selector):
    poses = [[SimpleNamespace(**point) for point in candidate] for candidate in image["image_candidates"]]
    if baseline.serialize_candidates(poses) != image["image_candidates"]:
        raise ValueError("Saved IMAGE candidates differ")
    choice = asdict(selector.select(poses))
    reproduced = baseline.frame_measurement(image["frame_index"], original["timestamp_ms"], native_ms,
        hashlib.sha256(pixels.tobytes()).hexdigest(), image["image_candidates"], choice, raw,
        original, target["width"], target["height"], config)
    if reproduced != image:
        raise ValueError("Saved IMAGE selector/control comparison differs")


def adjacent_jumps(frames, joint, slot_index=None, arm=None):
    """Slot index is a native array position; these are not tracked-person speeds."""
    values = []
    for before, after in zip(frames, frames[1:]):
        if after["frame_index"] != before["frame_index"] + 1:
            continue
        if arm:
            a, b = (frame["joints"][joint]["mediapipe"][arm] for frame in (before, after))
            if a["finite"] and b["finite"]:
                values.append(math.dist(a["xy_px"], b["xy_px"]))
        elif slot_index is not None:
            a, b = (frame["joints"][joint]["native_slots"][slot_index] for frame in (before, after))
            values.append(math.dist(a["xy_px"], b["xy_px"]))
        elif (before["association"]["descriptive_slot_index"] is not None and
                before["association"]["descriptive_slot_index"] == after["association"]["descriptive_slot_index"]):
            a, b = (frame["joints"][joint]["descriptive_association"] for frame in (before, after))
            values.append(math.dist(a["xy_px"], b["xy_px"]))
    return describe(values)


def summarize_frames(frames):
    frames = [frame for frame in frames if frame["effectiveness_eligible"]]
    joints = {}
    for name in JOINTS:
        rows = [frame["joints"][name] for frame in frames]
        native = [point for row in rows for point in row["native_slots"]]
        associated = [row["descriptive_association"] for row in rows if row["descriptive_association"] is not None]
        joint = {"non_seed_frame_denominator": len(frames), "all_native_slot_point_denominator": len(native),
            "all_native_scores": describe([point["native_score"] for point in native]),
            "all_native_outside_image": sum(point["outside_image"] for point in native),
            "descriptive_association_points": len(associated), "no_descriptive_association": len(frames) - len(associated),
            "descriptive_association_native_scores": describe([point["native_score"] for point in associated]),
            "descriptive_association_outside_image": sum(point["outside_image"] for point in associated),
            "adjacent_same_array_slot_descriptive_jump_px": adjacent_jumps(frames, name),
            "native_array_slot_jump_px": {str(index): adjacent_jumps(frames, name, index) for index in range(6)},
            "mediapipe": {}, "prediction_differences": {}}
        for arm in BASELINE_ARMS:
            states = [row["mediapipe"][arm] for row in rows]
            joint["mediapipe"][arm] = {key: sum(bool(state[key]) for state in states)
                for key in ("selected_raw", "finite", "missing", "existing_gate_pass", "outside_image")}
            joint["mediapipe"][arm].update({"visibility": describe([state["visibility"] for state in states]),
                "presence": describe([state["presence"] for state in states]),
                "adjacent_finite_jump_px": adjacent_jumps(frames, name, arm=arm)})
            joint["prediction_differences"][arm] = {key: describe([point["prediction_differences"][arm][key]
                for point in associated]) for key in ("both_finite_distance_px", "mediapipe_existing_gate_distance_px")}
        joints[name] = joint
    return {"non_seed_frames": len(frames),
        "association_status_counts": dict(Counter(frame["association"]["status"] for frame in frames)),
        "candidate_count_distribution": dict(Counter(len(frame["association"]["candidate_slot_indices"]) for frame in frames)),
        "descriptive_native_instance_score": describe([frame["slots"][frame["association"]["descriptive_slot_index"]]
            ["native_box_ymin_xmin_ymax_xmax_score"][4] for frame in frames
            if frame["association"]["descriptive_slot_index"] is not None]),
        "all_native_instance_scores": describe([slot["native_box_ymin_xmin_ymax_xmax_score"][4]
            for frame in frames for slot in frame["slots"]]), "per_joint": joints}


def coordinate_rows(manual, frames):
    """Only visible XY is truth; no best-slot oracle or GT association is used."""
    if len(manual["frames"]) != len(frames):
        raise ValueError("Manual frame denominator differs")
    rows = []
    for reference, frame in zip(manual["frames"], frames, strict=True):
        if (reference["frame_index"] != frame["frame_index"] or
                not math.isclose(reference["timestamp_ms"], frame["native_timestamp_ms"], rel_tol=0, abs_tol=1e-6)):
            raise ValueError("Manual/source frame or PTS differs")
        for joint in reference["joints"]:
            name, status = joint["name"], joint["status"]
            diagnostic = frame["joints"][name]
            associated = diagnostic["descriptive_association"]
            row = {"frame_index": frame["frame_index"], "effectiveness_eligible": frame["effectiveness_eligible"],
                "joint": name, "human_status": status, "original_major_label": frame["original_major_label"],
                "association_status": frame["association"]["status"],
                "descriptive_slot_index": frame["association"]["descriptive_slot_index"],
                "movenet_descriptive_error_px": None, "video_error_px": None, "image_error_px": None,
                "video_existing_gate_pass": diagnostic["mediapipe"]["video"]["existing_gate_pass"],
                "image_existing_gate_pass": diagnostic["mediapipe"]["image"]["existing_gate_pass"]}
            if status == "visible":
                truth = [joint["x_px"], joint["y_px"]]
                if associated is not None:
                    row["movenet_descriptive_error_px"] = math.dist(associated["xy_px"], truth)
                for arm in BASELINE_ARMS:
                    state = diagnostic["mediapipe"][arm]
                    if state["finite"]:
                        row[arm + "_error_px"] = math.dist(state["xy_px"], truth)
            rows.append(row)
    return rows


def coordinate_summary(rows):
    eligible = [row for row in rows if row["effectiveness_eligible"]]
    visible = [row for row in eligible if row["human_status"] == "visible"]
    summary = {"source_joint_rows": len(rows),
        "source_human_status_counts": dict(Counter(row["human_status"] for row in rows)),
        "source_visible_reference_denominator": sum(row["human_status"] == "visible" for row in rows),
        "non_seed_joint_rows": len(eligible),
        "human_status_counts": dict(Counter(row["human_status"] for row in eligible)),
        "visible_reference_denominator": len(visible), "hidden_coordinates_evaluated": 0,
        "movenet_descriptive_error_px": describe([row["movenet_descriptive_error_px"] for row in visible]),
        "visible_without_descriptive_association": sum(row["movenet_descriptive_error_px"] is None for row in visible),
        "mediapipe": {}, "common_finite_pairs": {}}
    for arm in BASELINE_ARMS:
        common = [row for row in visible if row["movenet_descriptive_error_px"] is not None and row[arm + "_error_px"] is not None]
        gated = [row for row in common if row[arm + "_existing_gate_pass"]]
        summary["mediapipe"][arm] = {"error_px": describe([row[arm + "_error_px"] for row in visible]),
            "visible_missing_or_nonfinite": sum(row[arm + "_error_px"] is None for row in visible),
            "existing_gate_points": sum(row[arm + "_existing_gate_pass"] for row in visible)}
        def pair(part):
            return {"count": len(part), "movenet_descriptive": describe([row["movenet_descriptive_error_px"] for row in part]),
                "mediapipe": describe([row[arm + "_error_px"] for row in part]),
                "movenet_error_lower": sum(row["movenet_descriptive_error_px"] < row[arm + "_error_px"] for row in part),
                "movenet_error_higher": sum(row["movenet_descriptive_error_px"] > row[arm + "_error_px"] for row in part),
                "equal": sum(row["movenet_descriptive_error_px"] == row[arm + "_error_px"] for row in part)}
        summary["common_finite_pairs"][arm] = {"all_finite": pair(common), "mediapipe_existing_gate_only": pair(gated)}
    return summary


def major_timeline(canonical, total):
    labels, occupied = ["known_negative"] * total, set()
    for interval in canonical["labels"]["major_pose_failure_intervals"]:
        start, end = interval["start_frame"], interval["end_frame"]
        indices = set(range(start, end + 1))
        if not 0 <= start <= end < total or occupied & indices:
            raise ValueError("Invalid original review grouping timeline")
        occupied.update(indices)
        labels[start:end + 1] = [interval["status"]] * len(indices)
    return labels


def protected_inventory(root, plan):
    if plan["protected_source_inventory"] != INVENTORY:
        raise ValueError("Changed protected source inventory")
    path = verify_ref(root, INVENTORY)
    hashes = read(path)[INVENTORY["key"]]
    if len(hashes) != INVENTORY["physical_files"]:
        raise ValueError("Changed protected source denominator")
    for path, digest in hashes.items():
        verify_ref(root, {"path": path, "sha256": digest})
    return hashes


def verify_evaluator_plan(root, plan):
    if plan["status"] != "frozen_before_offline_evaluation" or plan["association"] != ASSOCIATION:
        raise ValueError("Unfrozen or changed evaluator association")
    verify_ref(root, plan["producer_plan"])
    for ref in plan["code"].values():
        verify_ref(root, ref)
    if (plan["code"]["evaluator"]["sha256"] != sha(__file__) or
            plan["code"]["evaluator_tests"]["sha256"] != sha(root / "tests/test_movenet_cohort_evaluation.py")):
        raise ValueError("Unbound evaluator code/tests")
    if tuple(clip["target"]["pitch_id"] for clip in plan["clips"]) != PITCH_IDS:
        raise ValueError("Changed formal cohort order")
    if {"source_frames": sum(clip["target"]["total_frames"] for clip in plan["clips"]),
            "non_seed_frames": sum(clip["target"]["total_frames"] - 1 for clip in plan["clips"])} != EXPECTED:
        raise ValueError("Changed formal frame denominators")
    producer = read(root / plan["producer_plan"]["path"])
    if [clip["target"] for clip in producer["clips"]] != [clip["target"] for clip in plan["clips"]]:
        raise ValueError("Producer/evaluator cohort differs")
    for clip, produced in zip(plan["clips"], producer["clips"], strict=True):
        if clip["sources"] != produced["sources"]:
            raise ValueError("Producer/evaluator sources differ")
        expected = {"tracked_roi", "full_frame_image", "original_raw", "capture", "clean_config", "canonical_review"}
        if clip["target"]["pitch_id"] == "pitch_003":
            expected.add("manual_xy")
        if set(clip["evaluator_sources"]) != expected:
            raise ValueError("Unexpected or unbound evaluator input role")
        for ref in (*clip["sources"].values(), *clip["evaluator_sources"].values()):
            verify_ref(root, ref)
    return producer


def validate_run(run, plan, producer):
    if (run["status"] != "sealed_movenet_cohort_measurements" or
            run["plan_sha256"] != plan["producer_plan"]["sha256"] or
            run["human_annotation_inputs"] != [] or run["inference_calls"] != EXPECTED["source_frames"] or
            any(run[key] != value for key, value in EXPECTED.items()) or
            [clip["pitch_id"] for clip in run["clips"]] != list(PITCH_IDS) or
            run["producer_sha256"] != producer["producer_sha256"]):
        raise ValueError("Changed or unsealed producer cohort receipt")
    if run.get("warning_policy") is not None or run.get("phase2_automatic_reliability", "NOT PASSED") != "NOT PASSED":
        raise ValueError("Producer output asserts automatic reliability")


def evaluate(root, plan_path, measurements, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive new evaluation output inside analysis_results required")
    plan_path, measurements = bound_path(root, plan_path), bound_path(root, measurements)
    plan, run = read(plan_path), read(measurements)
    plan_sha, measurement_sha = sha(plan_path), sha(measurements)
    producer = verify_evaluator_plan(root, plan)
    inventory = protected_inventory(root, plan)
    validate_run(run, plan, producer)
    clips, refs = [], {}
    for clip, receipt in zip(plan["clips"], run["clips"], strict=True):
        target, sources = clip["target"], clip["evaluator_sources"]
        name, total = target["pitch_id"], target["total_frames"]
        measured_path = verify_ref(root, receipt)
        data = read(measured_path)
        if (data["status"] != "sealed_measurements_only" or data["target"] != target or
                data["plan_sha256"] != plan["producer_plan"]["sha256"] or
                data["producer_sha256"] != producer["producer_sha256"] or
                data["human_annotation_inputs"] != [] or data["inference_calls"] != total or data["total_frames"] != total or
                data["source_references"] != clip["sources"] or
                [frame["frame_index"] for frame in data["frames"]] != list(range(total))):
            raise ValueError("Incomplete or changed native clip measurements")
        refs[name] = receipt
        tracked, control, context, config, canonical = (read(root / sources[key]["path"])
            for key in ("tracked_roi", "full_frame_image", "capture", "clean_config", "canonical_review"))
        technical = read(root / clip["sources"]["video_technical"]["path"])
        video = root / clip["sources"]["video"]["path"]
        validate_ground_truth(canonical, source_video_path=video)
        source = canonical["source_video"]
        if (canonical["annotation_status"] != "reviewed" or canonical["review_profile"] != "phase2_full_review" or
                (source["pitch_id"], source["sha256"], source["total_frames"], source["frame_index_base"]) !=
                (name, clip["sources"]["video"]["sha256"], total, 0)):
            raise ValueError("Canonical reviewed source binding differs")
        gate = {key: config[key] for key in ("min_visibility", "min_presence")}
        if (tracked["status"] != "sealed_measurements_only" or tracked["target"] != target or
                control["pitch_id"] != name or control["gate"] != gate or
                control["video_sha256"] != clip["sources"]["video"]["sha256"] or
                (control["total_frames"], control["width"], control["height"]) != (total, target["width"], target["height"]) or
                technical["sha256"] != clip["sources"]["video"]["sha256"] or
                (technical["frame_count"], technical["width"], technical["height"]) != (total, target["width"], target["height"]) or
                len(technical["timestamps_ms"]) != total or any([frame["frame_index"] for frame in value["frames"]]
                    != list(range(total)) for value in (tracked, control))):
            raise ValueError("Saved tracker/IMAGE/technical binding differs")
        raw = baseline.load_video_raw(root / sources["original_raw"]["path"], context, total)
        export, archive_rgb = load_export(root, clip, data, technical)
        labels = major_timeline(canonical, total)
        selector, capture, frames = PitcherSelector(), cv2.VideoCapture(str(video)), []
        try:
            if not capture.isOpened():
                raise ValueError("Cannot independently decode source video")
            for index, (frame, tracker, image) in enumerate(zip(data["frames"], tracked["frames"], control["frames"], strict=True)):
                ok, pixels = capture.read()
                if not ok:
                    raise ValueError("Missing independent source frame")
                native_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                slots, rgb = verify_frame(frame, tracker, image, pixels, native_ms, technical["timestamps_ms"][index], target)
                if not np.array_equal(rgb, archive_rgb[index]):
                    raise ValueError("Independent RGB source differs from exported full-frame archive")
                replay_image(image, pixels, native_ms, context["selection_frames"][index], raw[index], target, gate, selector)
                association = geometric_association(slots, tracker["usable_rectangle_xywh"], target["width"], target["height"])
                arms = {"video": raw[index], "image": baseline.selected_points(image["image_candidates"], image["image_selection"])}
                frames.append({"frame_index": index, "native_timestamp_ms": native_ms,
                    "effectiveness_eligible": index != 0, "original_major_label": labels[index],
                    "association": association, "slots": slots,
                    "joints": joint_diagnostics(slots, association, arms, target, gate),
                    "new_output_major_failure": None, "subject_alignment_verified": False})
            if capture.read()[0]:
                raise ValueError("Extra independent source frame")
        finally:
            capture.release()
        del archive_rgb
        xy = None
        if "manual_xy" in sources:
            manual = read(root / sources["manual_xy"]["path"])
            validate_manual_keypoints(manual, source_video_path=video)
            if (manual["annotation_status"] != "reviewed" or manual["source_video"] != source or
                    manual["image_size"] != {key: target[key] for key in ("width", "height")}):
                raise ValueError("Reviewed manual XY binding differs")
            rows = coordinate_rows(manual, frames)
            xy = {"status": "visible_xy_conditional_on_unverified_unique_geometric_association",
                "all_non_seed": coordinate_summary(rows),
                "by_joint": {name: coordinate_summary([row for row in rows if row["joint"] == name]) for name in JOINT_NAMES},
                "original_major_label_groups": {label: coordinate_summary([row for row in rows if row["original_major_label"] == label])
                    for label in sorted(set(labels))}, "rows": rows}
        clips.append({"pitch_id": name, "target": target, "source_measurement": receipt,
            "source_frames": total, "summary": summarize_frames(frames),
            "original_major_label_groups": {label: summarize_frames([frame for frame in frames if frame["original_major_label"] == label])
                for label in sorted(set(labels))}, "frames": frames, "xy_accuracy": xy,
            "identity_accuracy": None, "warning_tp_fn_fp": None, "full_body_completeness": None, "passed": None})
    verify_evaluator_plan(root, plan)
    for ref in refs.values():
        verify_ref(root, ref)
    if protected_inventory(root, plan) != inventory or sha(plan_path) != plan_sha or sha(measurements) != measurement_sha:
        raise ValueError("Frozen evidence changed during offline evaluation")
    report = {"status": "complete_offline_movenet_cohort_evaluation", "plan_sha256": plan_sha,
        "producer_plan": plan["producer_plan"], "measurement_sha256": measurement_sha,
        "evaluator_sha256": sha(__file__), "denominators": EXPECTED, "clips": clips,
        "association": ASSOCIATION, "excluded_seed_frame_index": 0, "seed_frames_excluded": 5,
        "independent_source_frames_verified": 592, "native_slot_mapping_frames_verified": 592,
        "exported_full_frame_rgb_archive_frames_verified": 592,
        "saved_image_selector_frames_verified": 592, "protected_physical_files_verified": len(inventory),
        "tracker_inference_calls": 0, "pose_inference_calls": 0, "warning_policy": None,
        "warning_tp_fn_fp": None, "new_warning_counts": None, "identity_accuracy": None,
        "event_accuracy": None, "passed": None, "phase2_automatic_reliability": "NOT PASSED",
        "production_adoption": False, "original_major_labels_used_for_grouping_only": True,
        "new_outputs_have_human_labels": False, "hidden_xy_used_as_truth": False,
        "original_predictions_modified": False,
        "limitations": ["All six slots are raw hypotheses, including zero-score slots; slot index is not identity.",
            "Unique geometric candidacy is descriptive and does not verify subject identity or anatomy.",
            "Native scores are not visibility, presence, observability or reliability; no cutoff is fitted.",
            "Prediction differences are not accuracy; only reviewed visible pitch_003 XY supplies coordinate truth.",
            "The other four clips have null XY accuracy; original qualitative labels describe original VIDEO predictions.",
            "Coordinate inverse is replayed from recorded geometry; TensorFlow resize pixels and inference are not rerun.",
            "Adjacent jumps at a native array position may include different people; no speed or acceptance claim.",
            "No automatic winner, warning policy, original FN repair, generalization or Phase 2 pass is established."]}
    output.mkdir(parents=True)
    write(output / "movenet_cohort_evaluation.json", report)
    write(output / "evidence_integrity_check.json", {"protected_physical_files_verified_before_and_after": len(inventory),
        "source_frames_verified": 592, "tracker_inference_calls": 0, "pose_inference_calls": 0,
        "source_inventories_unchanged": True, "human_annotations_modified": False, "warning_policy": None})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = evaluate(args.root, args.plan, args.measurements, args.output)
    print(json.dumps({"denominators": result["denominators"], "phase2": result["phase2_automatic_reliability"]}))
