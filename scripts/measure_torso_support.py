"""GT-blind torso-overlap sidecar from sealed measurements; no inference."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

import measure_movenet_support as bbox
import torso_geometry as hulls

geometry = bbox.geometry
TORSO = bbox.TORSO
CODE_PATHS = {
    "producer_code": "scripts/measure_torso_support.py",
    "producer_tests": "tests/test_torso_support.py",
    "hull_helpers": "scripts/torso_geometry.py",
    "hull_tests": "tests/test_torso_geometry.py",
    "bbox_helpers": "scripts/measure_movenet_support.py",
    "association_helpers": "scripts/evaluate_movenet_cohort.py",
    "baseline_helpers": "scripts/measure_pose_mode_countercheck.py",
    "native_helpers": "scripts/check_movenet_compatibility.py",
}
WARNING_POLICY = {
    "rule": "existing_bbox_conflict_or_all_compatible_torso_hulls_disjoint",
    "candidate_association": geometry.ASSOCIATION,
    "raw_torso_order": list(TORSO),
    "raw_finite_rule": "existing_finite_point_no_visibility_or_presence_cutoff",
    "torso_domain": "source_pixel_convex_hull_of_four_shoulders_and_hips",
    "overlap_rule": "closed_sets_touching_edges_or_corners_count_as_overlap",
    "warning_rule": "preserve_bbox_warning_else_all_compatible_valid_hulls_disjoint",
    "support_rule": "any_one_compatible_nondegenerate_torso_hull_overlaps_raw_hull",
    "degenerate_rule": "fewer_than_three_convex_hull_vertices_abstain_unless_another_hull_overlaps",
    "insufficient_evidence": ["raw_torso_missing_or_nonfinite", "no_compatible_native_boxes",
        "raw_torso_hull_degenerate", "compatible_torso_hull_degenerate_without_overlap"],
    "previous_bbox_policy": bbox.WARNING_POLICY,
    "multiple_candidates": "retain_all_no_winner_no_cross_slot_point_assembly",
    "score_cutoff": None, "iou_cutoff": None, "padding": None,
    "temporal_slot_identity": False, "no_warning_means_correct_alignment": False,
    "warning_means_confirmed_major_failure": False,
}


def verify_plan(root, plan):
    if (plan["status"] != "frozen_before_support_measurement" or
            plan["warning_policy"] != WARNING_POLICY or plan["human_annotation_inputs"] != [] or
            plan["pose_inference_budget"] != 0 or plan["tracker_inference_budget"] != 0 or
            plan["production_adoption"]):
        raise ValueError("Unfrozen, contaminated or changed torso support policy")
    if not set(CODE_PATHS) <= set(plan["code"]):
        raise ValueError("Required producer/helper/test code references missing")
    for name, path in CODE_PATHS.items():
        if plan["code"][name]["path"] != path:
            raise ValueError("Changed code role")
    for ref in plan["code"].values():
        if Path(ref["path"]).suffix.lower() not in {".py", ".md"}:
            raise ValueError("Code references may bind only code or protocol documents")
        geometry.verify_ref(root, ref)
    if geometry.sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Unbound torso producer")
    targets = [clip["target"] for clip in plan["clips"]]
    if not targets or len({target["pitch_id"] for target in targets}) != len(targets):
        raise ValueError("Empty or duplicate cohort")
    for clip in plan["clips"]:
        target = clip["target"]
        if set(target) != {"pitch_id", "total_frames", "width", "height"} or any(
                isinstance(target[key], bool) or not isinstance(target[key], int) or target[key] <= 0
                for key in ("total_frames", "width", "height")):
            raise ValueError("Invalid target")
        name = target["pitch_id"]
        if not isinstance(name, str) or not name or Path(name).name != name:
            raise ValueError("Invalid pitch ID")
        if set(clip["sources"]) != bbox.SOURCE_ROLES:
            raise ValueError("Producer only permits native/CSRT/raw/capture inputs")
        for ref in clip["sources"].values():
            geometry.verify_ref(root, ref)
    if (plan["source_frames"] != sum(target["total_frames"] for target in targets) or
            plan["non_seed_frames"] != sum(target["total_frames"] - 1 for target in targets)):
        raise ValueError("Changed source/effectiveness denominators")


def torso_shape(points):
    """No visibility gate, padding, area threshold or anatomical inference."""
    polygon = hulls.convex_hull(points)
    return {"hull_xy_px": polygon, "nondegenerate": len(polygon) >= 3,
        "area_px2": hulls.polygon_area(polygon),
        "center_xy_px": [sum(point[axis] for point in points) / len(points) for axis in (0, 1)]}


def refine_frame(frame):
    previous = {key: frame[key] for key in ("status", "warning", "reason", "supporting_slot_indices")}
    raw_points = [frame["raw_torso"][name]["xy_px"] for name in TORSO]
    raw_shape = torso_shape(raw_points) if frame["raw_torso_all_finite"] else None
    candidates = set(frame["candidate_slot_indices"])
    overlapping, degenerate, tests = [], [], []
    for slot in frame["slots"]:
        index = slot["slot_index"]
        points = [slot["source_xy"][geometry.JOINTS.index(name)] for name in TORSO]
        native_shape = torso_shape(points)
        candidate = index in candidates
        overlap = None
        if raw_shape and raw_shape["nondegenerate"] and native_shape["nondegenerate"]:
            overlap = hulls.closed_convex_polygons_intersect(raw_shape["hull_xy_px"], native_shape["hull_xy_px"])
        if candidate and overlap:
            overlapping.append(index)
        if candidate and not native_shape["nondegenerate"]:
            degenerate.append(index)
        residuals = {name: math.dist(raw_points[i], points[i]) for i, name in enumerate(TORSO)} if raw_shape else None
        tests.append({"slot_index": index, "geometric_candidate": candidate,
            "native_torso": native_shape, "closed_hulls_overlap": overlap,
            "same_named_joint_residual_px": residuals,
            "center_residual_px": math.dist(raw_shape["center_xy_px"], native_shape["center_xy_px"]) if raw_shape else None,
            "native_hip_minus_shoulder_y_px": (points[2][1] + points[3][1] - points[0][1] - points[1][1]) / 2})
    if previous["status"] == "warning":
        status, warning, reason = "warning", True, "preserved_existing_bbox_conflict"
    elif previous["status"] == "insufficient_evidence":
        status, warning, reason = previous["status"], None, previous["reason"]
    elif not raw_shape["nondegenerate"]:
        status, warning, reason = "insufficient_evidence", None, "raw_torso_hull_degenerate"
    elif overlapping:
        status, warning, reason = "no_warning", False, "at_least_one_compatible_torso_hull_overlaps"
    elif degenerate:
        status, warning, reason = "insufficient_evidence", None, "compatible_torso_hull_degenerate_without_overlap"
    else:
        status, warning, reason = "warning", True, "all_compatible_torso_hulls_disjoint"
    return {**frame, "bbox_screen": previous, "raw_torso_shape": raw_shape,
        "torso_support_tests": tests, "overlapping_torso_slot_indices": overlapping,
        "degenerate_candidate_slot_indices": degenerate,
        "status": status, "warning": warning, "reason": reason}


def measure_clip(root, clip, plan_sha, producer_sha):
    result = bbox.measure_clip(root, clip, plan_sha, producer_sha)
    frames = [refine_frame(frame) for frame in result["frames"]]
    non_seed = frames[1:]
    return {**result, "warning_policy": WARNING_POLICY, "frames": frames,
        "summary": {"all_source_status_counts": dict(Counter(frame["status"] for frame in frames)),
            "non_seed_status_counts": dict(Counter(frame["status"] for frame in non_seed)),
            "non_seed_association_counts": dict(Counter(frame["association_status"] for frame in non_seed))}}


def measure(root, plan_path):
    root = Path(root).resolve()
    plan_path = geometry.bound_path(root, str(plan_path))
    plan, plan_sha = geometry.read(plan_path), geometry.sha(plan_path)
    output = bbox.output_path(root, plan["output_directory"])
    verify_plan(root, plan)
    producer_sha = geometry.sha(__file__)
    results = [measure_clip(root, clip, plan_sha, producer_sha) for clip in plan["clips"]]
    verify_plan(root, plan)
    if geometry.sha(plan_path) != plan_sha:
        raise ValueError("Plan changed during measurement")
    output.mkdir(parents=True)
    receipts = []
    for result in results:
        name = result["target"]["pitch_id"]
        path = output / (name + ".json")
        geometry.write(path, result)
        receipts.append({"pitch_id": name, "path": path.relative_to(root).as_posix(), "sha256": geometry.sha(path)})
    run = {"status": "sealed_movenet_support_diagnostics", "plan_sha256": plan_sha,
        "producer_sha256": producer_sha, "clips": receipts,
        "source_frames": sum(result["source_frames"] for result in results),
        "non_seed_frames": sum(result["non_seed_frames"] for result in results),
        "warning_policy": WARNING_POLICY, "human_annotation_inputs": [],
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "subject_selection_performed": False, "phase2_automatic_reliability": "NOT PASSED"}
    geometry.write(output / "support_run.json", run)
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = measure(args.root, args.plan)
    print(json.dumps({key: result[key] for key in ("status", "source_frames", "non_seed_frames")}))
