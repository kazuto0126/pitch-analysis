"""Offline replay of a frozen assisted ROI cohort; no tracker or pose inference."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import importlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from measure_seeded_subject import read, sha, write, verify_sources, rectangle_status
from measure_tracked_roi_pose import crop_bounds, map_candidates, serialize_candidates
from measure_pose_mode_countercheck import (load_video_raw, selected_points, gate,
                                            finite_point, frame_measurement)
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints
from pitch_analysis.subject import PitcherSelector


ARMS = ("crop", "image", "video")
EVALUATOR_ROLES = {"full_frame_image", "original_raw", "capture", "clean_config", "canonical_review"}
INVENTORY = {"path": "docs/evaluation_plans/phase2_pose_mode_countercheck_20261009.json",
             "sha256": "587d7df4e91e279262be408607c8bdc13d73b6f11c1a28e5f874ab0af3c3bb69",
             "key": "protected_source_hashes", "physical_files": 374}
EXPECTED = {"source_frames": 592, "non_seed_frames": 587,
            "new_source_frames": 477, "reused_source_frames": 115}


def bound_path(root, value):
    path = (root / value).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Bound input outside workspace")
    return path


def protected_inventory(root, proposal):
    ref = proposal["protected_source_inventory"]
    if ref != INVENTORY or sha(bound_path(root, ref["path"])) != ref["sha256"]:
        raise ValueError("Protected inventory changed")
    hashes = read(root / ref["path"])[ref["key"]]
    if len(hashes) != ref["physical_files"]:
        raise ValueError("Protected source denominator changed")
    verify_sources(root, {p: {"path": p, "sha256": h} for p, h in hashes.items()})
    return hashes


def describe(values):
    values = sorted(values)
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    def percentile(q):
        at = (len(values) - 1) * q
        lo, hi = math.floor(at), math.ceil(at)
        return values[lo] + (values[hi] - values[lo]) * (at - lo)
    return {"count": len(values), "mean": sum(values) / len(values),
            "median": percentile(.5), "p90": percentile(.9), "max": values[-1]}


def _poses(candidates):
    poses = [[SimpleNamespace(**p) for p in pose] for pose in candidates]
    if serialize_candidates(poses) != candidates:
        raise ValueError("Saved candidate serialization differs")
    return poses


def replay_frame(frame, tracked, pixels, native_ms, technical_ms, selector, target):
    """Recompute pixels, half-open crop, XY/Z/confidence mapping and selector."""
    if (not isinstance(pixels, np.ndarray) or pixels.dtype != np.uint8 or
            pixels.shape != (target["height"], target["width"], 3)):
        raise ValueError("Independent source dimensions/type mismatch")
    digest = hashlib.sha256(pixels.tobytes()).hexdigest()
    if (frame["frame_index"] != tracked["frame_index"] or
            digest != frame["decoded_bgr_sha256"] or digest != tracked["decoded_bgr_sha256"] or
            not math.isfinite(native_ms) or any(not math.isclose(native_ms, t, rel_tol=0, abs_tol=1e-6)
                for t in (technical_ms, frame["native_timestamp_ms"], tracked["native_timestamp_ms"])) or
            frame["timestamp_ms"] != round(native_ms)):
        raise ValueError("Independent source pixel/PTS mismatch")
    rectangle = tracked["usable_rectangle_xywh"]
    bounds = crop_bounds(rectangle, target["width"], target["height"])
    if frame["tracker_rectangle_xywh"] != rectangle or frame["crop_bounds_xyxy"] != bounds:
        raise ValueError("Derived crop differs from sealed tracking geometry")
    candidates = frame["crop_candidates"]
    _poses(candidates)
    if bounds is None:
        if (candidates or frame["inference_status"] != "roi_unavailable" or
                any(frame[k] is not None for k in ("crop_bgr_sha256", "crop_rgb_sha256", "crop_shape"))):
            raise ValueError("Unavailable ROI contains fabricated pixels or pose")
        mapped = []
    else:
        x0, y0, x1, y1 = bounds
        bgr = np.ascontiguousarray(pixels[y0:y1, x0:x1].copy())
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        if (frame["crop_bgr_sha256"] != hashlib.sha256(bgr.tobytes()).hexdigest() or
                frame["crop_rgb_sha256"] != hashlib.sha256(rgb.tobytes()).hexdigest() or
                frame["crop_shape"] != list(bgr.shape) or frame["inference_status"] != "measured"):
            raise ValueError("Independent crop pixel/color receipt mismatch")
        mapped = map_candidates(candidates, bounds, target["width"], target["height"])
    if mapped != frame["full_image_candidates"]:
        raise ValueError("Mapped XY/Z/confidence differs from crop candidates")
    selection = asdict(selector.select(_poses(mapped)))
    if (selection != frame["selection"] or frame["warning_prediction"] is not None or
            frame["subject_alignment_verified"] is not False):
        raise ValueError("Original selector replay or experimental semantics differs")


def replay_image_frame(control, pixels, native_ms, technical_ms, selector, raw, original_choice, target, config):
    """Replay the bound full-frame IMAGE control and original VIDEO comparison."""
    if (control["decoded_bgr_sha256"] != hashlib.sha256(pixels.tobytes()).hexdigest() or
            not math.isclose(native_ms, technical_ms, rel_tol=0, abs_tol=1e-6) or
            not math.isclose(native_ms, control["native_timestamp_ms"], rel_tol=0, abs_tol=1e-6) or
            control["timestamp_ms"] != round(native_ms) or
            original_choice["timestamp_ms"] != round(native_ms)):
        raise ValueError("Independent IMAGE control pixel/PTS mismatch")
    candidates = control["image_candidates"]
    choice = asdict(selector.select(_poses(candidates)))
    reproduced = frame_measurement(control["frame_index"], original_choice["timestamp_ms"], native_ms,
        control["decoded_bgr_sha256"], candidates, choice, raw, original_choice,
        target["width"], target["height"], config)
    if reproduced != control:
        raise ValueError("Saved IMAGE selector/control comparison does not reproduce")


def joint_row(index, name, arms, crop_points, bounds, target, config, original_major_label):
    """Raw presence and input support are diagnostics, never observed truth."""
    row = {"frame_index": index, "joint": name, "effectiveness_eligible": index != 0,
           "original_major_label": original_major_label, "arms": {}}
    for arm in ARMS:
        point = arms[arm].get(name)
        finite = finite_point(point)
        source_point = crop_points.get(name) if arm == "crop" else point
        support = bool(finite and finite_point(source_point) and (arm != "crop" or bounds is not None)
                       and 0 <= source_point["x"] < 1 and 0 <= source_point["y"] < 1)
        row["arms"][arm] = {"selected_raw": point is not None, "finite": finite, "raw_finite": finite,
            "gate_pass": gate(point, config), "input_supported_raw": support,
            "missing": point is None, "low_gate": bool(finite and not gate(point, config)),
            "extrapolation": bool(finite and not support),
            "visibility": point["visibility"] if finite else None,
            "presence": point["presence"] if finite else None,
            "xy_px": [point["x"] * target["width"], point["y"] * target["height"]] if finite else None}
    return row


def longest_span(rows, predicate):
    best, start, previous = None, None, None
    for row in rows:
        index = row["frame_index"]
        if predicate(row):
            if previous is None or index != previous + 1:
                start = index
            span = {"start_frame": start, "end_frame": index, "frames": index - start + 1}
            if best is None or span["frames"] > best["frames"]:
                best = span
            previous = index
        else:
            start = previous = None
    return best


def adjacent_jumps(rows, arm, *, require_gate=False):
    values = []
    for before, after in zip(rows, rows[1:]):
        a, b = before["arms"][arm], after["arms"][arm]
        if (after["frame_index"] == before["frame_index"] + 1 and
                a["input_supported_raw"] and b["input_supported_raw"] and
                (not require_gate or (a["gate_pass"] and b["gate_pass"]))):
            values.append(math.dist(a["xy_px"], b["xy_px"]))
    return describe(values)


def summarize_joint_rows(rows):
    """Exclude each seed and retain absent/low-confidence/unsupported denominators."""
    rows = sorted((r for r in rows if r["effectiveness_eligible"]), key=lambda r: r["frame_index"])
    result = {"non_seed_frames": len(rows), "arms": {}}
    for arm in ARMS:
        points = [r["arms"][arm] for r in rows]
        result["arms"][arm] = {key: sum(p[key] for p in points) for key in
            ("selected_raw", "finite", "gate_pass", "input_supported_raw", "low_gate", "missing", "extrapolation")}
        result["arms"][arm].update({
            "supported_gate_pass": sum(p["input_supported_raw"] and p["gate_pass"] for p in points),
            "nonfinite_selected_raw": sum(p["selected_raw"] and not p["finite"] for p in points),
            "visibility": describe([p["visibility"] for p in points if p["visibility"] is not None]),
            "presence": describe([p["presence"] for p in points if p["presence"] is not None]),
            "longest_missing_span": longest_span(rows, lambda r: r["arms"][arm]["missing"]),
            "longest_supported_gate_unavailable_span": longest_span(rows, lambda r:
                not (r["arms"][arm]["input_supported_raw"] and r["arms"][arm]["gate_pass"])),
            "adjacent_supported_raw_jump_px": adjacent_jumps(rows, arm),
            "adjacent_supported_gate_jump_px": adjacent_jumps(rows, arm, require_gate=True)})
    return result


def summarize_clip(frames):
    eligible = [f for f in frames if f["effectiveness_eligible"]]
    def group(part):
        return {"non_seed_frames": len(part),
            "frame_selection_counts": {arm: dict(Counter(f["selection"][arm]["status"] for f in part)) for arm in ARMS},
            "input_roi_valid": sum(f["input_roi_valid"] for f in part),
            "input_roi_missing": sum(not f["input_roi_valid"] for f in part),
            "per_joint": {name: summarize_joint_rows([f["joints"][name] for f in part]) for name in JOINT_NAMES}}
    return {"source_frames": len(frames), "non_seed_frames": len(eligible),
            "all_non_seed": group(eligible),
            "original_major_label_groups": {label: group([f for f in eligible if f["original_major_label"] == label])
                for label in sorted({f["original_major_label"] for f in eligible})}}


def major_timeline(canonical, total):
    labels = ["known_negative"] * total
    occupied = set()
    for interval in canonical["labels"]["major_pose_failure_intervals"]:
        start, end = interval["start_frame"], interval["end_frame"]
        indices = set(range(start, end + 1))
        if not 0 <= start <= end < total or occupied & indices:
            raise ValueError("Invalid original review grouping timeline")
        occupied.update(indices)
        labels[start:end + 1] = [interval["status"]] * len(indices)
    return labels


def validate_sealed_clip(clip, receipt, tracked, pose, plan_sha):
    target, sources = clip["target"], clip["sources"]
    total = target["total_frames"]
    if receipt["pitch_id"] != target["pitch_id"] or receipt["kind"] != clip["kind"] or receipt["target"] != target:
        raise ValueError("Cohort clip receipt differs")
    for data in (tracked, pose):
        if (data["status"] != "sealed_measurements_only" or data["target"] != target or
                [f["frame_index"] for f in data["frames"]] != list(range(total)) or
                data["warning_policy"] is not None or data["phase2_automatic_reliability"] != "NOT PASSED"):
            raise ValueError("Unsealed, incomplete or changed per-clip measurements")
        for role in ("video", "metadata", "video_technical"):
            if data["producer_sources"][role] != sources[role]:
                raise ValueError("Per-clip measurement source differs")
        if clip["kind"] == "new_measurement" and data["plan_sha256"] != plan_sha:
            raise ValueError("New measurement execution hash differs")
    if (tracked["producer_sources"]["initialization"] != sources["initialization"] or
            tracked["initialization_frame_excluded_from_effectiveness"] is not True or
            tracked["post_initialization_frame_denominator"] != total - 1 or
            tracked["initialization_calls"] != 1 or pose["human_annotation_inputs"] != [] or
            pose["producer_sources"]["tracked_roi"] != receipt["tracking"] or
            pose["inference_calls"] != sum(f["inference_status"] == "measured" for f in pose["frames"])):
        raise ValueError("Tracking/crop seal or call count differs")
    updates = sum(f["tracking_status"] in ("native_success", "terminal_break") for f in tracked["frames"][1:])
    if tracked["native_update_calls"] != updates:
        raise ValueError("Tracking update receipts differ")
    terminal = False
    for index, frame in enumerate(tracked["frames"]):
        status = frame["tracking_status"]
        if frame["warning_prediction"] is not None or frame["subject_assignment"] is not None:
            raise ValueError("Tracking receipt asserts subject identity or warning")
        if index == 0:
            if status not in ("initialized", "init_failed"):
                raise ValueError("Missing declared tracking initialization")
        elif terminal:
            if status not in ("not_attempted_after_initialization_failure", "not_attempted_after_terminal_break"):
                raise ValueError("Tracking restarted after terminal failure")
        elif status not in ("native_success", "terminal_break"):
            raise ValueError("Invalid tracking continuation status")
        if status in ("init_failed", "terminal_break"):
            terminal = True
        if status == "native_success":
            native, truncated, reason, diagnostic = rectangle_status(frame["native_rectangle_xywh"], target["width"], target["height"])
            if (frame["native_update_success"] is not True or reason is not None or
                    frame["usable_rectangle_xywh"] != native or frame["truncated"] != truncated or
                    frame["native_rectangle_diagnostic"] != diagnostic):
                raise ValueError("Usable rectangle does not reproduce native success")
        elif status != "initialized" and frame["usable_rectangle_xywh"] is not None:
            raise ValueError("Missing tracking state contains a usable rectangle")
    if clip["kind"] == "reuse_sealed":
        if receipt["tracking"] != clip["reused_tracking"] or receipt["pose"] != clip["reused_pose"]:
            raise ValueError("Reused sealed outputs changed")
        expected_calls = (0, 0, 0)
    else:
        expected_calls = (tracked["initialization_calls"], tracked["native_update_calls"], pose["inference_calls"])
    if tuple(receipt[k] for k in ("new_tracker_initialization_calls", "new_tracker_update_calls", "new_pose_inference_calls")) != expected_calls:
        raise ValueError("New/reused call accounting differs")


def xy_accuracy(root, sources, pose_ref, video, target, canonical):
    if "manual_xy" not in sources:
        return None
    manual = read(root / sources["manual_xy"]["path"])
    validate_manual_keypoints(manual, source_video_path=video)
    if (target["pitch_id"] != "pitch_003" or manual["annotation_status"] != "reviewed" or
            manual["source_video"] != canonical["source_video"] or
            manual["image_size"] != {k: target[k] for k in ("width", "height")}):
        raise ValueError("Manual XY binding differs from reviewed reused clip")
    old = read(root / sources["reused_xy_evaluation"]["path"])
    if old["status"] != "complete_offline_xy_evaluation" or old["measurement_sha256"] != pose_ref["sha256"]:
        raise ValueError("Reused XY evaluation does not bind reused pose")
    keys = ("denominators", "groups", "per_joint", "frame_selection_counts")
    return {"status": "reused_exact_sealed_summary", "source": sources["reused_xy_evaluation"],
            "summary": {key: old[key] for key in keys}, "evaluation_rerun": False}


def figure(pixels, index, bounds, arms, target):
    panels = []
    edges = [(a + "_" + first, a + "_" + second) for a in ("LEFT", "RIGHT")
             for first, second in (("SHOULDER", "ELBOW"), ("ELBOW", "WRIST"),
                                   ("SHOULDER", "HIP"), ("HIP", "KNEE"), ("KNEE", "ANKLE"))]
    for arm in ("source", "crop", "image"):
        panel = pixels.copy()
        if bounds is not None:
            x0, y0, x1, y1 = bounds
            cv2.rectangle(panel, (x0, y0), (x1 - 1, y1 - 1), (0, 220, 255), 1)
        points = arms.get(arm, {})
        def xy(point):
            return round(point["x"] * target["width"]), round(point["y"] * target["height"])
        for a, b in edges:
            if finite_point(points.get(a)) and finite_point(points.get(b)):
                cv2.line(panel, xy(points[a]), xy(points[b]), (230, 30, 210), 1)
        for name in JOINT_NAMES:
            if finite_point(points.get(name)):
                cv2.circle(panel, xy(points[name]), 2, (230, 30, 210), -1)
        cv2.putText(panel, f'f{index} {arm}: raw prediction', (5, 18), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
        panels.append(panel)
    return np.concatenate(panels, axis=1)


def verify_frozen_evaluator(root, plan, proposal):
    producer = importlib.import_module("measure_assisted_roi_cohort")
    producer.verify_execution(root, plan)
    if sha(bound_path(root, proposal["proposal_path"])) != proposal["proposal_sha256"]:
        raise ValueError("Frozen proposal document changed")
    if (plan["evaluator_sha256"] != sha(__file__) or
            plan["evaluator_test_sha256"] != sha(root / "tests/test_assisted_roi_cohort_evaluation.py")):
        raise ValueError("Frozen evaluator or tests changed")
    for key in ("evaluator_sources", "evaluator_dependencies", "review_frames"):
        if plan[key] != proposal[key]:
            raise ValueError("Frozen evaluator settings differ: " + key)
    names = [c["target"]["pitch_id"] for c in plan["clips"]]
    if set(plan["evaluator_sources"]) != set(names) or set(plan["review_frames"]) != set(names):
        raise ValueError("Evaluator cohort differs")
    for name, sources in plan["evaluator_sources"].items():
        expected = EVALUATOR_ROLES | ({"manual_xy", "reused_xy_evaluation"} if name == "pitch_003" else set())
        if set(sources) != expected:
            raise ValueError("Unexpected evaluator source role")
        verify_sources(root, sources)
    verify_sources(root, plan["evaluator_dependencies"])
    verify_sources(root, proposal["parent_only_sources"])


def evaluate(root, plan_path, measurements, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive new evaluation output inside analysis_results required")
    plan_path, measurements = bound_path(root, plan_path), bound_path(root, measurements)
    plan, measured = read(plan_path), read(measurements)
    proposal = read(bound_path(root, plan["proposal_manifest"]))
    plan_sha, measurement_sha = sha(plan_path), sha(measurements)
    verify_frozen_evaluator(root, plan, proposal)
    inventory = protected_inventory(root, proposal)
    if (measured["status"] != "sealed_cohort_measurements" or measured["plan_sha256"] != plan_sha or
            measured["producer_sha256"] != plan["producer_sha256"] or measured["human_initialized"] is not True or
            measured["warning_policy"] is not None or measured["phase2_automatic_reliability"] != "NOT PASSED" or
            any(measured[k] != value for k, value in EXPECTED.items()) or
            len(plan["clips"]) != 5 or len(measured["clips"]) != 5):
        raise ValueError("Changed or unsealed cohort denominator/semantics")
    names = [c["target"]["pitch_id"] for c in plan["clips"]]
    if names != ["pitch_001", "pitch_002", "pitch_003", "pitch_004", "pitch_005"]:
        raise ValueError("Changed original cohort order")
    if [c["kind"] for c in plan["clips"]] != ["new_measurement", "new_measurement", "reuse_sealed", "new_measurement", "new_measurement"]:
        raise ValueError("Changed sealed reuse denominator")
    if {"source_frames": sum(c["target"]["total_frames"] for c in plan["clips"]),
            "non_seed_frames": sum(c["target"]["total_frames"] - 1 for c in plan["clips"]),
            "new_source_frames": sum(c["target"]["total_frames"] for c in plan["clips"] if c["kind"] == "new_measurement"),
            "reused_source_frames": sum(c["target"]["total_frames"] for c in plan["clips"] if c["kind"] == "reuse_sealed")} != EXPECTED:
        raise ValueError("Frozen original frame denominators differ")
    clips, all_refs = [], {}
    output.mkdir(parents=True)
    for clip, receipt in zip(plan["clips"], measured["clips"], strict=True):
        target, producer_sources = clip["target"], clip["sources"]
        name, total = target["pitch_id"], target["total_frames"]
        refs = {"tracking": receipt["tracking"], "pose": receipt["pose"]}
        verify_sources(root, refs)
        all_refs.update({name + "_" + key: value for key, value in refs.items()})
        tracked, pose = (read(root / refs[key]["path"]) for key in ("tracking", "pose"))
        validate_sealed_clip(clip, receipt, tracked, pose, plan_sha)
        if (tracked["parameters"] != plan["tracker_parameters"] or
                pose["parameters"] != plan["crop_parameters"] or pose["options"] != plan["pose_options"] or
                pose["runtime"] != plan["runtime"] or pose["producer_sources"]["model"] != plan["model"] or
                pose["original_predictions_modified"] is not False):
            raise ValueError("Per-clip frozen tracker/pose settings differ")
        sources = plan["evaluator_sources"][name]
        data = {k: read(root / ref["path"]) for k, ref in sources.items() if k not in ("original_raw", "manual_xy", "reused_xy_evaluation")}
        control, context, config, canonical = (data[k] for k in ("full_frame_image", "capture", "clean_config", "canonical_review"))
        technical = read(root / producer_sources["video_technical"]["path"])
        seed = read(root / producer_sources["initialization"]["path"])
        video = root / producer_sources["video"]["path"]
        validate_ground_truth(canonical, source_video_path=video)
        source = canonical["source_video"]
        if (canonical["annotation_status"] != "reviewed" or canonical["review_profile"] != "phase2_full_review" or
                (source["pitch_id"], source["sha256"], source["total_frames"], source["frame_index_base"]) !=
                (name, producer_sources["video"]["sha256"], total, 0)):
            raise ValueError("Canonical reviewed source binding differs")
        gate_config = {k: config[k] for k in ("min_visibility", "min_presence")}
        if (control["gate"] != gate_config or control["pitch_id"] != name or
                control["video_sha256"] != producer_sources["video"]["sha256"] or
                (control["total_frames"], control["width"], control["height"]) != (total, target["width"], target["height"]) or
                [f["frame_index"] for f in control["frames"]] != list(range(total)) or
                technical["sha256"] != producer_sources["video"]["sha256"] or
                (technical["frame_count"], technical["width"], technical["height"]) != (total, target["width"], target["height"]) or
                len(technical["timestamps_ms"]) != total):
            raise ValueError("Control/technical source timeline or saved gate differs")
        if (seed["frame_index"] != 0 or tracked["frames"][0]["decoded_bgr_sha256"] != seed["decoded_bgr_sha256"] or
                tracked["frames"][0]["native_timestamp_ms"] != seed["native_timestamp_ms"] or
                (tracked["frames"][0]["tracking_status"] == "initialized" and
                 tracked["frames"][0]["usable_rectangle_xywh"] != seed["rectangle_xywh"])):
            raise ValueError("Declared seed differs from tracking receipt")
        raw = load_video_raw(root / sources["original_raw"]["path"], context, total)
        labels = major_timeline(canonical, total)
        review = plan["review_frames"][name]
        if len(review) != len(set(review)) or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < total for i in review):
            raise ValueError("Invalid frozen context sampling")
        selector, image_selector = PitcherSelector(), PitcherSelector()
        capture = cv2.VideoCapture(str(video))
        frames, examples = [], []
        try:
            if not capture.isOpened():
                raise ValueError("Cannot independently decode native source")
            for index, (frame, tracker_frame, image) in enumerate(zip(pose["frames"], tracked["frames"], control["frames"], strict=True)):
                ok, pixels = capture.read()
                if not ok:
                    raise ValueError("Incomplete independent original frame decode")
                ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                replay_frame(frame, tracker_frame, pixels, ms, technical["timestamps_ms"][index], selector, target)
                replay_image_frame(image, pixels, ms, technical["timestamps_ms"][index], image_selector,
                    raw[index], context["selection_frames"][index], target, gate_config)
                arms = {"crop": selected_points(frame["full_image_candidates"], frame["selection"]),
                        "image": selected_points(image["image_candidates"], image["image_selection"]), "video": raw[index]}
                crop_points = selected_points(frame["crop_candidates"], frame["selection"])
                bounds = frame["crop_bounds_xyxy"]
                frames.append({"frame_index": index, "native_timestamp_ms": ms, "effectiveness_eligible": index != 0,
                    "original_major_label": labels[index], "tracking_status": tracker_frame["tracking_status"],
                    "input_roi_valid": bounds is not None, "crop_bounds_xyxy": bounds,
                    "full_body_completeness": None, "subject_alignment_verified": False,
                    "new_output_major_failure": None,
                    "selection": {"crop": frame["selection"], "image": image["image_selection"], "video": context["selection_frames"][index]},
                    "joints": {joint: joint_row(index, joint, arms, crop_points, bounds, target, gate_config, labels[index]) for joint in JOINT_NAMES}})
                if index in review:
                    path = output / f"{name}_frame_{index:04d}.png"
                    if not cv2.imwrite(str(path), figure(pixels, index, bounds, arms, target)):
                        raise ValueError("Cannot save frozen context image")
                    examples.append({"frame_index": index, "path": path.relative_to(root).as_posix(), "sha256": sha(path),
                                     "human_review_answer": None})
            if capture.read()[0]:
                raise ValueError("Extra independent decoded source frame")
        finally:
            capture.release()
        clips.append({"pitch_id": name, "kind": clip["kind"], "target": target, "sources": refs,
            "summary": summarize_clip(frames), "frames": frames, "examples": examples,
            "xy_accuracy": xy_accuracy(root, sources, refs["pose"], video, target, canonical),
            "warning_tp_fn_fp": None, "identity_accuracy": None, "event_accuracy": None,
            "full_body_completeness": None, "passed": None})
    calls = {key: sum(c[key] for c in measured["clips"]) for key in
             ("new_tracker_initialization_calls", "new_tracker_update_calls", "new_pose_inference_calls")}
    if any(measured[key] != value for key, value in calls.items()) or calls["new_tracker_initialization_calls"] != 4:
        raise ValueError("Cohort new-call receipts differ")
    verify_frozen_evaluator(root, plan, proposal)
    verify_sources(root, all_refs)
    if protected_inventory(root, proposal) != inventory or sha(plan_path) != plan_sha or sha(measurements) != measurement_sha:
        raise ValueError("Frozen evidence changed during offline evaluation")
    report = {"status": "complete_offline_assisted_roi_cohort_evaluation", "plan_sha256": plan_sha,
        "measurement_sha256": measurement_sha, "evaluator_sha256": sha(__file__), "denominators": EXPECTED,
        **calls, "clips": clips, "independent_source_frames_verified": 592,
        "independent_crop_pixel_mapping_and_selector_frames_verified": 592,
        "independent_full_frame_image_selector_frames_verified": 592, "protected_physical_files_verified": len(inventory),
        "seed_frame_excluded_per_clip": 0, "warning_policy": None, "new_warning_counts": None,
        "warning_tp_fn_fp": None, "identity_accuracy": None, "event_accuracy": None, "passed": None,
        "phase2_automatic_reliability": "NOT PASSED", "human_initialized": True,
        "original_major_labels_used_for_grouping_only": True, "new_outputs_have_human_labels": False,
        "hidden_xy_used_as_truth": False, "original_predictions_modified": False,
        "limitations": ["Raw confidence and input support do not establish observed anatomy or subject identity.",
            "The four newly measured clips have no independent manual XY accuracy target.",
            "The pitch_003 XY summary is reused exactly from its bound sealed evaluation.",
            "Jump statistics include adjacent supported frames only, with no acceptance cutoff.",
            "No interpolation, warning threshold, new event score or automatic reliability pass is produced."]}
    write(output / "assisted_roi_cohort_evaluation.json", report)
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
