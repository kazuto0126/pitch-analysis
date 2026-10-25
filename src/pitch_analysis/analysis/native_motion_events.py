"""Describe saved curves at existing manual events without predicting events or pose."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import csv
from fractions import Fraction
import os
from pathlib import Path
from urllib.parse import quote

from .native_motion_viewer import _load_export, _path
from .native_motion_transition import describe_event_transition, describe_manual_event_transitions
from ..ground_truth import EVENT_NAMES, validate_ground_truth
from ..native_pose_io import BoundReader, read_json, reference, write_json


ROLES = ("throwing_elbow", "lead_knee")
TIMING_PAIRS = {
    "preparation_to_leg_lift": ("preparation_start", "leg_lift"),
    "leg_lift_to_foot_plant": ("leg_lift", "foot_plant"),
    "foot_plant_to_release": ("foot_plant", "approximate_release"),
    "release_to_follow_through_end": ("approximate_release", "follow_through_end"),
}
EVENT_LABELS = dict(zip(EVENT_NAMES, ("準備／啟動", "最高抬腿", "前腳落地", "大致出手", "收尾結束"), strict=True))
TIMING_LABELS = dict(zip(TIMING_PAIRS, ("啟動→最高抬腿", "最高抬腿→落地", "落地→出手", "出手→收尾"), strict=True))


def _angle_window(event: dict, rows: list[dict], role: str) -> dict:
    result = {"status": "unavailable", "total_frames": None, "calculated_frames": None,
              "missing_frames": None, "degenerate_frames": None, "min_deg": None,
              "max_deg": None, "usable_deg": None, "reading_kind": "event_unresolved",
              "sample_span_deg": None, "sample_span_scope": "not_assessable"}
    if event["status"] != "annotated" or event["frame_bounds"] is None:
        return result
    start, end = event["frame_bounds"]
    window = rows[start:end + 1]
    statuses = [row[f"{role}_coordinate_status"] for row in window]
    values = [row[f"{role}_model_xy_deg"] for row in window
              if row[f"{role}_coordinate_status"] == "calculated_from_model_xy"]
    result.update(status="descriptive_model_xy_window", total_frames=len(window),
                  calculated_frames=len(values), missing_frames=statuses.count("missing_coordinates"),
                  degenerate_frames=statuses.count("degenerate_geometry"),
                  min_deg=min(values) if values else None, max_deg=max(values) if values else None,
                  reading_kind="single_frame" if len(window) == 1 else "multiple_frames")
    if len(window) > 1 and len(values) >= 2:
        result.update(sample_span_deg=max(values)-min(values),
                      sample_span_scope="complete_window" if len(values) == len(window) else "calculated_samples_only")
    return result


def describe_events(events: dict, fps: Fraction, rows: list[dict]) -> dict:
    """Retain manual event uncertainty and compute conservative interval durations.

    Window extrema summarize all saved model-XY samples, not human angles or
    reliability. Neither an event midpoint nor an inferred event is introduced.
    """
    fps = Fraction(fps)
    if fps <= 0 or not rows or [row["frame_index"] for row in rows] != list(range(len(rows))):
        raise ValueError("Events require positive fractional FPS and a complete source timeline")
    if not isinstance(events, dict) or set(events) != set(EVENT_NAMES):
        raise ValueError("Events require the existing five ground-truth-v1 event names")
    normalized = {}
    for name in EVENT_NAMES:
        raw = events[name]
        if not isinstance(raw, dict) or raw.get("status") not in {"annotated", "uncertain", "not_observable", "not_visible"}:
            raise ValueError("Events must retain explicit manual status")
        item = deepcopy(raw)
        index, interval = raw.get("frame_index"), raw.get("frame_range")
        if index is not None and interval is not None:
            raise ValueError("An event cannot be both an exact frame and a range")
        bounds = ([index, index] if index is not None else
                  [interval["start_frame"], interval["end_frame"]] if interval is not None else None)
        if bounds is not None and (any(type(value) is not int for value in bounds)
                                   or not 0 <= bounds[0] <= bounds[1] < len(rows)):
            raise ValueError("Event frame bounds are outside the saved timeline")
        status = raw["status"]
        if status == "annotated" and bounds is None:
            raise ValueError("An annotated event requires a frame or range")
        if status in {"not_observable", "not_visible"} and bounds is not None:
            raise ValueError("Unobservable events cannot acquire a guessed position")
        if status != "annotated" and index is not None:
            raise ValueError("Uncertain events cannot acquire an exact frame")
        marker = ("exact" if index is not None else "range") if status == "annotated" else (
            "uncertain" if status == "uncertain" else "not_observable")
        item.update(frame_index=index, frame_range=deepcopy(interval), confidence=raw.get("confidence"),
                    frame_bounds=bounds, marker_kind=marker,
                    time_bounds_sec=[float(Fraction(value) / fps) for value in bounds] if bounds else None)
        item["angle_windows"] = {role: _angle_window(item, rows, role) for role in ROLES}
        normalized[name] = item

    timing = {}
    for key, (start_name, end_name) in TIMING_PAIRS.items():
        start, end = normalized[start_name], normalized[end_name]
        result = {"start_event": start_name, "end_event": end_name, "status": "unavailable",
                  "frame_bounds": None, "seconds_bounds": None, "seconds_bounds_fraction": None,
                  "reason": ""}
        status_labels = {"uncertain": "不確定", "not_observable": "不可觀測", "not_visible": "不可見"}
        unavailable = [f"{EVENT_LABELS[name]}：{status_labels[item['status']]}" for name, item in ((start_name, start), (end_name, end))
                       if item["status"] != "annotated"]
        if unavailable:
            result["reason"] = "; ".join(unavailable)
        else:
            a0, a1 = start["frame_bounds"]
            b0, b1 = end["frame_bounds"]
            if b1 < a0:
                raise ValueError("Event ranges do not admit chronological order")
            bounds = [max(0, b0 - a1), b1 - a0]
            seconds = [Fraction(value) / fps for value in bounds]
            result.update(status="exact" if bounds[0] == bounds[1] else "bounded",
                          frame_bounds=bounds, seconds_bounds=[float(value) for value in seconds],
                          seconds_bounds_fraction=[str(value) for value in seconds],
                          reason="依人工事件上下界計算；未取中點或推測事件")
        timing[key] = result
    return {"events": normalized, "timing": timing}


def _bounds_text(bounds: list | None, *, decimals: int | None = None) -> str:
    if bounds is None:
        return "—"
    values = [str(value) if decimals is None else f"{value:.{decimals}f}" for value in bounds]
    return values[0] if values[0] == values[1] else "–".join(values)


def _review_scope(root: Path, entry: dict, gt: dict, video_ref: dict) -> dict:
    """Accept full GT or an explicit, source-bound completion of just its events.

    The checkpoint records review scope, not a second set of event values. Its
    recording time must never replace the GT's unfinished full-review timestamp.
    """
    provenance = gt["provenance"]
    if "event_review_ref" not in entry:
        if gt["annotation_status"] != "reviewed":
            raise ValueError("Events require reviewed ground truth or a completed event review checkpoint")
        return {"kind": "full_ground_truth", "events_complete": True,
                "full_pose_gt_complete": True, "annotation_status": "reviewed",
                "reviewer": provenance["reviewer"], "recorded_at_utc": provenance["reviewed_at_utc"]}

    reader = BoundReader(root, [entry["event_review_ref"], entry["ground_truth_ref"], video_ref])
    checkpoint = reader.json(entry["event_review_ref"])
    scope = checkpoint.get("review_scope")
    if (checkpoint.get("schema_version") != "manual-event-review-checkpoint-v1"
            or gt["annotation_status"] != "in_progress"
            or checkpoint.get("events_complete") is not True
            or checkpoint.get("full_pose_gt_complete") is not False
            or not isinstance(scope, list) or len(scope) != len(EVENT_NAMES)
            or any(not isinstance(name, str) for name in scope)
            or set(scope) != set(EVENT_NAMES)
            or checkpoint.get("pitch_id") != entry["pitch_id"]
            or checkpoint.get("reviewer") != provenance["reviewer"]
            or type(checkpoint.get("non_event_labels_filled")) is not int
            or checkpoint["non_event_labels_filled"] != 0):
        raise ValueError("Event checkpoint must confirm only the complete five-event scope and matching reviewer")
    if (checkpoint.get("ground_truth_ref") != entry["ground_truth_ref"]
            or checkpoint.get("source_video_ref") != video_ref):
        raise ValueError("Event checkpoint must bind the exact current ground truth and source video")
    recorded = checkpoint.get("recorded_at_utc")
    try:
        if not isinstance(recorded, str) or datetime.fromisoformat(recorded).utcoffset() is None:
            raise ValueError
    except ValueError as error:
        raise ValueError("Event checkpoint requires a timezone-aware recording timestamp") from error
    reader.path(checkpoint["ground_truth_ref"])
    reader.path(checkpoint["source_video_ref"])
    return {"kind": "event_only", "events_complete": True,
            "full_pose_gt_complete": False, "annotation_status": gt["annotation_status"],
            "reviewer": provenance["reviewer"], "recorded_at_utc": recorded}


def _readout_text(window: dict) -> str:
    if window["total_frames"] is None:
        return "事件未確認；未估角度"
    if window["reading_kind"] == "single_frame":
        return "單格視窗；時間敏感度未評估"
    if window["sample_span_deg"] is None:
        return "多格視窗；跨度未估"
    scope = "窗內模型跨度" if window["sample_span_scope"] == "complete_window" else "可計算樣本跨度（視窗不完整）"
    return f"{scope} {window['sample_span_deg']:.1f}°；可用性未知"


def _report(clips: list[dict], transitions: list[dict] | None = None,
            manual_stages: list[dict] | None = None) -> str:
    lines = ["# 同投手人工事件與2D曲線時序摘要", "",
             "沿用既有人工事件及保存的模型XY曲線；沒有重新推論、猜事件或修改人工標註。",
             "範圍保留上下界，不確定候選不參與時距計算。秒數按原片分數FPS換算。", "",
             "## 逐球時距", "", "| 影片 | 時距 | 狀態 | 格數範圍 | 秒數範圍 |",
             "|---|---|---|---:|---:|"]
    for clip in clips:
        for key, item in clip["timing"].items():
            lines.append(f"| {clip['pitch_id']} | {TIMING_LABELS[key]} | {item['status']} | "
                         f"{_bounds_text(item['frame_bounds'])} | {_bounds_text(item['seconds_bounds'], decimals=3)} |")
    if manual_stages is not None:
        lines += ["", "## 人工事件四段動作讀值", "",
                  "各段共用中間人工事件，獨立的差值上下界不能直接相加成一套動作；同一事件必須選用一致影格。",
                  "以下僅描述人工事件之間的模型端點差，未自動判定投球階段。"]
        titles = ("啟動→最高抬腿的模型XY變化", "最高抬腿→落地的模型XY變化",
                  "落地→大致出手的模型XY變化", "大致出手→收尾的模型XY變化")
        groups = [(title, [item for item in manual_stages if item["transition_key"] == key], "manual_stage_pairs.csv")
                  for key, title in zip(TIMING_PAIRS, titles, strict=True)]
    else:
        groups = [] if transitions is None else [("落地→大致出手的模型XY變化", transitions, "event_transition_pairs.csv")]
    for title, group, pairs_file in groups:
        directions = {"positive": "全為正", "negative": "全為負", "zero": "皆為0",
                      "includes_zero": "包含0", "unavailable": "未計算"}
        lines += ["", f"## {title}", "",
                  "變化量＝終點模型角度−起點模型角度。保留人工範圍內所有時間先後成立的影格配對，不取中點。",
                  "這是端點差，不能當作期間最大活動範圍、真實關節伸屈或動作品質。", "",
                  "| 影片 | 關節 | 端點變化量（度） | 符號 | 計算／合法配對 | 不可計算 | 缺點端／退化端配對 |",
                  "|---|---|---:|---|---|---|---|"]
        for transition in group:
            for role, label in (("throwing_elbow", "投球肘"), ("lead_knee", "前導膝")):
                joint = transition["joints"][role]
                low, high = joint["min_delta_deg"], joint["max_delta_deg"]
                value = "—" if low is None else (f"{low:+.1f}" if low == high else f"{low:+.1f} 至 {high:+.1f}")
                count = "—" if joint["total_pairs"] is None else f"{joint['calculated_pairs']}/{joint['total_pairs']}"
                unavailable = "—" if joint["unavailable_pairs"] is None else str(joint["unavailable_pairs"])
                missing = "—" if joint["total_pairs"] is None else f"{joint['missing_endpoint_pairs']}/{joint['degenerate_endpoint_pairs']}"
                lines.append(f"| {transition['pitch_id']} | {label} | {value} | {directions[joint['delta_direction']]} | {count} | {unavailable} | {missing} |")
        lines += ["", "缺點端與退化端配對數可重疊；不可計算數為聯集，計算數＋不可計算數＝合法配對總數。",
                  "同一影格可出現在多個候選配對中，配對數不是獨立樣本數或機率；各球原時距與來源仍列於本報告。",
                  f"完整配對含原格號、分數時間、兩端狀態與差值，另存{pairs_file}。"]
    lines += ["", "## 事件與來源", ""]
    for clip in clips:
        lines += [f"### {clip['pitch_id']}", "", f"來源影格：{clip['frame_count']}；FPS：{clip['fps_fraction']}。", "",
                  "| 事件 | 人工狀態 | 影格／候選範圍 | 秒數／候選範圍 |", "|---|---|---:|---:|"]
        for name, event in clip["events"].items():
            lines.append(f"| {EVENT_LABELS[name]} | {event['status']} | {_bounds_text(event['frame_bounds'])} | "
                         f"{_bounds_text(event['time_bounds_sec'], decimals=3)} |")
        lines += ["", "#### 事件角度讀值（模型XY）", "",
                  "| 事件 | 關節 | min–max（度） | 讀值範圍 | 計算／總格數 | 缺失／退化 |",
                  "|---|---|---:|---|---|---|"]
        for name, event in clip["events"].items():
            for role, label in (("throwing_elbow", "投球肘"), ("lead_knee", "前導膝")):
                window = event["angle_windows"][role]
                values = [window["min_deg"], window["max_deg"]]
                text = _bounds_text(values, decimals=1) if all(value is not None for value in values) else "—"
                count = f"{window['calculated_frames']}/{window['total_frames']}" if window["total_frames"] is not None else "—"
                missing = f"{window['missing_frames']}/{window['degenerate_frames']}" if window["total_frames"] is not None else "—"
                lines.append(f"| {EVENT_LABELS[name]} | {label} | {text} | {_readout_text(window)} | {count} | {missing} |")
        lines.append("")
        for name, event in clip["events"].items():
            note = str(event.get("note", "")).replace("\n", " ")
            if note:
                lines.append(f"- {EVENT_LABELS[name]}：{note}")
        lines += ["", f"人工來源：`{clip['source_refs']['ground_truth_ref']['path']}`。"]
        if clip["event_review_scope"]["kind"] == "event_only":
            lines += ["本球只完成五事件覆核；完整pose GT仍為in_progress，其他欄位沒有補填。",
                      f"事件完成紀錄：`{clip['source_refs']['event_review_ref']['path']}`。"]
        lines.append("")
    lines += ["## 解讀限制", "",
              "事件取自同一原片的ground-truth-v1，只讀事件，不把舊模型關節品質標籤套到新骨架。",
              "事件區間的角度最小／最大值包含所有可計算模型樣本；缺值與退化樣本另計，沒有品質篩選。",
              "單格視窗不估時間敏感度；多格跨度只是模型讀值變動，部分視窗只描述可計算樣本，不視為完整範圍。",
              "這是2D模型投影與逐球節奏描述，沒有動作品質評分、3D推論、跨投手比較或精確出手對齊。",
              "逐點可靠性unknown，可用角度／usable_for_analysis仍null；不改Phase2或Phase3整體驗收。", ""]
    return "\n".join(lines)


def load_event_clips(root: str | Path, config_path: str | Path, output: str | Path) -> dict:
    """Validate saved curves and manual event scope without writing or inference."""
    root = Path(root).resolve(strict=True)
    request_path = _path(root, config_path)
    request_ref = reference(root, request_path)
    config = read_json(request_path)
    if (set(config) != {"schema_version", "pitcher_id", "clips"}
            or config["schema_version"] != "native-motion-events-request-v1"
            or not isinstance(config["pitcher_id"], str) or not config["pitcher_id"]
            or not isinstance(config["clips"], list) or not config["clips"]):
        raise ValueError("Event comparison requires a single-pitcher saved-motion request")
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Event comparison output must be inside this project's analysis_results")
    if output.exists():
        raise FileExistsError("Event comparison output already exists")
    clips, identities, source_refs = [], set(), [request_ref]
    for entry in config["clips"]:
        required = {"pitch_id", "motion_dir", "ground_truth_ref"}
        if not isinstance(entry, dict) or set(entry) not in (required, required | {"event_review_ref"}):
            raise ValueError("Each clip requires exact motion and ground truth references")
        summary, rows, motion_refs = _load_export(root, _path(root, entry["motion_dir"]))
        pid = summary["pitch_id"]
        if entry["pitch_id"] != pid or summary["pitcher_id"] != config["pitcher_id"]:
            raise ValueError("Motion clip or pitcher differs from the request")
        if pid in identities:
            raise ValueError("Duplicate pitch identity in event comparison")
        identities.add(pid)
        gt_reader = BoundReader(root, [entry["ground_truth_ref"]])
        gt = gt_reader.json(entry["ground_truth_ref"])
        video = root / summary["source_refs"]["video_ref"]["path"]
        validate_ground_truth(gt, source_video_path=video)
        source = gt["source_video"]
        if (source["pitch_id"] != pid
                or source["total_frames"] != len(rows) or source["frame_index_base"] != 0
                or source["sha256"] != summary["source_refs"]["video_ref"]["sha256"]):
            raise ValueError("Events require ground truth for the exact saved source timeline")
        scope = _review_scope(root, entry, gt, summary["source_refs"]["video_ref"])
        info = describe_events(gt["labels"]["events"], Fraction(summary["timebase"]["fps_fraction"]), rows)
        overlay = root / summary["source_refs"]["overlay_ref"]["path"]
        refs = {**motion_refs, "ground_truth_ref": entry["ground_truth_ref"],
                "video_ref": summary["source_refs"]["video_ref"],
                "overlay_ref": summary["source_refs"]["overlay_ref"]}
        if "event_review_ref" in entry:
            refs["event_review_ref"] = entry["event_review_ref"]
        source_refs.extend(refs.values())
        clips.append({"pitch_id": pid, "frame_count": len(rows),
                      "fps_fraction": summary["timebase"]["fps_fraction"], "rows": rows,
                      "overlay_url": quote(os.path.relpath(overlay, output / "viewer").replace("\\", "/"), safe="/."),
                      **info, "source_refs": refs, "event_reviewer": deepcopy(gt["provenance"]),
                      "event_review_scope": scope,
                      "pointwise_reliability": "unknown", "usable_for_analysis": None})
    reader = BoundReader(root, source_refs)
    for ref in source_refs:
        reader.path(ref)
    return {"root": root, "output": output, "clips": clips, "source_refs": source_refs,
            "pitcher_id": config["pitcher_id"], "request_ref": request_ref}


def write_event_comparison(root: str | Path, config_path: str | Path, output: str | Path) -> dict:
    """Read bound saved curves and existing manual events into a fresh comparison."""
    loaded = load_event_clips(root, config_path, output)
    root, output, clips = loaded["root"], loaded["output"], loaded["clips"]
    source_refs = loaded["source_refs"]
    transitions = [{"pitch_id": clip["pitch_id"], **describe_event_transition(clip)} for clip in clips]
    manual_stages = [{"pitch_id": clip["pitch_id"], **stage} for clip in clips
                     for stage in describe_manual_event_transitions(clip)]
    reader = BoundReader(root, source_refs)
    output.mkdir(parents=True, exist_ok=False)
    from .native_motion_event_viewer import write_event_viewer
    viewer = write_event_viewer(root, clips, output / "viewer")
    fields = ("pitch_id", "fps_fraction", "timing", "status", "min_frames", "max_frames",
              "min_seconds", "max_seconds", "reason")
    with (output / "event_timing.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for clip in clips:
            for key, item in clip["timing"].items():
                frames, seconds = item["frame_bounds"] or [None, None], item["seconds_bounds"] or [None, None]
                writer.writerow(dict(zip(fields, (clip["pitch_id"], clip["fps_fraction"], key, item["status"],
                                                  *frames, *seconds, item["reason"]), strict=True)))
    readout_fields = ("pitch_id", "event", "joint", "event_status", "frame_start", "frame_end",
                      "total_frames", "calculated_frames", "missing_frames", "degenerate_frames",
                      "min_deg", "max_deg", "reading_kind", "sample_span_deg", "sample_span_scope",
                      "pointwise_reliability", "usable_for_analysis", "confidence", "note")
    with (output / "event_angle_readouts.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=readout_fields)
        writer.writeheader()
        for clip in clips:
            for name, event in clip["events"].items():
                for role, window in event["angle_windows"].items():
                    bounds = event["frame_bounds"] or [None, None]
                    writer.writerow({"pitch_id": clip["pitch_id"], "event": name, "joint": role,
                                     "event_status": event["status"], "frame_start": bounds[0], "frame_end": bounds[1],
                                     **{key: window[key] for key in readout_fields[6:15]},
                                     "pointwise_reliability": "unknown", "usable_for_analysis": None,
                                     "confidence": event.get("confidence"), "note": event.get("note", "")})
    transition_fields = ("pitch_id", "joint", "start_event", "end_event", "status",
                         "start_frame_min", "start_frame_max", "end_frame_min", "end_frame_max",
                         "all_endpoint_pairs", "chronological_pairs", "excluded_nonchronological_pairs",
                         "total_pairs", "calculated_pairs", "unavailable_pairs", "missing_endpoint_pairs",
                         "degenerate_endpoint_pairs", "min_delta_deg", "max_delta_deg", "delta_direction",
                         "pointwise_reliability", "usable_for_analysis", "reason")
    pair_fields = ("pitch_id", "joint", "start_event", "end_event", "start_frame", "end_frame",
                   "elapsed_frames", "elapsed_seconds", "elapsed_seconds_fraction",
                   "start_model_xy_deg", "end_model_xy_deg", "start_coordinate_status", "end_coordinate_status",
                   "delta_model_xy_deg", "status", "pointwise_reliability", "usable_for_analysis")
    exports = (("event_transition_readouts.csv", "event_transition_pairs.csv", transitions, ()),
               ("manual_stage_readouts.csv", "manual_stage_pairs.csv", manual_stages, ("transition_key",)))
    for summary_file, pairs_file, items, extra in exports:
        with (output / summary_file).open("x", encoding="utf-8-sig", newline="") as stream, \
             (output / pairs_file).open("x", encoding="utf-8-sig", newline="") as pair_stream:
            writer = csv.DictWriter(stream, fieldnames=(*extra, *transition_fields))
            pair_writer = csv.DictWriter(pair_stream, fieldnames=(*extra, *pair_fields))
            writer.writeheader()
            pair_writer.writeheader()
            for transition in items:
                base = {key: transition[key] for key in (*extra, "pitch_id", "start_event", "end_event")}
                first, last = transition["start_frame_bounds"] or [None, None], transition["end_frame_bounds"] or [None, None]
                for role, joint in transition["joints"].items():
                    writer.writerow({**base, "joint": role, "status": transition["status"],
                                     "start_frame_min": first[0], "start_frame_max": first[1],
                                     "end_frame_min": last[0], "end_frame_max": last[1],
                                     **{key: transition[key] for key in transition_fields[9:12]},
                                     **{key: joint[key] for key in transition_fields[12:22]}, "reason": transition["reason"]})
                    for pair in joint["pairs"]:
                        pair_writer.writerow({**base, "joint": role, **pair,
                                              "pointwise_reliability": "unknown", "usable_for_analysis": None})
    with (output / "report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_report(clips, transitions, manual_stages))
    for ref in source_refs:
        reader.path(ref)
    result = {"schema_version": "native-motion-event-comparison-v1", "status": "event_comparison_created",
              "pitcher_id": loaded["pitcher_id"], "clip_count": len(clips),
              "source_frames": sum(clip["frame_count"] for clip in clips),
              "event_transition_readouts": transitions,
              "manual_stage_readouts": manual_stages,
              "clips": [{key: value for key, value in clip.items() if key not in {"rows", "overlay_url"}}
                        for clip in clips],
              "source_refs": {"request_ref": loaded["request_ref"]}, "viewer": viewer,
              "artifacts": {"timing_csv_ref": reference(root, output / "event_timing.csv"),
                            "angle_readouts_csv_ref": reference(root, output / "event_angle_readouts.csv"),
                            "transition_readouts_csv_ref": reference(root, output / "event_transition_readouts.csv"),
                            "transition_pairs_csv_ref": reference(root, output / "event_transition_pairs.csv"),
                            "manual_stage_readouts_csv_ref": reference(root, output / "manual_stage_readouts.csv"),
                            "manual_stage_pairs_csv_ref": reference(root, output / "manual_stage_pairs.csv"),
                            "report_ref": reference(root, output / "report.md")},
              "angle_values_recomputed": False, "event_midpoints_selected": False,
              "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "pointwise_reliability": "unknown", "quality_status": "not_calibrated", "usable_for_analysis": None,
              "exact_event_alignment": False, "cross_pitcher_comparison": False}
    write_json(output / "event_comparison.json", result)
    return result
