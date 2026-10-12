"""Evaluate sealed joint disagreement; no model, subject choice, or cutoff.

Human reliability describes the original raw overlay. Distances describe model
disagreement and cannot establish visibility, identity, or coordinate accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path

from check_movenet_compatibility import bound, sha, write
from disagreement_statistics import LABELS, spearman, summarize_labeled
from pitch_analysis.ground_truth import validate_ground_truth
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints

ROLES = ("throwing_shoulder", "throwing_elbow", "throwing_wrist", "lead_hip", "lead_knee", "lead_ankle")
ASSOCIATIONS = ("unique_geometric_candidate", "ambiguous", "none")
MODEL_STATES = ("observed", "interpolated", "missing")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def verify_receipt_boundaries(producer, run, data=None):
    """Refuse changed policies, inference budgets, GT inputs, or adoption."""
    documents = [(producer, "budget"), (run, "calls")]
    if data is not None:
        documents.append((data, "calls"))
    for document, suffix in documents:
        if (document["human_annotation_inputs"] != [] or document["production_adoption"] is not False or
                any(type(document[f"{kind}_inference_{suffix}"]) is not int or
                    document[f"{kind}_inference_{suffix}"] != 0 for kind in ("pose", "tracker"))):
            raise ValueError("Contaminated or nonzero-inference disagreement receipt")
        if suffix == "calls" and (document["policy"] != producer["policy"] or
                type(document["new_binary_warnings"]) is not int or document["new_binary_warnings"] != 0):
            raise ValueError("Changed disagreement policy or new binary warning receipt")


def expand_labels(intervals, total, *, major=False):
    """Expand exact inclusive intervals; joint review must cover every frame."""
    result = ["reliable" if major else None] * total
    previous = -1
    for interval in intervals:
        start, end = interval["start_frame"], interval["end_frame"]
        status = interval.get("status", "confirmed") if major else interval["status"]
        allowed = ("confirmed", "uncertain", "not_observable") if major else LABELS
        if (type(start) is not int or type(end) is not int or
                not 0 <= start <= end < total or start <= previous or
                (not major and start != previous + 1) or status not in allowed):
            raise ValueError("Invalid, overlapping, incomplete, or unknown human intervals")
        label = "unreliable" if status == "confirmed" else status
        result[start:end + 1] = [label] * (end - start + 1)
        previous = end
    if not major and (previous != total - 1 or any(value is None for value in result)):
        raise ValueError("Human joint review does not cover the complete timeline")
    return result


def _range(value):
    low, high = value["min"], value["max"]
    if low is None and high is None:
        return
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or
           not math.isfinite(v) or v < 0 for v in (low, high)) or low > high:
        raise ValueError("Invalid numerical disagreement range")


def verify_frames(data, total):
    frames = data["frames"]
    if ([frame["frame_index"] for frame in frames] != list(range(total)) or
            any(type(frame["frame_index"]) is not int or
                frame["effectiveness_eligible"] is not (frame["frame_index"] != 0) for frame in frames)):
        raise ValueError("Changed frame denominator or seed eligibility")
    if set(data["important_joints"]) != set(ROLES) or any(
            name not in JOINT_NAMES for name in data["important_joints"].values()):
        raise ValueError("Invalid focus-joint correspondence")
    for frame in frames:
        slots = frame["candidate_slot_indices"]
        if (len(set(slots)) != len(slots) or any(type(i) is not int or not 0 <= i < 6 for i in slots)
                or frame["association_status"] != ("none" if not slots else
                    "unique_geometric_candidate" if len(slots) == 1 else "ambiguous")
                or set(frame["joints"]) != set(JOINT_NAMES)):
            raise ValueError("Invalid association, slots, or twelve-joint denominator")
        for joint in frame["joints"].values():
            if joint["baseline_model_state"] not in MODEL_STATES:
                raise ValueError("Invalid processed baseline state")
            if [entry["slot_index"] for entry in joint["candidate_distances"]] != slots:
                raise ValueError("Missing or reordered candidate joint distances")
            _range(joint["distance_range_px"])
            _range(joint["distance_range_diagonal"])
        _range(frame["torso_rms"]["range_px"])
        _range(frame["torso_rms"]["range_diagonal"])


def joint_rows(data, canonical):
    total = data["target"]["total_frames"]
    output = {}
    for role in ROLES:
        labels = expand_labels(canonical["labels"][role + "_reliability"], total)
        name = data["important_joints"][role]
        output[role] = [{"label": labels[f["frame_index"]],
            **f["joints"][name]["distance_range_diagonal"],
            "association": f["association_status"], "candidate_count": len(f["candidate_slot_indices"]),
            "model_state": f["joints"][name]["baseline_model_state"]}
            for f in data["frames"][1:]]
    return output


def major_rows(data, canonical):
    labels = expand_labels(canonical["labels"]["major_pose_failure_intervals"],
                           data["target"]["total_frames"], major=True)
    return [{"label": labels[f["frame_index"]], **f["torso_rms"]["range_diagonal"],
        "association": f["association_status"], "candidate_count": len(f["candidate_slot_indices"])}
        for f in data["frames"][1:]]


def summarize_rows(rows):
    def measures(subset):
        return {key: summarize_labeled({"label": row["label"], "value": row[key]} for row in subset)
                for key in ("min", "max")}
    result = {**measures(rows),
        "by_association": {status: measures([r for r in rows if r["association"] == status])
                           for status in ASSOCIATIONS},
        "by_candidate_count": {str(count): measures([r for r in rows if r["candidate_count"] == count])
                               for count in range(7)}}
    if any("model_state" in row for row in rows):
        result["model_state_by_human_label"] = {label: {
            state: sum(r["label"] == label and r["model_state"] == state for r in rows)
            for state in MODEL_STATES} for label in LABELS}
    return result


def manual_rows(data, manual):
    """Visible manual XY only; no best-slot selection or hidden-joint scoring."""
    if [f["frame_index"] for f in manual["frames"]] != list(range(data["target"]["total_frames"])):
        raise ValueError("Manual XY timeline differs")
    result = []
    for frame, human in zip(data["frames"], manual["frames"], strict=True):
        if not math.isfinite(human["timestamp_ms"]) or abs(human["timestamp_ms"] - frame["native_timestamp_ms"]) > 1:
            raise ValueError("Manual XY timestamp differs from sealed frame")
        if not frame["effectiveness_eligible"]:
            continue
        for reference in human["joints"]:
            name, status = reference["name"], reference["status"]
            joint = frame["joints"][name]
            raw = joint["raw"]
            error = (math.hypot(raw["xy_px"][0] - reference["x_px"], raw["xy_px"][1] - reference["y_px"])
                     if status == "visible" and raw["finite"] else None)
            result.append({"joint": name, "human_status": status, "raw_error_px": error,
                **joint["distance_range_px"], "association": frame["association_status"]})
    return result


def summarize_manual(rows):
    visible = [row for row in rows if row["human_status"] == "visible"]
    result = {"human_status_counts": dict(Counter(row["human_status"] for row in rows)),
        "visible_denominator": len(visible), "raw_available": sum(r["raw_error_px"] is not None for r in visible),
        "raw_unavailable": sum(r["raw_error_px"] is None for r in visible)}
    for key in ("min", "max"):
        paired = [r for r in visible if r["raw_error_px"] is not None and r[key] is not None]
        result[key] = {"paired_count": len(paired), "unpaired_visible_count": len(visible) - len(paired),
            "measurement_unavailable": sum(r[key] is None for r in visible),
            "conditional_spearman": spearman((r[key], r["raw_error_px"]) for r in paired)}
    return result


def evaluate(root, plan_path, run_path, output):
    root, plan_path, run_path, output = (Path(p).resolve() for p in (root, plan_path, run_path, output))
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Exclusive evaluation output required")
    plan, run = read(plan_path), read(run_path)
    plan_sha, run_sha = sha(plan_path), sha(run_path)
    producer_path = bound(root, plan["producer_plan"])
    producer, producer_sha = read(producer_path), sha(producer_path)
    references = [plan["producer_plan"], *plan["code"].values(), *producer["code"].values(), *run["clips"]]
    if (plan["status"] != "frozen_before_disagreement_evaluation" or
            producer["status"] != "frozen_before_disagreement_measurement" or
            run["status"] != "sealed_joint_disagreement_measurements" or run["plan_sha256"] != producer_sha or
            run["producer_sha256"] != producer["code"]["producer_code"]["sha256"] or
            run["human_annotation_inputs"] != [] or run["source_frames"] != 592 or run["non_seed_frames"] != 587 or
            run["pose_inference_calls"] != 0 or run["tracker_inference_calls"] != 0 or run["production_adoption"] is not False):
        raise ValueError("Unfrozen, changed, or contaminated producer receipt")
    verify_receipt_boundaries(producer, run)
    if plan["code"]["evaluator"]["sha256"] != sha(__file__):
        raise ValueError("Running evaluator differs from frozen code")
    from disagreement_statistics import __file__ as statistics_path
    if plan["code"]["statistics"]["sha256"] != sha(statistics_path):
        raise ValueError("Running statistics differs from frozen code")
    names = [clip["target"]["pitch_id"] for clip in plan["clips"]]
    if (len(names) != 5 or len(set(names)) != 5 or
            [c["pitch_id"] for c in run["clips"]] != names or
            [c["target"]["pitch_id"] for c in producer["clips"]] != names or
            sum(c["target"]["total_frames"] for c in plan["clips"]) != 592):
        raise ValueError("Incomplete or duplicate five-clip denominator")
    reports, all_joints, all_major, all_manual = [], {role: [] for role in ROLES}, [], []
    for setup, measured, source in zip(plan["clips"], run["clips"], producer["clips"], strict=True):
        references.extend([*setup["sources"].values(), *source["sources"].values()])
        for ref in references:
            bound(root, ref)
        target = setup["target"]
        data = read(bound(root, measured))
        if (data["status"] != "sealed_joint_disagreement_only" or data["target"] != target or source["target"] != target or
                data["source_references"] != source["sources"] or data["plan_sha256"] != producer_sha or
                data["producer_sha256"] != run["producer_sha256"] or data["human_annotation_inputs"] != []):
            raise ValueError("Wrong clip or source binding")
        verify_receipt_boundaries(producer, run, data)
        verify_frames(data, target["total_frames"])
        capture_context = read(bound(root, source["sources"]["capture"]))
        capture = capture_context["selection_frames"]
        if [f["frame_index"] for f in capture] != list(range(target["total_frames"])) or any(
                not math.isfinite(f["native_timestamp_ms"]) or not math.isfinite(old["timestamp_ms"]) or
                abs(f["native_timestamp_ms"] - old["timestamp_ms"]) > 1 or f["capture_timestamp_ms"] != old["timestamp_ms"]
                for f, old in zip(data["frames"], capture, strict=True)):
            raise ValueError("Sealed and original capture timelines differ")
        video = bound(root, setup["sources"]["video"])
        capture_video = Path(capture_context["video"])
        if not capture_video.is_absolute():
            capture_video = root / capture_video
        if (capture_video.resolve() != video or
                tuple(capture_context[key] for key in ("width", "height", "start_frame", "end_frame", "requested_frames", "processed_frames")) !=
                (target["width"], target["height"], 0, target["total_frames"] - 1, target["total_frames"], target["total_frames"])):
            raise ValueError("Human source video differs from measured capture")
        pose = read(bound(root, source["sources"]["pose_reliability"]))
        if pose["important_joints"] != data["important_joints"]:
            raise ValueError("Focus-joint mapping differs from original pose reliability")
        canonical = read(bound(root, setup["sources"]["canonical_review"]))
        validate_ground_truth(canonical, source_video_path=video)
        identity = (target["pitch_id"], target["total_frames"], setup["sources"]["video"]["sha256"])
        if (canonical["annotation_status"] != "reviewed" or canonical["review_profile"] != "phase2_full_review" or
                tuple(canonical["source_video"][key] for key in ("pitch_id", "total_frames", "sha256")) != identity):
            raise ValueError("Wrong or incomplete canonical review")
        joints, major = joint_rows(data, canonical), major_rows(data, canonical)
        report = {"pitch_id": target["pitch_id"], "source_frames": target["total_frames"],
            "non_seed_frames": target["total_frames"] - 1,
            "focus_joints": {role: summarize_rows(rows) for role, rows in joints.items()},
            "major_torso": summarize_rows(major), "manual_xy": None}
        if "manual_xy" in setup["sources"]:
            manual = read(bound(root, setup["sources"]["manual_xy"]))
            validate_manual_keypoints(manual, source_video_path=video)
            if (manual["annotation_status"] != "reviewed" or
                    tuple(manual["source_video"][key] for key in ("pitch_id", "total_frames", "sha256")) != identity or
                    manual["image_size"] != {"width": target["width"], "height": target["height"]}):
                raise ValueError("Wrong or incomplete manual XY reference")
            xy = manual_rows(data, manual)
            report["manual_xy"] = {"aggregate": summarize_manual(xy),
                "joints": {name: summarize_manual([r for r in xy if r["joint"] == name]) for name in JOINT_NAMES}}
            all_manual.extend(xy)
        for role in ROLES:
            all_joints[role].extend(joints[role])
        all_major.extend(major)
        reports.append(report)
    for ref in references:
        bound(root, ref)
    if sha(plan_path) != plan_sha or sha(run_path) != run_sha:
        raise ValueError("Evidence changed during evaluation")
    result = {"status": "complete_offline_joint_disagreement_evaluation", "plan_sha256": plan_sha,
        "run_sha256": run_sha, "source_frames": 592, "non_seed_frames": 587, "clips": reports,
        "aggregate": {"focus_joints": {role: summarize_rows(rows) for role, rows in all_joints.items()},
            "major_torso": summarize_rows(all_major), "manual_xy": summarize_manual(all_manual)},
        "pose_inference_calls": 0, "tracker_inference_calls": 0, "production_adoption": False,
        "warning_threshold": None, "new_binary_predictions": False, "phase2_automatic_reliability": "NOT PASSED",
        "interpretation": "Conditional development-data associations only. Larger distance ranks toward unreliable; all human-scorable missing values remain in availability denominators. Min is an ambiguity lower bound, max an upper bound; neither chooses identity or proves correctness. No held-out generalization claim."}
    output.mkdir()
    write(output / "joint_disagreement_evaluation.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "run", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = evaluate(Path(__file__).resolve().parents[1], args.plan, args.run, args.output)
    print(json.dumps(result["aggregate"]["major_torso"]["min"]))
