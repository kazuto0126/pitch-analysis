"""Source-bound joint disagreement measurements; no inference or human labels."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

import measure_movenet_support as bbox
from pitch_analysis.manual_keypoints import JOINT_NAMES

geometry = bbox.geometry
JOINTS = tuple(JOINT_NAMES)
TORSO = bbox.TORSO
SOURCE_ROLES = bbox.SOURCE_ROLES | {"pose_reliability"}
CODE_PATHS = {
    "producer_code": "scripts/measure_joint_disagreement.py",
    "producer_tests": "tests/test_joint_disagreement.py",
    "bbox_helpers": "scripts/measure_movenet_support.py",
    "association_helpers": "scripts/evaluate_movenet_cohort.py",
    "baseline_helpers": "scripts/measure_pose_mode_countercheck.py",
    "native_helpers": "scripts/check_movenet_compatibility.py",
    "joint_contract": "src/pitch_analysis/manual_keypoints.py",
}
POLICY = {
    "joint_order": list(JOINTS), "candidate_association": geometry.ASSOCIATION,
    "distance": "euclidean_same_named_native_source_xy_minus_original_raw_source_xy",
    "units": ["source_pixels", "fraction_of_source_image_diagonal"],
    "candidate_summary": "minimum_and_maximum_across_all_compatible_slots_no_winner",
    "torso_summary": "same_single_slot_four_joint_rms_then_candidate_minimum_and_maximum",
    "finite_out_of_bounds": "retain_distance_and_explicit_in_source_flag",
    "raw_rule": "existing_finite_point_no_new_visibility_or_presence_gate",
    "model_state": "copy_original_pose_reliability_frame_states_without_reclassification",
    "score_cutoff": None, "new_warning_threshold": None,
    "identity_selected": False, "coordinate_correctness_claimed": False,
    "new_binary_warning": False, "temporal_slot_identity": False,
}


def verify_plan(root, plan):
    if (plan["status"] != "frozen_before_disagreement_measurement" or plan["policy"] != POLICY or
            plan["human_annotation_inputs"] != [] or plan["pose_inference_budget"] != 0 or
            plan["tracker_inference_budget"] != 0 or plan["production_adoption"]):
        raise ValueError("Changed or contaminated disagreement protocol")
    if not set(CODE_PATHS) <= set(plan["code"]):
        raise ValueError("Required producer code bindings absent")
    for role, path in CODE_PATHS.items():
        if plan["code"][role]["path"] != path:
            raise ValueError("Changed code role")
    for ref in plan["code"].values():
        if Path(ref["path"]).suffix.lower() not in {".py", ".md"}:
            raise ValueError("Code bindings only permit code/protocol documents")
        geometry.verify_ref(root, ref)
    if geometry.sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Unbound producer")
    targets = [clip["target"] for clip in plan["clips"]]
    if not targets or len({target["pitch_id"] for target in targets}) != len(targets):
        raise ValueError("Empty or duplicate cohort")
    for clip in plan["clips"]:
        target = clip["target"]
        if (set(target) != {"pitch_id", "total_frames", "width", "height"} or
                any(type(target[key]) is not int or target[key] <= 0 for key in ("total_frames", "width", "height")) or
                not isinstance(target["pitch_id"], str) or not target["pitch_id"] or
                Path(target["pitch_id"]).name != target["pitch_id"]):
            raise ValueError("Invalid target")
        if set(clip["sources"]) != SOURCE_ROLES:
            raise ValueError("Only sealed native/CSRT/raw/capture/pose-state inputs permitted")
        for ref in clip["sources"].values():
            geometry.verify_ref(root, ref)
    if (plan["source_frames"] != sum(t["total_frames"] for t in targets) or
            plan["non_seed_frames"] != sum(t["total_frames"] - 1 for t in targets)):
        raise ValueError("Changed frame denominators")


def value_range(values):
    values = [value for value in values if value is not None]
    return {"min": min(values) if values else None, "max": max(values) if values else None}


def raw_point(point, target):
    finite = bbox.baseline.finite_point(point)
    xy = [point["x"] * target["width"], point["y"] * target["height"]] if finite else None
    finite = finite and all(math.isfinite(value) for value in xy)
    return {"finite": finite, "xy_px": xy if finite else None,
        "visibility": point["visibility"] if finite else None,
        "presence": point["presence"] if finite else None,
        "in_source": geometry.inside(xy, [0., 0., target["width"], target["height"]]) if finite else None}


def frame_measurement(base, raw, states, target):
    diagonal = math.hypot(target["width"], target["height"])
    candidates = set(base["candidate_slot_indices"])
    joints = {}
    for name in JOINTS:
        point = raw_point(raw.get(name), target)
        distances = []
        for slot in base["slots"]:
            index = geometry.JOINTS.index(name)
            xy = slot["source_xy"][index]
            if len(xy) != 2 or not all(math.isfinite(value) for value in xy):
                raise ValueError("Nonfinite sealed native joint")
            distance = math.dist(point["xy_px"], xy) if point["finite"] else None
            distances.append({"slot_index": slot["slot_index"], "geometric_candidate": slot["slot_index"] in candidates,
                "native_xy_px": xy, "native_joint_score": slot["native_yx_score"][index][2],
                "native_in_source": geometry.inside(xy, [0., 0., target["width"], target["height"]]),
                "distance_px": distance, "distance_diagonal": distance / diagonal if distance is not None else None})
        compatible = [row for row in distances if row["geometric_candidate"]]
        if states[name] not in {"observed", "interpolated", "missing"}:
            raise ValueError("Invalid saved pose state")
        joints[name] = {"raw": point, "baseline_model_state": states[name], "slot_distances": distances,
            "candidate_distances": compatible,
            "distance_range_px": value_range(row["distance_px"] for row in compatible),
            "distance_range_diagonal": value_range(row["distance_diagonal"] for row in compatible)}
    rms = []
    for slot_index in range(6):
        distances = [joints[name]["slot_distances"][slot_index]["distance_px"] for name in TORSO]
        value = math.hypot(*distances) / 2 if all(value is not None for value in distances) else None
        rms.append({"slot_index": slot_index, "geometric_candidate": slot_index in candidates,
            "rms_px": value, "rms_diagonal": value / diagonal if value is not None else None})
    compatible = [row for row in rms if row["geometric_candidate"]]
    return {key: base[key] for key in ("frame_index", "effectiveness_eligible", "native_timestamp_ms",
        "capture_timestamp_ms", "decoded_bgr_sha256", "association_status", "candidate_slot_indices")} | {
        "joints": joints, "torso_rms": {"slot_values": rms, "candidate_values": compatible,
            "range_px": value_range(row["rms_px"] for row in compatible),
            "range_diagonal": value_range(row["rms_diagonal"] for row in compatible)}}


def measure_clip(root, clip, plan_sha, producer_sha):
    base = bbox.measure_clip(root, clip, plan_sha, producer_sha)
    target, sources = clip["target"], clip["sources"]
    total = target["total_frames"]
    pose = geometry.read(root / sources["pose_reliability"]["path"])
    capture = geometry.read(root / sources["capture"]["path"])
    if (pose["pitch_id"] != target["pitch_id"] or pose["total_frames"] != total or
            pose["frame_indices"] != list(range(total)) or any(len(pose["joints"][name]["frame_states"]) != total for name in JOINTS)):
        raise ValueError("Wrong original pose-state source or timeline")
    mapping = pose["important_joints"]
    roles = ("throwing_shoulder", "throwing_elbow", "throwing_wrist", "lead_hip", "lead_knee", "lead_ankle")
    throwing = mapping["throwing_shoulder"].split("_")[0]
    if throwing not in {"LEFT", "RIGHT"}:
        raise ValueError("Invalid saved throwing side")
    lead = "LEFT" if throwing == "RIGHT" else "RIGHT"
    expected = {role: (throwing if role.startswith("throwing_") else lead) + "_" + role.split("_")[1].upper() for role in roles}
    if mapping != expected:
        raise ValueError("Inconsistent saved role/landmark mapping")
    raw = bbox.baseline.load_video_raw(root / sources["original_raw"]["path"], capture, total)
    frames = [frame_measurement(frame, points,
        {name: pose["joints"][name]["frame_states"][frame["frame_index"]] for name in JOINTS}, target)
        for frame, points in zip(base["frames"], raw, strict=True)]
    return {"status": "sealed_joint_disagreement_only", "target": target, "source_references": sources,
        "plan_sha256": plan_sha, "producer_sha256": producer_sha, "human_annotation_inputs": [],
        "source_frames": total, "non_seed_frames": total - 1, "policy": POLICY,
        "important_joints": mapping, "frames": frames,
        "non_seed_association_counts": dict(Counter(f["association_status"] for f in frames[1:])),
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "new_binary_warnings": 0, "coordinate_correctness_claimed": False}


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
    run = {"status": "sealed_joint_disagreement_measurements", "plan_sha256": plan_sha,
        "producer_sha256": producer_sha, "clips": receipts,
        "source_frames": sum(result["source_frames"] for result in results),
        "non_seed_frames": sum(result["non_seed_frames"] for result in results),
        "policy": POLICY, "human_annotation_inputs": [], "pose_inference_calls": 0,
        "tracker_inference_calls": 0, "production_adoption": False, "new_binary_warnings": 0,
        "phase2_automatic_reliability": "NOT PASSED"}
    geometry.write(output / "measurement_run.json", run)
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = measure(args.root, args.plan)
    print(json.dumps({key: result[key] for key in ("status", "source_frames", "non_seed_frames")}))
