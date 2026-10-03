"""Export original PNG frames and a blank CVAT skeleton label configuration.

This reads an already validated source MP4. It never runs a pose model or
creates frame annotations. The sibling ZIP is portable to another computer.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
import math
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


JOINT_NAMES = (
    "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
    "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
    "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
)
HUMAN_STATES = ("unreviewed", "visible", "uncertain", "not_observable")
SKELETON_EDGES = ((1, 2), (1, 3), (3, 5), (2, 4), (4, 6), (1, 7),
                  (2, 8), (7, 8), (7, 9), (9, 11), (8, 10), (10, 12))
TIMESTAMP_TOLERANCE_MS = 1.0
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return payload


def write_json(path: Path, payload: dict | list) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def cvat_labels() -> list[dict]:
    """Return the JSON array accepted by CVAT's Raw label editor.

    The SVG is a schematic label template, never an annotation on an image.
    CVAT's Raw validator requires text attribute values to be nonempty, hence
    [""] for review_note. See official raw-viewer.tsx and common.ts in cvat-ui.
    """
    positions = ((35, 20), (65, 20), (25, 35), (75, 35), (15, 50), (85, 50),
                 (40, 50), (60, 50), (35, 70), (65, 70), (30, 90), (70, 90))
    svg = []
    for first, second in SKELETON_EDGES:
        x1, y1 = positions[first - 1]
        x2, y2 = positions[second - 1]
        svg.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                   f'stroke="black" stroke-width="0.5" data-type="edge" '
                   f'data-node-from="{first}" data-node-to="{second}"></line>')
    sublabels = []
    for node, (name, (x, y)) in enumerate(zip(JOINT_NAMES, positions), start=1):
        color = "#2675db" if name.startswith("LEFT_") else "#e48b20"
        svg.append(f'<circle r="1.5" stroke="black" fill="{color}" cx="{x}" cy="{y}" '
                   f'stroke-width="0.1" data-type="element node" data-element-id="{node}" '
                   f'data-node-id="{node}" data-label-name="{name}"></circle>')
        sublabels.append({
            "name": name, "type": "points", "color": color,
            "attributes": [
                {"name": "human_state", "input_type": "select", "mutable": True,
                 "default_value": "unreviewed", "values": list(HUMAN_STATES)},
                {"name": "review_note", "input_type": "text", "mutable": True,
                 "default_value": "", "values": [""]},
            ],
        })
    return [{"name": "PITCHER_2D", "type": "skeleton", "color": "#2675db",
             "attributes": [], "sublabels": sublabels, "svg": "\n".join(svg)}]


def _positive_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _input_metadata(source: Path, pitch: str) -> dict:
    metadata = read_json(source.with_suffix(".json"))
    if (metadata.get("schema_version") != "pitch-input-v1" or metadata.get("pitch_id") != pitch
            or metadata.get("video", {}).get("file") != source.name):
        raise ValueError("Input metadata filename or pitch ID differs from the source MP4")
    return {
        "schema_version": "pitch-input-v1", "pitch_id": pitch,
        "pitcher": {key: metadata.get("pitcher", {}).get(key) for key in ("id", "display_name", "throws")},
        "video": {key: metadata["video"].get(key) for key in (
            "file", "camera_view", "horizontal_mirror", "playback_speed",
            "contains_single_pitch", "continuous_shot", "subject_framing",
        )},
    }


def _validate_metadata(source: Path, metadata: dict) -> tuple[int, int, int, list[float]]:
    if metadata.get("schema_version") != "video-validation-v1" or metadata.get("status") != "validated":
        raise ValueError("Use the existing validated video_metadata.json")
    # Existing validation reports use Windows paths, including when moved to a
    # different machine. The original basename and hash establish the binding.
    if not isinstance(metadata.get("path"), str) or re.split(r"[\\/]", metadata["path"])[-1] != source.name:
        raise ValueError("video_metadata.json filename differs from the source MP4")
    if metadata.get("sha256") != digest(source):
        raise ValueError("Source MP4 SHA-256 differs from video_metadata.json")
    count = _positive_integer(metadata.get("frame_count"), "frame_count")
    width = _positive_integer(metadata.get("width"), "width")
    height = _positive_integer(metadata.get("height"), "height")
    fps = _number(metadata.get("fps"), "fps")
    if not 0 < fps <= 240:
        raise ValueError("Invalid metadata FPS")
    stamps = metadata.get("timestamps_ms")
    if not isinstance(stamps, list) or len(stamps) != count:
        raise ValueError("Metadata timestamps must cover every source frame")
    timestamps = [_number(value, "timestamp_ms") for value in stamps]
    if (abs(timestamps[0]) > 1e-6 or any(value < 0 for value in timestamps)
            or any(right <= left for left, right in zip(timestamps, timestamps[1:]))):
        raise ValueError("Metadata timestamps must start at zero and strictly increase")
    return count, width, height, timestamps


def _export_frames(source: Path, metadata: dict, folder: Path) -> tuple[list[dict], dict]:
    """Decode once, retaining every original pixel and presentation timestamp."""
    import cv2

    count, width, height, timestamps = _validate_metadata(source, metadata)
    capture = cv2.VideoCapture(str(source))
    rows = []
    previous_decoded = None
    first_decoded = None
    maximum_error = 0.0
    try:
        if not capture.isOpened():
            raise ValueError("Cannot decode the source MP4")
        header_count = _number(capture.get(cv2.CAP_PROP_FRAME_COUNT), "decoded header frame count")
        header_fps = _number(capture.get(cv2.CAP_PROP_FPS), "decoded header FPS")
        if round(header_count) != count:
            raise ValueError("Source header frame count differs from video_metadata.json")
        if header_fps <= 0 or abs(header_fps - metadata["fps"]) / metadata["fps"] > 0.01:
            raise ValueError("Source header FPS differs from video_metadata.json")
        if (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))) != (width, height):
            raise ValueError("Source dimensions differ from video_metadata.json")
        if capture.get(cv2.CAP_PROP_ORIENTATION_META) != 0:
            raise ValueError("Source rotation metadata requires a prepared display-correct MP4")
        for index in range(count):
            ok, frame = capture.read()
            if not ok:
                raise ValueError(f"Missing decoded source frame {index}")
            if frame.shape[:2] != (height, width):
                raise ValueError(f"Source dimensions changed at frame {index}")
            decoded = _number(capture.get(cv2.CAP_PROP_POS_MSEC), "decoded timestamp_ms")
            if decoded < 0 or (previous_decoded is not None and decoded <= previous_decoded):
                raise ValueError("Source presentation timestamps are missing or not increasing")
            if first_decoded is None:
                first_decoded = decoded
            normalized = decoded - first_decoded
            error = abs(normalized - timestamps[index])
            maximum_error = max(maximum_error, error)
            if error > TIMESTAMP_TOLERANCE_MS:
                raise ValueError(f"Decoded timestamp differs from video_metadata.json at frame {index}")
            previous_decoded = decoded
            image_name = f"{source.stem}_frame_{index:04d}.png"
            ok, encoded = cv2.imencode(".png", frame, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            if not ok:
                raise ValueError(f"Cannot encode lossless PNG frame {index}")
            image = folder / image_name
            with image.open("xb") as stream:
                stream.write(encoded.tobytes())
            rows.append({"frame_index": index, "timestamp_ms": timestamps[index],
                         "image_name": image_name, "image_sha256": digest(image)})
        if capture.read()[0]:
            raise ValueError("Extra decoded source frames beyond video_metadata.json")
    finally:
        capture.release()
    return rows, {"decoded_frames": len(rows), "image_width": width, "image_height": height,
                  "header_fps": header_fps, "max_timestamp_error_ms": maximum_error,
                  "timestamp_tolerance_ms": TIMESTAMP_TOLERANCE_MS}


def _peer_exporter():
    """Reuse the established blank-review checks, without invoking its CLI."""
    spec = importlib.util.spec_from_file_location("manual_pose_peer_helpers", Path(__file__).with_name("export_peer_review_package.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _blank_notes(pitch: str, scope: str, count: int) -> str:
    notes = (REPOSITORY_ROOT / "review_tools" / "peer_review" / "REVIEW_NOTES_TEMPLATE.md").read_text(encoding="utf-8")
    for key, value in {"PITCH_ID": pitch, "TASK_SCOPE": scope,
                       "TOTAL_FRAMES": count, "LAST_FRAME": count - 1}.items():
        notes = notes.replace("{{" + key + "}}", str(value))
    return notes


def _event_template(source: Path, count: int, folder: Path | None) -> dict:
    peer = _peer_exporter()
    blank = peer.expand_blank_review(peer.blank_ground_truth(source, source.stem, count))
    if folder is not None:
        if folder.is_symlink():
            raise ValueError("Event-template folder must not be a symbolic link")
        folder = folder.resolve(strict=True)
        if folder.name != source.stem:
            raise ValueError("Event-template pitch ID differs from the source")
        for name in ("ground_truth.json", "REVIEW_NOTES.md"):
            if (folder / name).is_symlink():
                raise ValueError("Event-template files must not be symbolic links")
        if read_json(folder / "ground_truth.json") != blank:
            raise ValueError("Event ground truth must be entirely blank and bound to the source video")
        notes = " ".join((folder / "REVIEW_NOTES.md").read_text(encoding="utf-8").split())
        if not any(notes == " ".join(_blank_notes(source.stem, scope, count).split())
                   for scope in ("full_review", "events_supplement")):
            raise ValueError("Event review notes must use the blank worksheet")
    return blank


def _supplement_job(folder: Path) -> tuple[Path, dict, list[dict], list[Path], list[Path]]:
    """Accept only a verified blank pitch_005 task from a portable peer package."""
    if folder.is_symlink():
        raise ValueError("Supplement folder must not be a symbolic link")
    folder = folder.resolve(strict=True)
    if folder.name != "pitch_005":
        raise ValueError("The event supplement must be the clean pitch_005 folder")
    peer = _peer_exporter()
    package = read_json(folder.parent / "package_manifest.json")
    tasks = [task for task in package.get("tasks", []) if task.get("pitch_id") == "pitch_005"]
    if (package.get("schema_version") != "peer-review-package-v1" or len(tasks) != 1
            or tasks[0].get("task_scope") != "events_supplement"):
        raise ValueError("Supplement must be bound to one existing pitch_005 event task")
    task = tasks[0]
    source_info = task["source_video"]
    video = folder / "browser_playback" / "pitch_005.mp4"
    blank = peer.expand_blank_review(peer.blank_ground_truth(video, "pitch_005", source_info["total_frames"]))
    if blank["source_video"] != source_info or read_json(folder / "ground_truth.json") != blank:
        raise ValueError("Supplement ground truth must be entirely blank and bound to its source video")
    rows = peer.read_frame_index(folder / "frame_index.csv", source_info["total_frames"])
    frames = [folder / "frames" / f"frame_{i:04d}.jpg" for i in range(len(rows))]
    sheets = [folder / "contact_sheets" / f"frames_{i:04d}_{min(i+11,len(rows)-1):04d}.jpg" for i in range(0, len(rows), 12)]
    expected_files = {folder / name for name in ("ground_truth.json", "REVIEW_NOTES.md", "review_all.html", "frame_index.csv")}
    expected_files.update(frames + sheets + [video, folder / "browser_playback" / "overlay_browser.mp4"])
    if (folder / "input_metadata.json").is_file():
        expected_files.add(folder / "input_metadata.json")
    observed_files = set()
    for path in folder.rglob("*"):
        if path.is_symlink():
            raise ValueError("Supplement assets must not be symbolic links")
        if path.is_file():
            observed_files.add(path)
    if observed_files != expected_files:
        raise ValueError("Supplement folder contains missing or unexpected files; use the clean portable task")
    for asset in list(task["assets"].values()) + task["frame_pairs"] + task["contact_sheets"]:
        relative = Path(asset["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "pitch_005":
            raise ValueError("Invalid supplement asset path")
        path = folder.parent / relative
        if path not in expected_files or digest(path) != asset["sha256"]:
            raise ValueError("Supplement asset hash differs from its package manifest")
    if digest(folder / "ground_truth.json") != task["ground_truth_template_sha256"]:
        raise ValueError("Supplement blank template differs from its package manifest")
    template = _blank_notes("pitch_005", "events_supplement", len(rows))
    if " ".join((folder / "REVIEW_NOTES.md").read_text(encoding="utf-8").split()) != " ".join(template.split()):
        raise ValueError("Supplement review notes must use the blank worksheet")
    # HTML carries instructions and model states. Verify the generated page to
    # prevent arbitrary human answers or external links riding along with it.
    if (folder / "review_all.html").read_text(encoding="utf-8") != peer._review_html(task, rows, sheets):
        raise ValueError("Supplement review page differs from the clean portable task")
    return folder, task, rows, frames, sheets


def _asset(path: Path, root: Path) -> dict:
    return {"path": path.relative_to(root).as_posix(), "sha256": digest(path), "size_bytes": path.stat().st_size}


def _start_html(pitch: str, count: int, supplement: bool) -> str:
    escaped = html.escape(pitch)
    extra = '<p><a href="pitch_005/review_all.html">pitch_005：事件補充覆核</a></p>' if supplement else ""
    return ('<!doctype html>\n<html lang="zh-Hant"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>人工 XY 骨架標註</title><body style="font:18px/1.6 system-ui;max-width:900px;margin:2rem auto;padding:1rem">'
            f'<h1>{escaped}：人工 XY 骨架標註</h1><p>請先閱讀 <a href="START_HERE.md">完整 CVAT 操作說明</a>。'
            f'原始影格 {count} 張，從 0 到 {count - 1}；每張人工覆核 12 個身體關節。</p>'
            f'<p><a href="raw_frames_{escaped}.zip">CVAT 上傳用原始 PNG ZIP</a> · '
            '<a href="cvat_labels.json">Raw 標籤設定</a> · <a href="frame_manifest.json">來源與影格清單</a></p>'
            f'<p><a href="{escaped}.mp4">原始影片播放</a></p>'
            '<p>標籤 SVG 只是關節連線示意圖；此包沒有任何預填座標。左右指投手自己的身體。'
            'CVAT 使用 Shape 模式，每一格各自檢查；請逐點設定 human_state。</p>'
            f'<p><a href="{escaped}/REVIEW_NOTES.md">{escaped}：空白事件工作表</a> · '
            f'<a href="{escaped}/ground_truth.json">空白事件 JSON</a></p>{extra}</body></html>\n')


def export_package(source_mp4: Path, video_metadata_json: Path, output_directory: Path, *,
                   supplement_folder: Path | None = None, producer_git_commit: str | None = None,
                   event_template_folder: Path | None = None,
                   documentation_root: Path | None = None) -> dict:
    """Create a new directory and sibling ZIP, refusing to replace either."""
    output = output_directory.resolve()
    archive = output.with_name(output.name + ".zip")
    for path in (output, archive):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Manual-pose output already exists: {path}")
    source = source_mp4.resolve(strict=True)
    if not source.is_file() or source.suffix.lower() != ".mp4" or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", source.stem):
        raise ValueError("Source must be an original, named pitch MP4")
    if producer_git_commit is not None and not re.fullmatch(r"[0-9a-fA-F]{7,40}", producer_git_commit):
        raise ValueError("producer_git_commit must be a Git commit hash")
    metadata_path = video_metadata_json.resolve(strict=True)
    metadata = read_json(metadata_path)
    count, width, height, _ = _validate_metadata(source, metadata)
    input_metadata = _input_metadata(source, source.stem)
    source_sha256 = metadata["sha256"]
    metadata_sha256 = digest(metadata_path)
    event_blank = _event_template(source, count, event_template_folder)
    supplement = _supplement_job(supplement_folder) if supplement_folder is not None else None
    docs = documentation_root or REPOSITORY_ROOT / "review_tools" / "manual_pose"
    instructions = (docs / "START_HERE.md").read_text(encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".manual_pose_", dir=output.parent) as temporary:
        staging = Path(temporary) / output.name
        staging.mkdir()
        frames_folder = staging / "raw_frames"
        frames_folder.mkdir()
        rows, timing = _export_frames(source, metadata, frames_folder)
        source_target = staging / source.name
        shutil.copyfile(source, source_target)
        if digest(source_target) != source_sha256 or digest(source) != source_sha256:
            raise ValueError("Source changed while exporting")
        if digest(metadata_path) != metadata_sha256:
            raise ValueError("Video metadata changed while exporting")
        write_json(staging / "cvat_labels.json", cvat_labels())
        event_folder = staging / source.stem
        event_folder.mkdir()
        write_json(event_folder / "ground_truth.json", event_blank)
        (event_folder / "REVIEW_NOTES.md").write_text(_blank_notes(source.stem, "events_supplement", count), encoding="utf-8")
        images_zip = staging / f"raw_frames_{source.stem}.zip"
        with zipfile.ZipFile(images_zip, "x", compression=zipfile.ZIP_STORED) as image_archive:
            for row in rows:
                image_archive.write(frames_folder / row["image_name"], arcname=row["image_name"])
        supplement_manifest = None
        if supplement is not None:
            folder, task, _, _, _ = supplement
            target = staging / "pitch_005"
            shutil.copytree(folder, target)
            assets = [_asset(path, staging) for path in sorted(target.rglob("*")) if path.is_file()]
            # Recheck bytes after copying; no completed review can enter the package.
            for asset in assets:
                if digest(folder / Path(asset["path"]).relative_to("pitch_005")) != asset["sha256"]:
                    raise ValueError("Supplement changed while exporting")
            supplement_manifest = {"pitch_id": "pitch_005", "task_scope": "events_supplement",
                                   "source_video": task["source_video"], "assets": assets}
        manifest = {
            "schema_version": "manual-pose-package-v1", "pitch_id": source.stem,
            "source_video": {"pitch_id": source.stem, "filename": source.name,
                             "sha256": source_sha256, "total_frames": count, "frame_index_base": 0},
            "image_width": width, "image_height": height, "joint_names": list(JOINT_NAMES), "frames": rows,
            "created_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "producer_git_commit": producer_git_commit, "video_metadata_sha256": metadata_sha256,
            "input_metadata": input_metadata, "decoded_timing_verification": timing,
            "raw_frames_zip": _asset(images_zip, staging), "cvat_labels": _asset(staging / "cvat_labels.json", staging),
            "events_supplement": supplement_manifest,
            "event_review": {"pitch_id": source.stem, "task_scope": "events_supplement",
                             "ground_truth": _asset(event_folder / "ground_truth.json", staging),
                             "review_notes": _asset(event_folder / "REVIEW_NOTES.md", staging)},
        }
        write_json(staging / "frame_manifest.json", manifest)
        (staging / "START_HERE.md").write_text(instructions, encoding="utf-8")
        (staging / "START_HERE.html").write_text(_start_html(source.stem, count, supplement is not None), encoding="utf-8")
        staged_archive = Path(temporary) / archive.name
        with zipfile.ZipFile(staged_archive, "x", compression=zipfile.ZIP_DEFLATED) as package_zip:
            for path in sorted(staging.rglob("*")):
                if path.is_file():
                    package_zip.write(path, arcname=f"{output.name}/{path.relative_to(staging).as_posix()}")
        for path in (output, archive):
            if path.exists() or path.is_symlink():
                raise FileExistsError(f"Manual-pose output appeared during export: {path}")
        # Exclusive archive creation also closes a race with another exporter.
        with archive.open("xb") as stream, staged_archive.open("rb") as prepared:
            shutil.copyfileobj(prepared, stream)
        try:
            if output.exists() or output.is_symlink():
                raise FileExistsError(f"Manual-pose output appeared during export: {output}")
            staging.rename(output)
        except BaseException:
            archive.unlink()  # Only the new archive created by this invocation.
            raise
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_mp4", type=Path)
    parser.add_argument("video_metadata_json", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--supplement-folder", type=Path)
    parser.add_argument("--event-template-folder", type=Path)
    parser.add_argument("--producer-commit", dest="producer_git_commit")
    args = parser.parse_args()
    result = export_package(args.source_mp4, args.video_metadata_json, args.output_directory,
                            supplement_folder=args.supplement_folder, producer_git_commit=args.producer_git_commit,
                            event_template_folder=args.event_template_folder)
    print(f"Exported {len(result['frames'])} original PNG frames: {args.output_directory} and {args.output_directory}.zip")


if __name__ == "__main__":
    main()
