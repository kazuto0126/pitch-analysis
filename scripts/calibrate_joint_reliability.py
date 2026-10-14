"""Explicit human-supervised reference fitting and annotation-free application.

This fits empirical disagreement bounds from existing qualitative raw reviews;
it does not train a pose model, certify hidden XY, or change production gates.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
import export_reviewed_reliability as review
import measure_local_joint_warnings as local

ROLES, STATES = local.ROLES, local.STATES
ELIGIBLE = "reviewed_raw_observation"
FIT_POLICY = {
    "stage": "explicit_supervised_qualitative_reference_fit",
    "reference": "other_clips_existing_use_disposition_exact_reviewed_raw_observation",
    "feature": "same_named_joint_all_compatible_slot_min_distance_fraction_of_image_diagonal",
    "bound": "maximum_finite_eligible_non_seed_reference_value",
    "query_clip_human_labels_in_own_fold": False,
    "source_view": "rebuild_existing_derive_clip_and_compare_without_overlay_export",
    "original_view_semantics": "confirmed_frame_holds_only_no_new_uncertainty_filter",
    "precision_claim": "qualitative_raw_review_not_exact_xy_or_native_accuracy",
    "production_adoption": False, "major_warning_generated": False,
    "pose_model_training": False, "validation_scope": "previously_reviewed_development_cross_validation",
}
APPLY_POLICY = {
    "stage": "annotation_free_application_of_explicit_supervised_reference",
    "feature": FIT_POLICY["feature"], "supervised_calibration_used": True,
    "decision": "existing_strict_exceedance_and_straddle_rule_using_frozen_supervised_numeric_bound",
    "application_reads_annotations": False, "within_range_means_reliable": False,
    "missing_means_occluded": False, "native_score_cutoff": None,
    "identity_selection": False, "cross_slot_joint_assembly": False,
    "temporal_expansion": False, "coordinate_correction": False,
    "production_adoption": False, "major_warning_generated": False,
    "validation_scope": "previously_reviewed_development_cross_validation_no_generalization_guarantee",
}
CODE_PATHS = {
    "producer_code": "scripts/calibrate_joint_reliability.py",
    "producer_tests": "tests/test_joint_reliability_calibration.py",
    "local_helpers": "scripts/measure_local_joint_warnings.py",
    "review_helpers": "scripts/export_reviewed_reliability.py",
    "native_helpers": "scripts/check_movenet_compatibility.py",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _measurements(measurements):
    names = [data["target"]["pitch_id"] for data in measurements]
    if not names or len(set(names)) != len(names):
        raise ValueError("Empty or duplicate calibration measurement cohort")
    for data in measurements:
        local.verify_focus(data)
        if data["important_joints"] != measurements[0]["important_joints"]:
            raise ValueError("Different anatomical mappings cannot share references")
    return names


def _training_ref(view):
    ref = view["source_artifacts"]["ground_truth"]
    if (not isinstance(ref.get("path"), str) or not ref["path"] or not isinstance(ref.get("sha256"), str) or
            len(ref["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in ref["sha256"])):
        raise ValueError("Missing human training provenance")
    return {**deepcopy(ref), "pitch_id": view["pitch_id"]}


def _view_measurement(view, data):
    total, width, height = (data["target"][key] for key in ("total_frames", "width", "height"))
    if (view["schema_version"] != "reviewed-reliability-view-v1" or
            view["output_kind"] != "derived_reviewed_reliability_view_not_editable_ground_truth" or
            view["pitch_id"] != data["target"]["pitch_id"] or view["summary"]["total_frames"] != total or
            [f["frame_index"] for f in view["frames"]] != list(range(total))):
        raise ValueError("Wrong reviewed-view source or timeline")
    _training_ref(view)
    for saved, measured in zip(view["frames"], data["frames"], strict=True):
        times = (saved["timestamp_ms"], measured["native_timestamp_ms"], measured["capture_timestamp_ms"])
        if (any(type(value) not in (int, float) or not math.isfinite(value) for value in times) or
                abs(times[0] - times[1]) > 1 or abs(times[1] - times[2]) > 1 or
                set(saved["focus_joints"]) != set(ROLES)):
            raise ValueError("Reviewed-view timestamp or joint denominator differs")
        for role, name in data["important_joints"].items():
            joint, original = saved["focus_joints"][role], measured["joints"][name]
            expected = review.disposition(joint["human_raw_overlay_review"]["status"], joint["model_state"], saved["human_review"])
            if (joint["landmark"] != name or joint["model_state"] != original["baseline_model_state"] or
                    joint["use_disposition"] != expected):
                raise ValueError("Reviewed disposition, landmark, or original model state changed")
            if original["raw"]["finite"]:
                point = joint["raw_landmark"]
                if (point is None or any(type(point.get(k)) not in (int, float) or not math.isfinite(point[k]) for k in ("x", "y")) or
                        [point["x"] * width, point["y"] * height] != original["raw"]["xy_px"]):
                    raise ValueError("Reviewed raw coordinate differs from measured raw source")


def fit_reference(measurements, views):
    """Fit each fold using only other clips' existing reviewed dispositions."""
    names = _measurements(measurements)
    if len(views) != len(measurements) or [v["pitch_id"] for v in views] != names:
        raise ValueError("Reviewed views do not match the complete ordered cohort")
    for view, data in zip(views, measurements, strict=True):
        _view_measurement(view, data)
    training = [_training_ref(view) for view in views]
    if len({ref["path"] for ref in training}) != len(training):
        raise ValueError("Human references must identify distinct source clips")
    folds = []
    for query in measurements:
        name = query["target"]["pitch_id"]
        references = [(d, v) for d, v in zip(measurements, views, strict=True) if d["target"]["pitch_id"] != name]
        calibration = {}
        for role, landmark in query["important_joints"].items():
            retained, excluded, eligible, missing = [], Counter(), 0, 0
            association, candidate_counts = Counter(), Counter()
            for data, view in references:
                for measured, saved in zip(data["frames"][1:], view["frames"][1:], strict=True):
                    association[measured["association_status"]] += 1
                    candidate_counts[str(len(measured["candidate_slot_indices"]))] += 1
                    disposition = saved["focus_joints"][role]["use_disposition"]["status"]
                    if disposition != ELIGIBLE:
                        excluded[disposition] += 1
                        continue
                    eligible += 1
                    value = measured["joints"][landmark]["distance_range_diagonal"]["min"]
                    if value is None:
                        missing += 1
                    else:
                        retained.append({"pitch_id": data["target"]["pitch_id"], "frame_index": measured["frame_index"], "value": value})
            maximum = max((row["value"] for row in retained), default=None)
            calibration[role] = {"query_pitch_id": name, "landmark": landmark, "reference_pitch_ids": [d["target"]["pitch_id"] for d, _ in references],
                "reference_non_seed_frames": sum(d["target"]["total_frames"] - 1 for d, _ in references),
                "eligible_reference_frames": eligible, "finite_frames": len(retained), "missing_frames": missing,
                "excluded_use_disposition_counts": dict(excluded), "maximum_min_disagreement_diagonal": maximum,
                "maximum_sources": [deepcopy(row) for row in retained if row["value"] == maximum],
                "retained_reference_rows": retained, "association_counts": dict(association),
                "candidate_count_counts": dict(candidate_counts)}
        folds.append({"query_pitch_id": name, "target": deepcopy(query["target"]),
            "important_joints": deepcopy(query["important_joints"]),
            "human_training_inputs": [deepcopy(ref) for ref in training if ref["pitch_id"] != name], "calibration": calibration})
    return {"status": "sealed_supervised_joint_reference", "fit_policy": deepcopy(FIT_POLICY),
        "supervised_calibration_used": True, "human_training_inputs": training,
        "source_frames": sum(d["target"]["total_frames"] for d in measurements),
        "non_seed_frames": sum(d["target"]["total_frames"] - 1 for d in measurements), "folds": folds,
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "major_warning_generated": False, "pose_model_training": False}


def _validate_reference(measurements, artifact):
    """Check numerical/provenance consistency without opening training files."""
    names = _measurements(measurements)
    if (artifact["status"] != "sealed_supervised_joint_reference" or artifact["fit_policy"] != FIT_POLICY or
            artifact["supervised_calibration_used"] is not True or artifact["production_adoption"] is not False or
            artifact["major_warning_generated"] is not False or artifact["pose_model_training"] is not False or
            [f["query_pitch_id"] for f in artifact["folds"]] != names or
            [ref["pitch_id"] for ref in artifact["human_training_inputs"]] != names or
            artifact["source_frames"] != sum(d["target"]["total_frames"] for d in measurements) or
            artifact["non_seed_frames"] != sum(d["target"]["total_frames"] - 1 for d in measurements) or
            any(type(artifact[k]) is not int or artifact[k] != 0 for k in ("pose_inference_calls", "tracker_inference_calls"))):
        raise ValueError("Unbound, incomplete, or mislabeled supervised reference")
    indexed = {d["target"]["pitch_id"]: d for d in measurements}
    for ref in artifact["human_training_inputs"]:
        _training_ref({"pitch_id": ref["pitch_id"], "source_artifacts": {"ground_truth": ref}})
    if len({ref["path"] for ref in artifact["human_training_inputs"]}) != len(names):
        raise ValueError("Human source provenance must identify distinct clips")
    for query, fold in zip(measurements, artifact["folds"], strict=True):
        name = query["target"]["pitch_id"]
        refs = [n for n in names if n != name]
        if (fold["target"] != query["target"] or fold["important_joints"] != query["important_joints"] or
                set(fold["calibration"]) != set(ROLES) or fold["human_training_inputs"] !=
                [ref for ref in artifact["human_training_inputs"] if ref["pitch_id"] != name]):
            raise ValueError("Query fold or human training provenance differs")
        for role, landmark in query["important_joints"].items():
            cal = fold["calibration"][role]
            expected_total = sum(indexed[n]["target"]["total_frames"] - 1 for n in refs)
            counts = [cal[k] for k in ("reference_non_seed_frames", "eligible_reference_frames", "finite_frames", "missing_frames")]
            excluded = cal["excluded_use_disposition_counts"]
            reference_frames = [f for pitch in refs for f in indexed[pitch]["frames"][1:]]
            if (cal["query_pitch_id"] != name or cal["landmark"] != landmark or cal["reference_pitch_ids"] != refs or cal["reference_non_seed_frames"] != expected_total or
                    any(type(v) is not int or v < 0 for v in [*counts, *excluded.values()]) or
                    ELIGIBLE in excluded or cal["eligible_reference_frames"] + sum(excluded.values()) != expected_total or
                    cal["finite_frames"] + cal["missing_frames"] != cal["eligible_reference_frames"] or
                    cal["association_counts"] != dict(Counter(f["association_status"] for f in reference_frames)) or
                    cal["candidate_count_counts"] != dict(Counter(str(len(f["candidate_slot_indices"])) for f in reference_frames))):
                raise ValueError("Invalid calibrated eligibility or missing denominator")
            rows, seen = cal["retained_reference_rows"], set()
            for row in rows:
                pitch, index, value = row["pitch_id"], row["frame_index"], row["value"]
                if (pitch not in refs or type(index) is not int or not 1 <= index < indexed[pitch]["target"]["total_frames"] or
                        (pitch, index) in seen):
                    raise ValueError("Query leakage, seed, duplicate, or unknown reference row")
                local.torso.valid_range(value, value)
                if value is None or value != indexed[pitch]["frames"][index]["joints"][landmark]["distance_range_diagonal"]["min"]:
                    raise ValueError("Reference row differs from sealed numerical evidence")
                seen.add((pitch, index))
            maximum = max((r["value"] for r in rows), default=None)
            local.torso.valid_range(cal["maximum_min_disagreement_diagonal"], cal["maximum_min_disagreement_diagonal"])
            if (len(rows) != cal["finite_frames"] or maximum != cal["maximum_min_disagreement_diagonal"] or
                    cal["maximum_sources"] != [r for r in rows if r["value"] == maximum]):
                raise ValueError("Changed empirical maximum or reference sources")


def apply_reference(measurements, artifact):
    """Apply frozen values; annotations/views are never opened or consulted."""
    _validate_reference(measurements, artifact)
    output = []
    for data, fold in zip(measurements, artifact["folds"], strict=True):
        frames = []
        for frame in data["frames"]:
            joints = {}
            for role, landmark in data["important_joints"].items():
                point = frame["joints"][landmark]
                low, high = (point["distance_range_diagonal"][k] for k in ("min", "max"))
                reference = fold["calibration"][role]["maximum_min_disagreement_diagonal"]
                state, warning, reasons = local.torso.classify(low, high, reference, seed=frame["frame_index"] == 0)
                if warning:
                    reasons = ["all_compatible_same_joint_disagreements_exceed_other_clip_human_reviewed_reference_maximum"]
                elif state == "candidate_dependent":
                    reasons = ["compatible_joint_candidates_straddle_supervised_bound_no_identity_selected"]
                elif state == "insufficient_evidence":
                    reasons = (["no_finite_other_clip_human_reviewed_reference"] if reference is None else [])
                    reasons += ["query_joint_or_candidate_measurement_unavailable"] if low is None else []
                joints[role] = {"landmark": landmark, "raw_model_state": point["baseline_model_state"],
                    "minimum_distance_diagonal": low, "maximum_distance_diagonal": high,
                    "evidence_state": state, "warning": warning, "reasons": reasons}
            frames.append({key: frame[key] for key in ("frame_index", "effectiveness_eligible", "native_timestamp_ms",
                "capture_timestamp_ms", "association_status", "candidate_slot_indices")} | {"joints": joints})
        output.append({"target": deepcopy(data["target"]), "important_joints": deepcopy(data["important_joints"]),
            "calibration": deepcopy(fold["calibration"]), "human_training_inputs": deepcopy(fold["human_training_inputs"]),
            "frames": frames, "state_counts_non_seed": {role: {state: sum(f["joints"][role]["evidence_state"] == state for f in frames[1:])
                for state in STATES[:-1]} for role in ROLES}})
    return output


def _code(root, plan):
    for role, path in CODE_PATHS.items():
        if plan["code"][role]["path"] != path:
            raise ValueError("Changed supervised code role")
    for ref in plan["code"].values():
        if Path(ref["path"]).suffix not in (".py", ".md"):
            raise ValueError("Code bindings cannot hide annotation inputs")
        bound(root, ref)
    if sha(__file__) != plan["code"]["producer_code"]["sha256"]:
        raise ValueError("Running calibration code differs from frozen source")


def _budget(plan):
    if (plan["production_adoption"] is not False or plan["major_warning_generated"] is not False or
            any(type(plan[k]) is not int or plan[k] != 0 for k in ("pose_inference_budget", "tracker_inference_budget"))):
        raise ValueError("Supervised study cannot adopt, infer, or generate major warnings")


def _reviewed_view(root, setup, measurement):
    view = read(bound(root, setup["reviewed_reliability"]))
    if set(view["source_artifacts"]) != review.REQUIRED_SOURCES:
        raise ValueError("Incomplete original reviewed-view sources")
    paths = {role: bound(root, ref) for role, ref in view["source_artifacts"].items()}
    rebuilt = review.derive_clip({"pitch_id": setup["target"]["pitch_id"], "sources": view["source_artifacts"]}, paths)
    if {k: v for k, v in view.items() if k != "export"} != rebuilt:
        raise ValueError("Reviewed cache differs from original source reconstruction")
    metadata = read(paths["video_metadata"])
    if tuple(metadata[k] for k in ("frame_count", "width", "height")) != tuple(setup["target"][k] for k in ("total_frames", "width", "height")):
        raise ValueError("Reviewed video dimensions differ from numerical measurement")
    if view["source_artifacts"]["pose_reliability"] != measurement["source_references"]["pose_reliability"]:
        raise ValueError("Reviewed and numerical original pose sources differ")
    _view_measurement(view, measurement)
    return view


def verify_fit_plan(root, plan):
    if plan["status"] != "frozen_before_supervised_joint_reference_fit" or plan["policy"] != FIT_POLICY:
        raise ValueError("Unfrozen or changed explicitly supervised fit policy")
    _code(root, plan)
    _budget(plan)
    parent = read(bound(root, plan["parent_evidence_plan"]))
    local.verify_plan(root, parent)
    if [{"target": c["target"], "source": c["measurement"]} for c in plan["clips"]] != parent["clips"]:
        raise ValueError("Fit measurements differ from sealed parent cohort")
    measurements, views = [], []
    for setup in plan["clips"]:
        measurement = read(bound(root, setup["measurement"]))
        measurements.append(measurement)
        views.append(_reviewed_view(root, setup, measurement))
    names = _measurements(measurements)
    if (len(names) != 5 or sum(d["target"]["total_frames"] for d in measurements) != 592 or
            plan["source_frames"] != 592 or plan["non_seed_frames"] != 587 or
            plan["human_training_inputs"] != [_training_ref(view) for view in views]):
        raise ValueError("Incomplete supervised cohort or hidden human training inputs")
    return measurements, views


def _output(root, plan):
    output = (root / plan["output_directory"]).resolve()
    if output.exists() or output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive supervised output inside analysis_results required")
    return output


def fit(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError("Fit plan outside project")
    plan, plan_sha = read(plan_path), sha(plan_path)
    output = _output(root, plan)
    measurements, views = verify_fit_plan(root, plan)
    artifact = fit_reference(measurements, views)
    artifact.update({"plan_sha256": plan_sha, "producer_sha256": sha(__file__),
        "measurement_sources": [deepcopy(c["measurement"]) for c in plan["clips"]],
        "reviewed_source_references": [deepcopy(c["reviewed_reliability"]) for c in plan["clips"]]})
    verify_fit_plan(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Fit plan changed during calibration")
    output.mkdir(parents=True)
    path = output / "joint_reference.json"
    write(path, artifact)
    result = {"status": "sealed_supervised_joint_reference_fit", "plan_sha256": plan_sha,
        "producer_sha256": sha(__file__), "policy": FIT_POLICY, "supervised_calibration_used": True,
        "human_training_inputs": artifact["human_training_inputs"], "source_frames": 592, "non_seed_frames": 587,
        "calibration_artifact": {"path": path.relative_to(root).as_posix(), "sha256": sha(path)},
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False, "major_warning_generated": False}
    write(output / "fit_run.json", result)
    return result


def verify_apply_plan(root, plan):
    """Verify numerical application without dereferencing views or GT refs."""
    if (plan["status"] != "frozen_before_supervised_joint_reference_apply" or plan["policy"] != APPLY_POLICY or
            plan["supervised_calibration_used"] is not True or plan["application_human_annotation_inputs"] != []):
        raise ValueError("Changed supervised application policy or annotation input boundary")
    _code(root, plan)
    _budget(plan)
    fit_path = bound(root, plan["fit_plan"])
    fit_plan = read(fit_path)
    _code(root, fit_plan)
    _budget(fit_plan)
    if fit_plan["status"] != "frozen_before_supervised_joint_reference_fit" or fit_plan["policy"] != FIT_POLICY:
        raise ValueError("Wrong supervised fit manifest")
    artifact = read(bound(root, plan["calibration_artifact"]))
    if (artifact["plan_sha256"] != sha(fit_path) or artifact["producer_sha256"] != fit_plan["code"]["producer_code"]["sha256"] or
            artifact["human_training_inputs"] != fit_plan["human_training_inputs"] or
            artifact["measurement_sources"] != [c["measurement"] for c in fit_plan["clips"]] or
            artifact["reviewed_source_references"] != [c["reviewed_reliability"] for c in fit_plan["clips"]]):
        raise ValueError("Unbound supervised calibration artifact")
    expected = [{"target": c["target"], "source": c["measurement"]} for c in fit_plan["clips"]]
    if plan["clips"] != expected:
        raise ValueError("Application measurement identities differ from fitted sources")
    parent = read(bound(root, fit_plan["parent_evidence_plan"]))
    local.verify_plan(root, parent)
    if plan["clips"] != parent["clips"]:
        raise ValueError("Application sources differ from GT-free parent")
    measurements = [read(bound(root, c["source"])) for c in plan["clips"]]
    _validate_reference(measurements, artifact)
    if len(measurements) != 5 or artifact["source_frames"] != 592 or artifact["non_seed_frames"] != 587:
        raise ValueError("Incomplete five-clip supervised application cohort")
    return measurements, artifact


def apply(root, plan_path):
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    if not plan_path.is_relative_to(root):
        raise ValueError("Application plan outside project")
    plan, plan_sha = read(plan_path), sha(plan_path)
    output = _output(root, plan)
    measurements, artifact = verify_apply_plan(root, plan)
    sidecars = apply_reference(measurements, artifact)
    verify_apply_plan(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Application plan changed during numeric warning application")
    output.mkdir(parents=True)
    common = {"plan_sha256": plan_sha, "producer_sha256": sha(__file__), "policy": APPLY_POLICY,
        "supervised_calibration_used": True, "application_human_annotation_inputs": [],
        "calibration_artifact": deepcopy(plan["calibration_artifact"]), "pose_inference_calls": 0,
        "tracker_inference_calls": 0, "production_adoption": False, "major_warning_generated": False}
    receipts = []
    for sidecar, setup in zip(sidecars, plan["clips"], strict=True):
        name = setup["target"]["pitch_id"]
        path = output / (name + ".json")
        write(path, common | sidecar | {"status": "sealed_supervised_local_joint_warning_sidecar", "source_reference": setup["source"]})
        receipts.append({"pitch_id": name, "path": path.relative_to(root).as_posix(), "sha256": sha(path)})
    result = common | {"status": "sealed_supervised_local_joint_warning_trial", "human_training_inputs": deepcopy(artifact["human_training_inputs"]),
        "source_frames": 592, "non_seed_frames": 587, "clips": receipts, "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "supervised_local_joint_warning_run.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("fit", "apply"))
    parser.add_argument("plan", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = fit(args.root, args.plan) if args.stage == "fit" else apply(args.root, args.plan)
    print(json.dumps({key: result[key] for key in ("status", "source_frames", "non_seed_frames")}))
