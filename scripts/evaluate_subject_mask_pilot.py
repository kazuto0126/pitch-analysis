"""Offline source-bound comparison; human answers never enter mask inference."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

from pitch_analysis.pose_capture import LANDMARK_NAMES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def evaluate(measurements, original_review, supplementary_review, baseline, output):
    if output.exists():
        raise FileExistsError("A new evaluation directory is required")
    sources = {}

    def verify(path, expected=None):
        actual = sha(path)
        if expected is not None and actual != expected:
            raise ValueError("Source hash mismatch: " + str(path))
        sources[str(path)] = actual

    for path in (measurements, original_review, supplementary_review,
                 baseline / "pose_raw.capture.json", baseline / "pose_raw.csv", Path(__file__)):
        verify(path)
    measured, original, supplement = map(read, (measurements, original_review, supplementary_review))
    verify(measured["plan_path"], measured["plan_sha256"])
    for path, expected in measured["source_hashes"].items():
        verify(path, expected)
    if measured["human_annotation_inputs"] or measured["warning_predictions_generated"]:
        raise ValueError("Expected a GT-blind measurement without warning decisions")
    for review in (original, supplement):
        for field in ("source_query_manifest", "source_video", "prior_review_version"):
            if field in review:
                item = review[field]
                verify(item["path"], item["sha256"])
        for image in review["display_files"]:
            verify(image["raw_image"], image["raw_sha256"])
            verify(image["display_image"], image["display_sha256"])
        if review["source_video"]["sha256"] != measured["source_video"]["sha256"]:
            raise ValueError("Human review belongs to another video")
    if supplement["region_clarification_pending"] or supplement["review_status"] != "all_eight_memberships_confirmed":
        raise ValueError("Supplement contains unresolved answers")

    def key(query):
        return (query["frame_index"], *query.get("image_xy_px", query.get("queried_image_xy_px")))

    original_ids = {q["query_id"]: q for q in original["queries"]}
    references = {}
    for q in original["queries"]:
        references[key(q)] = [{"query_id": q["query_id"], "code": q["human_code"],
                               "review_path": str(original_review)}]
    for q in supplement["queries"]:
        if q["region_status"] != "human_confirmed" or q["resolved_code"] not in ("T", "P", "O", "?"):
            raise ValueError("Unconfirmed or invalid human class")
        prior = q["previous_query_id"]
        if prior is not None and (prior not in original_ids or key(q) != key(original_ids[prior])):
            raise ValueError("Recheck does not match the original position")
        references.setdefault(key(q), []).append({"query_id": q["query_id"],
            "actual_reply_code": q["actual_reply_code"], "code": q["resolved_code"],
            "review_path": str(supplementary_review)})
    samples = {key(s): s for s in measured["samples"]}
    if len(samples) != len(measured["samples"]) or set(samples) != set(references):
        raise ValueError("Every unique human position must match exactly one measurement")
    joined, changes = [], []
    for position, history in sorted(references.items()):
        sample = samples[position]
        if set(sample["source_query_ids"]) != {entry["query_id"] for entry in history}:
            raise ValueError("Sample aliases do not match reviewed questions")
        if len(history) > 1 and history[0]["code"] != history[-1]["code"]:
            changes.append({"frame_index": position[0], "image_xy_px": list(position[1:]),
                            "previous_code": history[0]["code"], "latest_explicit_code": history[-1]["code"]})
        if sample["measurement_status"] == "missing" and (sample["mask_probability"] is not None or not sample["missing_reason"]):
            raise ValueError("Missing mask must retain null probability and a reason")
        joined.append({**sample, "latest_human_code": history[-1]["code"], "human_history": history})

    # Compare the isolated run with preserved raw outputs, never update them.
    capture = read(baseline / "pose_raw.capture.json")
    old_trace = {f["frame_index"]: f for f in capture["selection_frames"]}
    frames = {f["frame_index"]: f for f in measured["frames"]}
    if set(frames) != set(old_trace) or len(frames) != len(measured["frames"]):
        raise ValueError("Shadow and baseline timelines differ")
    trace_fields = {"timestamp_ms": "timestamp_ms", "index": "selected_index",
                    "status": "status", "reason": "reason", "candidate_count": "candidate_count",
                    "score": "score", "mean_confidence": "mean_confidence"}
    changed = [i for i, frame in frames.items()
               if any(frame[new] != old_trace[i][old] for new, old in trace_fields.items())]
    raw_rows = list(csv.DictReader((baseline / "pose_raw.csv").open(encoding="utf-8-sig", newline="")))
    landmark_indexes = {name: index for index, name in enumerate(LANDMARK_NAMES)}
    max_delta, different_rows, checked_values = 0.0, 0, 0
    for row in raw_rows:
        frame = frames[int(row["frame"])]
        if frame["index"] is None:
            raise ValueError("Shadow lacks a selected pose that baseline contains")
        point = frame["candidates"][frame["index"]][landmark_indexes[row["landmark"]]]
        deltas = [abs(float(row[name]) - point[name]) for name in ("x", "y", "z", "visibility", "presence")]
        max_delta = max(max_delta, *deltas)
        different_rows += any(delta != 0 for delta in deltas)
        checked_values += len(deltas)
    expected_rows = sum(len(f["candidates"][f["index"]]) for f in frames.values() if f["index"] is not None)
    if len(raw_rows) != expected_rows:
        raise ValueError("Selected landmark denominator mismatch")

    checks = []
    for path, field in (
        ("analysis_results/phase2_warning_design_20261006_01/evidence_integrity_check.json", "protected_sha256"),
        ("analysis_results/phase2_feature_support_20261006_01/evaluation/evidence_integrity_check.json", "source_hashes"),
        ("analysis_results/phase2_feature_membership_pilot_20261006_02/evaluation_01/human_membership_comparison.json", "source_hashes"),
    ):
        verify(path)
        prior_hashes = read(path)[field]
        for source, expected in prior_hashes.items():
            verify(source, expected)
        checks.append({"manifest": path, "files_checked": len(prior_hashes), "unchanged": True})
    available = sum(row["measurement_status"] == "available" for row in joined)
    report = {"status": "insufficient_mask_evidence" if available == 0 else "point_values_available",
        "source_hashes": sources, "unique_position_denominator": len(joined), "available_mask_values": available,
        "latest_unique_human_counts": dict(Counter(row["latest_human_code"] for row in joined)),
        "supplementary_human_counts": dict(Counter(q["resolved_code"] for q in supplement["queries"])),
        "explicit_recheck_changes": changes, "rows": joined,
        "missing_reasons": dict(Counter(row["missing_reason"] for row in joined if row["measurement_status"] == "missing")),
        "mask_accuracy": None, "mask_auc": None, "mask_iou": None,
        "metric_unavailability_reason": "No mask values; no decision cutoff or full-mask reference",
        "baseline_comparison": {"frames_checked": len(frames), "trace_difference_frames": changed,
            "selected_landmark_rows_checked": len(raw_rows), "numeric_values_checked": checked_values,
            "different_landmark_rows": different_rows, "max_absolute_numeric_delta": max_delta,
            "identity_verified": False, "scope": "Output consistency only; shared errors can persist"},
        "integrity_checks": checks, "warning_thresholds": None, "warning_predictions_generated": False,
        "canonical_predictions_or_gt_modified": False, "phase2_acceptance": "IN PROGRESS",
        "limits": ["Latest explicit rechecks resolve five repeated positions; older replies are preserved",
                   "Two targeted development frames are not a holdout or whole-clip tracking benchmark",
                   "The same model's optional mask is not independent identity or anatomical-coordinate truth"]}
    for path, expected in sources.items():
        verify(path, expected)
    output.mkdir(parents=True)
    (output / "human_mask_comparison.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("measurements", "original_review", "supplementary_review", "baseline", "output"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    result = evaluate(**vars(args))
    print(json.dumps({key: result[key] for key in ("status", "unique_position_denominator",
                     "available_mask_values", "latest_unique_human_counts", "baseline_comparison", "integrity_checks")}))
