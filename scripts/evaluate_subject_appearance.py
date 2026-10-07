"""Reproduce appearance receipts and add human geometry only after sealing."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from statistics import median

import cv2
import numpy as np

import measure_subject_appearance as measure


INVENTORIES = (
    ("analysis_results/phase2_warning_design_20261006_01/evidence_integrity_check.json", "protected_sha256"),
    ("analysis_results/phase2_feature_support_20261006_01/evaluation/evidence_integrity_check.json", "source_hashes"),
    ("analysis_results/phase2_feature_membership_pilot_20261006_02/evaluation_01/human_membership_comparison.json", "source_hashes"),
    ("analysis_results/phase2_subject_mask_pilot_20261006_03/evaluation_01/human_mask_comparison.json", "source_hashes"),
)


def describe(values):
    values = list(values)
    return {"count": len(values), "min": min(values) if values else None,
            "median": median(values) if values else None, "max": max(values) if values else None}


def manual_proxy(frame):
    by_name = {item["name"]: item for item in frame["joints"]}
    if not all(by_name[n]["status"] == "visible" for n in measure.TORSO):
        return None
    points = [[by_name[n]["x_px"], by_name[n]["y_px"]] for n in measure.TORSO]
    if not np.isfinite(points).all():
        raise ValueError("Visible manual reference has invalid coordinates")
    hull = cv2.convexHull(np.asarray(points, dtype=np.float32))
    return hull if cv2.contourArea(hull) > 0 else None


def proxy_context(candidate, hull):
    if hull is None:
        return {"center_inside_manual_torso_proxy": None, "all_corners_inside_manual_torso_proxy": None}
    x, y = candidate["center_xy_px"]
    left, top, width, height = candidate["rectangle_xywh"]
    inside = lambda a, b: cv2.pointPolygonTest(hull, (float(a), float(b)), False) >= 0
    return {"center_inside_manual_torso_proxy": inside(x, y),
            "all_corners_inside_manual_torso_proxy": all(inside(a, b) for a, b in (
                (left, top), (left+width-1, top), (left, top+height-1), (left+width-1, top+height-1)))}


def verify_candidate_receipts(stored, reproduced):
    # Stored raw floats, tie counts, validity counts and hash must all reproduce;
    # no tolerant position rejoin or GT-dependent patch choice is allowed.
    if stored != reproduced:
        raise ValueError("Appearance candidate/score-map receipts do not reproduce")


def check_sources(root, plan, result, measurement_file):
    checks = []
    for label, sources in (("producer", plan["measurement_source_hashes"]), ("evaluator_only", plan["evaluator_only_source_hashes"])):
        for relative, expected in sources.items():
            if measure.sha256(root / relative) != expected:
                raise ValueError(f"Changed {label} source")
        checks.append({"inventory": label, "files": len(sources), "unchanged": True})
    for relative, key in INVENTORIES:
        sources = measure.read(root / relative)[key]
        for source_path, expected in sources.items():
            if measure.sha256(root / source_path) != expected:
                raise ValueError(f"Protected evidence changed: {source_path}")
        checks.append({"inventory": relative, "files": len(sources), "unchanged": True})
    for name, expected in result["output_image_hashes"].items():
        if Path(name).name != name or measure.sha256(measurement_file.parent / name) != expected:
            raise ValueError("Source image receipt mismatch")
    return checks


def evaluate(root, plan_path, measurement_file, output):
    root, output = root.resolve(), output.resolve()
    plan, result = measure.read(plan_path), measure.read(measurement_file)
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Evaluation output must be new and within analysis_results")
    if result["plan_sha256"] != measure.sha256(plan_path) or result["source_hashes"] != plan["measurement_source_hashes"]:
        raise ValueError("Measurement/plan source mismatch")
    if plan["producer_sha256"] != measure.sha256(measure.__file__) or result["producer_sha256"] != plan["producer_sha256"]:
        raise ValueError("Producer hash mismatch")
    if plan["evaluator_sha256"] != measure.sha256(__file__) or result["runtime"] != measure.runtime():
        raise ValueError("Evaluation runtime/runner mismatch")
    if result["parameters"] != plan["parameters"] or result["parameters"] != measure.PARAMETERS:
        raise ValueError("Parameters changed after measurement")
    if result["human_files_read"] or result["template_updates"] or result["reset_frames"] or result["pose_inference_rerun"]:
        raise ValueError("Expected immutable GT-blind saved-data measurement")
    total = plan["total_frames"]
    if result["total_frames"] != total or [f["frame_index"] for f in result["frames"]] != list(range(total)):
        raise ValueError("Missing measurement frame denominator")
    if any([m["patch_id"] for m in f["patch_matches"]] != [1, 2] for f in result["frames"]):
        raise ValueError("Expected exactly two patch records on every original frame")
    integrity = check_sources(root, plan, result, measurement_file)
    manual = measure.read(root / plan["manual_reference"])
    gt = measure.read(root / plan["qualitative_reference"])
    if manual["source_video"]["sha256"] != plan["measurement_source_hashes"][plan["measurement_source_roles"]["video"]]:
        raise ValueError("Manual/video binding mismatch")
    if manual["source_video"]["total_frames"] != total or [f["frame_index"] for f in manual["frames"]] != list(range(total)):
        raise ValueError("Manual timeline mismatch")
    if any(gt["source_video"][key] != manual["source_video"][key] for key in ("pitch_id", "sha256", "total_frames", "frame_index_base")):
        raise ValueError("Qualitative/manual source binding mismatch")
    major = {i for interval in gt["labels"]["major_pose_failure_intervals"] if interval["status"] == "confirmed"
             for i in range(interval["start_frame"], interval["end_frame"]+1)}
    if any(i < 0 or i >= total for i in major):
        raise ValueError("Major-failure reference out of bounds")
    templates = {}
    for patch in result["source_patches"]:
        if patch["status"] == "available_unverified_ownership":
            value = np.asarray(patch["gray_pixels"], dtype=np.uint8)
            if measure.array_hash(value) != patch["gray_sha256"]:
                raise ValueError("Template pixel hash mismatch")
            templates[patch["patch_id"]] = value
    video = cv2.VideoCapture(str(root / plan["measurement_source_roles"]["video"]))
    if not video.isOpened():
        raise ValueError("Cannot decode reference video")
    rows, source_proxy = [], []
    try:
        for frame, manual_frame in zip(result["frames"], manual["frames"], strict=True):
            ok, image = video.read()
            if not ok:
                raise ValueError("Missing original image frame")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if measure.array_hash(gray) != frame["decoded_gray_sha256"]:
                raise ValueError("Decoded pixels changed")
            hull = manual_proxy(manual_frame)
            index = frame["frame_index"]
            if index == result["source_frame"]:
                for patch in result["source_patches"]:
                    if patch["rectangle_xywh"] is not None:
                        x, y, w, h = patch["rectangle_xywh"]
                        if measure.array_hash(gray[y:y+h, x:x+w]) != patch["gray_sha256"]:
                            raise ValueError("Template not taken from frozen original source rectangle")
                        source_proxy.append({"patch_id": patch["patch_id"], **proxy_context(
                            {"center_xy_px": [x+w//2, y+h//2], "rectangle_xywh": [x, y, w, h]}, hull),
                            "whole_patch_ownership": "unreviewed", "proxy_is_identity_truth": False})
            for match in frame["patch_matches"]:
                patch_id = match["patch_id"]
                if result["source_frame"] is not None and index >= result["source_frame"] and patch_id in templates:
                    reproduced = measure.matching_candidates(gray, templates[patch_id])
                    verify_candidate_receipts({k: v for k, v in match.items() if k != "patch_id"}, reproduced)
                candidates = [{**candidate, **proxy_context(candidate, hull), "whole_patch_ownership": "unreviewed"}
                              for candidate in match["candidates"]]
                rows.append({"frame_index": index, "timestamp_ms": frame["timestamp_ms"], "patch_id": patch_id,
                             "major_failure_reference": index in major, "manual_proxy_available": hull is not None,
                             "measurement_status": match["status"], "unavailable_reason": match["reason"],
                             "candidates": candidates, "top_competitor_margin": match.get("top_competitor_margin"),
                             "warning_prediction": None, "identity_truth": None})
        if video.read()[0]:
            raise ValueError("Extra reference video frames")
    finally:
        video.release()
    groups = {}
    for patch_id in (1, 2):
        groups[str(patch_id)] = {}
        for label, subset in (("all_frames", [r for r in rows if r["patch_id"] == patch_id]),
                              ("major_failure", [r for r in rows if r["patch_id"] == patch_id and r["major_failure_reference"]]),
                              ("other_frames", [r for r in rows if r["patch_id"] == patch_id and not r["major_failure_reference"]])):
            available = [r for r in subset if r["candidates"]]
            proxy_rows = [r for r in available if r["manual_proxy_available"]]
            groups[str(patch_id)][label] = {"frame_denominator": len(subset), "matching_available": len(available),
                "matching_unavailable": len(subset)-len(available),
                "manual_proxy_available": sum(r["manual_proxy_available"] for r in subset),
                "missing_manual_proxy": sum(not r["manual_proxy_available"] for r in subset),
                "paired_candidate_proxy_available": len(proxy_rows),
                "top_center_inside_proxy": sum(r["candidates"][0]["center_inside_manual_torso_proxy"] for r in proxy_rows),
                "top_center_outside_proxy": sum(not r["candidates"][0]["center_inside_manual_torso_proxy"] for r in proxy_rows),
                "candidate_proxy_comparison_unavailable": len(subset)-len(proxy_rows),
                "top_score": describe(r["candidates"][0]["score"] for r in available),
                "top_competitor_margin": describe(r["top_competitor_margin"] for r in available if r["top_competitor_margin"] is not None),
                "whole_patch_ownership_unreviewed": len(subset), "identity_accuracy": None, "warning_accuracy": None}
    # Repeat protection checks after computation; evaluator does not write sources.
    integrity = check_sources(root, plan, result, measurement_file)
    output.mkdir(parents=True)
    report = {"status": "diagnostic_complete_source_ownership_pending", "phase2_acceptance": "IN PROGRESS",
              "measurement_sha256": measure.sha256(measurement_file), "plan_sha256": measure.sha256(plan_path),
              "evaluator_sha256": measure.sha256(__file__), "total_frames": total, "major_failure_frames": len(major),
              "source_frame": result["source_frame"], "source_proxy_context": source_proxy, "groups": groups,
              "rows": rows, "all_available_match_receipts_recomputed": True,
              "whole_patch_human_questions_max": 2, "source_patch_human_answers": None,
              "identity_predictions": None, "warning_predictions": None, "warning_thresholds": None,
              "limits": ["Raw seed/human joint hull only supplies geometry, not whole-patch ownership",
                         "Cloth template center is not an anatomical landmark or exact torso center",
                         "Normalized correlation is uncalibrated similarity, not identity confidence",
                         "Three candidate rectangles and unknown ownership cannot prove subject continuity",
                         "Known single-pitch development clip, not independent generalization/holdout",
                         "Natural turning/occlusion and background/other-person competitors remain unresolved",
                         "Missing/unknown frames remain in all frame denominators"],
              "next_gate": "Human source-patch ownership review; do not promote to production or extend clips yet"}
    measure.write(output / "appearance_comparison.json", report)
    measure.write(output / "evidence_integrity_check.json", {"status": "passed", "inventories": integrity,
                  "all_match_receipts_recomputed": True, "human_inputs_evaluator_only": True,
                  "producer_inputs_unchanged": True, "new_warning_predictions": False,
                  "measurement_sha256": measure.sha256(measurement_file)})
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("measurements", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = evaluate(args.root, args.plan, args.measurements, args.output)
    print(json.dumps({k: result[k] for k in ("status", "total_frames", "major_failure_frames", "source_proxy_context", "groups")}))
