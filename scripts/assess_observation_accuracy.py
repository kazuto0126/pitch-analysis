"""Reaggregate saved manual/raw/clean diagnostics with fixed visible denominators.

This is an evaluator, not inference, training, a warning or a new quality gate.
No coordinate, state, threshold or historical artifact is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pitch_analysis.manual_keypoints import JOINT_NAMES, validate_manual_keypoints


STATES = ("observed", "interpolated", "missing")
INVENTORIES = (
    ("analysis_results/phase2_warning_design_20261006_01/evidence_integrity_check.json", "protected_sha256"),
    ("analysis_results/phase2_feature_support_20261006_01/evaluation/evidence_integrity_check.json", "source_hashes"),
    ("analysis_results/phase2_feature_membership_pilot_20261006_02/evaluation_01/human_membership_comparison.json", "source_hashes"),
    ("analysis_results/phase2_subject_mask_pilot_20261006_03/evaluation_01/human_mask_comparison.json", "source_hashes"),
)


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8") as target:
        json.dump(value, target, indent=2, allow_nan=False)
        target.write("\n")


def summary(values):
    values = list(values)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("Summary requires finite measurements; missing is never zero")
    ordered = sorted(values)
    position = (len(ordered)-1)*.95
    low, high = math.floor(position), math.ceil(position)
    return {"count": len(values), "mean_px": statistics.fmean(values) if values else None,
            "median_px": statistics.median(values) if values else None,
            "p95_px": ordered[low]+(ordered[high]-ordered[low])*(position-low) if values else None,
            "max_px": max(values) if values else None}


def pixel_xy(point, width, height):
    """Saved raw/clean X is image-width-normalized, never internal x_height."""
    if point.get("x") is None or point.get("y") is None:
        return None
    if any(type(point[k]) not in (int, float) or not math.isfinite(point[k]) for k in ("x", "y")):
        raise ValueError("Invalid saved XY")
    # Do not clamp projected coordinates or introduce a new spatial gate.
    return [point["x"]*width, point["y"]*height]


def state_of(point, raw_detected):
    if any(type(point[k]) is not bool for k in ("usable", "interpolated", "quality_valid")):
        raise ValueError("Saved state flags must be boolean")
    has_xy = point.get("x") is not None and point.get("y") is not None
    if not point["usable"] or not has_xy:
        return "missing"
    if point["interpolated"]:
        return "interpolated"
    if point["quality_valid"] and raw_detected:
        return "observed"
    raise ValueError("Unexpected usable coordinate without direct or interpolation provenance")


def aggregate(rows):
    rows = list(rows)
    visible = [r for r in rows if r["manual_state"] == "visible"]
    excluded = Counter(r["manual_state"] for r in rows if r["manual_state"] != "visible")
    if any(r["processed_state"] not in STATES for r in rows):
        raise ValueError("Unknown saved availability state")
    for row in rows:
        if row["manual_state"] != "visible":
            if row["raw_error_px"] is not None or row["processed_error_px"] is not None:
                raise ValueError("Nonvisible human coordinates cannot supply accuracy truth")
        elif row["processed_state"] == "missing":
            if row["processed_error_px"] is not None:
                raise ValueError("Missing prediction cannot have an error or zero placeholder")
        elif row["processed_error_px"] is None:
            raise ValueError("Available visible prediction must have a measured error")
    by_state = {}
    for state in STATES:
        selected = [r for r in visible if r["processed_state"] == state]
        paired = [r for r in selected if r["raw_error_px"] is not None and r["processed_error_px"] is not None]
        deltas = [r["processed_error_px"]-r["raw_error_px"] for r in paired]
        by_state[state] = {"visible_reference_count": len(selected),
            "raw_error": summary(r["raw_error_px"] for r in selected if r["raw_error_px"] is not None),
            "clean_error": summary(r["processed_error_px"] for r in selected if r["processed_error_px"] is not None),
            "same_point_raw_error": summary(r["raw_error_px"] for r in paired),
            "same_point_clean_error": summary(r["processed_error_px"] for r in paired),
            "same_point_delta_clean_minus_raw": summary(deltas),
            "paired_error_reduced": sum(v < 0 for v in deltas), "paired_error_increased": sum(v > 0 for v in deltas),
            "paired_error_unchanged": sum(v == 0 for v in deltas)}
    paired = [r for r in visible if r["raw_error_px"] is not None and r["processed_error_px"] is not None]
    usable = sum(r["processed_state"] != "missing" for r in visible)
    return {"all_reference_rows": len(rows), "visible_reference_denominator": len(visible),
        "excluded_human_states": dict(excluded), "raw_on_full_visible_reference": summary(
            r["raw_error_px"] for r in visible if r["raw_error_px"] is not None),
        "raw_missing_on_visible_reference": sum(r["raw_error_px"] is None for r in visible),
        "observed_retained": by_state["observed"]["visible_reference_count"],
        "interpolated_retained": by_state["interpolated"]["visible_reference_count"],
        "missing_after_existing_processing": by_state["missing"]["visible_reference_count"],
        "usable_reference_count": usable, "paired_usable_reference_count": len(paired),
        "usable_reference_fraction": usable/len(visible) if visible else None,
        "by_saved_state": by_state, "same_usable_points_raw": summary(r["raw_error_px"] for r in paired),
        "same_usable_points_clean": summary(r["processed_error_px"] for r in paired),
        "accuracy_pass_rate": None, "pixel_acceptance_threshold": None}


def verify_rows(manual, raw, processed, meta, pose, diagnostics):
    validate_manual_keypoints(manual)
    total, width, height = manual["source_video"]["total_frames"], manual["image_size"]["width"], manual["image_size"]["height"]
    if (manual["annotation_status"] != "reviewed" or meta["sha256"] != manual["source_video"]["sha256"]
        or meta["frame_count"] != total or (meta["width"], meta["height"]) != (width, height)
        or raw["pitch_id"] != manual["source_video"]["pitch_id"] or pose["pitch_id"] != raw["pitch_id"]):
        raise ValueError("Manual/raw/metadata/reliability binding mismatch")
    if not raw["coordinate_system"].startswith("normalized_image_xy;"):
        raise ValueError("Unknown saved coordinate normalization")
    for frames in (manual["frames"], raw["frames"], processed):
        if [f["frame_index"] for f in frames] != list(range(total)):
            raise ValueError("Frame denominator or order mismatch")
        if any(not math.isclose(f["timestamp_ms"], t, rel_tol=0, abs_tol=1e-7)
               for f, t in zip(frames, meta["timestamps_ms"], strict=True)):
            raise ValueError("Original frame timestamp mismatch")
    lookup = {}
    for row in diagnostics:
        key = row["frame_index"], row["joint"]
        if key in lookup:
            raise ValueError("Duplicate diagnostic row")
        lookup[key] = row
    expected = {(i, name) for i in range(total) for name in JOINT_NAMES}
    if set(lookup) != expected:
        raise ValueError("Diagnostic joint/frame denominator mismatch")
    checked = []
    for index in range(total):
        raw_points = {p["name"]: p for p in raw["frames"][index]["landmarks"]}
        if len(raw_points) != len(raw["frames"][index]["landmarks"]):
            raise ValueError("Duplicate raw landmark")
        detected = raw["frames"][index]["detected"]
        if type(detected) is not bool:
            raise ValueError("Invalid raw detected state")
        for human in manual["frames"][index]["joints"]:
            name = human["name"]
            row = lookup[index, name]
            point = processed[index]["landmarks"][name]
            state = state_of(point, detected)
            if state != pose["joints"][name]["frame_states"][index] or state != row["processed_state"]:
                raise ValueError("Saved availability state mismatch")
            if (row["manual_state"], row["manual_x_px"], row["manual_y_px"]) != (human["status"], human["x_px"], human["y_px"]):
                raise ValueError("Diagnostic differs from reviewed manual source")
            raw_xy = pixel_xy(raw_points[name], width, height) if detected and name in raw_points else None
            clean_xy = pixel_xy(point, width, height) if state != "missing" else None
            for prefix, xy in (("raw", raw_xy), ("processed", clean_xy)):
                stored = [row[f"{prefix}_x_px"], row[f"{prefix}_y_px"]]
                if xy != stored and not (xy is None and stored == [None, None]):
                    raise ValueError("Saved diagnostic coordinate mismatch")
                error = math.hypot(xy[0]-human["x_px"], xy[1]-human["y_px"]) if xy is not None and human["status"] == "visible" else None
                if error != row[f"{prefix}_error_px"]:
                    raise ValueError("Saved diagnostic distance does not reproduce")
            if state == "observed" and raw_xy != clean_xy:
                raise ValueError("Existing directly observed clean point differs from raw")
            checked.append(row)
    return checked


def assess(root, plan_path, output):
    root, output = root.resolve(), output.resolve()
    plan = read(plan_path)
    if plan["status"] != "frozen_before_assessment" or plan["runner_sha256"] != digest(__file__):
        raise ValueError("Expected unchanged frozen evaluator")
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Assessment must write a new workspace output")
    def integrity():
        inventories = [("bound_inputs", plan["source_hashes"])]
        inventories.extend((path, read(root/path)[key]) for path, key in INVENTORIES)
        for label, sources in inventories:
            for name, expected in sources.items():
                if digest(root/name) != expected:
                    raise ValueError(f"Changed preserved input in {label}: {name}")
        return [{"inventory": label, "files": len(sources), "unchanged": True} for label, sources in inventories]
    integrity()
    roles = {name: root/path for name, path in plan["source_roles"].items()}
    processed = [json.loads(line) for line in roles["processed"].read_text(encoding="utf-8-sig").splitlines()]
    rows = verify_rows(*(read(roles[k]) for k in ("manual", "raw")), processed,
                       *(read(roles[k]) for k in ("metadata", "pose")), read(roles["diagnostics"])["rows"])
    gt = read(roles["qualitative_gt"])
    major = {i for interval in gt["labels"]["major_pose_failure_intervals"] if interval["status"] == "confirmed"
             for i in range(interval["start_frame"], interval["end_frame"]+1)}
    if gt["source_video"] != read(roles["manual"])["source_video"]:
        raise ValueError("Qualitative/manual source binding mismatch")
    result = {"status": "assessment_complete", "scope": "reaggregation of existing 115-frame saved diagnostics; not new pose or warning",
        "pitch_id": plan["pitch_id"], "total_frames": plan["total_frames"], "plan_sha256": digest(plan_path),
        "runner_sha256": digest(__file__), "source_hashes": plan["source_hashes"],
        "overall": aggregate(rows), "joints": {name: aggregate(r for r in rows if r["joint"] == name) for name in JOINT_NAMES},
        "contexts": {"confirmed_major_failure": aggregate([r for r in rows if r["frame_index"] in major]),
                     "other_frames_not_necessarily_error_free": aggregate([r for r in rows if r["frame_index"] not in major])},
        "pose_inference_rerun": False, "new_warning_or_threshold": False, "ground_truth_or_prediction_modified": False,
        "phase2_acceptance": "IN PROGRESS", "limits": ["Observed means existing model gate, not image visibility/correctness",
            "Missing clean predictions remain in visible reference denominator, error stays null",
            "Paired raw/clean comparison uses identical usable points; dropping points is not localization improvement",
            "Interpolation error is not proof of true hidden-joint recovery",
            "Only pitch003 has reviewed manual XY; other clips have qualitative GT, not same coordinate accuracy evidence"]}
    checks = integrity()
    output.mkdir(parents=True)
    write(output/"observation_accuracy.json", result)
    write(output/"evidence_integrity_check.json", {"status": "passed", "inventories": checks,
        "all_1380_saved_rows_and_coordinates_checked": True, "old_measurements_reused": True,
        "new_inference": False, "new_warning_or_threshold": False})
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = assess(args.root, args.plan, args.output)
    print(json.dumps(result["overall"]))
