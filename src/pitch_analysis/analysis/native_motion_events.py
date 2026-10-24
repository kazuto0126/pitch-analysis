"""Describe saved curves at existing manual events without predicting events or pose."""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
import os
from pathlib import Path
from urllib.parse import quote

from .native_motion_viewer import _load_export, _path
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
              "max_deg": None, "usable_deg": None}
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
                  min_deg=min(values) if values else None, max_deg=max(values) if values else None)
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


def _report(clips: list[dict]) -> str:
    lines = ["# 同投手人工事件與2D曲線時序摘要", "",
             "沿用既有人工事件及保存的模型XY曲線；沒有重新推論、猜事件或修改人工標註。",
             "範圍保留上下界，不確定候選不參與時距計算。秒數按原片分數FPS換算。", "",
             "## 逐球時距", "", "| 影片 | 時距 | 狀態 | 格數範圍 | 秒數範圍 |",
             "|---|---|---|---:|---:|"]
    for clip in clips:
        for key, item in clip["timing"].items():
            lines.append(f"| {clip['pitch_id']} | {TIMING_LABELS[key]} | {item['status']} | "
                         f"{_bounds_text(item['frame_bounds'])} | {_bounds_text(item['seconds_bounds'], decimals=3)} |")
    lines += ["", "## 事件與來源", ""]
    for clip in clips:
        lines += [f"### {clip['pitch_id']}", "", f"來源影格：{clip['frame_count']}；FPS：{clip['fps_fraction']}。", "",
                  "| 事件 | 人工狀態 | 影格／候選範圍 | 秒數／候選範圍 |", "|---|---|---:|---:|"]
        for name, event in clip["events"].items():
            lines.append(f"| {EVENT_LABELS[name]} | {event['status']} | {_bounds_text(event['frame_bounds'])} | "
                         f"{_bounds_text(event['time_bounds_sec'], decimals=3)} |")
        for name, event in clip["events"].items():
            note = str(event.get("note", "")).replace("\n", " ")
            if note:
                lines.append(f"- {EVENT_LABELS[name]}：{note}")
        lines += ["", f"人工來源：`{clip['source_refs']['ground_truth_ref']['path']}`。", ""]
    lines += ["## 解讀限制", "",
              "事件取自同一原片的ground-truth-v1，只讀事件，不把舊模型關節品質標籤套到新骨架。",
              "事件區間的角度最小／最大值包含所有可計算模型樣本；缺值與退化樣本另計，沒有品質篩選。",
              "這是2D模型投影與逐球節奏描述，沒有動作品質評分、3D推論、跨投手比較或精確出手對齊。",
              "逐點可靠性unknown，可用角度／usable_for_analysis仍null；不改Phase2或Phase3整體驗收。", ""]
    return "\n".join(lines)


def write_event_comparison(root: str | Path, config_path: str | Path, output: str | Path) -> dict:
    """Read bound saved curves and existing manual events into a fresh comparison."""
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
        if not isinstance(entry, dict) or set(entry) != {"pitch_id", "motion_dir", "ground_truth_ref"}:
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
        if (gt["annotation_status"] != "reviewed" or source["pitch_id"] != pid
                or source["total_frames"] != len(rows) or source["frame_index_base"] != 0
                or source["sha256"] != summary["source_refs"]["video_ref"]["sha256"]):
            raise ValueError("Events require reviewed ground truth for the exact saved source timeline")
        info = describe_events(gt["labels"]["events"], Fraction(summary["timebase"]["fps_fraction"]), rows)
        overlay = root / summary["source_refs"]["overlay_ref"]["path"]
        refs = {**motion_refs, "ground_truth_ref": entry["ground_truth_ref"],
                "video_ref": summary["source_refs"]["video_ref"],
                "overlay_ref": summary["source_refs"]["overlay_ref"]}
        source_refs.extend(refs.values())
        clips.append({"pitch_id": pid, "frame_count": len(rows),
                      "fps_fraction": summary["timebase"]["fps_fraction"], "rows": rows,
                      "overlay_url": quote(os.path.relpath(overlay, output / "viewer").replace("\\", "/"), safe="/."),
                      **info, "source_refs": refs, "event_reviewer": deepcopy(gt["provenance"]),
                      "pointwise_reliability": "unknown", "usable_for_analysis": None})
    reader = BoundReader(root, source_refs)
    for ref in source_refs:
        reader.path(ref)
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
    with (output / "report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_report(clips))
    for ref in source_refs:
        reader.path(ref)
    result = {"schema_version": "native-motion-event-comparison-v1", "status": "event_comparison_created",
              "pitcher_id": config["pitcher_id"], "clip_count": len(clips),
              "source_frames": sum(clip["frame_count"] for clip in clips),
              "clips": [{key: value for key, value in clip.items() if key not in {"rows", "overlay_url"}}
                        for clip in clips],
              "source_refs": {"request_ref": request_ref}, "viewer": viewer,
              "artifacts": {"timing_csv_ref": reference(root, output / "event_timing.csv"),
                            "report_ref": reference(root, output / "report.md")},
              "angle_values_recomputed": False, "event_midpoints_selected": False,
              "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "pointwise_reliability": "unknown", "quality_status": "not_calibrated", "usable_for_analysis": None,
              "exact_event_alignment": False, "cross_pitcher_comparison": False}
    write_json(output / "event_comparison.json", result)
    return result
