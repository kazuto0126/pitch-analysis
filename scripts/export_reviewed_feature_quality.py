"""Apply completed raw-overlay review to two existing 2D feature streams.

Read-only, post-review evidence export. No pose estimation, feature rebuilding,
event detection, smoothing changes or training. Original values stay visible;
only a separate eligible_value is withheld when inputs lack reviewed evidence.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from copy import deepcopy
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_reviewed_reliability as review

DEPENDENCIES = {
    "throwing_elbow_angle": ("throwing_shoulder", "throwing_elbow", "throwing_wrist"),
    "lead_knee_angle": ("lead_hip", "lead_knee", "lead_ankle"),
}
COLORS = {
    "reviewed_2d_projection_inputs": (95, 191, 144),
    "hold_frame_review": (193, 62, 71),
    "hold_joint_review": (228, 126, 101),
    "unverifiable_joint": (217, 178, 88),
    "unverified_imputation": (151, 122, 194),
    "unavailable_base_value": (110, 126, 145),
}


def number(value):
    if value in ("", None):
        return None
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("nonfinite saved feature value")
    return result


def boolean(value):
    if value not in ("True", "False", "true", "false"):
        raise ValueError("saved provenance flag must be an explicit boolean")
    return value.lower() == "true"


def projected_angle(points, x_scale):
    """Independent saved-value integrity check, not a new analysis feature."""
    if not math.isfinite(x_scale) or x_scale <= 0:
        raise ValueError("positive finite original width/height ratio required")
    if any(not p["usable"] or p.get("x") is None or p.get("y") is None for p in points):
        return None
    xy = [(p["x"] * x_scale, p["y"]) for p in points]
    if not all(math.isfinite(value) for point in xy for value in point):
        raise ValueError("nonfinite processed coordinate")
    a, b, c = xy
    u, v = (a[0] - b[0], a[1] - b[1]), (c[0] - b[0], c[1] - b[1])
    lengths = math.hypot(*u) * math.hypot(*v)
    if lengths == 0:
        return None
    cosine = max(-1., min(1., (u[0] * v[0] + u[1] * v[1]) / lengths))
    return math.degrees(math.acos(cosine))


def same_number(actual, expected):
    # Only numerical serialization/recalculation tolerance, never accuracy acceptance.
    return actual is expected if actual is None or expected is None else math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-8)


def apply_review(row, frame, feature, x_scale):
    roles = DEPENDENCIES[feature]
    joints = {role: frame["focus_joints"][role] for role in roles}
    points = [joints[role]["processed_landmark"] for role in roles]
    values = {"base": number(row[feature]),
              "feature_interpolated": number(row[feature + "_interpolated"]),
              "smoothed": number(row[feature + "_smoothed"])}
    flags = {key: boolean(row[feature + "_" + key])
             for key in ("raw_observed", "coordinate_imputed", "imputed")}
    source_detected = boolean(row["source_frame_detected"])
    recomputed = projected_angle(points, x_scale)
    observed = all(joint["model_state"] == "observed" for joint in joints.values())
    raw_expected = recomputed is not None and observed and source_detected
    if (not same_number(values["base"], recomputed)
            or flags["raw_observed"] != raw_expected
            or flags["coordinate_imputed"] != (recomputed is not None and not raw_expected)):
        raise ValueError("saved feature/coordinate/provenance disagreement")
    if (flags["imputed"] != (values["base"] is None and values["feature_interpolated"] is not None)
            or (values["base"] is not None and not same_number(values["base"], values["feature_interpolated"]))):
        raise ValueError("saved base/feature-interpolation provenance disagreement")
    reasons = []
    human = frame["human_review"]
    for key in ("major_pose_failure", "track_break", "identity_switch"):
        for interval in human[key]:
            status = interval.get("status", "confirmed")
            if status not in {"confirmed", "uncertain", "not_observable"}:
                raise ValueError("unsupported whole-frame human evidence status")
            reason = "human_" + status + "_" + key
            if reason not in reasons:
                reasons.append(reason)
    if human["pitcher_correctly_selected"] is not True:
        reasons.append("subject_review_does_not_confirm_pitcher")
    for role, joint in joints.items():
        label = joint["human_raw_overlay_review"]["status"]
        state = joint["model_state"]
        if label != "reliable":
            reasons.append(f"human_raw_{label}:{role}")
        if state != "observed":
            reasons.append(f"model_{state}:{role}")
        if joint["use_disposition"]["status"] != "reviewed_raw_observation":
            reasons.append(f"joint_not_eligible:{role}")
    if values["base"] is None:
        reasons.append("no_saved_base_value")
    if not flags["raw_observed"]:
        reasons.append("saved_feature_not_raw_observed")
    if flags["coordinate_imputed"]:
        reasons.append("saved_feature_uses_coordinate_imputation")
    eligible = not reasons
    if eligible:
        status = "reviewed_2d_projection_inputs"
    elif any(reason.startswith(("human_confirmed_", "human_uncertain_", "human_not_observable_", "subject_review_")) for reason in reasons):
        status = "hold_frame_review"
    elif any(reason.startswith("human_raw_unreliable:") for reason in reasons):
        status = "hold_joint_review"
    elif any(reason.startswith(("human_raw_not_observable:", "human_raw_uncertain:")) for reason in reasons):
        status = "unverifiable_joint"
    elif values["base"] is None:
        status = "unavailable_base_value"
    else:
        status = "unverified_imputation"
    return {"unit": "degree", "required_roles": list(roles), "saved_values": values,
            "saved_flags": flags, "source_frame_detected": source_detected,
            "eligible_value": values["base"] if eligible else None,
            "eligible": eligible, "status": status, "reason_codes": reasons,
            "constituent_evidence": deepcopy(joints),
            "alternate_values_review": "feature-interpolated/smoothed variants not verified by this export"}


def longest_false(values):
    longest = run = 0
    for value in values:
        run = 0 if value else run + 1
        longest = max(longest, run)
    return longest


def derive(view, rows, metrics, quality, meta):
    total = view["summary"]["total_frames"]
    if (len(rows) != total or [int(r["frame"]) for r in rows] != list(range(total))
            or meta["frame_count"] != total or quality["timeline_frames"] != total
            or len(meta["timestamps_ms"]) != total
            or [f["frame_index"] for f in view["frames"]] != list(range(total))):
        raise ValueError("all original frames required once and in order")
    if metrics["pitch_id"] != view["pitch_id"] or metrics["pitcher_id"] != view["pitcher"]["id"]:
        raise ValueError("metric/video identity disagreement")
    if quality["throwing_side"] != view["pitcher"]["throws"]:
        raise ValueError("feature handedness disagreement")
    if meta["sha256"] != view["source_artifacts"]["original_video"]["sha256"]:
        raise ValueError("feature/review video hash disagreement")
    aspect = meta["width"] / meta["height"]
    if not same_number(quality["coordinate_x_scale"], aspect):
        raise ValueError("saved feature aspect-ratio disagreement")
    frames = []
    for row, source_frame, timestamp in zip(rows, view["frames"], meta["timestamps_ms"]):
        if not same_number(source_frame["timestamp_ms"], timestamp):
            raise ValueError("feature/review original timestamp disagreement")
        frames.append({"frame_index": source_frame["frame_index"], "timestamp_ms": timestamp,
                       "human_frame_evidence": deepcopy(source_frame["human_review"]),
                       "features": {name: apply_review(row, source_frame, name, aspect) for name in DEPENDENCIES}})
    summaries = {}
    for name in DEPENDENCIES:
        feature_rows = [frame["features"][name] for frame in frames]
        raw_count = sum(f["saved_flags"]["raw_observed"] for f in feature_rows)
        saved_count = sum(f["saved_values"]["base"] is not None for f in feature_rows)
        eligible_count = sum(f["eligible"] for f in feature_rows)
        if (metrics["metrics"][name]["observed_frames"] != raw_count
                or not same_number(metrics["metrics"][name]["raw_coverage"], raw_count / total)
                or not same_number(quality["raw_feature_coverage"][name], raw_count / total)):
            raise ValueError("original feature summary disagrees with per-frame saved flags")
        summaries[name] = {
            "total_frame_denominator": total,
            "saved_base_values": saved_count, "original_raw_observed_frames": raw_count,
            "reviewed_eligible_frames": eligible_count, "reviewed_eligible_fraction": eligible_count / total,
            "saved_base_values_held": saved_count - eligible_count,
            "original_raw_values_held": raw_count - eligible_count,
            "longest_not_eligible_span_frames": longest_false(f["eligible"] for f in feature_rows),
            "status_counts": dict(Counter(f["status"] for f in feature_rows)),
            "reason_counts_nonexclusive": dict(Counter(reason for f in feature_rows for reason in f["reason_codes"])),
        }
    return {
        "schema_version": "reviewed-feature-quality-view-v1",
        "output_kind": "derived_post_review_feature_use_view_not_new_prediction",
        "pitch_id": view["pitch_id"], "pitcher": deepcopy(view["pitcher"]),
        "review_scope": "raw_overlay_unsmoothed_base_2d_feature_inputs",
        "ground_truth_provenance": deepcopy(view["ground_truth_provenance"]),
        "original_metrics_quality_gate_passed": metrics["quality_gate_passed"],
        "original_metrics_status": metrics["status"],
        "limitations": [
            "Eligibility applies existing qualitative human review, not new automatic error detection.",
            "Only two existing unsmoothed 2D projection features; not new biomechanics or phase analysis.",
            "No exact numeric-angle accuracy, 3D or unseen-video certification.",
            "All base values retained; held eligible_value is null, never zero or interpolation.",
            "Raw availability coverage and Phase1 acceptance gate are unchanged; review eligibility is separate.",
            "Feature-interpolated/smoothed neighbors are not certified by current-frame joint review.",
            "Subset extrema/median are not recomputed; gaps stay gaps, no trajectory resampling.",
        ], "summary": summaries, "frames": frames,
    }


def write_csv(path, report):
    fields = ["frame", "timestamp_ms"]
    for name in DEPENDENCIES:
        fields.extend(f"{name}_{suffix}" for suffix in ("original_base", "eligible_value", "eligible", "status", "reasons_json"))
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for frame in report["frames"]:
            row = {"frame": frame["frame_index"], "timestamp_ms": frame["timestamp_ms"]}
            for name, item in frame["features"].items():
                row.update({f"{name}_original_base": item["saved_values"]["base"],
                            f"{name}_eligible_value": item["eligible_value"],
                            f"{name}_eligible": item["eligible"], f"{name}_status": item["status"],
                            f"{name}_reasons_json": json.dumps(item["reason_codes"], ensure_ascii=False)})
            writer.writerow(row)


def timeline(path, report, font_path):
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1200, 360), (20, 25, 34))
    draw = ImageDraw.Draw(image)
    font, small = ImageFont.truetype(str(font_path), 21), ImageFont.truetype(str(font_path), 16)
    draw.text((22, 14), report["pitch_id"] + "  既有角度的人工覆核可用性", font=font, fill="white")
    draw.text((22, 50), "綠色只表示組成點有人工定性對位證據；不代表精確角度／3D認證。", font=small, fill=(180, 193, 211))
    total = len(report["frames"])
    for n, (name, label) in enumerate(zip(DEPENDENCIES, ("投球手肘角度", "前導膝角度"))):
        y = 94 + 98 * n
        summary = report["summary"][name]
        draw.text((22, y), f"{label}：{summary['reviewed_eligible_frames']} / {total} 格可依覆核保留", font=font, fill="white")
        for i, frame in enumerate(report["frames"]):
            left, right = 24 + 1150 * i // total, 24 + 1150 * (i + 1) // total
            draw.rectangle((left, y + 33, right - 1, y + 62), fill=COLORS[frame["features"][name]["status"]])
        draw.text((24, y + 66), "0", font=small, fill="white")
        draw.text((1118, y + 66), str(total - 1), font=small, fill="white")
    labels = ("可保留", "整格待覆核", "關節不可靠", "無法核對", "插值未覆核", "原值缺失")
    for i, (status, label) in enumerate(zip(COLORS, labels)):
        x = 22 + i * 191
        draw.rectangle((x, 300, x + 18, 318), fill=COLORS[status])
        draw.text((x + 25, 298), label, font=small, fill="white")
    draw.text((22, 333), "原數值完整保留；新可用值在不符合覆核條件時留空。未改原品質門檻。", font=small, fill=(180, 193, 211))
    with Path(path).open("xb") as stream:
        image.save(stream, format="PNG")


def run(plan_path, output):
    plan_path, output = Path(plan_path), Path(output)
    if output.exists():
        raise FileExistsError("new result directory required")
    plan_hash = review.sha256(plan_path)
    plan = review.read_json(plan_path)
    if plan["schema_version"] != "reviewed-feature-export-plan-v1" or review.sha256(plan_path) != plan_hash:
        raise ValueError("unsupported or changed frozen plan")
    for record in plan["implementation"].values():
        review.bound_path(ROOT, record)
    font = review.bound_path(ROOT, plan["font"])
    reports, seen = [], set()
    for spec in plan["clips"]:
        if spec["pitch_id"] in seen or set(spec["sources"]) != {"reviewed_reliability", "features", "metrics", "feature_quality"}:
            raise ValueError("duplicate pitch or incomplete source bindings")
        seen.add(spec["pitch_id"])
        sources = {role: review.bound_path(ROOT, record) for role, record in spec["sources"].items()}
        view = review.read_json(sources["reviewed_reliability"])
        original_sources = {role: review.bound_path(ROOT, record) for role, record in view["source_artifacts"].items()}
        fresh = review.derive_clip({"pitch_id": spec["pitch_id"], "sources": view["source_artifacts"]}, original_sources)
        if {k: v for k, v in view.items() if k != "export"} != fresh:
            raise ValueError("derived review does not match canonical/model sources")
        with sources["features"].open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        report = derive(view, rows, review.read_json(sources["metrics"]),
                        review.read_json(sources["feature_quality"]), review.read_json(original_sources["video_metadata"]))
        report["source_artifacts"] = deepcopy(spec["sources"])
        report["original_review_sources"] = deepcopy(view["source_artifacts"])
        report["frozen_plan_sha256"] = plan_hash
        reports.append(report)
    if not reports:
        raise ValueError("no reviewed clips")
    output.mkdir(parents=True, exist_ok=False)
    for report in reports:
        directory = output / report["pitch_id"]
        directory.mkdir()
        review.write_new(directory / "reviewed_feature_quality.json", report)
        write_csv(directory / "reviewed_features.csv", report)
        timeline(directory / "feature_use_timeline.png", report, font)
    for spec in plan["clips"]:
        for record in spec["sources"].values():
            review.bound_path(ROOT, record)
    for report in reports:
        for record in report["original_review_sources"].values():
            review.bound_path(ROOT, record)
    for record in [*plan["implementation"].values(), plan["font"]]:
        review.bound_path(ROOT, record)
    if review.sha256(plan_path) != plan_hash:
        raise ValueError("frozen plan changed during export")
    summary = {"schema_version": "reviewed-feature-export-receipt-v1",
               "status": "exported_not_phase2_acceptance", "source_hashes_verified_after_export": True,
               "frozen_plan_sha256": plan_hash,
               "total_frames": sum(len(r["frames"]) for r in reports),
               "total_feature_rows": sum(2 * len(r["frames"]) for r in reports),
               "clips": [{"pitch_id": r["pitch_id"], "summary": r["summary"]} for r in reports]}
    review.write_new(output / "export_summary.json", summary)
    lines = ["# 既有角度的人工覆核可用性", "", "每支先看時間軸圖，逐格原因在JSON。",
             "CSV的original_base完整保留；eligible_value只有符合原人工定性對位、直接觀測與整格覆核條件時保留。",
             "留空表示此輸出未認證，不是0，也不要自動補值或跨gap平滑。未改Phase1門檻。", "",
             "這是覆核後的2D資料使用檢視，不是自動錯位偵測、新動作特徵或Phase2 PASSED。", ""]
    for report in reports:
        pid = report["pitch_id"]
        lines.append(f"- [{pid}時間軸]({pid}/feature_use_timeline.png) · [逐格CSV]({pid}/reviewed_features.csv) · [完整原因JSON]({pid}/reviewed_feature_quality.json)")
    (output / "START_HERE.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.plan, args.output)
    print(json.dumps({"status": result["status"], "frames": result["total_frames"], "feature_rows": result["total_feature_rows"]}))
