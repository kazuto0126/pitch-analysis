"""Evaluate source-bound human-calibrated local warnings after application seals."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
import evaluate_local_joint_warnings as local
from pitch_analysis.ground_truth import validate_ground_truth


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_receipt(data, apply_plan, plan_sha, artifact_ref, expected_training, *, sidecar=False):
    expected = "sealed_supervised_local_joint_warning_sidecar" if sidecar else "sealed_supervised_local_joint_warning_trial"
    if (data["status"] != expected or data["plan_sha256"] != plan_sha or
            data["producer_sha256"] != apply_plan["code"]["producer_code"]["sha256"] or
            data["policy"] != apply_plan["policy"] or data["calibration_artifact"] != artifact_ref or
            data["supervised_calibration_used"] is not True or data["application_human_annotation_inputs"] != [] or
            data["human_training_inputs"] != expected_training or not expected_training or
            data["production_adoption"] is not False or data["major_warning_generated"] is not False or
            any(type(data[k]) is not int or data[k] != 0 for k in ("pose_inference_calls", "tracker_inference_calls"))):
        raise ValueError("Unbound, mislabeled, GT-reading, or adopted supervised application receipt")
    if not sidecar and (data["source_frames"] != 592 or data["non_seed_frames"] != 587):
        raise ValueError("Changed supervised cohort denominator")


def compare_screens(old, new):
    """Compare the same target without changing its exclusions or missed rows."""
    for key in ("non_seed_joint_rows", "human_label_counts", "human_positive", "human_negative", "human_excluded", "scorable_frames"):
        if old[key] != new[key]:
            raise ValueError("Old and supervised local targets differ")
    return {"previous_gt_blind_screen": old, "supervised_screen": new,
        "change": {key: new[key] - old[key] for key in ("tp", "fn", "fp", "tn", "warning_total")},
        "interpretation": "Developmental local target only; no major promotion, coordinate correction or pass criterion."}


def evaluate(root, plan_path, run_path, output):
    import calibrate_joint_reliability as model

    root, plan_path, run_path, output = (Path(p).resolve() for p in (root, plan_path, run_path, output))
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive new supervised evaluation output required")
    plan, run = read(plan_path), read(run_path)
    plan_sha, run_sha = sha(plan_path), sha(run_path)
    if plan["status"] != "frozen_before_supervised_joint_warning_evaluation":
        raise ValueError("Unfrozen supervised evaluation plan")
    apply_path = bound(root, plan["application_plan"])
    application, apply_sha = read(apply_path), sha(apply_path)
    model.verify_apply_plan(root, application)
    refs = [plan["application_plan"], *plan["code"].values(), *application["code"].values(), *run["clips"]]
    for entry in refs: bound(root, entry)
    if (sha(__file__) != plan["code"]["evaluator"]["sha256"] or
            sha(local.__file__) != plan["code"]["local_evaluator"]["sha256"] or
            sha(model.__file__) != application["code"]["producer_code"]["sha256"] or
            application["policy"] != model.APPLY_POLICY):
        raise ValueError("Running supervised code or policy differs from frozen bytes")
    artifact_ref = application["calibration_artifact"]
    artifact = read(bound(root, artifact_ref))
    verify_receipt(run, application, apply_sha, artifact_ref, artifact["human_training_inputs"])
    names = [c["target"]["pitch_id"] for c in plan["clips"]]
    if (len(names) != 5 or len(set(names)) != 5 or names != [c["target"]["pitch_id"] for c in application["clips"]] or
            names != [c["pitch_id"] for c in run["clips"]] or names != [f["query_pitch_id"] for f in artifact["folds"]]):
        raise ValueError("Changed five-clip supervised source order")
    loaded, measurements = [], []
    for setup, result, source, fold in zip(plan["clips"], run["clips"], application["clips"], artifact["folds"], strict=True):
        refs.extend([*setup["sources"].values(), source["source"]])
        for entry in [*setup["sources"].values(), source["source"]]: bound(root, entry)
        target, total = setup["target"], setup["target"]["total_frames"]
        data, measurement = read(bound(root, result)), read(bound(root, source["source"]))
        verify_receipt(data, application, apply_sha, artifact_ref, fold["human_training_inputs"], sidecar=True)
        if (data["target"] != target or source["target"] != target or data["source_reference"] != source["source"] or
                measurement["target"] != target or measurement["source_references"]["capture"] != setup["sources"]["capture"] or
                measurement["source_references"]["pose_reliability"] != setup["sources"]["pose_reliability"]):
            raise ValueError("Wrong supervised clip or original pose source")
        local.verify_frames(data, total)
        capture = read(bound(root, setup["sources"]["capture"]))
        if ([f["frame_index"] for f in capture["selection_frames"]] != list(range(total)) or any(
                f["capture_timestamp_ms"] != saved["timestamp_ms"] or abs(f["native_timestamp_ms"] - saved["timestamp_ms"]) > 1
                for f, saved in zip(data["frames"], capture["selection_frames"], strict=True))):
            raise ValueError("Changed supervised capture timeline")
        video = bound(root, setup["sources"]["video"])
        capture_video = Path(capture["video"])
        if not capture_video.is_absolute(): capture_video = root / capture_video
        if (capture_video.resolve() != video or tuple(capture[k] for k in
                ("width", "height", "start_frame", "end_frame", "requested_frames", "processed_frames")) !=
                (target["width"], target["height"], 0, total - 1, total, total)):
            raise ValueError("Query review video differs from calibrated measurement")
        loaded.append((setup, data, read(bound(root, setup["sources"]["pose_reliability"])), video))
        measurements.append(measurement)
    expected = model.apply_reference(measurements, artifact)
    for (_, data, _, _), sidecar in zip(loaded, expected, strict=True):
        if any(data[k] != sidecar[k] for k in ("target", "important_joints", "human_training_inputs", "calibration", "frames", "state_counts_non_seed")):
            raise ValueError("Application does not reproduce from sealed numerical artifact")
    old_path = bound(root, plan["gt_blind_evaluation"])
    refs.append(plan["gt_blind_evaluation"])
    old = read(old_path)
    if old["source_frames"] != 592 or old["non_seed_joint_rows_before_human_exclusions"] != 3522:
        raise ValueError("Wrong prior local evaluation")
    reports, pooled = [], {role: [] for role in local.ROLES}
    for setup, data, pose, video in loaded:
        target = setup["target"]
        canonical = read(bound(root, setup["sources"]["canonical_review"]))
        validate_ground_truth(canonical, source_video_path=video)
        if (canonical["annotation_status"] != "reviewed" or canonical["review_profile"] != "phase2_full_review" or
                tuple(canonical["source_video"][k] for k in ("pitch_id", "total_frames", "sha256")) !=
                (target["pitch_id"], target["total_frames"], setup["sources"]["video"]["sha256"])):
            raise ValueError("Incomplete or wrong query canonical review")
        rows = local.make_rows(data, canonical, pose)
        role_reports = {role: local.summarize_rows(values) for role, values in rows.items()}
        previous = next(c for c in old["clips"] if c["pitch_id"] == target["pitch_id"])
        reports.append({"pitch_id": target["pitch_id"], "source_frames": target["total_frames"],
            "calibration": data["calibration"], "human_training_inputs": data["human_training_inputs"], "focus_joints": role_reports,
            "comparison_to_gt_blind": {r: compare_screens(previous["focus_joints"][r]["new_local_disagreement_screen"],
                role_reports[r]["new_local_disagreement_screen"]) for r in local.ROLES}})
        for role, values in rows.items(): pooled[role].extend(values)
    aggregate = {role: local.summarize_rows(values) for role, values in pooled.items()}
    if sum(len(values) for values in pooled.values()) != 3522:
        raise ValueError("Changed complete supervised local denominator")
    for entry in refs: bound(root, entry)
    model.verify_apply_plan(root, application)
    if sha(plan_path) != plan_sha or sha(run_path) != run_sha:
        raise ValueError("Supervised application/evaluation source changed")
    result = {"status": "complete_supervised_local_joint_warning_evaluation", "plan_sha256": plan_sha, "run_sha256": run_sha,
        "source_frames": 592, "non_seed_frames": 587, "non_seed_joint_rows_before_human_exclusions": 3522,
        "supervised_calibration_used": True, "human_training_inputs": artifact["human_training_inputs"],
        "calibration_artifact": artifact_ref, "clips": reports, "aggregate": {"focus_joints": aggregate},
        "comparison_to_gt_blind": {r: compare_screens(old["aggregate"]["focus_joints"][r]["new_local_disagreement_screen"],
            aggregate[r]["new_local_disagreement_screen"]) for r in local.ROLES},
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "major_warning_generated": False, "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "Human-calibrated developmental leave-one-clip-out screening, not pose-model training or independent unseen validation. Query GT was not used in its own bound. Original raw-overlay targets, missing denominators, exclusions and reference-scope differences remain unchanged."}
    output.mkdir()
    write(output / "supervised_joint_warning_evaluation.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "run", "output"): parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = evaluate(Path(__file__).resolve().parents[1], args.plan, args.run, args.output)
    print(json.dumps({r: d["supervised_screen"] for r, d in report["comparison_to_gt_blind"].items()}))
