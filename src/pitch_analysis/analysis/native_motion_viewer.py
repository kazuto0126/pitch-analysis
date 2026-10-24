"""Build a local synchronized viewer from source-bound saved motion exports."""
from __future__ import annotations

from collections import Counter
import csv
from fractions import Fraction
from importlib.resources import files
import json
import math
import os
from pathlib import Path
from urllib.parse import quote

from .native_input import MANIFEST_NAME, SUMMARY_NAME, load_native_analysis_input
from ..native_pose_io import BoundReader, read_json, reference, write_json


_ROLES = ("throwing_elbow", "lead_knee")
_STATUSES = {"calculated_from_model_xy": "calculated", "missing_coordinates": "missing",
             "degenerate_geometry": "degenerate"}
_FIELDS = {"frame_index", "timestamp_sec", "pointwise_reliability"} | {
    f"{role}_{field}" for role in _ROLES for field in ("model_xy_deg", "coordinate_status", "usable_deg")}


def _path(root: Path, value: str | Path) -> Path:
    value = Path(value)
    value = (value if value.is_absolute() else root / value).resolve(strict=True)
    if not value.is_relative_to(root):
        raise ValueError("Motion exports must be inside the project root")
    return value


def _load_export(root: Path, folder: Path) -> tuple[dict, list[dict], dict]:
    summary = read_json(folder / "motion_summary.json")
    if (summary.get("schema_version") != "native-motion-description-v1"
            or summary.get("scope") != "descriptive_model_xy_projection"
            or summary.get("quality_status") != "not_calibrated"
            or summary.get("pointwise_reliability") != "unknown"
            or summary.get("usable_for_analysis") is not None):
        raise ValueError("Viewer requires an uncalibrated descriptive motion export")
    refs, artifacts = summary.get("source_refs"), summary.get("artifacts")
    if not isinstance(refs, dict) or not isinstance(artifacts, dict):
        raise ValueError("Motion export requires bound sources and artifacts")
    reader = BoundReader(root, [*refs.values(), *artifacts.values()])
    analysis_path = reader.path(refs["analysis_input_ref"])
    if analysis_path.name != MANIFEST_NAME:
        raise ValueError("Motion export requires its exact native analysis input")
    pitch = load_native_analysis_input(root, analysis_path.parent)
    expected = {"analysis_input_ref": reference(root, analysis_path),
                "usage_summary_ref": reference(root, analysis_path.parent / SUMMARY_NAME),
                **pitch.manifest["source_refs"]}
    if refs != expected or summary.get("human_overlay_review") != pitch.review:
        raise ValueError("Motion source or human review differs from its accepted input")
    manifest = pitch.manifest
    if (summary.get("pitch_id") != manifest["pitch_id"]
            or summary.get("pitcher_id") != pitch.metadata["pitcher"]["id"]
            or summary.get("total_frames") != len(pitch)
            or summary.get("timebase", {}).get("fps_fraction") != manifest["timebase"]["fps_fraction"]):
        raise ValueError("Motion identity, frame count or fractional FPS differs")
    csv_path = reader.path(artifacts["curves_ref"])
    if csv_path != folder / "motion_curves.csv" or reader.path(artifacts["plot_ref"]) != folder / "motion_curves.png":
        raise ValueError("Motion artifacts must be the exact siblings of their summary")
    fps = Fraction(manifest["timebase"]["fps_fraction"])
    rows = []
    counts = {role: Counter() for role in _ROLES}
    with csv_path.open(encoding="utf-8-sig", newline="") as stream:
        source = csv.DictReader(stream)
        if source.fieldnames is None or len(source.fieldnames) != len(_FIELDS) or set(source.fieldnames) != _FIELDS:
            raise ValueError("Motion CSV requires its exact unique column names")
        for index, value in enumerate(source):
            if (None in value or any(item is None for item in value.values())
                    or value["frame_index"] != str(index) or value["pointwise_reliability"] != "unknown"):
                raise ValueError("Motion CSV requires complete ordered source frames and unknown reliability")
            seconds = float(value["timestamp_sec"])
            expected_time = float(Fraction(index) / fps)
            if not math.isfinite(seconds) or seconds != expected_time:
                raise ValueError("Motion CSV must retain the zero-based fractional source timeline")
            row = {"frame_index": index, "timestamp_sec": seconds}
            for role in _ROLES:
                status = value[f"{role}_coordinate_status"]
                text = value[f"{role}_model_xy_deg"]
                if status not in _STATUSES or value[f"{role}_usable_deg"] != "":
                    raise ValueError("Motion state or null usability was changed")
                angle = float(text) if text != "" else None
                if ((status == "calculated_from_model_xy") != (angle is not None)
                        or angle is not None and (not math.isfinite(angle) or not 0 <= angle <= 180)):
                    raise ValueError("Motion values must match their coordinate state and 2D angle definition")
                row[f"{role}_model_xy_deg"] = angle
                row[f"{role}_coordinate_status"] = status
                counts[role][_STATUSES[status]] += 1
            rows.append(row)
    if len(rows) != len(pitch):
        raise ValueError("Motion CSV must retain the full source frame count")
    for role in _ROLES:
        expected_counts = {"total_frames": len(rows), **{key: counts[role][key] for key in _STATUSES.values()}}
        if summary.get("curves", {}).get(role) != expected_counts:
            raise ValueError("Motion summary counts differ from its CSV")
    for ref in reader.allowed.items():
        reader.path({"path": ref[0], "sha256": ref[1]})
    return summary, rows, {"summary_ref": reference(root, folder / "motion_summary.json"), **artifacts}


_HTML = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>影片與2D曲線連動</title>
<style>body{font:17px system-ui;color:#1d2c3d;background:#f1f4f8;max-width:1080px;margin:24px auto;padding:0 16px}
h1{font-size:27px}.note{background:#fff0cb;border-radius:9px;padding:14px;line-height:1.6}.card{background:white;border-radius:12px;padding:18px;margin-top:18px}
video{display:block;width:min(100%,640px);margin:12px auto;background:#17212c}button,input,select{font:inherit;padding:7px}button{cursor:pointer}
.controls{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.metrics{display:flex;gap:18px;flex-wrap:wrap;margin:16px 0;font-weight:600}
#frame-slider{width:100%;padding:0;margin:16px 0}#frame-input{width:90px}svg{width:100%;height:auto;display:block;cursor:crosshair;touch-action:pan-y}
.hint{font-size:14px;color:#52657b}#sync-status{min-height:24px;color:#52657b}a{color:#106b9b}</style>
<h1>單投手：影片與2D角度曲線</h1>
<p class="note">沿用已接受的骨架。藍色為投球肘，橘色為前導膝；角度是模型座標的2D投影，逐點可靠性尚未校準。
遮擋時也可能有模型估計座標，曲線不能直接當成真實3D動作或好壞評分。</p>
<div class="card"><label>影片 <select id="clip-select"></select></label>
<video id="video" controls preload="metadata" playsinline></video>
<div class="controls"><button id="play" disabled>播放／暫停</button><button id="previous" disabled>上一格</button><button id="next" disabled>下一格</button>
<label>格號 <input id="frame-input" type="number" min="0" value="0" step="1" disabled></label><button id="seek" disabled>前往</button>
<label>觀看速度 <select id="playback-rate"><option value="1">1×</option><option value="0.5">0.5×</option><option value="0.25">0.25×</option></select></label></div>
<input id="frame-slider" aria-label="影格位置" type="range" min="0" value="0" step="1" disabled>
<div class="metrics"><span id="frame-label">等待影格</span><span id="time-label">—</span><span id="elbow-label">投球肘：—</span><span id="knee-label">前導膝：—</span></div>
<p id="sync-status" aria-live="polite">影片載入中</p>
<h2>投球肘</h2><svg id="elbow-chart" viewBox="0 0 960 250" role="img" aria-label="投球肘曲線，點選可跳至對應影格"></svg>
<h2>前導膝</h2><svg id="knee-chart" viewBox="0 0 960 250" role="img" aria-label="前導膝曲線，點選可跳至對應影格"></svg>
<p class="hint">點選曲線或使用滑桿／格號跳轉。格號從0開始；游標與數值優先依播放器實際呈現影格更新。
若瀏覽器不支援畫格回呼，會明示為「時間估計」。←／→可逐格前後移動。
觀看速度只影響播放器，不修改來源資料。每球以原片第0格計時，未依出手／落地對齊。</p></div>
<script id="motion-data" type="application/json">__DATA__</script><script src="motion_viewer.js" defer></script></html>'''


def write_motion_viewer(root: str | Path, motion_dirs: list[str | Path], output: str | Path) -> dict:
    """Write a fresh self-contained local UI using already exported angle values."""
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Motion viewer output must be inside this project's analysis_results")
    if output.exists():
        raise FileExistsError("Motion viewer output already exists")
    if not motion_dirs:
        raise ValueError("At least one saved motion export is required")
    clips, sources, identities, pitchers = [], [], set(), set()
    for name in motion_dirs:
        folder = _path(root, name)
        summary, rows, refs = _load_export(root, folder)
        if summary["pitch_id"] in identities:
            raise ValueError("Duplicate pitch identity in motion viewer")
        identities.add(summary["pitch_id"])
        pitchers.add(summary["pitcher_id"])
        overlay = root / summary["source_refs"]["overlay_ref"]["path"]
        clips.append({"pitch_id": summary["pitch_id"], "frame_count": len(rows),
                      "fps_fraction": summary["timebase"]["fps_fraction"],
                      "overlay_url": quote(os.path.relpath(overlay, output).replace("\\", "/"), safe="/."),
                      "rows": rows})
        sources.append(refs)
    if len(pitchers) != 1:
        raise ValueError("This viewer supports a single pitcher only")
    data = json.dumps({"clips": clips}, ensure_ascii=False, allow_nan=False)
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    script = files("pitch_analysis").joinpath("review_assets/native_motion_viewer.js").read_bytes()
    output.mkdir(parents=True, exist_ok=False)
    with (output / "review_motion.html").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(_HTML.replace("__DATA__", data))
    with (output / "motion_viewer.js").open("xb") as stream:
        stream.write(script)
    result = {"schema_version": "native-motion-viewer-v1", "status": "viewer_created",
              "pitcher_id": next(iter(pitchers)), "clip_count": len(clips),
              "source_frames": sum(clip["frame_count"] for clip in clips), "source_exports": sources,
              "html_ref": reference(root, output / "review_motion.html"),
              "script_ref": reference(root, output / "motion_viewer.js"),
              "angle_values_recomputed": False, "new_inference_calls": 0,
              "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "quality_status": "not_calibrated", "usable_for_analysis": None,
              "frame_sync": "presented mediaTime when supported; explicitly marked time estimate otherwise",
              "browser_interaction_verified": False}
    write_json(output / "motion_viewer_manifest.json", result)
    return result
