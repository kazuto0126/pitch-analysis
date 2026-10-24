"""Add saved human event annotations to the existing native motion viewer.

The caller supplies validated event windows and timing bounds. This writer only
packages those descriptions alongside the unchanged playback/synchronization UI.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
from importlib.resources import files
import json
from pathlib import Path

from .native_motion_viewer import _HTML
from ..native_pose_io import reference, write_json


_EVENT_NAMES = (
    "preparation_start", "leg_lift", "foot_plant", "approximate_release", "follow_through_end",
)
_TIMING_NAMES = (
    "preparation_to_leg_lift", "leg_lift_to_foot_plant", "foot_plant_to_release", "release_to_follow_through_end",
)
_EXTRA_HTML = '''<style>
.event-table-wrap{overflow-x:auto}.event-table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.6}
.event-table th,.event-table td{padding:9px;text-align:left;vertical-align:top;border-bottom:1px solid #dce2eb;white-space:normal}
.event-table th{background:#eef3f8}.event-table td{min-width:110px}.event-table td:first-child{font-weight:600}
.event-legend{display:flex;flex-wrap:wrap;gap:10px;font-size:14px}.event-legend span{white-space:nowrap}
.event-note{line-height:1.7}.event-table small{display:block;color:#52657b}
</style>
<section class="card"><h2>本球：人工事件與模型2D角度視窗</h2>
<p class="event-note">實線＝精確事件；色帶＝人工影格範圍；虛線＝不確定候選，即使候選只有一格仍不視為精確。
不可觀測事件只列在表中，不猜位置。曲線與影片保留原片第0格時間，<strong>未做精確事件對齊</strong>。</p>
<div id="event-legend" class="event-legend"></div><div id="event-table" class="event-table-wrap"></div>
<p class="hint">角度範圍只描述事件視窗內已保存的模型XY座標；缺失不插值。原人工事件標註可用於時序對照，
舊骨架的可靠性判讀不會搬到新骨架。逐點可靠性未知，角度可用性仍為null。</p></section>
<section class="card"><h2>同投手各球：人工事件時距</h2>
<p class="hint">列出每球原時間軸上的精確值或上下界；不排序、不評分、不計算跨球平均，不強制對齊出手。</p>
<div id="event-timing-table" class="event-table-wrap"></div></section>
'''


def _validate_clips(clips: list[dict]) -> None:
    if not isinstance(clips, list) or not clips:
        raise ValueError("Event viewer requires at least one saved clip")
    seen = set()
    for clip in clips:
        pitch_id = clip.get("pitch_id")
        count = clip.get("frame_count")
        if not isinstance(pitch_id, str) or not pitch_id or pitch_id in seen:
            raise ValueError("Event viewer requires unique nonempty pitch identities")
        seen.add(pitch_id)
        if not isinstance(count, int) or isinstance(count, bool) or count < 1:
            raise ValueError("Event viewer requires a positive complete frame count")
        fps = Fraction(clip["fps_fraction"])
        if fps <= 0:
            raise ValueError("Event viewer requires a positive fractional FPS")
        rows = clip.get("rows")
        if not isinstance(rows, list) or len(rows) != count:
            raise ValueError("Event viewer requires all saved motion rows")
        for index, row in enumerate(rows):
            if row.get("frame_index") != index or row.get("timestamp_sec") != float(Fraction(index) / fps):
                raise ValueError("Event viewer must preserve complete zero-based fractional source time")
        if not isinstance(clip.get("overlay_url"), str) or not clip["overlay_url"]:
            raise ValueError("Event viewer requires its saved overlay URL")
        events = clip.get("events")
        timing = clip.get("timing")
        if not isinstance(events, dict) or set(events) != set(_EVENT_NAMES):
            raise ValueError("Event viewer requires the five supplied human event records")
        if not isinstance(timing, dict) or set(timing) != set(_TIMING_NAMES):
            raise ValueError("Event viewer requires the four supplied timing intervals")
        for event in events.values():
            kind = event.get("marker_kind")
            bounds = event.get("frame_bounds")
            if kind not in ("exact", "range", "uncertain", "not_observable"):
                raise ValueError("Unknown event marker kind")
            if bounds is not None and (not isinstance(bounds, list) or len(bounds) != 2
                    or any(not isinstance(value, int) or isinstance(value, bool) for value in bounds)
                    or not 0 <= bounds[0] <= bounds[1] < count):
                raise ValueError("Event marker bounds must use this clip's source frames")
            if kind == "exact" and (bounds is None or bounds[0] != bounds[1]):
                raise ValueError("An exact marker requires one exact source frame")
            if kind == "range" and bounds is None:
                raise ValueError("A range marker requires supplied source bounds")
            if kind == "not_observable" and bounds is not None:
                raise ValueError("An unobservable event cannot acquire a visible location")
            if not isinstance(event.get("angle_windows"), dict):
                raise ValueError("Event angle windows must come from the saved description")
        for interval in timing.values():
            if interval.get("status") not in ("exact", "bounded", "unavailable"):
                raise ValueError("Unknown event interval status")


def write_event_viewer(root: Path, clips: list[dict], output: Path) -> dict:
    """Write a fresh event viewer without recomputing predictions or angles."""
    root = Path(root).resolve(strict=True)
    output = Path(output)
    output = (output if output.is_absolute() else root / output).resolve()
    if output == root / "analysis_results" or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Event viewer output must be inside this project's analysis_results")
    if output.exists():
        raise FileExistsError("Event viewer output already exists")
    _validate_clips(clips)
    data = json.dumps({"clips": clips}, ensure_ascii=False, allow_nan=False)
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template = _HTML.replace("<title>影片與2D曲線連動</title>", "<title>人工事件與2D曲線對照</title>")
    template = template.replace('<script id="motion-data"', _EXTRA_HTML + '<script id="motion-data"')
    template = template.replace('</script></html>', '</script><script src="motion_events.js" defer></script></html>')
    html = template.replace("__DATA__", data)
    resources = files("pitch_analysis").joinpath("review_assets")
    base_script = resources.joinpath("native_motion_viewer.js").read_bytes()
    event_script = resources.joinpath("native_motion_events.js").read_bytes()
    output.mkdir(parents=True, exist_ok=False)
    with (output / "review_motion_events.html").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(html)
    for name, script in (("motion_viewer.js", base_script), ("motion_events.js", event_script)):
        with (output / name).open("xb") as stream:
            stream.write(script)
    result = {
        "schema_version": "native-motion-event-viewer-v1", "status": "event_viewer_created",
        "clip_count": len(clips), "pitch_ids": [clip["pitch_id"] for clip in clips],
        "source_frames": sum(clip["frame_count"] for clip in clips),
        "html_ref": reference(root, output / "review_motion_events.html"),
        "script_ref": reference(root, output / "motion_viewer.js"),
        "event_script_ref": reference(root, output / "motion_events.js"),
        "source_html_template_sha256": hashlib.sha256(_HTML.encode("utf-8")).hexdigest(),
        "base_script_sha256": hashlib.sha256(base_script).hexdigest(),
        "event_script_sha256": hashlib.sha256(event_script).hexdigest(),
        "angle_values_recomputed": False, "new_inference_calls": 0, "new_ground_truth_labels": 0,
        "events_aligned": False, "legacy_joint_reliability_transferred": False,
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "browser_interaction_verified": False,
    }
    write_json(output / "event_viewer_manifest.json", result)
    return result
