"""Export a portable, blank peer-review package from existing review evidence.

This copies existing media and model states only. It never runs inference,
transcodes video, or changes canonical ground truth. Reviewers can double-click
START_HERE.html after extracting the ZIP; Python is only an optional fallback.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pitch_analysis.ground_truth import blank_ground_truth, expand_blank_review


JOINT_ROLES = (
    "throwing_shoulder", "throwing_elbow", "throwing_wrist",
    "lead_hip", "lead_knee", "lead_ankle",
)
CSV_FIELDS = ("frame_index", "timestamp_ms", "selection_status", "model_warnings") + JOINT_ROLES
SCOPES = {"full_review": "完整覆核", "events_supplement": "事件補充"}
STYLE = """body{font:17px/1.6 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#18222b;background:#f7f8fa}a{color:#075aa8}h1,h2{line-height:1.25}.notice,article,figure{background:white;padding:1rem;border:1px solid #d5dce2;border-radius:10px;margin:1rem 0}.videos,.sheets{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}video,img{max-width:100%;height:auto}video{width:100%;background:#111}small{display:block;color:#455561}nav{position:sticky;top:0;background:#f7f8fa;padding:.6rem 0}input,button,select{font:inherit;padding:.2rem .5rem}figure:target{outline:3px solid #efb527}code{background:#eaf0f4;padding:.1rem .3rem}table{border-collapse:collapse}td,th{border:1px solid #ccd4da;padding:.4rem}"""

SERVE_REVIEW = '''"""Optional loopback-only fallback. Default: double-click START_HERE.html."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import webbrowser

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    handler = partial(SimpleHTTPRequestHandler, directory=str(root))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        url = f"http://127.0.0.1:{server.server_address[1]}/START_HERE.html"
        print(f"Review available locally at {url}; press Ctrl+C to stop.")
        webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
'''


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def read_frame_index(path: Path, total_frames: int) -> list[dict]:
    """Require complete, ordered, zero-based evidence before copying anything."""
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise ValueError("frame_index.csv has unexpected model-state columns")
        rows = list(reader)
    if len(rows) != total_frames:
        raise ValueError("frame_index.csv does not cover every source frame")
    previous_stamp = -1.0
    for index, row in enumerate(rows):
        if row["frame_index"] != str(index):
            raise ValueError("frame_index.csv must be ordered frames 0 through N-1")
        try:
            stamp = float(row["timestamp_ms"])
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid frame timestamp") from error
        if not math.isfinite(stamp) or stamp < 0 or stamp <= previous_stamp:
            raise ValueError("Frame timestamps must be finite and strictly increasing")
        if index == 0 and abs(stamp) > 1.0:
            raise ValueError("Frame timestamps must start at clip time zero")
        if any(row[role] not in ("observed", "interpolated", "missing") for role in JOINT_ROLES):
            raise ValueError("Invalid model joint state in frame_index.csv")
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Malformed row in frame_index.csv")
        previous_stamp = stamp
    return rows


def verify_timing(source: Path, overlay: Path, rows: list[dict]) -> dict:
    """Decode existing playback assets and check counts/FPS/timestamps, without writes."""
    import cv2

    videos = {}
    for name, path in (("source", source), ("overlay", overlay)):
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise ValueError(f"Cannot decode {name} playback video")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            if not math.isfinite(fps) or fps <= 0:
                raise ValueError(f"Invalid {name} playback FPS")
            max_error = 0.0
            for row in rows:
                if not capture.read()[0]:
                    raise ValueError(f"Missing {name} decoded frame {row['frame_index']}")
                stamp = float(capture.get(cv2.CAP_PROP_POS_MSEC))
                if not math.isfinite(stamp):
                    raise ValueError(f"Invalid {name} decoded timestamp")
                max_error = max(max_error, abs(stamp - float(row["timestamp_ms"])))
            if capture.read()[0]:
                raise ValueError(f"Extra decoded frames in {name} playback video")
            if max_error > 1.0:
                raise ValueError(f"{name} playback timestamps differ from frame_index.csv by more than 1 ms")
            videos[name] = {"decoded_frames": len(rows), "fps": fps, "max_timestamp_error_ms": max_error}
        finally:
            capture.release()
    if abs(videos["source"]["fps"] - videos["overlay"]["fps"]) > 0.01:
        raise ValueError("Source and overlay playback FPS disagree")
    return videos


def _asset(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path), "size_bytes": path.stat().st_size}


def _copy(path: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, destination)
    if digest(path) != digest(destination):
        raise ValueError(f"Copied asset hash differs: {destination.name}")


def _document(name: str, documentation_root: Path | None, default: str) -> str:
    folder = documentation_root or Path(__file__).resolve().parents[1] / "review_tools" / "peer_review"
    path = folder / name
    return path.read_text(encoding="utf-8") if path.is_file() else default


def _input_metadata(source_root: Path, pitch: str) -> dict | None:
    path = source_root / f"{pitch}.json"
    if not path.is_file():
        return None
    payload = read_json(path)
    if payload.get("pitch_id") != pitch:
        raise ValueError("Input metadata pitch ID differs from the selected task")
    # Only source interpretation fields are relevant; no free-form notes are copied.
    return {
        "schema_version": payload.get("schema_version"), "pitch_id": pitch,
        "pitcher": {key: payload.get("pitcher", {}).get(key) for key in ("id", "display_name", "throws")},
        "video": {key: payload.get("video", {}).get(key) for key in (
            "camera_view", "horizontal_mirror", "playback_speed", "contains_single_pitch", "continuous_shot", "subject_framing",
        )},
    }


def _page(title: str, content: str) -> str:
    return f'<!doctype html>\n<html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{STYLE}</style><body>{content}</body></html>\n'


def _review_html(task: dict, rows: list[dict], sheets: list[Path]) -> str:
    pitch = task["pitch_id"]
    scope = SCOPES[task["task_scope"]]
    instruction = ("覆核全段：投手選擇、identity switch、track break、六個關節可靠性、major pose failure、投球手遮擋與五個事件。"
                   if task["task_scope"] == "full_review" else
                   "本次只補五個事件；未覆核的投手選擇、區間和關節欄位請保持 null，annotation_status 保持 in_progress。")
    metadata = task.get("input_metadata")
    anatomy = ""
    if metadata:
        throws = metadata["pitcher"].get("throws")
        sides = {"RIGHT": ("右", "左"), "LEFT": ("左", "右")}
        if throws in sides:
            arm, leg = sides[throws]
            anatomy = f'<p>來源 metadata：{arm}手投球。throwing shoulder / elbow / wrist 是{arm}肩／肘／腕；lead hip / knee / ankle 是{leg}髖／膝／踝。解剖側別與畫面左右不同。</p>'
    content = f'''<p><a href="../START_HERE.html">← 開始頁</a></p><h1>{html.escape(pitch)} · {scope}</h1>
<div class="notice"><p>{instruction}</p><p>影格從 <strong>0</strong> 起算，範圍 0–{task['last_frame']}（兩端皆包含）。人工標註檔是空白的 ground-truth-v1 / phase2_full_review。</p>
<p>observed / interpolated / missing、selection_status 和 warnings 都是<strong>既有模型狀態</strong>。observed 不代表人工判定正確；請依原片與完整動作獨立判讀。</p>{anatomy}
<p><a href="ground_truth.json" download>空白 ground_truth.json</a> · <a href="REVIEW_NOTES.md" download>REVIEW_NOTES.md 工作表</a> · <a href="frame_index.csv">逐格模型狀態 CSV</a> · <a href="../START_HERE.md">填寫說明</a></p></div>
<h2>完整影片</h2><p>原片保持原始位元組；骨架片是既有 raw overlay 的瀏覽器播放轉檔。下方圖片是原片／raw overlay 的逐格對照。</p>
<div class="videos"><article><h3>原始影片</h3><video controls preload="metadata" src="browser_playback/{pitch}.mp4"></video><p><a href="browser_playback/{pitch}.mp4">直接開啟原片</a></p></article>
<article><h3>既有骨架影片</h3><video controls preload="metadata" src="browser_playback/overlay_browser.mp4"></video><p><a href="browser_playback/overlay_browser.mp4">直接開啟骨架片</a></p></article></div>
<p><label>播放速度 <select id="speed"><option value="1">1×</option><option value="0.5">0.5×</option><option value="0.25">0.25×</option></select></label> <button type="button" id="sync">以原片目前時間對齊骨架片</button></p>
<h2>全部 contact sheets</h2><p>縮圖用於定位；關節判讀請使用下方全尺寸影格，搭配影片的前後動作。</p><div class="sheets">'''
    for sheet in sheets:
        link = f"contact_sheets/{sheet.name}"
        content += f'<a href="{link}" target="_blank"><img loading="lazy" src="{link}" alt="{html.escape(sheet.stem)}"></a>\n'
    content += f'''</div><h2>全部逐影格對照</h2><nav><label>前往影格 <input id="frame" type="number" min="0" max="{task['last_frame']}" value="0"></label> <button type="button" id="jump">前往</button></nav>'''
    for row in rows:
        index = int(row["frame_index"])
        link = f"frames/frame_{index:04d}.jpg"
        states = " · ".join(f"{role}: {row[role]}" for role in JOINT_ROLES)
        details = f"模型狀態：{states}; selection: {row['selection_status']}; warnings: {row['model_warnings'] or 'none'}"
        content += f'<figure id="frame-{index}"><figcaption>第 {index} 格 · {float(row["timestamp_ms"])/1000:.3f} 秒</figcaption><a href="{link}" target="_blank"><img loading="lazy" src="{link}" alt="第 {index} 格原片與骨架對照"></a><small>{html.escape(details)}</small></figure>\n'
    content += '''<script>
document.getElementById('speed').addEventListener('change',e=>document.querySelectorAll('video').forEach(v=>v.playbackRate=Number(e.target.value)));
document.getElementById('sync').addEventListener('click',()=>{const videos=document.querySelectorAll('video');videos[1].currentTime=videos[0].currentTime;});
document.getElementById('jump').addEventListener('click',()=>{const n=Number(document.getElementById('frame').value);const target=document.getElementById('frame-'+n);if(target)target.scrollIntoView();});
</script>'''
    return _page(f"{pitch} peer review", content)


def _start_html(tasks: list[dict]) -> str:
    content = '''<h1>離線同儕覆核包</h1><div class="notice"><p>先解壓縮整個 ZIP，再以 Edge 或 Chrome 雙擊開啟這個 START_HERE.html。影片與图片均在包內；覆核不需要 Python、Git 或網路。</p>
<p>流程：原片完整播放 → 骨架片完整播放 → 逐格對照 → 填 REVIEW_NOTES.md 或 ground_truth.json → 把完成檔交回。請先填自己的 reviewer；空白範本 annotation_status 是 unreviewed，開始填寫後改為 in_progress。</p>
<p>所有影格均從 0 起算，區間兩端皆包含。null 代表尚未覆核；[] 是已覆核後確認無該類區間。不要用模型輸出代填人工判斷；不清楚時保留 uncertain 或 not_observable 並寫原因。</p>
<p>JSON 是唯一結構化格式 ground-truth-v1。工作表可先記錄觀察，再由接收者轉錄到該 JSON；事件補充覆核不代表完整覆核。</p>
<p><a href="START_HERE.md">完整填寫與交回說明</a> · <a href="package_manifest.json">來源綁定與任務清單</a></p></div>'''
    for task in tasks:
        pitch = task["pitch_id"]
        content += f'<article><h2><a href="{pitch}/review_all.html">{html.escape(pitch)} · {SCOPES[task["task_scope"]]}</a></h2><p>{task["total_frames"]} 格；影格 0–{task["last_frame"]}。</p><p><a href="{pitch}/REVIEW_NOTES.md">工作表</a> · <a href="{pitch}/ground_truth.json">空白標註檔</a></p></article>'
    content += '<p>若瀏覽器無法以檔案方式播放影片，可直接開啟每支原片／骨架片；有 Python 的使用者也可執行 <code>python serve_review.py</code> 啟動本機備援頁面。此服務僅綁定 127.0.0.1；關閉時按 Ctrl+C。</p>'
    return _page("離線同儕覆核包", content)


def export_package(
    baseline_root: Path, source_root: Path, output_directory: Path, *,
    full_review: list[str], events_supplement: list[str],
    review_assets_root: Path | None = None, producer_git_commit: str | None = None,
    verify_video_timing: bool = True, documentation_root: Path | None = None,
) -> dict:
    """Create a new package directory and sibling ZIP; never replace an export."""
    baseline_root, source_root = baseline_root.resolve(strict=True), source_root.resolve(strict=True)
    output = output_directory.resolve()
    archive = output.with_name(output.name + ".zip")
    for path in (output, archive):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Peer-review output already exists: {path}")
    selected = [(pitch, "full_review") for pitch in full_review] + [(pitch, "events_supplement") for pitch in events_supplement]
    if not selected:
        raise ValueError("Select at least one explicit review task")
    if len({pitch for pitch, _ in selected}) != len(selected):
        raise ValueError("A pitch may have only one task scope per package")
    if producer_git_commit is not None and not re.fullmatch(r"[0-9a-fA-F]{7,40}", producer_git_commit):
        raise ValueError("producer_git_commit must be a Git commit hash")
    if review_assets_root is None:
        helpers = sorted(path for path in baseline_root.glob("review_helper_*") if path.is_dir())
        if len(helpers) != 1:
            raise ValueError("Specify --review-assets-root when there is not exactly one review_helper_* directory")
        review_assets_root = helpers[0]
    review_assets_root = review_assets_root.resolve(strict=True)
    jobs = []
    for pitch, scope in selected:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", pitch):
            raise ValueError("Invalid pitch ID")
        canonical = read_json(baseline_root / "ground_truth" / pitch / "ground_truth.json")
        source_info = canonical["source_video"]
        if source_info.get("pitch_id") != pitch or source_info.get("filename") != f"{pitch}.mp4" or source_info.get("frame_index_base") != 0:
            raise ValueError("Canonical source metadata does not match the selected pitch")
        video = source_root / source_info["filename"]
        # Rebuild from source binding. No reviewer, timestamp, labels, or notes are reused.
        blank = expand_blank_review(blank_ground_truth(video, pitch, source_info["total_frames"]))
        if blank["source_video"] != source_info:
            raise ValueError("Canonical source binding does not match the original video")
        folder = review_assets_root / pitch
        browser_source = folder / "browser_playback" / "source_browser.mp4"
        browser_overlay = folder / "browser_playback" / "overlay_browser.mp4"
        if digest(browser_source) != source_info["sha256"]:
            raise ValueError("Browser source copy differs from the original video")
        if not browser_overlay.is_file():
            raise FileNotFoundError(browser_overlay)
        rows = read_frame_index(folder / "frame_index.csv", source_info["total_frames"])
        frames = [folder / "frames" / f"frame_{i:04d}.jpg" for i in range(len(rows))]
        if any(not path.is_file() for path in frames):
            raise ValueError(f"Missing frame pair for {pitch}")
        if set((folder / "frames").iterdir()) != set(frames):
            raise ValueError(f"Unexpected frame pair assets for {pitch}")
        sheets = [folder / "contact_sheets" / f"frames_{i:04d}_{min(i+11,len(rows)-1):04d}.jpg" for i in range(0,len(rows),12)]
        if any(not path.is_file() for path in sheets):
            raise ValueError(f"Missing contact sheet for {pitch}")
        if set((folder / "contact_sheets").iterdir()) != set(sheets):
            raise ValueError(f"Unexpected contact sheet assets for {pitch}")
        timing = verify_timing(browser_source, browser_overlay, rows) if verify_video_timing else None
        metadata = _input_metadata(source_root, pitch)
        jobs.append((pitch, scope, folder, blank, rows, frames, sheets, timing, metadata))
    # Validate every selected task before creating output, and stage the complete ZIP.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".peer_review_", dir=output.parent) as temporary:
        staging = Path(temporary) / output.name
        staging.mkdir()
        tasks = []
        for pitch, scope, folder, blank, rows, frames, sheets, timing, metadata in jobs:
            target = staging / pitch
            target.mkdir()
            source_target = target / "browser_playback" / f"{pitch}.mp4"
            overlay_target = target / "browser_playback" / "overlay_browser.mp4"
            _copy(folder / "browser_playback" / "source_browser.mp4", source_target)
            _copy(folder / "browser_playback" / "overlay_browser.mp4", overlay_target)
            if digest(source_target) != blank["source_video"]["sha256"]:
                raise ValueError("Source changed while exporting")
            _copy(folder / "frame_index.csv", target / "frame_index.csv")
            for asset in frames + sheets:
                _copy(asset, target / asset.relative_to(folder))
            ground_truth = target / "ground_truth.json"
            write_json(ground_truth, blank)
            task = {
                "pitch_id": pitch, "task_scope": scope, "source_video": blank["source_video"],
                "total_frames": len(rows), "first_frame": 0, "last_frame": len(rows) - 1,
                "ground_truth_path": f"{pitch}/ground_truth.json", "ground_truth_template_sha256": digest(ground_truth),
                "review_notes_path": f"{pitch}/REVIEW_NOTES.md", "frame_pair_count": len(frames), "contact_sheet_count": len(sheets),
                "assets": {"source_video": _asset(source_target, staging), "overlay_video": _asset(overlay_target, staging), "frame_index": _asset(target / "frame_index.csv", staging)},
                "frame_pairs": [_asset(target / path.relative_to(folder), staging) for path in frames],
                "contact_sheets": [_asset(target / path.relative_to(folder), staging) for path in sheets],
                "playback_timing_verification": timing, "input_metadata": metadata,
            }
            if metadata is not None:
                write_json(target / "input_metadata.json", metadata)
            notes = _document("REVIEW_NOTES_TEMPLATE.md", documentation_root,
                "# {{PITCH_ID}} — {{TASK_SCOPE}}\n\nReviewer: \n\nSource frames: 0–{{LAST_FRAME}} ({{TOTAL_FRAMES}} total; inclusive)\n\n## Observations\n\n| Field / event | Frame or inclusive range | Status | Reason / uncertainty |\n|---|---|---|---|\n| | | | |\n")
            for key, value in {"PITCH_ID": pitch, "TASK_SCOPE": scope, "TOTAL_FRAMES": len(rows), "LAST_FRAME": len(rows)-1}.items():
                notes = notes.replace("{{" + key + "}}", str(value))
            (target / "REVIEW_NOTES.md").write_text(notes, encoding="utf-8")
            (target / "review_all.html").write_text(_review_html(task, rows, sheets), encoding="utf-8")
            tasks.append(task)
        manifest = {"schema_version": "peer-review-package-v1", "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "producer_git_commit": producer_git_commit, "frame_index_base": 0, "tasks": tasks}
        write_json(staging / "package_manifest.json", manifest)
        (staging / "START_HERE.html").write_text(_start_html(tasks), encoding="utf-8")
        (staging / "START_HERE.md").write_text(_document("START_HERE.md", documentation_root,
            "# Peer review\n\nExtract the complete ZIP and double-click START_HERE.html in Edge or Chrome.\n\nReview the original video, existing overlay and all frame pairs. Frame indices are zero-based; ranges are inclusive. Model states are not human labels. Fill only the assigned scope using ground_truth.json (ground-truth-v1) or REVIEW_NOTES.md. Return completed files with your reviewer name. Event supplements remain in_progress with unreviewed labels null.\n"), encoding="utf-8")
        (staging / "serve_review.py").write_text(SERVE_REVIEW, encoding="utf-8")
        staged_archive = Path(temporary) / archive.name
        with zipfile.ZipFile(staged_archive, "x", compression=zipfile.ZIP_DEFLATED) as package_zip:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    package_zip.write(path, arcname=f"{output.name}/{path.relative_to(staging).as_posix()}")
        for path in (output, archive):
            if path.exists() or path.is_symlink():
                raise FileExistsError(f"Peer-review output appeared during export: {path}")
        staging.rename(output)
        with archive.open("xb") as stream, staged_archive.open("rb") as prepared_zip:
            shutil.copyfileobj(prepared_zip, stream)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_root", type=Path)
    parser.add_argument("source_root", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--full-review", action="append", default=[], metavar="PITCH_ID")
    parser.add_argument("--events-supplement", action="append", default=[], metavar="PITCH_ID")
    parser.add_argument("--review-assets-root", type=Path)
    parser.add_argument("--producer-commit", dest="producer_git_commit")
    args = parser.parse_args()
    result = export_package(args.baseline_root, args.source_root, args.output_directory,
        full_review=args.full_review, events_supplement=args.events_supplement,
        review_assets_root=args.review_assets_root, producer_git_commit=args.producer_git_commit)
    print(f"Exported {len(result['tasks'])} explicit peer-review tasks: {args.output_directory} and {args.output_directory}.zip")
