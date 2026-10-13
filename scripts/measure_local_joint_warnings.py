"""GT-free extreme same-joint disagreement screens; no anatomy certification."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
import measure_disagreement_warning as torso

ROLES = ("throwing_shoulder", "throwing_elbow", "throwing_wrist", "lead_hip", "lead_knee", "lead_ankle")
STATES = torso.STATES
POLICY = {
    "scope": "local_extreme_positional_disagreement_not_major_failure_or_visibility",
    "roles": list(ROLES),
    "feature": "minimum_same_named_joint_raw_native_distance_fraction_of_image_diagonal",
    "calibration": "all_finite_non_seed_frames_of_same_anatomical_joint_in_all_other_clips_without_human_filtering",
    "experimental_threshold": "other_clip_sample_maximum_strict_exceedance",
    "mapping": "saved_anatomical_mapping_must_be_identical_across_cohort",
    "states": torso.POLICY["warning"] + "; candidate_dependent,within_reference_range,insufficient_evidence,seed_excluded",
    "decision_rule": "apply_existing_frozen_torso_classify_to_each_joint_range_and_own_reference",
    "within_range_means_reliable": False, "missing_means_occluded": False,
    "native_score_cutoff": None, "identity_selection": False, "cross_slot_joint_assembly": False,
    "raw_processed_state": "copy_original_state_as_context_never_convert_missing_to_positional_warning",
    "major_warning_generated": False, "temporal_expansion": False,
    "human_annotation_inputs": [], "production_adoption": False,
    "calibration_limitation": "only_clips_containing_cohort_extreme_min_disagreement_can_exceed_other_clip_maximum",
    "validation_scope": "previously_inspected_development_cohort_no_generalization_or_false_alarm_guarantee",
}
CODE_PATHS = {
    "producer_code": "scripts/measure_local_joint_warnings.py",
    "producer_tests": "tests/test_local_joint_warnings.py",
    "torso_policy_helpers": "scripts/measure_disagreement_warning.py",
    "native_helpers": "scripts/check_movenet_compatibility.py",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_focus(data):
    torso.verify_measurement(data)
    mapping = data["important_joints"]
    if set(mapping) != set(ROLES):
        raise ValueError("Incomplete six-focus-joint mapping")
    side = mapping["throwing_shoulder"].split("_")[0]
    if side not in ("LEFT", "RIGHT"):
        raise ValueError("Invalid throwing side")
    lead = "LEFT" if side == "RIGHT" else "RIGHT"
    expected = {role: (side if role.startswith("throwing_") else lead) + "_" + role.split("_")[1].upper() for role in ROLES}
    if mapping != expected:
        raise ValueError("Inconsistent anatomical role mapping")
    for frame in data["frames"]:
        slots = frame["candidate_slot_indices"]
        for name in mapping.values():
            joint = frame["joints"][name]
            if joint["baseline_model_state"] not in ("observed", "interpolated", "missing"):
                raise ValueError("Unknown original model state")
            raw_finite = joint["raw"]["finite"]
            if type(raw_finite) is not bool:
                raise ValueError("Invalid raw finite flag")
            native = joint["slot_distances"]
            if [row["slot_index"] for row in native] != list(range(6)):
                raise ValueError("Incomplete six-slot joint evidence")
            for row in native:
                if row["geometric_candidate"] is not (row["slot_index"] in slots):
                    raise ValueError("Joint slot membership differs from frame association")
                torso.valid_range(row["distance_diagonal"], row["distance_diagonal"])
                if (row["distance_diagonal"] is not None) != raw_finite:
                    raise ValueError("Raw availability differs across saved native slots")
            values = joint["candidate_distances"]
            if ([row["slot_index"] for row in values] != slots or
                    values != [row for row in native if row["geometric_candidate"]]):
                raise ValueError("Incomplete/reordered compatible joint candidates")
            numbers = [row["distance_diagonal"] for row in values]
            for value in numbers:
                torso.valid_range(value, value)
            finite = [v for v in numbers if v is not None]
            if finite and len(finite) != len(numbers):
                raise ValueError("Partial raw availability across native slots")
            low, high = (joint["distance_range_diagonal"][k] for k in ("min", "max"))
            torso.valid_range(low, high)
            if (low, high) != ((min(finite), max(finite)) if finite else (None, None)):
                raise ValueError("Range omits compatible candidates")
            if slots and raw_finite != bool(finite):
                raise ValueError("Raw finite status differs from candidate distances")


def make_sidecars(measurements):
    if not measurements or len({d["target"]["pitch_id"] for d in measurements}) != len(measurements):
        raise ValueError("Empty or duplicate source cohort")
    for data in measurements:
        verify_focus(data)
        if data["important_joints"] != measurements[0]["important_joints"]:
            raise ValueError("Cannot pool different anatomical mappings")
    output = []
    for data in measurements:
        name = data["target"]["pitch_id"]
        references = [d for d in measurements if d["target"]["pitch_id"] != name]
        rows = [(d["target"]["pitch_id"], f) for d in references for f in d["frames"][1:]]
        calibration = {}
        for role, landmark in data["important_joints"].items():
            finite = [(n, f) for n, f in rows if f["joints"][landmark]["distance_range_diagonal"]["min"] is not None]
            maximum = max((f["joints"][landmark]["distance_range_diagonal"]["min"] for _, f in finite), default=None)
            calibration[role] = {"query_pitch_id": name, "landmark": landmark,
                "reference_pitch_ids": [d["target"]["pitch_id"] for d in references],
                "reference_non_seed_frames": len(rows), "finite_frames": len(finite), "missing_frames": len(rows) - len(finite),
                "maximum_min_disagreement_diagonal": maximum,
                "maximum_sources": [{"pitch_id": n, "frame_index": f["frame_index"], "value": maximum}
                    for n, f in finite if f["joints"][landmark]["distance_range_diagonal"]["min"] == maximum],
                "association_counts": dict(Counter(f["association_status"] for _, f in rows)),
                "candidate_count_counts": dict(Counter(str(len(f["candidate_slot_indices"])) for _, f in rows))}
        frames = []
        for frame in data["frames"]:
            joints = {}
            for role, landmark in data["important_joints"].items():
                joint = frame["joints"][landmark]
                low, high = (joint["distance_range_diagonal"][k] for k in ("min", "max"))
                state, warning, reasons = torso.classify(low, high,
                    calibration[role]["maximum_min_disagreement_diagonal"], seed=frame["frame_index"] == 0)
                # Reuse the exact numeric decision, but state the local target.
                if warning:
                    reasons = ["all_compatible_same_named_joint_disagreements_exceed_other_clip_sample_maximum"]
                elif state == "candidate_dependent":
                    reasons = ["compatible_candidates_straddle_joint_reference_no_identity_selected"]
                elif state == "insufficient_evidence":
                    reasons = ["no_finite_other_clip_joint_reference"] if calibration[role]["maximum_min_disagreement_diagonal"] is None else []
                    reasons += ["query_joint_or_candidate_measurement_unavailable"] if low is None else []
                joints[role] = {"landmark": landmark, "raw_model_state": joint["baseline_model_state"],
                    "minimum_distance_diagonal": low, "maximum_distance_diagonal": high,
                    "evidence_state": state, "warning": warning, "reasons": reasons}
            frames.append({key: frame[key] for key in ("frame_index", "effectiveness_eligible", "native_timestamp_ms",
                "capture_timestamp_ms", "association_status", "candidate_slot_indices")} | {"joints": joints})
        output.append({"target": data["target"], "important_joints": data["important_joints"], "calibration": calibration,
            "frames": frames, "state_counts_non_seed": {role: {s: sum(f["joints"][role]["evidence_state"] == s for f in frames[1:])
                for s in STATES if s != "seed_excluded"} for role in ROLES}})
    return output


def verify_plan(root, plan):
    if (plan["status"] != "frozen_before_local_joint_warning_trial" or plan["policy"] != POLICY or
            plan["human_annotation_inputs"] != [] or plan["production_adoption"] is not False or
            plan["major_warning_generated"] is not False or
            any(type(plan[k]) is not int or plan[k] != 0 for k in ("pose_inference_budget", "tracker_inference_budget"))):
        raise ValueError("Changed local trial policy or contamination")
    for role, path in CODE_PATHS.items():
        if plan["code"][role]["path"] != path:
            raise ValueError("Unbound code role")
    for entry in plan["code"].values():
        if Path(entry["path"]).suffix not in (".py", ".md"):
            raise ValueError("Code inputs must be code/protocol, never human annotation data")
        bound(root, entry)
    if sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Unbound producer")
    parent = read(bound(root, plan["parent_evidence_plan"]))
    torso.verify_plan(root, parent)
    if plan["clips"] != parent["clips"]:
        raise ValueError("Changed complete sealed cohort")
    for clip in plan["clips"]:
        verify_focus(read(bound(root, clip["source"])))
    if (plan["source_frames"] != parent["source_frames"] or plan["non_seed_frames"] != parent["non_seed_frames"]):
        raise ValueError("Changed source/effectiveness denominators")


def measure(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError("Plan outside workspace")
    plan, plan_sha = read(plan_path), sha(plan_path)
    verify_plan(root, plan)
    output = (root / plan["output_directory"]).resolve()
    if output.exists() or output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive output directory inside analysis_results required")
    sidecars = make_sidecars([read(bound(root, c["source"])) for c in plan["clips"]])
    verify_plan(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Frozen plan changed")
    common = {"plan_sha256": plan_sha, "producer_sha256": sha(__file__), "policy": POLICY, "human_annotation_inputs": [],
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False, "major_warning_generated": False}
    output.mkdir(parents=True)
    receipts = []
    for sidecar, clip in zip(sidecars, plan["clips"], strict=True):
        name = clip["target"]["pitch_id"]
        path = output / (name + ".json")
        write(path, common | sidecar | {"status": "sealed_local_joint_warning_sidecar", "source_reference": clip["source"]})
        receipts.append({"pitch_id": name, "path": path.relative_to(root).as_posix(), "sha256": sha(path)})
    run = common | {"status": "sealed_local_joint_warning_trial", "clips": receipts,
        "source_frames": plan["source_frames"], "non_seed_frames": plan["non_seed_frames"], "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "local_joint_warning_run.json", run)
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = measure(args.root, args.plan)
    print(json.dumps({key: result[key] for key in ("status", "source_frames", "non_seed_frames")}))
