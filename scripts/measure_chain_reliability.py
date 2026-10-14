"""Supervised upper-envelope checks of raw 2D chain-to-torso projected length.

Only raw points, their original states, and source metadata enter the feature.
Parent verifiers check immutable input receipts; no native point enters a rule.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
import calibrate_joint_reliability as parent

CHAINS = {"arm_chain": ("throwing_shoulder", "throwing_elbow", "throwing_wrist"),
          "lead_leg_chain": ("lead_hip", "lead_knee", "lead_ankle")}
ANCHORS = ("throwing_shoulder", "lead_hip")
DEPENDENCIES = {name: tuple(dict.fromkeys((*members, *ANCHORS))) for name, members in CHAINS.items()}
STATES = ("warning", "within_reference_range", "insufficient_evidence", "seed_excluded")
POLICY = {
    "scope": "raw_2d_chain_relative_stretch_not_joint_major_identity_or_occlusion",
    "chains": {name: list(members) for name, members in CHAINS.items()}, "anchors": list(ANCHORS),
    "feature": "sum_two_raw_source_pixel_segment_lengths_divided_by_same_frame_anchor_distance",
    "calibration": "all_unique_dependencies_existing_reviewed_raw_observation_other_clips_non_seed_only",
    "bound": "maximum_finite_eligible_reference_ratio_strict_exceedance_only",
    "no_lower_bound": True, "positive_denominator_floor_or_clamp": None,
    "native_coordinates_or_scores_used_by_feature": False, "query_human_labels_in_own_reference": False,
    "application_reads_annotations": False, "within_range_means_reliable": False,
    "coordinate_correction": False, "temporal_expansion": False,
    "joint_warning_generated": False, "major_warning_generated": False, "production_adoption": False,
    "validation_scope": "previously_reviewed_development_cohort_not_true_bone_length_or_generalization",
}
CODE_PATHS = {"producer_code": "scripts/measure_chain_reliability.py", "producer_tests": "tests/test_chain_reliability.py",
              "parent_helpers": "scripts/calibrate_joint_reliability.py", "native_helpers": "scripts/check_movenet_compatibility.py"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _raw_sources(measurements):
    names = [d["target"]["pitch_id"] for d in measurements]
    if not names or len(set(names)) != len(names):
        raise ValueError("Empty or duplicate raw-source cohort")
    for data in measurements:
        target, mapping = data["target"], data["important_joints"]
        if (any(type(target[k]) is not int or target[k] <= 0 for k in ("total_frames", "width", "height")) or
                mapping != measurements[0]["important_joints"] or set(mapping) != set(parent.ROLES) or
                mapping != parent.review.role_mapping(mapping["throwing_shoulder"].split("_")[0]) or
                [f["frame_index"] for f in data["frames"]] != list(range(target["total_frames"]))):
            raise ValueError("Changed raw mapping, target, or timeline")
        for frame in data["frames"]:
            times = (frame["native_timestamp_ms"], frame["capture_timestamp_ms"])
            if (type(frame["frame_index"]) is not int or frame["effectiveness_eligible"] is not (frame["frame_index"] != 0) or
                    any(type(v) not in (int, float) or not math.isfinite(v) for v in times) or abs(times[0] - times[1]) > 1):
                raise ValueError("Changed raw seed or source time")
            if any(frame["joints"][name]["baseline_model_state"] not in ("observed", "interpolated", "missing")
                   for name in mapping.values()):
                raise ValueError("Unknown original model state")
    return names


def chain_feature(frame, mapping, chain):
    members, dependencies = CHAINS[chain], DEPENDENCIES[chain]
    points, states, reasons = {}, {}, []
    for role in dependencies:
        joint = frame["joints"][mapping[role]]
        states[role] = joint["baseline_model_state"]
        point = joint["raw"].get("xy_px")
        good = (joint["raw"].get("finite") is True and isinstance(point, (list, tuple)) and len(point) == 2 and
                all(type(v) in (int, float) and math.isfinite(v) for v in point))
        points[role] = list(point) if good else None
        if not good:
            reasons.append("raw_dependency_missing_or_nonfinite:" + role)
    segments = [math.dist(points[a], points[b]) if points[a] is not None and points[b] is not None else None
                for a, b in zip(members, members[1:])]
    denominator = math.dist(points[ANCHORS[0]], points[ANCHORS[1]]) if all(points[r] is not None for r in ANCHORS) else None
    numerator = sum(segments) if all(v is not None for v in segments) else None
    ratio = None
    if denominator == 0:
        reasons.append("zero_projected_anchor_distance")
    if any(v is not None and not math.isfinite(v) for v in (*segments, numerator, denominator)):
        reasons.append("nonfinite_projected_geometry")
    elif numerator is not None and denominator is not None and denominator > 0:
        value = numerator / denominator
        if math.isfinite(value):
            ratio = value
        else:
            reasons.append("nonfinite_ratio_from_unclamped_positive_denominator")
    return {"ratio": ratio, "segment_lengths_px": [v if v is None or math.isfinite(v) else None for v in segments],
        "numerator_px": numerator if numerator is None or math.isfinite(numerator) else None,
        "denominator_px": denominator if denominator is None or math.isfinite(denominator) else None,
        "dependency_raw_states": states, "raw_xy_px": points, "measurement_reasons": reasons}


def fit_reference(measurements, views):
    names = _raw_sources(measurements)
    if [v["pitch_id"] for v in views] != names:
        raise ValueError("Reviewed views differ from complete raw cohort")
    for data, view in zip(measurements, views, strict=True):
        parent._view_measurement(view, data)
    training = [parent._training_ref(v) for v in views]
    folds = []
    for query in measurements:
        name = query["target"]["pitch_id"]
        references = [(d, v) for d, v in zip(measurements, views, strict=True) if d["target"]["pitch_id"] != name]
        calibration = {}
        for chain, dependencies in DEPENDENCIES.items():
            retained, excluded, eligible, missing = [], Counter(), 0, 0
            for data, view in references:
                for frame, reviewed in zip(data["frames"][1:], view["frames"][1:], strict=True):
                    holds = [role + "=" + reviewed["focus_joints"][role]["use_disposition"]["status"] for role in dependencies
                             if reviewed["focus_joints"][role]["use_disposition"]["status"] != parent.ELIGIBLE]
                    if holds:
                        excluded["|".join(holds)] += 1
                        continue
                    eligible += 1
                    value = chain_feature(frame, data["important_joints"], chain)["ratio"]
                    if value is None:
                        missing += 1
                    else:
                        retained.append({"pitch_id": data["target"]["pitch_id"], "frame_index": frame["frame_index"], "value": value})
            maximum = max((r["value"] for r in retained), default=None)
            calibration[chain] = {"query_pitch_id": name, "dependency_roles": list(dependencies),
                "reference_pitch_ids": [d["target"]["pitch_id"] for d, _ in references],
                "reference_non_seed_frames": sum(d["target"]["total_frames"] - 1 for d, _ in references),
                "eligible_reference_frames": eligible, "finite_frames": len(retained), "missing_frames": missing,
                "excluded_reference_frames": sum(excluded.values()), "excluded_use_disposition_counts": dict(excluded),
                "retained_reference_rows": retained, "maximum_ratio": maximum,
                "maximum_sources": [deepcopy(r) for r in retained if r["value"] == maximum]}
        folds.append({"query_pitch_id": name, "target": deepcopy(query["target"]), "important_joints": deepcopy(query["important_joints"]),
            "human_training_inputs": [deepcopy(r) for r in training if r["pitch_id"] != name], "calibration": calibration})
    return {"status": "sealed_chain_reference", "policy": deepcopy(POLICY), "folds": folds, "human_training_inputs": training,
        "source_frames": sum(d["target"]["total_frames"] for d in measurements),
        "non_seed_frames": sum(d["target"]["total_frames"] - 1 for d in measurements), **_flags()}


def _flags():
    return {"supervised_calibration_used": True, "pose_inference_calls": 0, "tracker_inference_calls": 0,
            "production_adoption": False, "joint_warning_generated": False, "major_warning_generated": False}


def _reference(measurements, artifact):
    names = _raw_sources(measurements)
    indexed = {d["target"]["pitch_id"]: d for d in measurements}
    if (artifact["status"] != "sealed_chain_reference" or artifact["policy"] != POLICY or
            any(artifact[k] != v or type(artifact[k]) is not type(v) for k, v in _flags().items()) or
            [f["query_pitch_id"] for f in artifact["folds"]] != names or
            [r["pitch_id"] for r in artifact["human_training_inputs"]] != names or
            artifact["source_frames"] != sum(d["target"]["total_frames"] for d in measurements) or
            artifact["non_seed_frames"] != sum(d["target"]["total_frames"] - 1 for d in measurements)):
        raise ValueError("Changed chain reference scope, source, or training provenance")
    for data, fold in zip(measurements, artifact["folds"], strict=True):
        name = data["target"]["pitch_id"]
        others = [n for n in names if n != name]
        if (fold["target"] != data["target"] or fold["important_joints"] != data["important_joints"] or
                set(fold["calibration"]) != set(CHAINS) or fold["human_training_inputs"] !=
                [r for r in artifact["human_training_inputs"] if r["pitch_id"] != name]):
            raise ValueError("Changed query fold or anatomical mapping")
        for chain, cal in fold["calibration"].items():
            counts = [cal[k] for k in ("reference_non_seed_frames", "eligible_reference_frames", "finite_frames", "missing_frames", "excluded_reference_frames")]
            if (cal["query_pitch_id"] != name or cal["reference_pitch_ids"] != others or cal["dependency_roles"] != list(DEPENDENCIES[chain]) or
                    any(type(v) is not int or v < 0 for v in (*counts, *cal["excluded_use_disposition_counts"].values())) or
                    cal["reference_non_seed_frames"] != sum(indexed[n]["target"]["total_frames"] - 1 for n in others) or
                    cal["eligible_reference_frames"] + cal["excluded_reference_frames"] != cal["reference_non_seed_frames"] or
                    cal["finite_frames"] + cal["missing_frames"] != cal["eligible_reference_frames"] or
                    sum(cal["excluded_use_disposition_counts"].values()) != cal["excluded_reference_frames"]):
                raise ValueError("Changed chain calibration denominator")
            rows, seen = cal["retained_reference_rows"], set()
            for row in rows:
                pitch, index = row["pitch_id"], row["frame_index"]
                if pitch not in others or type(index) is not int or not 1 <= index < indexed[pitch]["target"]["total_frames"] or (pitch, index) in seen:
                    raise ValueError("Query leakage, seed, duplicate, or unknown chain reference row")
                value = chain_feature(indexed[pitch]["frames"][index], indexed[pitch]["important_joints"], chain)["ratio"]
                if type(row["value"]) not in (int, float) or value is None or row["value"] != value:
                    raise ValueError("Retained chain value differs from sealed raw geometry")
                seen.add((pitch, index))
            maximum = max((r["value"] for r in rows), default=None)
            limit = cal["maximum_ratio"]
            if limit is not None and (type(limit) not in (int, float) or not math.isfinite(limit) or limit < 0):
                raise ValueError("Nonfinite, negative, or boolean chain reference bound")
            if len(rows) != cal["finite_frames"] or maximum != cal["maximum_ratio"] or cal["maximum_sources"] != [r for r in rows if r["value"] == maximum]:
                raise ValueError("Changed chain upper envelope or maximum sources")


def apply_reference(measurements, artifact):
    _reference(measurements, artifact)
    output = []
    for data, fold in zip(measurements, artifact["folds"], strict=True):
        frames = []
        for frame in data["frames"]:
            chains = {}
            for chain in CHAINS:
                feature = chain_feature(frame, data["important_joints"], chain)
                value, limit = feature["ratio"], fold["calibration"][chain]["maximum_ratio"]
                if not frame["effectiveness_eligible"]:
                    state, reasons = "seed_excluded", ["initialization_frame_excluded"]
                elif value is None or limit is None:
                    state = "insufficient_evidence"
                    reasons = feature["measurement_reasons"] + (["no_finite_other_clip_reviewed_chain_reference"] if limit is None else [])
                elif value > limit:
                    state, reasons = "warning", ["chain_relative_stretch_warning"]
                else:
                    state, reasons = "within_reference_range", ["within_upper_envelope_does_not_prove_reliability"]
                chains[chain] = feature | {"evidence_state": state, "warning": state == "warning", "reasons": reasons}
            frames.append({k: frame[k] for k in ("frame_index", "effectiveness_eligible", "native_timestamp_ms", "capture_timestamp_ms")} | {"chains": chains})
        output.append({"target": deepcopy(data["target"]), "important_joints": deepcopy(data["important_joints"]),
            "human_training_inputs": deepcopy(fold["human_training_inputs"]), "calibration": deepcopy(fold["calibration"]), "frames": frames,
            "state_counts_non_seed": {chain: {s: sum(f["chains"][chain]["evidence_state"] == s for f in frames[1:]) for s in STATES[:-1]} for chain in CHAINS}})
    return output


def _plan(root, plan, stage):
    if (plan["status"] != "frozen_before_chain_reference_" + stage or plan["policy"] != POLICY or
            any(plan[k] is not False for k in ("production_adoption", "joint_warning_generated", "major_warning_generated")) or
            any(type(plan[k]) is not int or plan[k] != 0 for k in ("pose_inference_budget", "tracker_inference_budget")) or
            plan["supervised_calibration_used"] is not True or
            any(type(plan[k]) is not int or plan[k] != value for k, value in (("source_frames", 592), ("non_seed_frames", 587)))):
        raise ValueError("Changed chain plan, scope, or inference budget")
    for role, path in CODE_PATHS.items():
        if plan["code"][role]["path"] != path:
            raise ValueError("Changed chain code role")
    for ref in plan["code"].values():
        if Path(ref["path"]).suffix not in (".py", ".md"):
            raise ValueError("Code bindings cannot hide annotation inputs")
        bound(root, ref)
    if sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Running chain code differs from frozen bytes")


def _cohort(measurements, plan, training):
    if (len(_raw_sources(measurements)) != 5 or sum(d["target"]["total_frames"] for d in measurements) != plan["source_frames"] or
            sum(d["target"]["total_frames"] - 1 for d in measurements) != plan["non_seed_frames"] or
            plan["human_training_inputs"] != training):
        raise ValueError("Declared chain cohort or supervised training pool differs from evidence")


def verify_plan(root, plan):
    _plan(root, plan, "fit")
    measurements, views = parent.verify_fit_plan(root, read(bound(root, plan["parent_fit_plan"])))
    applied, artifact = parent.verify_apply_plan(root, read(bound(root, plan["parent_apply_plan"])))
    if applied != measurements or plan["human_training_inputs"] != artifact["human_training_inputs"]:
        raise ValueError("FIT/APPLY parent evidence or disclosed training provenance differs")
    _cohort(measurements, plan, artifact["human_training_inputs"])
    return measurements, views


def verify_apply_plan(root, plan):
    """No FIT verifier, GT, or reviewed-view reads in application."""
    _plan(root, plan, "apply")
    if plan["application_human_annotation_inputs"] != [] or plan["supervised_calibration_used"] is not True:
        raise ValueError("Changed chain application annotation boundary")
    fit_path = bound(root, plan["fit_plan"])
    fit_plan = read(fit_path)
    _plan(root, fit_plan, "fit")
    if plan["parent_apply_plan"] != fit_plan["parent_apply_plan"]:
        raise ValueError("Application parent differs from fitted source")
    original_apply = read(bound(root, plan["parent_apply_plan"]))
    measurements, previous = parent.verify_apply_plan(root, original_apply)
    artifact = read(bound(root, plan["calibration_artifact"]))
    if (artifact["plan_sha256"] != sha(fit_path) or artifact["producer_sha256"] != fit_plan["code"]["producer_code"]["sha256"] or
            artifact["measurement_sources"] != [c["source"] for c in original_apply["clips"]] or
            artifact["reviewed_source_references"] != previous["reviewed_source_references"] or
            artifact["human_training_inputs"] != previous["human_training_inputs"] or
            artifact["human_training_inputs"] != fit_plan["human_training_inputs"]):
        raise ValueError("Unbound chain numeric artifact or provenance")
    _reference(measurements, artifact)
    _cohort(measurements, plan, artifact["human_training_inputs"])
    return measurements, artifact


def fit(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError("Chain fit plan outside project")
    plan, plan_sha = read(plan_path), sha(plan_path)
    output = parent._output(root, plan)
    measurements, views = verify_plan(root, plan)
    artifact = fit_reference(measurements, views)
    original_apply = read(bound(root, plan["parent_apply_plan"]))
    original_fit = read(bound(root, plan["parent_fit_plan"]))
    artifact.update({"plan_sha256": plan_sha, "producer_sha256": sha(__file__),
        "measurement_sources": [deepcopy(c["source"]) for c in original_apply["clips"]],
        "reviewed_source_references": [deepcopy(c["reviewed_reliability"]) for c in original_fit["clips"]]})
    verify_plan(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Chain fit plan changed")
    output.mkdir(parents=True)
    path = output / "chain_reference.json"
    write(path, artifact)
    result = {"status": "sealed_chain_reference_fit", "plan_sha256": plan_sha, "producer_sha256": sha(__file__), "policy": POLICY,
        "calibration_artifact": {"path": path.relative_to(root).as_posix(), "sha256": sha(path)},
        "human_training_inputs": artifact["human_training_inputs"], "source_frames": 592, "non_seed_frames": 587, **_flags()}
    write(output / "fit_run.json", result)
    return result


def apply(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError("Chain application plan outside project")
    plan, plan_sha = read(plan_path), sha(plan_path)
    output = parent._output(root, plan)
    measurements, artifact = verify_apply_plan(root, plan)
    sidecars = apply_reference(measurements, artifact)
    verify_apply_plan(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Chain application plan changed")
    output.mkdir(parents=True)
    common = {"plan_sha256": plan_sha, "producer_sha256": sha(__file__), "policy": POLICY,
        "calibration_artifact": deepcopy(plan["calibration_artifact"]), "application_human_annotation_inputs": [], **_flags()}
    receipts = []
    for data, source in zip(sidecars, artifact["measurement_sources"], strict=True):
        name = data["target"]["pitch_id"]
        path = output / (name + ".json")
        write(path, common | data | {"status": "sealed_chain_warning_sidecar", "source_reference": source})
        receipts.append({"pitch_id": name, "path": path.relative_to(root).as_posix(), "sha256": sha(path)})
    result = common | {"status": "sealed_chain_warning_trial", "clips": receipts, "human_training_inputs": artifact["human_training_inputs"],
        "source_frames": 592, "non_seed_frames": 587, "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "chain_warning_run.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("fit", "apply"))
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = fit(args.root, args.plan) if args.stage == "fit" else apply(args.root, args.plan)
    print(json.dumps({key: result[key] for key in ("status", "source_frames", "non_seed_frames")}))
