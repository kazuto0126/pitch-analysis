"""Offline cross-clip torso disagreement warnings; no inference or human inputs."""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from check_movenet_compatibility import bound, sha, write

STATES = ("warning", "candidate_dependent", "within_reference_range", "insufficient_evidence", "seed_excluded")
POLICY = {
    "feature": "minimum_same_slot_four_torso_rms_fraction_of_image_diagonal",
    "calibration": "all_finite_non_seed_frames_of_all_other_clips_without_human_filtering",
    "experimental_threshold": "maximum_calibration_feature_strict_exceedance",
    "warning": "query_min_strictly_greater_than_other_clip_sample_maximum",
    "candidate_dependent": "query_min_at_or_below_bound_and_query_max_strictly_above_bound",
    "within_reference_range": "query_max_at_or_below_bound_does_not_establish_alignment",
    "missing": "no_candidates_or_raw_torso_missing_or_no_finite_reference_is_insufficient",
    "seed": "retain_frame_zero_but_exclude_from_all_calibration_and_warning_decisions",
    "candidate_selection": "none_preserve_all_compatible_slots_no_cross_slot_joint_assembly",
    "temporal_expansion": False, "human_calibration_or_query_labels": False,
    "production_adoption": False, "coordinate_correction": False,
    "identity_claim": False, "generalization_or_false_alarm_guarantee": False,
    "validation_scope": "previously_inspected_development_cohort_leave_one_clip_out",
}
CODE_PATHS = {
    "producer_code": "scripts/measure_disagreement_warning.py",
    "producer_tests": "tests/test_disagreement_warning.py",
    "native_helpers": "scripts/check_movenet_compatibility.py",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def valid_range(low, high):
    if low is None and high is None:
        return
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in (low, high)) or low > high:
        raise ValueError("Malformed torso disagreement range")


def verify_measurement(data):
    target = data["target"]
    if (set(target) != {"pitch_id", "total_frames", "width", "height"} or
            not isinstance(target["pitch_id"], str) or not target["pitch_id"] or
            Path(target["pitch_id"]).name != target["pitch_id"] or
            any(type(target[k]) is not int or target[k] <= 0 for k in ("total_frames", "width", "height"))):
        raise ValueError("Invalid measurement target")
    if (data["status"] != "sealed_joint_disagreement_only" or data["human_annotation_inputs"] != [] or
            data["production_adoption"] is not False or data["coordinate_correctness_claimed"] is not False or
            any(type(data[k]) is not int or data[k] != 0 for k in
                ("pose_inference_calls", "tracker_inference_calls", "new_binary_warnings"))):
        raise ValueError("Unsealed, contaminated or adopted measurement")
    if [f["frame_index"] for f in data["frames"]] != list(range(target["total_frames"])):
        raise ValueError("Incomplete measurement timeline")
    for frame in data["frames"]:
        index = frame["frame_index"]
        slots = frame["candidate_slot_indices"]
        if (type(index) is not int or frame["effectiveness_eligible"] is not (index != 0) or
                len(set(slots)) != len(slots) or any(type(i) is not int or not 0 <= i < 6 for i in slots) or
                frame["association_status"] != ("none" if not slots else
                    "unique_geometric_candidate" if len(slots) == 1 else "ambiguous")):
            raise ValueError("Changed seed, association or candidate set")
        for key in ("native_timestamp_ms", "capture_timestamp_ms"):
            if type(frame[key]) not in (int, float) or not math.isfinite(frame[key]):
                raise ValueError("Nonfinite measurement timestamp")
        if abs(frame["native_timestamp_ms"] - frame["capture_timestamp_ms"]) > 1:
            raise ValueError("Measurement timelines differ")
        torso = frame["torso_rms"]
        values = torso["candidate_values"]
        if [v["slot_index"] for v in values] != slots:
            raise ValueError("Missing/reordered same-slot torso values")
        numbers = [v["rms_diagonal"] for v in values]
        for number in numbers:
            valid_range(number, number)
        if numbers and any(v is None for v in numbers) and any(v is not None for v in numbers):
            raise ValueError("Partial same-frame torso availability is invalid")
        finite = [v for v in numbers if v is not None]
        low, high = torso["range_diagonal"]["min"], torso["range_diagonal"]["max"]
        valid_range(low, high)
        if (low, high) != ((min(finite), max(finite)) if finite else (None, None)):
            raise ValueError("Range does not summarize all compatible whole-slot torso values")


def classify(low, high, reference, *, seed=False):
    valid_range(low, high)
    valid_range(reference, reference)
    if seed:
        return "seed_excluded", False, ["initialization_frame_excluded"]
    if reference is None or low is None:
        reasons = (["no_finite_other_clip_reference"] if reference is None else [])
        reasons += ["query_torso_or_candidate_measurement_unavailable"] if low is None else []
        return "insufficient_evidence", False, reasons
    if low > reference:
        return "warning", True, ["all_compatible_same_slot_torso_disagreements_exceed_other_clip_sample_maximum"]
    if high > reference:
        return "candidate_dependent", False, ["compatible_candidates_straddle_reference_bound_no_identity_selected"]
    return "within_reference_range", False, ["within_empirical_range_does_not_prove_correct_alignment"]


def make_sidecars(measurements):
    if not measurements or len({d["target"]["pitch_id"] for d in measurements}) != len(measurements):
        raise ValueError("Empty or duplicate measurement cohort")
    for data in measurements:
        verify_measurement(data)
    output = []
    for data in measurements:
        name = data["target"]["pitch_id"]
        references = [d for d in measurements if d["target"]["pitch_id"] != name]
        rows = [(d["target"]["pitch_id"], f) for d in references for f in d["frames"][1:]]
        finite = [(n, f) for n, f in rows if f["torso_rms"]["range_diagonal"]["min"] is not None]
        maximum = max((f["torso_rms"]["range_diagonal"]["min"] for _, f in finite), default=None)
        calibration = {
            "query_pitch_id": name, "reference_pitch_ids": [d["target"]["pitch_id"] for d in references],
            "reference_non_seed_frames": len(rows), "finite_frames": len(finite), "missing_frames": len(rows) - len(finite),
            "maximum_min_disagreement_diagonal": maximum,
            "maximum_sources": [{"pitch_id": n, "frame_index": f["frame_index"], "value": maximum}
                for n, f in finite if f["torso_rms"]["range_diagonal"]["min"] == maximum],
            "association_counts": dict(Counter(f["association_status"] for _, f in rows)),
            "candidate_count_counts": dict(Counter(str(len(f["candidate_slot_indices"])) for _, f in rows)),
            "per_reference_clip": [{"pitch_id": d["target"]["pitch_id"], "non_seed_frames": len(d["frames"]) - 1,
                "finite_frames": sum(f["torso_rms"]["range_diagonal"]["min"] is not None for f in d["frames"][1:])}
                for d in references],
        }
        frames = []
        for frame in data["frames"]:
            low, high = (frame["torso_rms"]["range_diagonal"][k] for k in ("min", "max"))
            state, warning, reasons = classify(low, high, maximum, seed=frame["frame_index"] == 0)
            frames.append({key: frame[key] for key in ("frame_index", "effectiveness_eligible", "native_timestamp_ms",
                "capture_timestamp_ms", "association_status", "candidate_slot_indices")} | {
                "min_disagreement_diagonal": low, "max_disagreement_diagonal": high,
                "evidence_state": state, "warning": warning, "reasons": reasons})
        output.append({"target": data["target"], "calibration": calibration, "frames": frames,
            "state_counts_non_seed": {s: sum(f["evidence_state"] == s for f in frames[1:]) for s in STATES if s != "seed_excluded"}})
    return output


def verify_plan(root, plan):
    if (plan["status"] != "frozen_before_disagreement_warning_trial" or plan["policy"] != POLICY or
            plan["human_annotation_inputs"] != [] or plan["production_adoption"] is not False or
            any(type(plan[k]) is not int or plan[k] != 0 for k in ("pose_inference_budget", "tracker_inference_budget"))):
        raise ValueError("Changed warning trial policy, budgets or human input boundary")
    for role, path in CODE_PATHS.items():
        if plan["code"][role]["path"] != path:
            raise ValueError("Unbound producer code role")
    for ref in plan["code"].values():
        if Path(ref["path"]).suffix not in {".py", ".md"}:
            raise ValueError("Only code and protocol documents permitted as code bindings")
        bound(root, ref)
    if sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Producer bytes do not match frozen plan")
    parent = read(bound(root, plan["measurement_plan"]))
    run = read(bound(root, plan["measurement_run"]))
    if (run["status"] != "sealed_joint_disagreement_measurements" or
            run["plan_sha256"] != plan["measurement_plan"]["sha256"] or run["policy"] != parent["policy"] or
            run["producer_sha256"] != parent["code"]["producer_code"]["sha256"] or
            run["human_annotation_inputs"] != [] or run["production_adoption"] is not False or
            any(type(run[k]) is not int or run[k] != 0 for k in
                ("pose_inference_calls", "tracker_inference_calls", "new_binary_warnings"))):
        raise ValueError("Unbound parent measurement run")
    if len(plan["clips"]) != len(run["clips"]) or len(parent["clips"]) != len(run["clips"]):
        raise ValueError("Incomplete sealed cohort")
    for setup, receipt, original in zip(plan["clips"], run["clips"], parent["clips"], strict=True):
        if (set(setup) != {"target", "source"} or setup["source"] != receipt or
                setup["target"] != original["target"] or setup["target"]["pitch_id"] != receipt["pitch_id"]):
            raise ValueError("Changed source role or target")
        data = read(bound(root, receipt))
        verify_measurement(data)
        if (data["target"] != setup["target"] or data["plan_sha256"] != run["plan_sha256"] or
                data["policy"] != run["policy"] or data["producer_sha256"] != run["producer_sha256"] or
                data["source_references"] != original["sources"]):
            raise ValueError("Unbound per-clip disagreement measurement")
        for ref in data["source_references"].values():
            bound(root, ref)
    if (plan["source_frames"] != sum(c["target"]["total_frames"] for c in plan["clips"]) or
            plan["non_seed_frames"] != sum(c["target"]["total_frames"] - 1 for c in plan["clips"])):
        raise ValueError("Changed cohort denominator")


def measure(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError("Plan outside project")
    plan, plan_sha = read(plan_path), sha(plan_path)
    verify_plan(root, plan)
    output = (root / plan["output_directory"]).resolve()
    if output.exists() or output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive new analysis_results output required")
    sidecars = make_sidecars([read(bound(root, c["source"])) for c in plan["clips"]])
    verify_plan(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Plan changed during warning production")
    output.mkdir(parents=True)
    common = {"plan_sha256": plan_sha, "producer_sha256": sha(__file__), "policy": POLICY,
        "human_annotation_inputs": [], "pose_inference_calls": 0, "tracker_inference_calls": 0,
        "production_adoption": False}
    receipts = []
    for sidecar, setup in zip(sidecars, plan["clips"], strict=True):
        name = sidecar["target"]["pitch_id"]
        path = output / (name + ".json")
        write(path, common | sidecar | {"status": "sealed_disagreement_warning_sidecar", "source_reference": setup["source"]})
        receipts.append({"pitch_id": name, "path": path.relative_to(root).as_posix(), "sha256": sha(path)})
    run = common | {"status": "sealed_disagreement_warning_trial", "source_frames": plan["source_frames"],
        "non_seed_frames": plan["non_seed_frames"], "clips": receipts, "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "warning_run.json", run)
    return run


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = measure(args.root, args.plan)
    print(json.dumps({key: result[key] for key in ("status", "source_frames", "non_seed_frames")}))
