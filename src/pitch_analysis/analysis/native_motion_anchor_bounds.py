"""Retain annotated foot-plant uncertainty as alternative display origins."""
from __future__ import annotations

from copy import deepcopy
import csv
from fractions import Fraction
from pathlib import Path

from .native_motion_events import ROLES, load_event_clips
from ..native_pose_io import BoundReader, reference, write_json


def describe_anchor_bounds(clip: dict) -> dict:
    """Add a time interval per source sample without selecting an anchor frame."""
    rows, fps = clip["rows"], Fraction(clip["fps_fraction"])
    if (fps <= 0 or not rows or len(rows) != clip["frame_count"]
            or [row["frame_index"] for row in rows] != list(range(len(rows)))
            or any(row["timestamp_sec"] != float(Fraction(row["frame_index"]) / fps) for row in rows)):
        raise ValueError("Anchor bounds require the complete zero-based source timeline")
    event = clip["events"]["foot_plant"]
    status, bounds = "unavailable", None
    if event["status"] == "annotated":
        bounds = event["frame_bounds"]
        if (not isinstance(bounds, list) or len(bounds) != 2
                or any(type(value) is not int for value in bounds)
                or not 0 <= bounds[0] <= bounds[1] < len(rows)):
            raise ValueError("Annotated foot plant requires valid source bounds")
        status = "bounded" if event.get("frame_range") is not None else "exact"
        if status == "exact" and (type(event.get("frame_index")) is not int
                                  or bounds != [event["frame_index"], event["frame_index"]]):
            raise ValueError("An exact foot plant must retain its exact human frame")
    result = deepcopy(clip)
    result.update(origin_status=status, origin_frame_bounds=deepcopy(bounds),
                  origin_candidates=list(range(bounds[0], bounds[1]+1)) if bounds is not None else [],
                  origin_reason="" if bounds is not None else "foot_plant_not_confirmed",
                  bounded_rows=[])
    for row in rows:
        frames = [row["frame_index"]-bounds[1], row["frame_index"]-bounds[0]] if bounds is not None else None
        seconds = [Fraction(value)/fps for value in frames] if frames is not None else None
        result["bounded_rows"].append({**deepcopy(row), "relative_frame_bounds": frames,
                                      "relative_seconds_bounds": [float(value) for value in seconds] if seconds is not None else None,
                                      "relative_seconds_bounds_fraction": [str(value) for value in seconds] if seconds is not None else None})
    return result


def _plot(clips: list[dict], role: str, output: Path) -> None:
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(12, 10), dpi=150, layout="constrained")
    FigureCanvasAgg(figure)
    full, zoom, release = figure.subplots(3, 1, gridspec_kw={"height_ratios": [3, 3, 1.6]})
    colors = ["#0072b2", "#d55e00", "#009e73", "#cc79a7", "#82660a"]
    for index, clip in enumerate(clips):
        color, fps = colors[index % len(colors)], Fraction(clip["fps_fraction"])
        values = [row[f"{role}_model_xy_deg"] if row[f"{role}_model_xy_deg"] is not None
                  else float("nan") for row in clip["rows"]]
        label = f"{clip['pitch_id']} ({clip['origin_status']})"
        for position, origin in enumerate(clip["origin_candidates"]):
            times = [float(Fraction(row["frame_index"]-origin)/fps) for row in clip["rows"]]
            for axis in (full, zoom):
                axis.plot(times, values, color=color, linewidth=1.2,
                          linestyle="--" if clip["origin_status"] == "bounded" else "-",
                          alpha=.7 if clip["origin_status"] == "bounded" else .95,
                          label=label if position == 0 else None)
        if not clip["origin_candidates"]:
            full.plot([], [], color=color, label=label)
        # The existing event-duration calculation already preserves both event
        # uncertainties and never treats uncertain candidates as measured times.
        timing = clip["timing"]["foot_plant_to_release"]
        bounds = timing["seconds_bounds"] if clip["origin_status"] != "unavailable" else None
        if bounds is None:
            release.text(.02, index, "unavailable", color=color, va="center")
        else:
            release.hlines(index, *bounds, color=color, linewidth=3)
            release.plot(bounds, [index, index], "|", color=color, markersize=10)
            frames = timing["frame_bounds"]
            text = str(frames[0]) if frames[0] == frames[1] else f"{frames[0]}–{frames[1]}"
            release.text(bounds[1]+.012, index, f"{text} frames", color=color, va="center", fontsize=9)
    for axis in (full, zoom):
        axis.axvline(0, color="#29384b", linestyle=":", linewidth=1)
        axis.set(ylim=(-3, 183), ylabel="Model XY angle (degrees)", xlabel="Seconds relative to an admissible human foot-plant frame")
        axis.set_yticks([0,45,90,135,180])
        axis.grid(alpha=.2)
        axis.spines[["top", "right"]].set_visible(False)
    full.legend(fontsize=9, loc="upper right", ncols=2)
    full.set_title("Complete source timelines; dashed paths retain every annotated origin", loc="left", fontsize=10)
    zoom.set_xlim(-.5,.5)
    zoom.set_title("Display zoom: -0.5 to +0.5 seconds (same samples)", loc="left", fontsize=10)
    release.set_yticks(range(len(clips)), [clip["pitch_id"] for clip in clips])
    release.set_ylim(len(clips)-.5,-.5)
    intervals = [clip["timing"]["foot_plant_to_release"]["seconds_bounds"] for clip in clips
                 if clip["origin_status"] != "unavailable" and clip["timing"]["foot_plant_to_release"]["seconds_bounds"] is not None]
    low = min([0., *[bounds[0] for bounds in intervals]])
    high = max([.1, *[bounds[1] for bounds in intervals]])
    release.set(xlim=(low-.03,high+.22), xlabel="Release interval includes manual foot-plant and release bounds")
    release.axvline(0,color="#29384b",linestyle=":",linewidth=1)
    release.grid(axis="x",alpha=.2)
    release.spines[["top","right","left"]].set_visible(False)
    release.tick_params(axis="y",length=0,labelsize=9)
    name = "Throwing elbow" if role == "throwing_elbow" else "Lead knee"
    figure.suptitle(f"{name} | manual foot-plant origins retained\n"
                   "Alternative shifts are not additional observations or probability bounds", fontsize=12)
    figure.savefig(output, metadata={"Description":"All annotated origin candidates; no midpoint, resampling or new pose samples"})
    figure.clear()


def write_bounded_alignment(root: str | Path, config_path: str | Path, output: str | Path) -> dict:
    loaded = load_event_clips(root, config_path, output)
    root, output = loaded["root"], loaded["output"]
    clips = [describe_anchor_bounds(clip) for clip in loaded["clips"]]
    output.mkdir(parents=True,exist_ok=False)
    csv_path = output/"bounded_curves.csv"
    fields = ["pitch_id","frame_index","timestamp_sec","pointwise_reliability"]
    fields += [f"{role}_{field}" for role in ROLES for field in ("model_xy_deg","coordinate_status","usable_deg")]
    fields += ["origin_status","origin_frame_min","origin_frame_max","relative_frame_min","relative_frame_max",
               "relative_seconds_min","relative_seconds_max","relative_fraction_min","relative_fraction_max"]
    with csv_path.open("x",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for clip in clips:
            for row in clip["bounded_rows"]:
                source={k:v for k,v in row.items() if k not in {"relative_frame_bounds","relative_seconds_bounds","relative_seconds_bounds_fraction"}}
                origin=clip["origin_frame_bounds"] or [None,None]
                frames=row["relative_frame_bounds"] or [None,None]
                seconds=row["relative_seconds_bounds"] or [None,None]
                fractions=row["relative_seconds_bounds_fraction"] or [None,None]
                writer.writerow({**source,"pitch_id":clip["pitch_id"],"pointwise_reliability":"unknown",
                                 **{f"{role}_usable_deg":None for role in ROLES},"origin_status":clip["origin_status"],
                                 "origin_frame_min":origin[0],"origin_frame_max":origin[1],
                                 "relative_frame_min":frames[0],"relative_frame_max":frames[1],
                                 "relative_seconds_min":seconds[0],"relative_seconds_max":seconds[1],
                                 "relative_fraction_min":fractions[0],"relative_fraction_max":fractions[1]})
    plots={}
    for role in ROLES:
        path=output/f"{role}_bounds.png"
        _plot(clips,role,path)
        plots[role]=reference(root,path)
    report=["# 保留人工落地範圍的曲線比較","",
            "每條原始曲線對所有annotated落地候選格各作時間平移，不選中點或指定單一原點。",
            "虛線是同一球的替代平移，不是新增觀測或機率分布；CSV每個來源影格仍只有一列。",
            "不確定／不可觀測落地保持unavailable，不以候選猜原點。原樣本、角度與缺值保持。","",
            "| 球 | 原點狀態 | 原點候選格 | 原始格數 | 出手相對落地格數 |","|---|---|---|---:|---|"]
    for clip in clips:
        timing=clip["timing"]["foot_plant_to_release"]
        report.append(f"| {clip['pitch_id']} | {clip['origin_status']} | {clip['origin_candidates']} | {clip['frame_count']} | {timing['frame_bounds'] if clip['origin_candidates'] else None} |")
    report += ["","![投球肘](throwing_elbow_bounds.png)","","![前導膝](lead_knee_bounds.png)","",
               "對齊圖只是模型2D投影；範圍代表人工標註容許的候選，不是統計信賴區間。",
               "沒有改GT、補點、平滑、重取樣、角度重算或品質篩選，逐點可靠性unknown、usable_for_analysis=null。",""]
    with (output/"report.md").open("x",encoding="utf-8",newline="\n") as stream:
        stream.write("\n".join(report))
    reader=BoundReader(root,loaded["source_refs"])
    for ref in loaded["source_refs"]:
        reader.path(ref)
    result={"schema_version":"native-motion-anchor-bounds-v1","status":"bounded_alignment_created",
            "pitcher_id":loaded["pitcher_id"],"clip_count":len(clips),"source_frames":sum(c["frame_count"] for c in clips),
            "clips":[{k:v for k,v in c.items() if k not in {"rows","bounded_rows","overlay_url"}} for c in clips],
            "source_refs":{"request_ref":loaded["request_ref"]},
            "artifacts":{"curves_ref":reference(root,csv_path),"plot_refs":plots,"report_ref":reference(root,output/"report.md")},
            "candidate_origins_are_observations":False,"probabilities_assigned":False,
            "event_midpoints_selected":False,"samples_resampled":False,"angle_values_recomputed":False,
            "smoothed":False,"interpolated":False,"new_inference_calls":0,"new_tracking_replays":0,"new_ground_truth_labels":0,
            "pointwise_reliability":"unknown","usable_for_analysis":None,"cross_pitcher_comparison":False}
    write_json(output/"anchor_bounds_summary.json",result)
    return result
