"""Compare source-bound manual event durations without comparing pose quality."""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
import os
from pathlib import Path
from urllib.parse import quote

from .native_motion_events import TIMING_LABELS, TIMING_PAIRS, load_event_clips
from .native_motion_viewer import _path
from ..native_pose_io import BoundReader, read_json, reference, write_json


def _duration(timing: dict, fps: str | int | Fraction) -> list[Fraction] | None:
    if isinstance(fps, bool) or not isinstance(fps, (str, int, Fraction)):
        raise ValueError("Use fractional FPS, not floating-point FPS")
    try:
        rate = Fraction(fps)
    except (ValueError, ZeroDivisionError) as error:
        raise ValueError("FPS must be a positive fraction") from error
    if rate <= 0:
        raise ValueError("FPS must be a positive fraction")
    if not isinstance(timing, dict):
        raise ValueError("Expected a source timing record")
    status, bounds = timing.get("status"), timing.get("frame_bounds")
    if status == "unavailable":
        if bounds is not None:
            raise ValueError("Unavailable timing cannot use candidate frame bounds")
        return None
    if (status not in {"exact", "bounded"} or not isinstance(bounds, list)
            or len(bounds) != 2 or any(type(v) is not int for v in bounds)
            or not 0 <= bounds[0] <= bounds[1]
            or (status == "exact") != (bounds[0] == bounds[1])):
        raise ValueError("Timing requires consistent nonnegative integer frame bounds")
    return [Fraction(v) / rate for v in bounds]


def compare_timing_intervals(timing_a: dict, fps_a: str | int | Fraction,
                             timing_b: dict, fps_b: str | int | Fraction) -> dict:
    """Describe A minus B using exact seconds and all admitted event choices.

    Ordering is conditional on the supplied manual bounds. It does not estimate
    annotation error, significance, timing accuracy or a pitcher's performance.
    """
    a, b = _duration(timing_a, fps_a), _duration(timing_b, fps_b)
    result = {
        "status": "unavailable", "relation": "unavailable",
        "a_seconds_bounds_fraction": [str(v) for v in a] if a is not None else None,
        "b_seconds_bounds_fraction": [str(v) for v in b] if b is not None else None,
        "delta_seconds_bounds_fraction": None, "delta_seconds_bounds": None,
        "unavailable_reasons": {
            "a": (timing_a.get("reason") or "Manual event timing unavailable") if a is None else None,
            "b": (timing_b.get("reason") or "Manual event timing unavailable") if b is None else None,
        },
    }
    if a is None or b is None:
        return result
    delta = [a[0] - b[1], a[1] - b[0]]
    if a[1] < b[0]:
        relation = "a_shorter"
    elif b[1] < a[0]:
        relation = "a_longer"
    elif a[0] == a[1] == b[0] == b[1]:
        relation = "identical_exact"
    elif a[1] == b[0] or b[1] == a[0]:
        relation = "touching"
    else:
        relation = "overlapping"
    result.update(status="descriptive_manual_timing", relation=relation,
                  delta_seconds_bounds_fraction=[str(v) for v in delta],
                  delta_seconds_bounds=[float(v) for v in delta])
    return result


def _load_report(root: Path, path: str | Path, output: Path) -> tuple[dict, dict]:
    path = _path(root, path)
    payload = read_json(path)
    if (payload.get("schema_version") != "native-motion-event-comparison-v1"
            or payload.get("status") != "event_comparison_created"):
        raise ValueError("Timing comparison requires an existing native event report")
    request_ref = payload["source_refs"]["request_ref"]
    reader = BoundReader(root, [request_ref])
    loaded = load_event_clips(root, reader.path(request_ref), output)
    expected = [{k: v for k, v in clip.items() if k not in {"rows", "overlay_url"}}
                for clip in loaded["clips"]]
    if (payload.get("pitcher_id") != loaded["pitcher_id"]
            or payload.get("clip_count") != len(expected)
            or payload.get("clips") != expected):
        raise ValueError("Saved event report differs from its bound manual events or sources")
    return loaded, reference(root, path)


def _text(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def _display(bounds: list | None) -> str:
    if bounds is None:
        return "未定"
    a, b = (float(Fraction(v)) for v in bounds)
    return f"{a:.6f}" if a == b else f"{a:.6f}–{b:.6f}"


def _link(root: Path, output: Path, ref: dict) -> str:
    return quote(os.path.relpath(root / ref["path"], output).replace("\\", "/"), safe="/.")


def write_timing_comparison(root: str | Path, report_paths: list[str | Path],
                            output: str | Path) -> dict:
    """Write an additive two-pitcher timing-only comparison of verified reports."""
    if len(report_paths) != 2:
        raise ValueError("Supply exactly two single-pitcher event reports")
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Timing comparison output must be inside analysis_results")
    if output.exists():
        raise FileExistsError("Timing comparison output already exists")
    sources = [_load_report(root, path, output) for path in report_paths]
    a, b = (source[0] for source in sources)
    if a["pitcher_id"] == b["pitcher_id"]:
        raise ValueError("Use two distinct pitchers; retain the existing same-pitcher entry")
    cohorts, timings, pairs, refs = [], [], [], []
    for side, (loaded, report_ref) in zip(("a", "b"), sources, strict=True):
        refs.extend([report_ref, *loaded["source_refs"]])
        cohorts.append({"side": side, "pitcher_id": loaded["pitcher_id"],
                        "clip_count": len(loaded["clips"]),
                        "source_frames": sum(c["frame_count"] for c in loaded["clips"]),
                        "report_ref": report_ref, "request_ref": loaded["request_ref"]})
        for clip in loaded["clips"]:
            for key, (start, end) in TIMING_PAIRS.items():
                timing = clip["timing"][key]
                duration = _duration(timing, clip["fps_fraction"])
                timings.append({"side": side, "pitcher_id": loaded["pitcher_id"],
                                "pitch_id": clip["pitch_id"], "timing_key": key,
                                "fps_fraction": clip["fps_fraction"], "status": timing["status"],
                                "frame_bounds": deepcopy(timing["frame_bounds"]),
                                "seconds_bounds_fraction": [str(v) for v in duration] if duration is not None else None,
                                "start_event": deepcopy(clip["events"][start]),
                                "end_event": deepcopy(clip["events"][end]),
                                "reason": timing["reason"], "source_refs": deepcopy(clip["source_refs"])})
    for key, (start, end) in TIMING_PAIRS.items():
        for ca in a["clips"]:
            for cb in b["clips"]:
                row = {"timing_key": key}
                for side, loaded, clip in (("a", a, ca), ("b", b, cb)):
                    row.update({f"{side}_pitcher_id": loaded["pitcher_id"],
                                f"{side}_pitch_id": clip["pitch_id"],
                                f"{side}_fps_fraction": clip["fps_fraction"],
                                f"{side}_frame_bounds": deepcopy(clip["timing"][key]["frame_bounds"]),
                                f"{side}_start_event_bounds": deepcopy(clip["events"][start]["frame_bounds"]),
                                f"{side}_end_event_bounds": deepcopy(clip["events"][end]["frame_bounds"]),
                                f"{side}_source_refs": deepcopy(clip["source_refs"])})
                row.update(compare_timing_intervals(ca["timing"][key], ca["fps_fraction"],
                                                    cb["timing"][key], cb["fps_fraction"]))
                pairs.append(row)
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    output.mkdir(parents=True, exist_ok=False)
    with (output / "pitch_timings.csv").open("x", encoding="utf-8", newline="") as stream:
        fields = ["side", "pitcher_id", "pitch_id", "timing_key", "fps_fraction", "status",
                  "min_frames", "max_frames", "min_seconds_fraction", "max_seconds_fraction", "reason"]
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in timings:
            frames, seconds = row["frame_bounds"], row["seconds_bounds_fraction"]
            writer.writerow({**{k: row[k] for k in fields[:6]}, "reason": row["reason"],
                             "min_frames": frames[0] if frames else None, "max_frames": frames[1] if frames else None,
                             "min_seconds_fraction": seconds[0] if seconds else None,
                             "max_seconds_fraction": seconds[1] if seconds else None})
    fields = ["timing_key", "a_pitcher_id", "a_pitch_id", "b_pitcher_id", "b_pitch_id",
              "a_fps_fraction", "b_fps_fraction", "status", "relation",
              "delta_min_seconds_fraction", "delta_max_seconds_fraction",
              "delta_min_seconds", "delta_max_seconds", "a_unavailable_reason", "b_unavailable_reason"]
    fields += [f"{side}_{name}" for side in ("a", "b") for name in (
        "min_frames", "max_frames", "min_seconds_fraction", "max_seconds_fraction", "video_path", "ground_truth_path")]
    with (output / "timing_pairs.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in pairs:
            fractions, seconds = row["delta_seconds_bounds_fraction"], row["delta_seconds_bounds"]
            source_fields = {}
            for side in ("a", "b"):
                frames, duration = row[f"{side}_frame_bounds"], row[f"{side}_seconds_bounds_fraction"]
                source_fields.update({f"{side}_min_frames": frames[0] if frames else None,
                                      f"{side}_max_frames": frames[1] if frames else None,
                                      f"{side}_min_seconds_fraction": duration[0] if duration else None,
                                      f"{side}_max_seconds_fraction": duration[1] if duration else None,
                                      f"{side}_video_path": row[f"{side}_source_refs"]["video_ref"]["path"],
                                      f"{side}_ground_truth_path": row[f"{side}_source_refs"]["ground_truth_ref"]["path"]})
            writer.writerow({**{k: row[k] for k in fields[:9]},
                             **source_fields,
                             "delta_min_seconds_fraction": fractions[0] if fractions else None,
                             "delta_max_seconds_fraction": fractions[1] if fractions else None,
                             "delta_min_seconds": seconds[0] if seconds else None,
                             "delta_max_seconds": seconds[1] if seconds else None,
                             "a_unavailable_reason": row["unavailable_reasons"]["a"],
                             "b_unavailable_reason": row["unavailable_reasons"]["b"]})
    relation_names = {"a_shorter": "A較短", "a_longer": "A較長", "identical_exact": "精確時距相同",
                      "touching": "範圍相接", "overlapping": "範圍重疊", "unavailable": "事件不足"}
    lines = ["# 兩位投手：已標人工事件時距對照", "",
             f"A＝{_text(a['pitcher_id'])}；B＝{_text(b['pitcher_id'])}。差值＝A時距−B時距。",
             "逐片以原格數／分數FPS換算精確秒數；保留範圍、未知與原片事件位置，不取中點。",
             "此處只比較本批人工界線下的時距，沒有比較角度、姿勢相似度、動作品質或排名。",
             "不同FPS的極小算術差不代表人體計時精度；影格粒度及未量測的人工界線誤差仍存在。",
             "球對共用影片，並非獨立樣本；配對計數不是投手整體快慢、機率或統計顯著的證據。", "",
             "## 本批對照數量", "", "| 區段 | 全部 | A較短 | A較長 | 精確相同 | 相接 | 重疊 | 事件不足 |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for key in TIMING_PAIRS:
        rows = [row for row in pairs if row["timing_key"] == key]
        counts = [sum(row["relation"] == relation for row in rows) for relation in relation_names]
        lines.append(f"| {TIMING_LABELS[key]} | {len(rows)} | " + " | ".join(str(v) for v in counts) + " |")
    lines += ["", "## 各球時距（秒）", "", "| 側 | 投手 | 球 | 區段 | 原格數 | FPS | 秒數 |",
              "|---|---|---|---|---|---|---|"]
    for row in timings:
        lines.append(f"| {row['side'].upper()} | {_text(row['pitcher_id'])} | {_text(row['pitch_id'])} | "
                     f"{TIMING_LABELS[row['timing_key']]} | {row['frame_bounds']} | {row['fps_fraction']} | "
                     f"{_display(row['seconds_bounds_fraction'])} |")
    lines += ["", "## 全部球對（差值秒數）", "", "| 區段 | A球 | B球 | 關係 | A−B範圍 | 未定原因 |",
              "|---|---|---|---|---|---|"]
    for row in pairs:
        reasons = "; ".join(f"{side.upper()}: {reason}" for side, reason in row["unavailable_reasons"].items() if reason)
        lines.append(f"| {TIMING_LABELS[row['timing_key']]} | {_text(row['a_pitch_id'])} | {_text(row['b_pitch_id'])} | "
                     f"{relation_names[row['relation']]} | {_display(row['delta_seconds_bounds_fraction'])} | {_text(reasons)} |")
    lines += ["", "## 原片與人工事件來源", "", "| 投手 | 球 | 原片 | 人工事件 |", "|---|---|---|---|"]
    for loaded, _ in sources:
        for clip in loaded["clips"]:
            sr = clip["source_refs"]
            lines.append(f"| {_text(loaded['pitcher_id'])} | {_text(clip['pitch_id'])} | "
                         f"[MP4]({_link(root, output, sr['video_ref'])}) | "
                         f"[GT]({_link(root, output, sr['ground_truth_ref'])}) |")
    lines += ["", "完整JSON保留兩側原事件界線、FPS、來源SHA與未知原因；CSV保留全部球對及空值。",
              "本輸出不修改素材資格、registry、原prediction／GT或Phase驗收狀態。",
              "這不是正式pitcher-comparison-v1結果，逐點可靠性仍unknown、usable_for_analysis仍null。"]
    with (output / "report.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    for ref in refs:
        reader.path(ref)
    available = sum(row["status"] != "unavailable" for row in pairs)
    result = {"schema_version": "native-manual-timing-comparison-v1", "status": "timing_comparison_created",
              "scope": "recorded_manual_event_durations_only", "cohorts": cohorts,
              "pitch_timings": timings, "pairs": pairs, "total_pairs": len(pairs),
              "comparable_pairs": available, "unavailable_pairs": len(pairs) - available,
              "source_refs": refs,
              "artifacts": {name: reference(root, output / name)
                            for name in ("pitch_timings.csv", "timing_pairs.csv", "report.md")},
              "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "angle_comparison_performed": False, "cross_pitcher_comparison": True,
              "pointwise_reliability": "unknown", "quality_status": "not_calibrated", "usable_for_analysis": None}
    write_json(output / "timing_comparison.json", result)
    return result
