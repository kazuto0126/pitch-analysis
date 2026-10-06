"""Source-bound human point comparison; descriptive values, no fitted decisions."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

import evaluate_subject_mask_pilot as reference_join


def evaluate(measurements, original_review, supplementary_review, baseline, output):
    measured = reference_join.read(measurements)
    if measured.get("numpy_view_called") is not False or measured.get("private_pointer_used") is not False:
        raise ValueError("Expected validated public indexing measurements")
    frames = {f["frame_index"]: f for f in measured["frames"]}
    checked = 0
    for sample in measured["samples"]:
        if sample["measurement_status"] == "missing":
            if sample["mask_probability"] is not None or not sample["missing_reason"]:
                raise ValueError("Missing evidence must remain explicit")
            continue
        if sample["measurement_status"] != "available" or sample["missing_reason"] is not None:
            raise ValueError("Invalid availability state")
        frame = frames[sample["frame_index"]]
        index = sample["selected_candidate_index"]
        if index != frame["index"] or index is None or frame["mask_count"] != frame["candidate_count"]:
            raise ValueError("Ambiguous current-result candidate association")
        metadata = frame["mask_metadata"][index]
        if metadata["candidate_index"] != index or metadata["format"] != 9 or metadata["channels"] != 1:
            raise ValueError("Unsupported mask metadata")
        width, height = metadata["width"], metadata["height"]
        x, y = sample["image_xy_px"]
        if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < width and 0 <= y < height):
            raise ValueError("Invalid source point")
        left, top = math.floor(x), math.floor(y)
        right, bottom = min(left+1, width-1), min(top+1, height-1)
        dx, dy = x-left, y-top
        expected = {}
        for row, col, weight in ((top,left,(1-dy)*(1-dx)),(top,right,(1-dy)*dx),
                                 (bottom,left,dy*(1-dx)),(bottom,right,dy*dx)):
            expected[row,col] = expected.get((row,col),0) + weight
        actual = {}
        for pixel in sample["native_pixels"]:
            row, col, value, weight = (pixel[k] for k in ("row","column","probability","weight"))
            if not (isinstance(row,int) and isinstance(col,int) and 0 <= row < height and 0 <= col < width):
                raise ValueError("Invalid native pixel coordinate")
            if not (math.isfinite(value) and 0 <= value <= 1 and math.isfinite(weight) and 0 <= weight <= 1):
                raise ValueError("Invalid native pixel probability or weight")
            if (row,col) in actual:
                raise ValueError("Duplicated native read receipt")
            actual[row,col] = (value,weight)
        if set(actual) != set(expected) or any(not math.isclose(actual[p][1],w,rel_tol=0,abs_tol=1e-12)
                                               for p,w in expected.items()):
            raise ValueError("Native reads do not correspond to original query coordinates")
        recomputed = sum(value*weight for value,weight in actual.values())
        if not math.isclose(recomputed,sample["mask_probability"],rel_tol=0,abs_tol=1e-12):
            raise ValueError("Stored point probability does not reproduce from native receipts")
        checked += len(actual)
    # Reuse the preserved join/history/baseline/source-integrity logic. Only this
    # new output's presentation is extended; historical code/results stay intact.
    report = reference_join.evaluate(measurements, original_review, supplementary_review, baseline, output)
    statistics = {}
    for code in ("T", "P", "O", "?"):
        rows = [r for r in report["rows"] if r["latest_human_code"] == code]
        values = [r["mask_probability"] for r in rows if r["measurement_status"] == "available"]
        statistics[code] = {"human_positions":len(rows),"available":len(values),"missing":len(rows)-len(values),
                           "minimum":min(values) if values else None,"median":median(values) if values else None,
                           "maximum":max(values) if values else None}
    report.update({"class_probability_statistics":statistics,"native_pixel_receipts_checked":checked,
        "whole_mask_read":False,"read_api":measured["read_api"],"numpy_view_called":False,
        "metric_unavailability_reason":"No classification cutoff or full-mask reference; targeted development points are not independent validation",
        "metric_status":{"accuracy":"not_computed_no_decision_cutoff","auc":"not_reported_sparse_targeted_development_points",
                         "iou":"unavailable_no_full_mask_or_full_mask_reference"},
        "evaluation_method":"Historical source-bound join plus public pixel receipt validation and descriptive class statistics",
        "production_warning_or_mask_cutoff_selected":False})
    report["source_hashes"][str(Path(__file__))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output / "human_mask_comparison.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("measurements", "original_review", "supplementary_review", "baseline", "output"):
        parser.add_argument(name,type=Path)
    args = parser.parse_args()
    result = evaluate(**vars(args))
    print(json.dumps({key:result[key] for key in ("status","unique_position_denominator","available_mask_values",
                      "class_probability_statistics","native_pixel_receipts_checked","baseline_comparison")}))
