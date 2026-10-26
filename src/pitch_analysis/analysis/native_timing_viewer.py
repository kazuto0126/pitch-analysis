"""Read-only two-player navigation for an existing manual timing comparison."""
from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import json
import os
from pathlib import Path
from urllib.parse import quote

from .native_motion_event_viewer import _validate_clips
from .native_motion_events import TIMING_LABELS, TIMING_PAIRS
from .native_motion_viewer import _HTML, _path
from .native_timing_comparison import _load_report, compare_timing_intervals
from ..native_pose_io import BoundReader, read_json, reference, write_json


_PAGE = '''<!doctype html><html lang="zh-Hant"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>人工時距與兩側影片對照</title>
<style>body{font:17px system-ui;color:#1d2c3d;background:#f1f4f8;margin:20px auto;max-width:1500px;padding:0 16px}
.note{background:#fff0cb;padding:14px;line-height:1.6;border-radius:10px}.panels{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
section{background:white;border-radius:10px;padding:16px}button,select{font:inherit;padding:7px;margin:4px}iframe{width:100%;height:1050px;border:1px solid #ccd4df}
a{color:#106b9b}#pair-result{font-weight:600}#pair-reasons{color:#6d3c00}@media(max-width:850px){.panels{grid-template-columns:1fr}}</style>
<h1>人工時距：兩側影片對照</h1>
<p class="note">選區段與兩側影片，查看已保存的時距差值，再按人工事件界線回看片段。
範圍保留下界／上界，未確認事件不自動定位。兩側使用各自原片FPS，獨立播放；沒有時間拉伸、角度相似度或排名。
按鈕只送出跳格要求，實際呈現請看各播放器的格號。模型XY曲線只供各片回看，逐點可靠性尚未校準。</p>
<label>人工事件區段 <select id="timing-select"></select></label>
<p id="pair-durations"></p><p id="pair-result" aria-live="polite"></p><p id="pair-reasons"></p>
<div class="panels">
<section><h2 id="a-heading">A</h2><label>影片 <select id="a-select"></select></label>
<p id="a-fps"></p><a id="a-raw" target="_blank" rel="noopener">開啟原片</a><div id="a-events"></div>
<iframe id="a-player" title="A原片影格播放器"></iframe></section>
<section><h2 id="b-heading">B</h2><label>影片 <select id="b-select"></select></label>
<p id="b-fps"></p><a id="b-raw" target="_blank" rel="noopener">開啟原片</a><div id="b-events"></div>
<iframe id="b-player" title="B原片影格播放器"></iframe></section></div>
<script id="timing-data" type="application/json">__DATA__</script><script src="timing_viewer.js" defer></script></html>'''


def _embedded(value: dict) -> str:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False).replace("&", "\\u0026")
            .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def _url(root: Path, output: Path, ref: dict) -> str:
    return quote(os.path.relpath(root / ref["path"], output).replace("\\", "/"), safe="/.")


def write_timing_viewer(root: str | Path, comparison_json: str | Path,
                        output: str | Path) -> dict:
    """Reuse the unchanged source player in isolated pages; never seek a candidate."""
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Timing viewer output must be a new analysis_results subdirectory")
    if output.exists():
        raise FileExistsError("Timing viewer output already exists")
    path = _path(root, comparison_json)
    payload = read_json(path)
    if (payload.get("schema_version") != "native-manual-timing-comparison-v1"
            or payload.get("status") != "timing_comparison_created"
            or payload.get("scope") != "recorded_manual_event_durations_only"
            or not isinstance(payload.get("cohorts"), list) or len(payload["cohorts"]) != 2):
        raise ValueError("Expected an existing two-pitcher manual timing comparison")
    comparison_ref = reference(root, path)
    sources, refs = [], [comparison_ref]
    for side, cohort in zip(("a", "b"), payload["cohorts"], strict=True):
        reader = BoundReader(root, [cohort["report_ref"]])
        loaded, report_ref = _load_report(root, reader.path(cohort["report_ref"]), output)
        expected = {"side": side, "pitcher_id": loaded["pitcher_id"],
                    "clip_count": len(loaded["clips"]),
                    "source_frames": sum(c["frame_count"] for c in loaded["clips"]),
                    "report_ref": report_ref, "request_ref": loaded["request_ref"]}
        if cohort != expected:
            raise ValueError("Timing viewer cohort differs from bound source reports")
        sources.append(loaded)
        refs.extend([report_ref, *loaded["source_refs"]])
    a, b = sources
    if a["pitcher_id"] == b["pitcher_id"]:
        raise ValueError("Timing viewer requires two distinct pitchers")
    expected_pairs = []
    for key, (start, end) in TIMING_PAIRS.items():
        for ca in a["clips"]:
            for cb in b["clips"]:
                row = {"timing_key": key}
                for side, loaded, clip in (("a", a, ca), ("b", b, cb)):
                    row.update({f"{side}_pitcher_id": loaded["pitcher_id"],
                                f"{side}_pitch_id": clip["pitch_id"],
                                f"{side}_fps_fraction": clip["fps_fraction"],
                                f"{side}_frame_bounds": clip["timing"][key]["frame_bounds"],
                                f"{side}_start_event_bounds": clip["events"][start]["frame_bounds"],
                                f"{side}_end_event_bounds": clip["events"][end]["frame_bounds"],
                                f"{side}_source_refs": clip["source_refs"]})
                row.update(compare_timing_intervals(ca["timing"][key], ca["fps_fraction"],
                                                    cb["timing"][key], cb["fps_fraction"]))
                expected_pairs.append(row)
    comparable = sum(row["status"] != "unavailable" for row in expected_pairs)
    if (payload.get("pairs") != expected_pairs or payload.get("total_pairs") != len(expected_pairs)
            or payload.get("comparable_pairs") != comparable
            or payload.get("unavailable_pairs") != len(expected_pairs) - comparable):
        raise ValueError("Saved timing pairs differ from their original manual events")
    cohorts, pages = [], {}
    for side, loaded in zip(("a", "b"), sources, strict=True):
        packaged = []
        for index, clip in enumerate(loaded["clips"]):
            player = deepcopy(clip)
            player["overlay_url"] = _url(root, output, clip["source_refs"]["overlay_ref"])
            _validate_clips([player])
            name = f"{side}_{index:03d}.html"
            html = _HTML.replace("<title>影片與2D曲線連動</title>", "<title>來源影格回看</title>")
            html = html.replace('<script id="motion-data"', '<p id="frame-link-status" aria-live="polite"></p><script id="motion-data"')
            html = html.replace('</script></html>', '</script><script src="frame_link.js" defer></script></html>')
            pages[name] = html.replace("__DATA__", _embedded({"clips": [player]}))
            packaged.append({"pitch_id": clip["pitch_id"], "frame_count": clip["frame_count"],
                             "fps_fraction": clip["fps_fraction"], "page_url": name,
                             "video_url": _url(root, output, clip["source_refs"]["video_ref"]),
                             "events": deepcopy(clip["events"])})
        cohorts.append({"side": side, "pitcher_id": loaded["pitcher_id"], "clips": packaged})
    # Each page owns one source and reads only its own frame hash. Old loads
    # cannot seek a newly selected clip; no iframe DOM bridge is required.
    data = {"cohorts": cohorts,
            "stages": [{"key": key, "label": TIMING_LABELS[key], "start": bounds[0], "end": bounds[1]}
                       for key, bounds in TIMING_PAIRS.items()],
            "pairs": [{key: value for key, value in row.items()
                       if key in {"timing_key", "a_pitch_id", "b_pitch_id", "status", "relation",
                                  "a_seconds_bounds_fraction", "b_seconds_bounds_fraction",
                                  "delta_seconds_bounds", "delta_seconds_bounds_fraction", "unavailable_reasons"}}
                      for row in expected_pairs]}
    resources = files("pitch_analysis").joinpath("review_assets")
    scripts = {"motion_viewer.js": resources.joinpath("native_motion_viewer.js").read_bytes(),
               "frame_link.js": resources.joinpath("native_motion_frame_link.js").read_bytes(),
               "timing_viewer.js": resources.joinpath("native_timing_viewer.js").read_bytes()}
    reader = BoundReader(root, refs)
    for ref in refs:
        reader.path(ref)
    output.mkdir(parents=True, exist_ok=False)
    for name, html in {"review_timing.html": _PAGE.replace("__DATA__", _embedded(data)), **pages}.items():
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(html)
    for name, content in scripts.items():
        with (output / name).open("xb") as stream:
            stream.write(content)
    for ref in refs:
        reader.path(ref)
    result = {"schema_version": "native-manual-timing-viewer-v1", "status": "timing_viewer_created",
              "comparison_ref": comparison_ref, "clip_count": sum(len(c["clips"]) for c in cohorts),
              "source_frames": sum(c["source_frames"] for c in payload["cohorts"]),
              "total_pairs": len(expected_pairs), "comparable_pairs": comparable,
              "unavailable_pairs": len(expected_pairs) - comparable,
              "artifacts": {name: reference(root, output / name)
                            for name in ("review_timing.html", *pages, *scripts)},
              "new_inference_calls": 0, "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "independent_playback": True, "base_player_modified": False,
              "browser_interaction_verified": False,
              "pointwise_reliability": "unknown", "usable_for_analysis": None}
    write_json(output / "timing_viewer_manifest.json", result)
    return result
