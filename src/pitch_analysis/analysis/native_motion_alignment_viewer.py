"""Package aligned plots with the unchanged, accepted source-frame player."""
from __future__ import annotations

from importlib.resources import files
import json
import os
from pathlib import Path
from urllib.parse import quote

from .native_motion_alignment import align_clip
from .native_motion_events import load_event_clips
from .native_motion_event_viewer import _validate_clips
from .native_motion_viewer import _HTML
from ..native_pose_io import BoundReader, reference, write_json


_PANEL = '''<section class="alignment-panel">
<h2>同投手曲線：人工前腳落地＝0秒</h2>
<p>點選任一顏色的曲線，回看該球最近的原片影格；也可用下方按鈕回到各球落地。
原始格號與播放器時間保持，對齊圖只平移橫軸。曲線重疊時，可先選球，再點圖中空白處定位。</p>
<div id="alignment-clips" class="controls"></div>
<p><label>曲線範圍 <select id="alignment-window"><option value="zoom">落地前後0.5秒</option><option value="full">完整原片</option></select></label></p>
<p id="alignment-status" class="hint" aria-live="polite">等待影片呈現影格</p>
<h3>投球肘</h3><svg id="aligned-elbow-chart" viewBox="0 0 960 280" aria-label="五球投球肘落地對齊曲線"></svg>
<h3>前導膝</h3><svg id="aligned-knee-chart" viewBox="0 0 960 280" aria-label="五球前導膝落地對齊曲線"></svg>
<p class="hint">虛線0秒是人工落地；出手標記顯示目前所選影片，人工範圍保留為色帶。
不確定候選使用虛線。曲線缺值仍斷線，沒有重取樣、補點、平滑或評分。</p></section>
<details><summary>目前影片的原片影格曲線</summary>'''


def write_alignment_viewer(root: str | Path, config_path: str | Path, output: str | Path) -> dict:
    """Verify bound events/curves, then write a fresh local comparison page."""
    loaded = load_event_clips(root, config_path, output)
    root, output = loaded["root"], loaded["output"]
    clips = [align_clip(clip) for clip in loaded["clips"]]
    _validate_clips(clips)
    packaged = [{key: value for key, value in clip.items() if key != "aligned_rows"} for clip in clips]
    # load_event_clips normally creates URLs for output/viewer; this page lives
    # directly inside output, so rebase those URLs from the original bound path.
    for clip in packaged:
        clip["overlay_url"] = quote(os.path.relpath(root / clip["source_refs"]["overlay_ref"]["path"], output)
                                    .replace("\\", "/"), safe="/.")
    data = json.dumps({"clips": packaged}, ensure_ascii=False, allow_nan=False)
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = _HTML.replace("<title>影片與2D曲線連動</title>", "<title>落地對齊曲線與來源影格</title>")
    html = html.replace("<h1>單投手：影片與2D角度曲線</h1>", "<h1>同投手：落地對齊曲線與影片回看</h1>")
    html = html.replace("<h2>投球肘</h2>", _PANEL + "<h2>投球肘</h2>", 1)
    html = html.replace('<p class="hint">點選曲線或使用滑桿', '</details><p class="hint">點選原片曲線或使用滑桿', 1)
    html = html.replace('</script></html>', '</script><script src="motion_alignment.js" defer></script></html>')
    html = html.replace("__DATA__", data)
    resources = files("pitch_analysis").joinpath("review_assets")
    scripts = {"motion_viewer.js": resources.joinpath("native_motion_viewer.js").read_bytes(),
               "motion_alignment.js": resources.joinpath("native_motion_alignment.js").read_bytes()}
    output.mkdir(parents=True, exist_ok=False)
    with (output / "review_alignment.html").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(html)
    for name, content in scripts.items():
        with (output / name).open("xb") as stream:
            stream.write(content)
    reader = BoundReader(root, loaded["source_refs"])
    for ref in loaded["source_refs"]:
        reader.path(ref)
    result = {"schema_version": "native-motion-alignment-viewer-v1", "status": "alignment_viewer_created",
              "pitcher_id": loaded["pitcher_id"], "clip_count": len(clips),
              "source_frames": sum(clip["frame_count"] for clip in clips),
              "request_ref": loaded["request_ref"],
              "source_exports": [clip["source_refs"] for clip in clips],
              "html_ref": reference(root, output / "review_alignment.html"),
              "script_ref": reference(root, output / "motion_viewer.js"),
              "alignment_script_ref": reference(root, output / "motion_alignment.js"),
              "navigation": "nearest original frame for chosen clip; wait for matching loaded source",
              "base_player_modified": False, "samples_resampled": False, "angle_values_recomputed": False,
              "event_midpoints_selected": False, "new_inference_calls": 0,
              "new_tracking_replays": 0, "new_ground_truth_labels": 0,
              "pointwise_reliability": "unknown", "usable_for_analysis": None,
              "browser_interaction_verified": False, "human_page_acceptance": "not_yet_recorded"}
    write_json(output / "alignment_viewer_manifest.json", result)
    return result
