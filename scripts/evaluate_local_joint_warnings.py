"""Evaluate sealed local disagreement warnings against joint-specific review.

Missing model/evidence states are retained in human-scorable denominators.
Local warnings are never promoted to major failures or used to rewrite raw XY.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
import evaluate_joint_disagreement as joint_evaluator
from pitch_analysis.ground_truth import validate_ground_truth

ROLES = joint_evaluator.ROLES
LABELS = ("reliable", "unreliable", "uncertain", "not_observable")
MODEL_STATES = ("observed", "interpolated", "missing")
STATES = ("warning", "candidate_dependent", "within_reference_range", "insufficient_evidence", "seed_excluded")
ASSOCIATIONS = ("unique_geometric_candidate", "ambiguous", "none")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_receipt(data, producer, plan_sha, *, sidecar=False):
    expected = "sealed_local_joint_warning_sidecar" if sidecar else "sealed_local_joint_warning_trial"
    if (data["status"] != expected or data["policy"] != producer["policy"] or data["plan_sha256"] != plan_sha or
            data["producer_sha256"] != producer["code"]["producer_code"]["sha256"] or
            data["human_annotation_inputs"] != [] or data["production_adoption"] is not False or
            data["major_warning_generated"] is not False or
            any(type(data[key]) is not int or data[key] != 0 for key in ("pose_inference_calls", "tracker_inference_calls"))):
        raise ValueError("Changed, contaminated, adopted, or major-promoted local warning receipt")
    if not sidecar and (data["source_frames"] != 592 or data["non_seed_frames"] != 587):
        raise ValueError("Changed local warning cohort denominator")


def verify_frames(data, total):
    if (set(data["important_joints"]) != set(ROLES) or
            [f["frame_index"] for f in data["frames"]] != list(range(total))):
        raise ValueError("Incomplete focus-joint mapping or local warning timeline")
    for frame in data["frames"]:
        index, slots = frame["frame_index"], frame["candidate_slot_indices"]
        if (type(index) is not int or frame["effectiveness_eligible"] is not (index != 0) or
                len(set(slots)) != len(slots) or any(type(i) is not int or not 0 <= i < 6 for i in slots) or
                frame["association_status"] != ("none" if not slots else "unique_geometric_candidate" if len(slots) == 1 else "ambiguous") or
                set(frame["joints"]) != set(ROLES)):
            raise ValueError("Changed seed, association, slots, or six-joint denominator")
        for role, joint in frame["joints"].items():
            state = joint["evidence_state"]
            if (joint["landmark"] != data["important_joints"][role] or joint["raw_model_state"] not in MODEL_STATES or
                    state not in STATES or joint["warning"] is not (state == "warning") or
                    (state == "seed_excluded") != (index == 0)):
                raise ValueError("Changed landmark, original state, evidence flag, or seed")
    expected = {role: {state: sum(f["joints"][role]["evidence_state"] == state for f in data["frames"][1:])
                      for state in STATES[:-1]} for role in ROLES}
    if data["state_counts_non_seed"] != expected:
        raise ValueError("Changed local warning state summary")


def make_rows(data, canonical, pose):
    """Read old jump endpoints and processed states as independent contexts."""
    total, name = data["target"]["total_frames"], data["target"]["pitch_id"]
    if (pose["pitch_id"] != name or pose["total_frames"] != total or pose["frame_indices"] != list(range(total)) or
            pose["important_joints"] != data["important_joints"]):
        raise ValueError("Wrong original pose context or landmark mapping")
    result = {}
    for role in ROLES:
        landmark = data["important_joints"][role]
        source = pose["joints"][landmark]
        states, jumps = source["frame_states"], source["frame_to_frame_jump"]["candidate_frames"]
        if (len(states) != total or any(state not in MODEL_STATES for state in states) or len(set(jumps)) != len(jumps) or
                any(type(i) is not int or not 0 <= i < total for i in jumps) or
                source["frame_to_frame_jump"]["candidate_count"] != len(jumps)):
            raise ValueError("Wrong original model-state or jump timeline")
        labels = joint_evaluator.expand_labels(canonical["labels"][role + "_reliability"], total)
        rows = []
        for frame in data["frames"]:
            index, joint = frame["frame_index"], frame["joints"][role]
            if joint["raw_model_state"] != states[index]:
                raise ValueError("Local sidecar changed original processed state")
            if not frame["effectiveness_eligible"]:
                continue
            rows.append({"frame_index": index, "label": labels[index], "model_state": states[index],
                "state": joint["evidence_state"], "warning": joint["warning"], "jump": index in jumps,
                "association": frame["association_status"], "candidate_count": len(frame["candidate_slot_indices"])})
        result[role] = rows
    return result


def score_rows(rows, screen):
    if screen not in ("jump", "new", "union"):
        raise ValueError("Unknown local warning screen")
    counts = dict.fromkeys(("tp", "fn", "fp", "tn"), 0)
    excluded_warnings = dict.fromkeys(("uncertain", "not_observable"), 0)
    unavailable = dict.fromkeys(LABELS, 0)
    human_counts = dict.fromkeys(LABELS, 0)
    warnings = 0
    for row in rows:
        label = row["label"]
        if label not in LABELS or row["state"] not in STATES[:-1]:
            raise ValueError("Unknown human or local evidence state")
        warning = row["jump"] if screen == "jump" else row["warning"] if screen == "new" else row["jump"] or row["warning"]
        abstain = screen != "jump" and row["state"] == "insufficient_evidence" and not (screen == "union" and row["jump"])
        warnings += warning
        human_counts[label] += 1
        unavailable[label] += abstain
        if label in excluded_warnings:
            excluded_warnings[label] += warning
        else:
            key = ("tp" if warning else "fn") if label == "unreliable" else ("fp" if warning else "tn")
            counts[key] += 1
    positive, negative = human_counts["unreliable"], human_counts["reliable"]
    scorable = positive + negative
    tp, fp = counts["tp"], counts["fp"]
    return {"non_seed_joint_rows": len(rows), "human_label_counts": human_counts,
        "human_positive": positive, "human_negative": negative,
        "human_excluded": human_counts["uncertain"] + human_counts["not_observable"], "scorable_frames": scorable,
        **counts, "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / positive if positive else None, "fpr": fp / negative if negative else None,
        "warning_total": warnings, "warning_on_excluded": excluded_warnings,
        "insufficient_evidence_by_human_label": unavailable if screen != "jump" else None,
        "evidence_coverage_on_scorable": ((scorable - unavailable["reliable"] - unavailable["unreliable"]) / scorable
            if scorable and screen != "jump" else None)}


def summarize_rows(rows):
    def state_counts(subset):
        return {state: sum(row["state"] == state for row in subset) for state in STATES[:-1]}
    return {"non_seed_joint_rows": len(rows), "state_counts": state_counts(rows),
        "old_jump_screen": score_rows(rows, "jump"), "new_local_disagreement_screen": score_rows(rows, "new"),
        "additive_local_screen": score_rows(rows, "union"),
        "query_state_by_association": {a: state_counts([r for r in rows if r["association"] == a]) for a in ASSOCIATIONS},
        "query_state_by_candidate_count": {str(n): state_counts([r for r in rows if r["candidate_count"] == n]) for n in range(7)},
        "model_state_by_human_label_by_evidence": {model: {human: state_counts([
            row for row in rows if row["model_state"] == model and row["label"] == human])
            for human in LABELS} for model in MODEL_STATES}}


def evaluate(root, plan_path, run_path, output):
    import measure_local_joint_warnings as producer_module

    root, plan_path, run_path, output = (Path(p).resolve() for p in (root, plan_path, run_path, output))
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive local evaluation output required")
    plan, run = read(plan_path), read(run_path)
    plan_sha, run_sha = sha(plan_path), sha(run_path)
    if plan["status"] != "frozen_before_local_joint_warning_evaluation":
        raise ValueError("Unfrozen local evaluation plan")
    producer_path = bound(root, plan["producer_plan"])
    producer, producer_sha = read(producer_path), sha(producer_path)
    producer_module.verify_plan(root, producer)
    refs = [plan["producer_plan"], *plan["code"].values(), *producer["code"].values(), *run["clips"]]
    for ref in refs:
        bound(root, ref)
    verify_receipt(run, producer, producer_sha)
    if (producer["policy"] != producer_module.POLICY or tuple(producer_module.ROLES) != ROLES or
            tuple(producer_module.STATES) != STATES or sha(producer_module.__file__) != producer["code"]["producer_code"]["sha256"] or
            sha(__file__) != plan["code"]["evaluator"]["sha256"] or
            sha(joint_evaluator.__file__) != plan["code"]["joint_evaluator"]["sha256"]):
        raise ValueError("Changed running policy, landmark roles, or frozen code")
    names = [c["target"]["pitch_id"] for c in plan["clips"]]
    if (len(names) != 5 or len(set(names)) != 5 or names != [c["target"]["pitch_id"] for c in producer["clips"]] or
            names != [c["pitch_id"] for c in run["clips"]] or sum(c["target"]["total_frames"] for c in plan["clips"]) != 592):
        raise ValueError("Changed five-clip local denominator")
    loaded, measurements = [], []
    for setup, binding, source in zip(plan["clips"], run["clips"], producer["clips"], strict=True):
        references = [*setup["sources"].values(), source["source"]]
        refs.extend(references)
        for ref in references:
            bound(root, ref)
        data, measurement = read(bound(root, binding)), read(bound(root, source["source"]))
        target, total = setup["target"], setup["target"]["total_frames"]
        verify_receipt(data, producer, producer_sha, sidecar=True)
        if (data["target"] != target or source["target"] != target or data["source_reference"] != source["source"] or
                measurement["target"] != target or measurement["source_references"]["capture"] != setup["sources"]["capture"] or
                measurement["source_references"]["pose_reliability"] != setup["sources"]["pose_reliability"]):
            raise ValueError("Changed original pose/capture or local clip binding")
        verify_frames(data, total)
        capture = read(bound(root, setup["sources"]["capture"]))
        if ([f["frame_index"] for f in capture["selection_frames"]] != list(range(total)) or any(
                type(f["native_timestamp_ms"]) not in (int, float) or not math.isfinite(f["native_timestamp_ms"]) or
                f["capture_timestamp_ms"] != old["timestamp_ms"] or abs(f["native_timestamp_ms"] - old["timestamp_ms"]) > 1
                for f, old in zip(data["frames"], capture["selection_frames"], strict=True))):
            raise ValueError("Changed original capture timeline")
        video = bound(root, setup["sources"]["video"])
        capture_video = Path(capture["video"])
        if not capture_video.is_absolute():
            capture_video = root / capture_video
        if (capture_video.resolve() != video or tuple(capture[k] for k in
                ("width", "height", "start_frame", "end_frame", "requested_frames", "processed_frames")) !=
                (target["width"], target["height"], 0, total - 1, total, total)):
            raise ValueError("Canonical video differs from measured capture")
        pose = read(bound(root, setup["sources"]["pose_reliability"]))
        loaded.append((setup, data, pose, video))
        measurements.append(measurement)
    recomputed = producer_module.make_sidecars(measurements)
    if len(recomputed) != len(loaded):
        raise ValueError("Incomplete local warning recomputation")
    for (_, data, _, _), expected in zip(loaded, recomputed, strict=True):
        if any(data[key] != expected[key] for key in ("target", "important_joints", "calibration", "frames", "state_counts_non_seed")):
            raise ValueError("Local warning or calibration differs from GT-free recomputation")
    reports, all_rows = [], {role: [] for role in ROLES}
    for setup, data, pose, video in loaded:
        target, total = setup["target"], setup["target"]["total_frames"]
        canonical = read(bound(root, setup["sources"]["canonical_review"]))
        validate_ground_truth(canonical, source_video_path=video)
        if (canonical["annotation_status"] != "reviewed" or canonical["review_profile"] != "phase2_full_review" or
                tuple(canonical["source_video"][k] for k in ("pitch_id", "total_frames", "sha256")) !=
                (target["pitch_id"], total, setup["sources"]["video"]["sha256"])):
            raise ValueError("Wrong or incomplete canonical joint review")
        rows = make_rows(data, canonical, pose)
        reports.append({"pitch_id": target["pitch_id"], "source_frames": total, "non_seed_frames": total - 1,
            "important_joints": data["important_joints"], "calibration": data["calibration"],
            "focus_joints": {role: summarize_rows(value) for role, value in rows.items()},
            "old_jump_context": {role: pose["joints"][data["important_joints"][role]]["frame_to_frame_jump"] for role in ROLES}})
        for role in ROLES:
            all_rows[role].extend(rows[role])
    for ref in refs:
        bound(root, ref)
    producer_module.verify_plan(root, producer)
    if sha(plan_path) != plan_sha or sha(run_path) != run_sha:
        raise ValueError("Local evidence changed during evaluation")
    result = {"status": "complete_offline_local_joint_warning_evaluation", "plan_sha256": plan_sha, "run_sha256": run_sha,
        "source_frames": 592, "non_seed_frames": 587, "non_seed_joint_rows_before_human_exclusions": 3522,
        "policy": producer["policy"], "clips": reports,
        "aggregate": {"focus_joints": {role: summarize_rows(value) for role, value in all_rows.items()}},
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "major_warning_generated": False, "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "Local raw-overlay reliability targets only. Unknown human labels are excluded per joint; model/evidence missing remains in the primary denominator. Existing processed states and jump endpoints are unchanged and independently scored. Within-range is not reliability. Other-clip sample maxima are developmental extreme-disagreement screens, not generalization, coordinate correction, or major failure detection."}
    output.mkdir()
    write(output / "local_joint_warning_evaluation.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "run", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    report = evaluate(Path(__file__).resolve().parents[1], args.plan, args.run, args.output)
    print(json.dumps({role: value["new_local_disagreement_screen"] for role, value in report["aggregate"]["focus_joints"].items()}))
