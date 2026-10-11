"""GT-blind offline geometry support diagnostics; no model or subject selection."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

import evaluate_movenet_cohort as geometry
import measure_pose_mode_countercheck as baseline


TORSO = geometry.TORSO
SOURCE_ROLES = {"native_measurement", "tracked_roi", "original_raw", "capture"}
CODE_PATHS = {
    "producer_code": "scripts/measure_movenet_support.py",
    "producer_tests": "tests/test_movenet_support.py",
    "association_helpers": "scripts/evaluate_movenet_cohort.py",
    "baseline_helpers": "scripts/measure_pose_mode_countercheck.py",
    "native_helpers": "scripts/check_movenet_compatibility.py",
}
WARNING_POLICY = {
    "rule": "all_compatible_native_boxes_contradict_raw_torso",
    "candidate_association": geometry.ASSOCIATION,
    "raw_torso_order": list(TORSO),
    "raw_finite_rule": "existing_finite_point_no_visibility_or_presence_cutoff",
    "box_domain": "unclipped_source_xy_half_open",
    "support_rule": "at_least_one_single_compatible_box_contains_all_four_raw_torso_points",
    "warning_rule": "every_compatible_box_excludes_at_least_one_raw_torso_point",
    "insufficient_evidence": ["raw_torso_missing_or_nonfinite", "no_compatible_native_boxes"],
    "multiple_candidates": "retain_all_no_winner_all_boxes_tested",
    "score_cutoff": None,
    "iou_cutoff": None,
    "temporal_slot_identity": False,
    "no_warning_means_correct_alignment": False,
    "warning_means_confirmed_major_failure": False,
}


def output_path(root, value):
    output = geometry.bound_path(root, value)
    if output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results") or output.exists():
        raise ValueError("Exclusive new output directory inside analysis_results required")
    return output


def verify_plan(root, plan):
    if plan["status"] != "frozen_before_support_measurement" or plan["warning_policy"] != WARNING_POLICY:
        raise ValueError("Unfrozen or changed support warning policy")
    if not set(CODE_PATHS) <= set(plan["code"]):
        raise ValueError("Required producer/helper/test code references missing")
    for name, value in CODE_PATHS.items():
        if plan["code"][name]["path"] != value:
            raise ValueError("Changed producer/helper/test code role")
    for ref in plan["code"].values():
        if Path(ref["path"]).suffix.lower() not in {".py", ".md"}:
            raise ValueError("Code references may bind code or protocol documents, not annotation data")
        geometry.verify_ref(root, ref)
    if geometry.sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Unbound support producer")
    targets = [clip["target"] for clip in plan["clips"]]
    if not targets or len({target["pitch_id"] for target in targets}) != len(targets):
        raise ValueError("Empty or duplicate source cohort")
    for clip in plan["clips"]:
        target = clip["target"]
        if set(target) != {"pitch_id", "total_frames", "width", "height"} or any(
                isinstance(target[key], bool) or not isinstance(target[key], int) or target[key] <= 0
                for key in ("total_frames", "width", "height")):
            raise ValueError("Invalid support source target")
        if not isinstance(target["pitch_id"], str) or not target["pitch_id"] or Path(target["pitch_id"]).name != target["pitch_id"]:
            raise ValueError("Invalid source pitch ID")
        if set(clip["sources"]) != SOURCE_ROLES:
            raise ValueError("Support producer only permits native/CSRT/raw/capture input roles")
        for ref in clip["sources"].values():
            geometry.verify_ref(root, ref)
    if (plan["source_frames"] != sum(target["total_frames"] for target in targets) or
            plan["non_seed_frames"] != sum(target["total_frames"] - 1 for target in targets)):
        raise ValueError("Source/effectiveness denominators differ from declared cohort")


def frame_support(slots, rectangle, raw, target):
    """Test entire compatible boxes; never assemble support across people/slots."""
    association = geometry.geometric_association(slots, rectangle, target["width"], target["height"])
    torso = {}
    for name in TORSO:
        point = raw.get(name)
        finite = baseline.finite_point(point)
        xy = [point["x"] * target["width"], point["y"] * target["height"]] if finite else None
        finite = finite and all(math.isfinite(value) for value in xy)
        torso[name] = {"missing": point is None, "finite": finite,
            "xy_px": xy if finite else None,
            "visibility": point["visibility"] if finite else None,
            "presence": point["presence"] if finite else None}
    all_finite = all(point["finite"] for point in torso.values())
    tests, supporting = [], []
    for slot, competitor in zip(slots, association["competitors"], strict=True):
        inside = {name: geometry.inside(point["xy_px"], slot["source_box_xyxy"])
            if point["finite"] else None for name, point in torso.items()}
        contains_all = all(inside.values()) if all_finite else None
        if competitor["geometric_candidate"] and contains_all:
            supporting.append(slot["slot_index"])
        tests.append({"slot_index": slot["slot_index"],
            "geometric_candidate": competitor["geometric_candidate"],
            "source_box_xyxy": slot["source_box_xyxy"],
            "native_box_ymin_xmin_ymax_xmax_score": slot["native_box_ymin_xmin_ymax_xmax_score"],
            "raw_torso_inside_box": inside, "contains_all_raw_torso": contains_all})
    candidates = association["candidate_slot_indices"]
    if not all_finite:
        status, warning, reason = "insufficient_evidence", None, "raw_torso_missing_or_nonfinite"
    elif not candidates:
        status, warning, reason = "insufficient_evidence", None, "no_compatible_native_boxes"
    elif supporting:
        status, warning, reason = "no_warning", False, "at_least_one_compatible_box_supports_all_raw_torso"
    else:
        status, warning, reason = "warning", True, WARNING_POLICY["rule"]
    return {"status": status, "warning": warning, "reason": reason,
        "raw_torso": torso, "raw_torso_all_finite": all_finite,
        "association_status": association["status"], "candidate_count": len(candidates),
        "candidate_slot_indices": candidates, "supporting_slot_indices": supporting,
        "association": association, "slot_support_tests": tests,
        "subject_alignment_verified": False, "confirmed_major_failure": None}


def measure_clip(root, clip, plan_sha, producer_sha):
    target, sources = clip["target"], clip["sources"]
    native, tracked, capture = (geometry.read(root / sources[key]["path"])
        for key in ("native_measurement", "tracked_roi", "capture"))
    total = target["total_frames"]
    if (native["status"] != "sealed_measurements_only" or native["target"] != target or
            native["human_annotation_inputs"] != [] or native["total_frames"] != total or
            native["completed_frames"] != total or native["inference_calls"] != total or
            tracked["status"] != "sealed_measurements_only" or tracked["target"] != target or
            any([frame["frame_index"] for frame in data["frames"]] != list(range(total))
                for data in (native, tracked))):
        raise ValueError("Changed or incomplete native/CSRT source receipt")
    video_ref = native["source_references"]["video"]
    capture_video = Path(capture["video"])
    if not capture_video.is_absolute():
        capture_video = root / capture_video
    if (tracked["producer_sources"]["video"] != video_ref or
            capture_video.resolve() != geometry.bound_path(root, video_ref["path"]) or
            (capture["width"], capture["height"], capture["start_frame"], capture["end_frame"],
             capture["requested_frames"], capture["processed_frames"]) !=
            (target["width"], target["height"], 0, total - 1, total, total)):
        raise ValueError("Native/CSRT/raw capture source identity or range differs")
    raw = baseline.load_video_raw(root / sources["original_raw"]["path"], capture, total)
    frames = []
    for index, (frame, tracker, original, points) in enumerate(zip(
            native["frames"], tracked["frames"], capture["selection_frames"], raw, strict=True)):
        native_ms, tracker_ms, capture_ms = (frame["native_timestamp_ms"],
            tracker["native_timestamp_ms"], original["timestamp_ms"])
        if (not all(math.isfinite(value) for value in (native_ms, tracker_ms, capture_ms)) or
                not math.isclose(native_ms, tracker_ms, rel_tol=0, abs_tol=1e-6) or
                abs(native_ms - capture_ms) > 1. or frame["timestamp_ms"] != round(native_ms) or
                frame["decoded_bgr_sha256"] != tracker["decoded_bgr_sha256"]):
            raise ValueError("Native/CSRT/raw frame timeline or source pixels differ")
        slots = geometry.derive_slots(frame, target)
        frames.append({"frame_index": index, "effectiveness_eligible": index != 0,
            "native_timestamp_ms": native_ms, "capture_timestamp_ms": capture_ms,
            "decoded_bgr_sha256": frame["decoded_bgr_sha256"],
            "input_geometry": frame["input_geometry"], "native_output": frame["native_output"],
            "slots": slots, **frame_support(slots, tracker["usable_rectangle_xywh"], points, target)})
    non_seed = [frame for frame in frames if frame["effectiveness_eligible"]]
    return {"status": "sealed_support_diagnostics_only", "target": target,
        "plan_sha256": plan_sha, "producer_sha256": producer_sha,
        "source_references": sources, "human_annotation_inputs": [],
        "source_frames": total, "non_seed_frames": total - 1,
        "summary": {"all_source_status_counts": dict(Counter(frame["status"] for frame in frames)),
            "non_seed_status_counts": dict(Counter(frame["status"] for frame in non_seed)),
            "non_seed_association_counts": dict(Counter(frame["association_status"] for frame in non_seed))},
        "warning_policy": WARNING_POLICY, "frames": frames,
        "pose_inference_calls": 0, "tracker_inference_calls": 0,
        "production_adoption": False, "subject_selection_performed": False}


def measure(root, plan_path):
    root = Path(root).resolve()
    plan_path = geometry.bound_path(root, str(plan_path))
    plan, plan_sha = geometry.read(plan_path), geometry.sha(plan_path)
    output = output_path(root, plan["output_directory"])
    verify_plan(root, plan)
    producer_sha = geometry.sha(__file__)
    results = [measure_clip(root, clip, plan_sha, producer_sha) for clip in plan["clips"]]
    verify_plan(root, plan)
    if geometry.sha(plan_path) != plan_sha:
        raise ValueError("Support plan changed during measurement")
    # Create output only after every declared source is verified again.
    output.mkdir(parents=True)
    receipts = []
    for result in results:
        pitch_id = result["target"]["pitch_id"]
        path = output / (pitch_id + ".json")
        geometry.write(path, result)
        receipts.append({"pitch_id": pitch_id, "path": path.relative_to(root).as_posix(),
            "sha256": geometry.sha(path)})
    run = {"status": "sealed_movenet_support_diagnostics", "plan_sha256": plan_sha,
        "producer_sha256": producer_sha, "clips": receipts,
        "source_frames": sum(result["source_frames"] for result in results),
        "non_seed_frames": sum(result["non_seed_frames"] for result in results),
        "warning_policy": WARNING_POLICY, "human_annotation_inputs": [],
        "pose_inference_calls": 0, "tracker_inference_calls": 0,
        "production_adoption": False, "subject_selection_performed": False,
        "phase2_automatic_reliability": "NOT PASSED"}
    geometry.write(output / "support_run.json", run)
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    run = measure(args.root, args.plan)
    print(json.dumps({key: run[key] for key in ("status", "source_frames", "non_seed_frames")}))
