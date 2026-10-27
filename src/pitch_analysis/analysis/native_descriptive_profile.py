"""Reproduce a single-pitcher description from source-bound saved event reports."""
from __future__ import annotations

from copy import deepcopy
import csv
from itertools import combinations
from pathlib import Path

from .native_motion_event_viewer import _validate_clips
from .native_motion_events import TIMING_LABELS, TIMING_PAIRS
from .native_motion_transition import ROLES, describe_manual_event_transitions
from .native_timing_comparison import (
    _display, _duration, _link, _load_report, _text, compare_timing_intervals,
)
from ..native_pose_io import BoundReader, read_json, reference, write_json


DIRECTIONS = ("positive", "negative", "zero", "includes_zero", "unavailable")


def summarize_profile(clips: list[dict]) -> dict:
    """Describe all supplied clips without selecting a reference or usable data.

    Timing envelopes cover recorded bounds, not annotation error or population
    variation. Joint directions describe saved model-XY endpoints only. Unknown
    events and unavailable coordinates retain their distinct original counts.
    """
    _validate_clips(clips)
    transitions = {
        clip["pitch_id"]: {stage["transition_key"]: stage
                           for stage in describe_manual_event_transitions(clip)}
        for clip in clips
    }
    stages = []
    comparable = calculable = 0
    for key in TIMING_PAIRS:
        durations = [(clip["pitch_id"], _duration(clip["timing"][key], clip["fps_fraction"]))
                     for clip in clips]
        known = [duration for _, duration in durations if duration is not None]
        pairs = [{"a_pitch_id": a["pitch_id"], "b_pitch_id": b["pitch_id"],
                  **compare_timing_intervals(a["timing"][key], a["fps_fraction"],
                                             b["timing"][key], b["fps_fraction"])}
                 for a, b in combinations(clips, 2)]
        comparable += sum(pair["status"] != "unavailable" for pair in pairs)
        joints = {}
        for role in ROLES:
            grouped = {direction: [] for direction in DIRECTIONS}
            summaries = []
            for clip in clips:
                stage = transitions[clip["pitch_id"]][key]
                joint = stage["joints"][role]
                grouped[joint["delta_direction"]].append(clip["pitch_id"])
                calculable += bool(joint["calculated_pairs"])
                summaries.append({"pitch_id": clip["pitch_id"],
                                  "transition_status": stage["status"],
                                  "transition_reason": stage["reason"], **deepcopy(joint)})
            joints[role] = {
                "direction_counts": {direction: len(ids) for direction, ids in grouped.items()},
                "clip_ids_by_direction": grouped,
                "common_direction": next((direction for direction in ("positive", "negative", "zero")
                                          if len(grouped[direction]) == len(clips)), None),
                "clip_summaries": summaries,
            }
        stages.append({
            "timing_key": key,
            "timing_available_clip_ids": [pid for pid, value in durations if value is not None],
            "timing_unavailable_clip_ids": [pid for pid, value in durations if value is None],
            "timing_envelope_seconds_fraction":
                [str(min(v[0] for v in known)), str(max(v[1] for v in known))] if known else None,
            "timing_pairs": pairs, "joints": joints,
        })
    total_pairs = sum(len(stage["timing_pairs"]) for stage in stages)
    joint_count = len(clips) * len(TIMING_PAIRS) * len(ROLES)
    return {"clip_count": len(clips), "source_frames": sum(c["frame_count"] for c in clips),
            "timing_pair_count": total_pairs, "timing_comparable_pairs": comparable,
            "timing_unavailable_pairs": total_pairs - comparable,
            "joint_summary_count": joint_count, "joint_calculable_summaries": calculable,
            "joint_unavailable_summaries": joint_count - calculable, "stages": stages}


def _write_csvs(output: Path, summary: dict) -> None:
    fields = ["timing_key", "a_pitch_id", "b_pitch_id", "status", "relation"]
    fields += [f"{side}_{bound}_seconds_fraction"
               for side in ("a", "b", "delta") for bound in ("min", "max")]
    fields += ["a_unavailable_reason", "b_unavailable_reason"]
    with (output / "timing_relations.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for stage in summary["stages"]:
            for pair in stage["timing_pairs"]:
                row = {"timing_key": stage["timing_key"], **{key: pair[key] for key in fields[1:5]}}
                for side in ("a", "b", "delta"):
                    bounds = pair[f"{side}_seconds_bounds_fraction"]
                    for index, bound in enumerate(("min", "max")):
                        row[f"{side}_{bound}_seconds_fraction"] = bounds[index] if bounds else None
                row.update({f"{side}_unavailable_reason": pair["unavailable_reasons"][side] for side in ("a", "b")})
                writer.writerow(row)
    fields = ["timing_key", "joint", "clip_count", *DIRECTIONS, "common_direction"]
    with (output / "joint_direction_summary.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for stage in summary["stages"]:
            for role, joint in stage["joints"].items():
                writer.writerow({"timing_key": stage["timing_key"], "joint": role,
                                 "clip_count": summary["clip_count"], **joint["direction_counts"],
                                 "common_direction": joint["common_direction"]})


def _report(root: Path, output: Path, loaded: dict, summary: dict, report_ref: dict) -> str:
    relation_names = {"a_shorter": "A較短", "a_longer": "A較長", "identical_exact": "精確時距相同",
                      "touching": "範圍相接", "overlapping": "範圍重疊", "unavailable": "事件不足"}
    direction_names = {"positive": "正", "negative": "負", "zero": "零",
                       "includes_zero": "含零", "unavailable": "未定"}
    lines = [f"# {_text(loaded['pitcher_id'])}：本批單投手動作描述", "",
             f"{summary['clip_count']}球、{summary['source_frames']}格；讀取[原事件報告]({_link(root, output, report_ref)})。",
             "各球保留原格號與分數FPS；事件範圍不取中點，未確認事件不使用候選位置。",
             "此處共同方向只描述模型XY端點差，不代表整段單調變化、真實解剖角度或動作品質。", "",
             "## 各球來源", "", "| 球 | FPS | 格數 | 原片 | 人工事件 |", "|---|---|---:|---|---|"]
    for clip in loaded["clips"]:
        refs = clip["source_refs"]
        lines.append(f"| {_text(clip['pitch_id'])} | {clip['fps_fraction']} | {clip['frame_count']} | "
                     f"[MP4]({_link(root, output, refs['video_ref'])}) | "
                     f"[GT]({_link(root, output, refs['ground_truth_ref'])}) |")
    lines += ["", "## 已確認時距涵蓋範圍", "",
              "下表是本批已確認界線的最小下界至最大上界，不是平均、信賴區間或投手整體變異。",
              "| 區段 | 已確認球數 | 秒數範圍 | 事件未定球 |", "|---|---:|---|---|"]
    for stage in summary["stages"]:
        lines.append(f"| {TIMING_LABELS[stage['timing_key']]} | {len(stage['timing_available_clip_ids'])} | "
                     f"{_display(stage['timing_envelope_seconds_fraction'])} | "
                     f"{_text(', '.join(stage['timing_unavailable_clip_ids']) or '無')} |")
    lines += ["", "## 同投手全部球對", "",
              "A−B以各球原FPS換成精確分數秒計算；顯示小數不參與關係判斷。",
              "球對共用影片，不能當成獨立統計樣本；極小算術差也不代表人體事件計時精度。",
              "| 區段 | A球 | B球 | 關係 | A−B秒數 | 未定原因 |", "|---|---|---|---|---|---|"]
    for stage in summary["stages"]:
        for pair in stage["timing_pairs"]:
            reasons = "; ".join(f"{side.upper()}: {reason}" for side, reason in pair["unavailable_reasons"].items() if reason)
            lines.append(f"| {TIMING_LABELS[stage['timing_key']]} | {_text(pair['a_pitch_id'])} | "
                         f"{_text(pair['b_pitch_id'])} | {relation_names[pair['relation']]} | "
                         f"{_display(pair['delta_seconds_bounds_fraction'])} | {_text(reasons)} |")
    if summary["clip_count"] == 1:
        lines += ["", "本批只有一球，沒有跨球配對，也不能據此推論跨球穩定性。"]
    lines += ["", "## 肘／膝模型端點差方向", "",
              "共同方向只在全部球皆有讀值且同為正／負／零時列出；空值不當成零。",
              "| 區段 | 關節 | 正 | 負 | 零 | 含零 | 未定 | 全部球共同方向 |", "|---|---|---|---|---|---|---|---|"]
    for stage in summary["stages"]:
        for role, joint in stage["joints"].items():
            ids = [_text(', '.join(joint['clip_ids_by_direction'][d]) or '無') for d in DIRECTIONS]
            common = direction_names.get(joint["common_direction"], "無")
            lines.append(f"| {TIMING_LABELS[stage['timing_key']]} | {role} | " + " | ".join(ids) + f" | {common} |")
    lines += ["", "## 各球端點差與缺值", "",
              "| 區段 | 球 | 關節 | 最小／最大差（度） | 可算／全部配對 | 事件狀態 | 缺座標配對 | 退化配對 |",
              "|---|---|---|---|---|---|---|---|"]
    for stage in summary["stages"]:
        for role, joint in stage["joints"].items():
            for row in joint["clip_summaries"]:
                bounds = [row['min_delta_deg'], row['max_delta_deg']] if row['calculated_pairs'] else None
                show = lambda value: "未定" if value is None else str(value)
                lines.append(f"| {TIMING_LABELS[stage['timing_key']]} | {_text(row['pitch_id'])} | {role} | "
                             f"{_display(bounds)} | {show(row['calculated_pairs'])}/{show(row['total_pairs'])} | "
                             f"{row['transition_status']} | {show(row['missing_endpoint_pairs'])} | "
                             f"{show(row['degenerate_endpoint_pairs'])} |")
    lines += ["", "完整JSON保留每一事件端點配對及未定原因；CSV空格表示未定，不是零。",
              "關節摘要可算只要求至少一組端點有保存讀值，不表示所有候選端點可算或關節可信。",
              "共用事件的各段極值不能相加成單一路徑；缺座標與退化配對可能重疊計數。",
              "沒有新增推論、追蹤或人工標註。逐點可靠性仍unknown，usable_for_analysis仍null。",
              "此描述不是正式pitcher-profile-v1、標準動作、3D生物力學、品質分數或排名；不提升reference資格或Phase狀態。"]
    return "\n".join(lines) + "\n"


def write_descriptive_profile(root: str | Path, event_report_json: str | Path,
                              output: str | Path) -> dict:
    """Bind saved report, original sources and manual stages before fresh export."""
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Descriptive profile output must be inside this project's analysis_results")
    if output.exists():
        raise FileExistsError("Descriptive profile output already exists")
    loaded, report_ref = _load_report(root, event_report_json, output)
    payload = read_json(root / report_ref["path"])
    expected = [{"pitch_id": clip["pitch_id"], **stage} for clip in loaded["clips"]
                for stage in describe_manual_event_transitions(clip)]
    if payload.get("manual_stage_readouts") != expected:
        raise ValueError("Saved manual stage readouts differ from their bound sources")
    summary = summarize_profile(loaded["clips"])
    refs = [report_ref, *loaded["source_refs"]]
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    report = _report(root, output, loaded, summary, report_ref)
    output.mkdir(parents=True, exist_ok=False)
    _write_csvs(output, summary)
    with (output / "report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(report)
    for ref in refs:
        reader.path(ref)
    result = {
        "schema_version": "native-descriptive-pitcher-profile-v1", "status": "descriptive_profile_created",
        "scope": "same_pitcher_manual_timing_and_model_xy_endpoints", "pitcher_id": loaded["pitcher_id"],
        "summary": summary,
        "clips": [{k: deepcopy(v) for k, v in clip.items() if k not in {"rows", "overlay_url"}}
                  for clip in loaded["clips"]],
        "source_ref": report_ref, "source_refs": refs,
        "artifacts": {name: reference(root, output / name)
                      for name in ("report.md", "timing_relations.csv", "joint_direction_summary.csv")},
        "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
        "pointwise_reliability": "unknown", "quality_status": "not_calibrated", "usable_for_analysis": None,
        "formal_reference_promotion": False,
    }
    write_json(output / "profile.json", result)
    return result
