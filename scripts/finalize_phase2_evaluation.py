"""Close the existing five-clip Phase 2 evaluation without certifying automation.

Reproduce saved comparisons and reviewed exports from hash-bound evidence.
Never run inference, write annotations, repair coordinates or tune acceptance.
The terminal evaluation outcome and the automatic-reliability verdict differ.
"""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import assess_observation_accuracy as accuracy
import evaluate_phase2_ground_truth as comparison
import export_reviewed_feature_quality as features
import export_reviewed_reliability as review
from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth

PITCH_IDS = tuple(f"pitch_{i:03d}" for i in range(1, 6))


def physical_file_count(root, inventory):
    """Absolute/relative or slash spellings do not multiply protected files."""
    return len({os.path.normcase(str((root / name).resolve())) for name in inventory})


def terminal_verdict(comparisons, test_result):
    """Known baseline findings decide this ending; no invented tolerance score."""
    if tuple(item["pitch_id"] for item in comparisons) != PITCH_IDS:
        raise ValueError("Exactly the five formal baseline clips are required in order")
    if any(item["comparison"].get("review_profile") != "phase2_full_review"
           or item["comparison"].get("ground_truth_status") != "reviewed"
           for item in comparisons):
        raise ValueError("Complete canonical human reviews are required")
    tests = deepcopy(test_result)
    for key in ("passed", "failed", "errors", "skipped"):
        if type(tests.get(key)) is not int or tests[key] < 0:
            raise ValueError("Explicit nonnegative full-suite counts required")
    if (tests.get("tests_run") != sum(tests[k] for k in ("passed", "failed", "errors", "skipped"))
            or tests["tests_run"] <= 0 or tests.get("formal_five_video_e2e_enabled") is not True):
        raise ValueError("Full suite and all five real-video E2E inputs required")
    aggregate = comparison._aggregate(comparisons)
    misses = []
    for item in comparisons:
        screen = item["comparison"]["major_pose_failure_screening"]
        if screen["false_negative_frames"]:
            misses.append({"pitch_id": item["pitch_id"],
                           "missed_confirmed_major_failure_frames": screen["false_negative_frames"],
                           "ranges": deepcopy(screen["ranges"]["false_negative"])})
    # Absence of misses does not by itself grant certification either. This tool
    # closes a diagnostic baseline; it cannot invent a new automatic pass rule.
    verdict = "NOT PASSED" if misses else "NOT ESTABLISHED"
    return {"evaluation_status": "COMPLETE", "evaluation_complete": True,
            "automatic_reliability": verdict, "phase2_acceptance": verdict,
            "accepted": False, "known_major_failure_misses": misses,
            "aggregate": aggregate,
            "test_gate": "PASSED" if tests["failed"] == tests["errors"] == tests["skipped"] == 0 else "NOT PASSED",
            "tests": tests,
            "basis": "Original qualitative reliability requirements and confirmed baseline findings; no new numeric tolerance or total score",
            "stop_before": ["Phase 3", "shared delivery folder integration"],
            "future_work_requires_new_instruction": True}


def verify_inventory(root, record):
    """Bind both the inventory file and every original file it protects."""
    path = review.bound_path(root, record)
    inventory = review.read_json(path)[record["key"]]
    for name, sha in inventory.items():
        review.bound_path(root, {"path": name, "sha256": sha})
    return inventory


def reproduce_observation(root, record, assessment_plan_record):
    saved = review.read_json(review.bound_path(root, record))
    plan_path = review.bound_path(root, assessment_plan_record)
    plan = review.read_json(plan_path)
    if saved["source_hashes"] != plan["source_hashes"] or saved["plan_sha256"] != review.sha256(plan_path):
        raise ValueError("Coordinate assessment source plan disagrees")
    roles = {role: root / path for role, path in plan["source_roles"].items()}
    for name, sha in plan["source_hashes"].items():
        review.bound_path(root, {"path": name, "sha256": sha})
    processed = [json.loads(line) for line in roles["processed"].read_text(encoding="utf-8-sig").splitlines()]
    rows = accuracy.verify_rows(*(review.read_json(roles[k]) for k in ("manual", "raw")), processed,
                               *(review.read_json(roles[k]) for k in ("metadata", "pose")),
                               review.read_json(roles["diagnostics"])["rows"])
    gt = review.read_json(roles["qualitative_gt"])
    major = {i for item in gt["labels"]["major_pose_failure_intervals"]
             if item.get("status", "confirmed") == "confirmed"
             for i in range(item["start_frame"], item["end_frame"] + 1)}
    fresh = {"overall": accuracy.aggregate(rows),
             "joints": {name: accuracy.aggregate(r for r in rows if r["joint"] == name) for name in accuracy.JOINT_NAMES},
             "contexts": {"confirmed_major_failure": accuracy.aggregate(r for r in rows if r["frame_index"] in major),
                          "other_frames_not_necessarily_error_free": accuracy.aggregate(r for r in rows if r["frame_index"] not in major)}}
    if any(saved[key] != value for key, value in fresh.items()):
        raise ValueError("Saved coordinate assessment does not reproduce")
    return {"source": deepcopy(record), "pitch_id": saved["pitch_id"],
            "source_bound_rows_reproduced": len(rows), **fresh, "limits": deepcopy(saved["limits"])}


def reproduce_clip(root, spec):
    import export_existing_reliability_cues as cues
    if set(spec["sources"]) != {"reviewed_reliability", "reviewed_feature_quality", "automatic_cues"}:
        raise ValueError("Incomplete final clip artifact bindings")
    paths = {role: review.bound_path(root, record) for role, record in spec["sources"].items()}
    view = review.read_json(paths["reviewed_reliability"])
    originals = {role: review.bound_path(root, record) for role, record in view["source_artifacts"].items()}
    fresh_view = review.derive_clip({"pitch_id": spec["pitch_id"], "sources": view["source_artifacts"]}, originals)
    if {k: v for k, v in view.items() if k != "export"} != fresh_view:
        raise ValueError("Reviewed view differs from canonical/model evidence")
    saved_features = review.read_json(paths["reviewed_feature_quality"])
    fp = {role: review.bound_path(root, record) for role, record in saved_features["source_artifacts"].items()}
    if saved_features["source_artifacts"]["reviewed_reliability"] != spec["sources"]["reviewed_reliability"]:
        raise ValueError("Features refer to a different reviewed view")
    with fp["features"].open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    meta = review.read_json(originals["video_metadata"])
    fresh_features = features.derive(view, rows, review.read_json(fp["metrics"]),
                                    review.read_json(fp["feature_quality"]), meta)
    feature_extras = {"source_artifacts", "original_review_sources", "frozen_plan_sha256"}
    if ({k: v for k, v in saved_features.items() if k not in feature_extras} != fresh_features
            or saved_features["original_review_sources"] != view["source_artifacts"]):
        raise ValueError("Reviewed features differ from saved values/provenance")
    pose = review.read_json(originals["pose_reliability"])
    tracking = review.read_json(originals["tracking_reliability"])
    gt = review.read_json(originals["ground_truth"])
    processed = [json.loads(line) for line in originals["processed_keypoints"].read_text(encoding="utf-8-sig").splitlines()]
    saved_cues = review.read_json(paths["automatic_cues"])
    expected_cue_sources = {role: record for role, record in view["source_artifacts"].items()
                            if role in cues.REQUIRED_SOURCES | {"original_video"}}
    if saved_cues["source_artifacts"] != expected_cue_sources or saved_cues["source_hashes_verified"] is not True:
        raise ValueError("Automatic cue source roles disagree with formal model sources")
    for record in expected_cue_sources.values():
        review.bound_path(root, record)
    fresh_cues = cues.build_cues(pose, tracking, meta, processed)
    cues.check_clean_csv(originals["pose_clean"], fresh_cues)
    cue_extras = {"source_artifacts", "source_hashes_verified", "frozen_plan_sha256", "rendered_overlay"}
    if {k: v for k, v in saved_cues.items() if k not in cue_extras} != fresh_cues:
        raise ValueError("Existing automatic cues do not reproduce")
    if "rendered_overlay" in saved_cues:
        receipt = saved_cues["rendered_overlay"]
        review.bound_path(root, receipt)
        if (receipt["decoded_frames"] != meta["frame_count"] or receipt["width"] != meta["width"] + 460
                or receipt["height"] != meta["height"] or receipt["fps"] != meta["fps"]
                or receipt.get("codec_name") != "h264" or receipt.get("pix_fmt") != "yuv420p"
                or receipt.get("lossy_reencoding") is not True or receipt.get("pre_encoding_source_area_exact") is not True):
            raise ValueError("New automatic-cue media receipt differs from formal timeline/geometry")
    result = evaluate_against_ground_truth(gt, pose, tracking)
    roles = {role: {"landmark": name, **{key: deepcopy(value) for key, value in pose["joints"][name].items()
                                      if key != "frame_states"}}
             for role, name in pose["important_joints"].items()}
    return {"pitch_id": spec["pitch_id"], "total_frames": meta["frame_count"],
            "video": {"sha256": meta["sha256"], "width": meta["width"], "height": meta["height"], "fps": meta["fps"]},
            "reviewer": gt["provenance"]["reviewer"], "ground_truth_status": gt["annotation_status"],
            "ground_truth_reviewed_at_utc": gt["provenance"]["reviewed_at_utc"],
            "comparison": result, "reviewed_joint_summary": deepcopy(view["summary"]),
            "pose_summary": {"valid_pose_ratio": pose["valid_pose_ratio"],
                             "longest_missing_pose_gap_frames": pose["longest_missing_pose_gap_frames"],
                             "original_status": pose["status"], "original_reasons": deepcopy(pose["reasons"]),
                             "important_joints": roles, "left_right_consistency": deepcopy(pose["left_right_consistency"]),
                             "throwing_side_reliability": deepcopy(pose["throwing_side_reliability"])},
            "tracking_summary": {k: deepcopy(v) for k, v in tracking.items() if k not in {"frames", "warning_events"}},
            "reviewed_feature_summary": deepcopy(fresh_features["summary"]),
            "existing_automatic_cue_summary": deepcopy(fresh_cues["summary"]),
            "artifacts": deepcopy(spec["sources"]), "original_sources": deepcopy(view["source_artifacts"])}


def markdown(report):
    v = report["verdict"]
    lines = ["# Phase 2 最終評估", "", "**Phase 2 evaluation = COMPLETE**",
             f"**Phase 2 = {v['phase2_acceptance']}；automatic reliability = {v['automatic_reliability']}**", "",
             "人工 GT 5/5 reviewed。這輪評估已結束；已知重大錯位漏報使自動可靠性未通過。",
             "無新總分、數值通過線、模型、pose／tracking／平滑修改。測試通過不等於可靠性通過。", "",
             "## 五片摘要", "",
             "| 影片 | 格數 | 重大失效 | 原警示 TP/FN/FP | +既有跳點 TP/FN/FP | 手肘關節 raw coverage | 角度可用：肘/膝 |",
             "|---|---:|---:|---|---|---:|---|" ]
    for p in report["pitches"]:
        c = p["comparison"]
        a, b = c["major_pose_failure_screening"], c["major_pose_failure_with_joint_jump_cues"]
        triple = lambda row: "/".join(str(row[k + "_frames"]) for k in ("true_positive", "false_negative", "false_positive"))
        fs = p["reviewed_feature_summary"]
        lines.append(f"| {p['pitch_id']} | {p['total_frames']} | {a['human_positive_frames']} | {triple(a)} | {triple(b)} | "
                     f"{p['pose_summary']['important_joints']['throwing_elbow']['raw_coverage']:.1%} | "
                     f"{fs['throwing_elbow_angle']['reviewed_eligible_frames']}/{fs['lead_knee_angle']['reviewed_eligible_frames']} |")
    aggregate = v["aggregate"]["screening"]
    a, b = aggregate["major_pose_failure_screening"], aggregate["major_pose_failure_with_joint_jump_cues"]
    lines += ["", f"全部 {report['total_frames']} 格：原警示 TP{a['true_positive_frames']}/FN{a['false_negative_frames']}/FP{a['false_positive_frames']}；"
              f"既有跳點診斷聯集 TP{b['true_positive_frames']}/FN{b['false_negative_frames']}/FP{b['false_positive_frames']}。",
              "聯集是診斷對照，沒有成為新 detector；跳點只標相鄰 observed 轉移的當前端點，不擴張成整段錯誤。",
              "身分切換 confirmed 0 格，不能估 sensitivity；track break 3/3 格與人工吻合。", "",
              "## 這次可使用的成果", "",
              "- `phase2_final_assessment.json`：來源驗證、逐片六關節 coverage／visibility／gap／jump、比較與判定。",
              "- `release_status.json`：評估完成與自動驗收分開；`accepted=false`，停止在 Phase 3／共用資料夾之前。",
              "- 既有自動提示的新五片影片、逐格 JSON／CSV：沒有讀入人工 GT。無提示仍不代表對位正確。",
              "- 已完成的人工覆核影片／逐關節狀態，以及既有角度側檔保留；可用欄位僅限本批定性覆核的直接觀測 2D 輸入。", "",
              "## 座標與限制", ""]
    o = report["observation_accuracy"]["overall"]
    lines += [f"pitch_003：{o['visible_reference_denominator']} 可見點，同 {o['paired_usable_reference_count']} 可用點 raw 均誤差 "
              f"{o['same_usable_points_raw']['mean_px']:.4f}px，clean {o['same_usable_points_clean']['mean_px']:.4f}px。",
              f"{o['usable_reference_fraction']:.2%} 是保留率，不是準確率；不可觀測／不確定點不作精確座標真值。",
              "其餘片沒有相同人工 XY；事件沒有自動預測可比較；一位投手不代表其他投手泛化。",
              "pitch_005 canonical 啟動／最高抬腿仍為 uncertain；同學的獨立事件補充未回傳，另存待辦，不冒填或重開已完成 GT。", "",
              "## 測試與停止點", "",
              f"完整測試：{v['tests']['passed']} passed / {v['tests']['failed']} failed / {v['tests']['errors']} errors / {v['tests']['skipped']} skipped，含正式五片 E2E。",
              "下一次若要修復自動錯位警示，先指定新工作與驗收方式。共用交付資料夾接入仍未开始，須另行開始指示。",
              "本輪 Phase 2 評估與報告收尾後停止；沒有開始 Phase 3。", ""]
    return "\n".join(lines)


def run(root, plan_path, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Final output must be a new workspace analysis_results directory")
    plan_hash = review.sha256(plan_path)
    plan = review.read_json(plan_path)
    if plan.get("schema_version") != "phase2-final-evaluation-plan-v1" or plan.get("status") != "frozen_before_final_evaluation":
        raise ValueError("An unchanged frozen final evaluation plan is required")
    if tuple(s["pitch_id"] for s in plan["clips"]) != PITCH_IDS:
        raise ValueError("Expected the five formal clips")
    def integrity():
        protected = {}
        for record in [*plan["implementation"].values(), *plan["sources"].values()]:
            review.bound_path(root, record)
            protected[record["path"]] = record["sha256"]
        for record in plan["inventories"]:
            protected.update(verify_inventory(root, record))
        for spec in plan["clips"]:
            for record in spec["sources"].values():
                review.bound_path(root, record)
                protected[record["path"]] = record["sha256"]
            view = review.read_json(root / spec["sources"]["reviewed_reliability"]["path"])
            feature = review.read_json(root / spec["sources"]["reviewed_feature_quality"]["path"])
            cue = review.read_json(root / spec["sources"]["automatic_cues"]["path"])
            for record in [*view["source_artifacts"].values(), *feature["source_artifacts"].values(),
                           *cue["source_artifacts"].values()]:
                review.bound_path(root, record)
                protected[record["path"]] = record["sha256"]
            if "rendered_overlay" in cue:
                record = cue["rendered_overlay"]
                review.bound_path(root, record)
                protected[record["path"]] = record["sha256"]
        if review.sha256(plan_path) != plan_hash:
            raise ValueError("Frozen final evaluation plan changed")
        return protected
    before = integrity()
    cue_plan_path = root / plan["sources"]["cue_plan"]["path"]
    cue_plan = review.read_json(cue_plan_path)
    for spec in plan["clips"]:
        cue = review.read_json(root / spec["sources"]["automatic_cues"]["path"])
        cue_spec = next(s for s in cue_plan["clips"] if s["pitch_id"] == spec["pitch_id"])
        if (cue["frozen_plan_sha256"] != review.sha256(cue_plan_path)
                or cue["source_artifacts"] != cue_spec["sources"]):
            raise ValueError("Automatic cue receipt differs from frozen producer plan")
    pitches = [reproduce_clip(root, spec) for spec in plan["clips"]]
    old = review.read_json(root / plan["sources"]["verified_comparison"]["path"])
    aggregate = comparison._aggregate(pitches)
    if (old["aggregate"] != aggregate or [p["comparison"] for p in pitches] != [p["comparison"] for p in old["pitches"]]):
        raise ValueError("The verified historical GT comparison no longer reproduces")
    test_result = review.read_json(root / plan["sources"]["full_suite_result"]["path"])
    verdict = terminal_verdict(pitches, test_result)
    if verdict["test_gate"] != "PASSED":
        raise ValueError("Full suite has failures/errors/skips; do not finalize before recording or fixing them")
    required_tests = {"test_phase2_final_evaluation", "test_existing_reliability_cues"}
    if not required_tests.issubset(set(test_result.get("included_test_modules", []))):
        raise ValueError("The final full suite must include the new finalizer/cue tests")
    report = {"schema_version": "phase2-final-assessment-v1", "output_kind": "terminal_existing_baseline_evaluation_not_new_prediction",
              "frozen_plan_sha256": plan_hash, "total_frames": sum(p["total_frames"] for p in pitches),
              "pitch_count": len(pitches), "reviewed_count": len(pitches), "verdict": verdict, "pitches": pitches,
              "observation_accuracy": reproduce_observation(root, plan["sources"]["observation_accuracy"], plan["sources"]["observation_plan"]),
              "separate_pending_work": [{"item": "pitch_005 independent peer event supplement", "status": "not_returned",
                                         "canonical_review_complete": True, "canonical_events": deepcopy(pitches[-1]["comparison"]["human_events"])}],
              "historical_baseline_summary": "Preserved initial pending-human snapshot; current status derives from actual canonical reviews",
              "new_inference_or_algorithm_change": False, "new_numeric_acceptance_threshold": False,
              "human_annotation_modified": False, "phase3_or_handoff_integration_started": False}
    after = integrity()
    if before != after:
        raise ValueError("Evidence protection inventory changed during evaluation")
    # Derived/nested inputs were also checked again, without another inference run.
    for spec in plan["clips"]:
        reproduce_clip(root, spec)
    output.mkdir(parents=True, exist_ok=False)
    review.write_new(output / "phase2_final_assessment.json", report)
    review.write_new(output / "release_status.json", {**verdict, "frozen_plan_sha256": plan_hash})
    review.write_new(output / "evidence_integrity_check.json", {"status": "passed", "protected_sha256": before,
                                                               "inventory_entry_count": len(before),
                                                               "unique_inventory_files": physical_file_count(root, before),
                                                               "all_bound_inputs_reproduced": True})
    (output / "START_HERE.md").write_text(markdown(report), encoding="utf-8")
    for role, filename in (("full_suite_result", "full_test_suite_result.json"), ("full_suite_log", "full_test_suite.log")):
        shutil.copyfile(root / plan["sources"][role]["path"], output / filename)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-passed", action="store_true", help="Exit 2 unless automatic acceptance is explicitly established")
    args = parser.parse_args()
    result = run(args.root, args.plan, args.output)
    print(json.dumps({"evaluation": result["verdict"]["evaluation_status"], "phase2": result["verdict"]["phase2_acceptance"], "frames": result["total_frames"]}))
    if args.require_passed and not result["verdict"]["accepted"]:
        raise SystemExit(2)
