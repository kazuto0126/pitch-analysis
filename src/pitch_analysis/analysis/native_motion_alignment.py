"""Shift saved model-XY curves to an exact human foot plant without resampling."""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
from pathlib import Path

from .native_motion_events import ROLES, load_event_clips
from ..native_pose_io import BoundReader, reference, write_json


def align_clip(clip: dict) -> dict:
    """Preserve every source value and add only relative frame/time coordinates."""
    event = clip["events"]["foot_plant"]
    anchor, rows = event.get("frame_index"), clip["rows"]
    fps = Fraction(clip["fps_fraction"])
    if (event.get("status") != "annotated" or type(anchor) is not int
            or event.get("frame_range") is not None or fps <= 0
            or len(rows) != clip["frame_count"] or not 0 <= anchor < len(rows)
            or [row["frame_index"] for row in rows] != list(range(len(rows)))):
        raise ValueError("Alignment requires an exact annotated foot plant and complete source frames")
    if any(row["timestamp_sec"] != float(Fraction(row["frame_index"]) / fps) for row in rows):
        raise ValueError("Alignment requires the unshifted source fractional timeline")
    result = deepcopy(clip)
    result["alignment_frame"] = anchor
    result["aligned_rows"] = []
    for row in rows:
        delta = row["frame_index"] - anchor
        seconds = Fraction(delta) / fps
        result["aligned_rows"].append({**deepcopy(row), "relative_frame_index": delta,
                                       "relative_timestamp_sec": float(seconds),
                                       "relative_timestamp_fraction": str(seconds)})
    result["aligned_events"] = {}
    for name, original in clip["events"].items():
        bounds = original["frame_bounds"]
        relative = [value - anchor for value in bounds] if bounds is not None else None
        seconds = [Fraction(value) / fps for value in relative] if relative is not None else None
        result["aligned_events"][name] = {
            **deepcopy(original), "relative_frame_bounds": relative,
            "relative_seconds_bounds": [float(value) for value in seconds] if seconds is not None else None,
            "relative_seconds_bounds_fraction": [str(value) for value in seconds] if seconds is not None else None,
        }
    return result


def _plot(clips: list[dict], role: str, output: Path) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(12, 10), dpi=150, layout="constrained")
    FigureCanvasAgg(figure)
    full, zoom, releases = figure.subplots(3, 1, gridspec_kw={"height_ratios": [3, 3, 1.6]})
    colors = ["#0072b2", "#d55e00", "#009e73", "#cc79a7", "#82660a"]
    for index, clip in enumerate(clips):
        color = colors[index % len(colors)]
        rows = clip["aligned_rows"]
        times = [row["relative_timestamp_sec"] for row in rows]
        values = [row[f"{role}_model_xy_deg"] if row[f"{role}_model_xy_deg"] is not None
                  else float("nan") for row in rows]
        for axis in (full, zoom):
            axis.plot(times, values, color=color, linewidth=1.1, alpha=.9, label=clip["pitch_id"])
        event = clip["aligned_events"]["approximate_release"]
        bounds = event["relative_seconds_bounds"]
        if bounds is None:
            releases.text(.02, index, event["status"], color=color, va="center")
        else:
            confirmed = event["status"] == "annotated"
            releases.hlines(index, *bounds, color=color, linewidth=3, linestyle="solid" if confirmed else "dashed")
            releases.plot(bounds, [index, index], "|", color=color, markersize=10)
            frames = event["relative_frame_bounds"]
            label = str(frames[0]) if frames[0] == frames[1] else f"{frames[0]}–{frames[1]}"
            prefix = "" if confirmed else "uncertain candidate: "
            releases.text(bounds[1]+.012, index, f"{prefix}{label} frames", color=color, va="center", fontsize=9)
    for axis in (full, zoom):
        axis.axvline(0, color="#29384b", linewidth=1, linestyle="--")
        axis.set(ylim=(-3, 183), ylabel="Model XY angle (degrees)")
        axis.set_yticks([0, 45, 90, 135, 180])
        axis.grid(alpha=.2)
        axis.spines[["top", "right"]].set_visible(False)
    full.set_title("Complete source timelines (all frames retained)", loc="left", fontsize=10)
    full.legend(loc="upper right", ncols=min(3, len(clips)), fontsize=9)
    full.set_xlabel("Seconds relative to exact human foot plant")
    zoom.set(xlim=(-.5, .5), xlabel="Seconds relative to exact human foot plant")
    zoom.set_title("Display zoom: -0.5 to +0.5 seconds (same samples, no filtering)", loc="left", fontsize=10)
    releases.axvline(0, color="#29384b", linewidth=1, linestyle="--")
    releases.set_yticks(range(len(clips)), [clip["pitch_id"] for clip in clips])
    releases.set_ylim(len(clips)-.5, -.5)
    release_bounds = [event["relative_seconds_bounds"] for clip in clips
                      if (event := clip["aligned_events"]["approximate_release"])["relative_seconds_bounds"] is not None]
    low = min([0., *[value[0] for value in release_bounds]])
    high = max([.1, *[value[1] for value in release_bounds]])
    releases.set_xlim(low-.03, high+.22)
    releases.set_xlabel("Release timing in the shifted display; human ranges retained")
    releases.grid(axis="x", alpha=.2)
    releases.spines[["top", "right", "left"]].set_visible(False)
    releases.tick_params(axis="y", length=0, labelsize=9)
    title = "Throwing elbow" if role == "throwing_elbow" else "Lead knee"
    figure.suptitle(f"{title} | exact human foot plant = 0 s\n"
                   "Saved 2D model projection; no resampling or smoothing; pointwise quality unknown", fontsize=12)
    figure.savefig(output, metadata={"Description": "Display time shift only; original angles and missing samples retained"})
    figure.clear()


def write_native_alignment(root: str | Path, config_path: str | Path, output: str | Path) -> dict:
    """Export a same-pitcher display alignment from verified saved source data."""
    loaded = load_event_clips(root, config_path, output)
    root, output = loaded["root"], loaded["output"]
    clips = [align_clip(clip) for clip in loaded["clips"]]
    output.mkdir(parents=True, exist_ok=False)
    csv_path = output / "aligned_curves.csv"
    fields = ["pitch_id", "frame_index", "timestamp_sec", "alignment_frame", "relative_frame_index",
              "relative_timestamp_sec", "relative_timestamp_fraction", "pointwise_reliability"]
    fields += [f"{role}_{field}" for role in ROLES for field in ("model_xy_deg", "coordinate_status", "usable_deg")]
    with csv_path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for clip in clips:
            for row in clip["aligned_rows"]:
                writer.writerow({**row, "pitch_id": clip["pitch_id"], "alignment_frame": clip["alignment_frame"],
                                 "pointwise_reliability": "unknown", **{f"{role}_usable_deg": None for role in ROLES}})
    plot_refs = {}
    for role in ROLES:
        path = output / f"{role}_aligned.png"
        _plot(clips, role, path)
        plot_refs[role] = reference(root, path)
    report = ["# 同投手：以前腳落地為0秒的模型曲線", "",
              "只平移顯示時間：t = (原片影格 − 人工確認落地影格) / 分數FPS。",
              "原片格號、時間、角度與缺值全部保留；沒有重取樣、平滑、插值、品質篩選或跨球平均。",
              "兩張圖各含完整原片範圍與落地附近±0.5秒放大；放大不改CSV內容。",
              "出手仍保留人工單格／區間；不確定候選不升為已確認事件。", "",
              "| 影片 | 落地原片格 | 完整格數 | 出手相對落地格數／候選 | 出手狀態 |",
              "|---|---:|---:|---|---|"]
    for clip in clips:
        event = clip["aligned_events"]["approximate_release"]
        bounds = event["relative_frame_bounds"]
        label = "—" if bounds is None else (str(bounds[0]) if bounds[0] == bounds[1] else f"{bounds[0]}–{bounds[1]}")
        report.append(f"| {clip['pitch_id']} | {clip['alignment_frame']} | {clip['frame_count']} | {label} | {event['status']} |")
    report += ["", "![投球肘](throwing_elbow_aligned.png)", "", "![前導膝](lead_knee_aligned.png)", "",
               "角度只代表模型XY投影，不是人體3D屈曲角；逐點可靠性unknown、usable_for_analysis=null。",
               "事件對齊不能證明動作好壞或建立標準動作，也沒有改變原骨架、GT及整體Phase驗收。", ""]
    with (output / "report.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(report))
    reader = BoundReader(root, loaded["source_refs"])
    for ref in loaded["source_refs"]:
        reader.path(ref)
    result = {"schema_version": "native-motion-foot-plant-alignment-v1", "status": "alignment_created",
              "pitcher_id": loaded["pitcher_id"], "clip_count": len(clips),
              "source_frames": sum(clip["frame_count"] for clip in clips),
              "alignment_event": "foot_plant", "alignment_kind": "exact_human_event_display_time_shift",
              "source_refs": {"request_ref": loaded["request_ref"]},
              "clips": [{k: v for k, v in clip.items() if k not in {"rows", "aligned_rows", "overlay_url"}} for clip in clips],
              "artifacts": {"curves_ref": reference(root, csv_path), "plot_refs": plot_refs,
                            "report_ref": reference(root, output / "report.md")},
              "angle_values_recomputed": False, "samples_resampled": False, "time_warped": False,
              "smoothed": False, "interpolated": False, "event_midpoints_selected": False,
              "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "pointwise_reliability": "unknown", "usable_for_analysis": None, "cross_pitcher_comparison": False}
    write_json(output / "alignment_summary.json", result)
    return result
