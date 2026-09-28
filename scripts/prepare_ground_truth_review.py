"""Export review evidence without inference, scoring, or human annotation.

Only untouched ground-truth-v1 templates may be expanded, with byte backups.
All original predictions, videos, and reports are read-only inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

from pitch_analysis.ground_truth import expand_blank_review, load_ground_truth


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def timeline_rows(metadata: dict, pose: dict, tracking: dict, processed: list[dict]) -> list[dict]:
    total = metadata["frame_count"]
    expected = list(range(total))
    if (pose["total_frames"] != total or tracking["total_frames"] != total
            or pose["frame_indices"] != expected
            or [row["frame_index"] for row in tracking["frames"]] != expected
            or [row["frame_index"] for row in processed] != expected
            or len(metadata["timestamps_ms"]) != total):
        raise ValueError("Review evidence timelines do not align")
    rows = []
    for frame in expected:
        stamp = metadata["timestamps_ms"][frame]
        if abs(stamp - processed[frame]["timestamp_ms"]) > 0.01:
            raise ValueError("Processed timestamp differs from decoded-video metadata")
        row = {"frame_index": frame, "timestamp_ms": stamp,
               "selection_status": tracking["frames"][frame]["selection_status"],
               "model_warnings": ";".join(tracking["frames"][frame]["warnings"])}
        for role, name in pose["important_joints"].items():
            states = pose["joints"][name]["frame_states"]
            if len(states) != total:
                raise ValueError("Joint-state timeline is incomplete")
            landmark = processed[frame]["landmarks"][name]
            actual = ("missing" if not landmark["usable"] else
                      "interpolated" if landmark["interpolated"] else "observed")
            if states[frame] != actual:
                raise ValueError("Reliability state differs from processed keypoints")
            row[role] = states[frame]
        rows.append(row)
    return rows


def pair_image(original: np.ndarray, overlay: np.ndarray, row: dict) -> np.ndarray:
    if original.shape != overlay.shape:
        raise ValueError("Original and overlay dimensions differ")
    height, width = original.shape[:2]
    canvas = np.full((height + 156, max(2 * width, 840), 3), 245, np.uint8)
    canvas[40:40 + height, :width] = original
    canvas[40:40 + height, width:width * 2] = overlay
    def label(value, x, y, size=0.48):
        cv2.putText(canvas, value, (x, y), cv2.FONT_HERSHEY_SIMPLEX, size, (15, 15, 15), 1, cv2.LINE_AA)
    label(f"ORIGINAL | frame {row['frame_index']:04d} | {row['timestamp_ms'] / 1000:.3f} s", 8, 25)
    label("EXISTING RAW OVERLAY", width + 8, 25)
    label("MODEL STATES (not human truth):", 8, height + 60)
    roles = ("throwing_shoulder", "throwing_elbow", "throwing_wrist", "lead_hip", "lead_knee", "lead_ankle")
    for index, role in enumerate(roles):
        label(f"{role}: {row[role]}", 8 + (index // 3) * 420, height + 82 + (index % 3) * 20)
    label(f"selection: {row['selection_status']}  warnings: {row['model_warnings'] or 'none'}", 8, height + 146)
    return canvas


def save_image(path: Path, image: np.ndarray) -> None:
    if path.exists():
        raise FileExistsError(path)
    if not cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise OSError(f"Cannot write {path}")


def export_frames(video: Path, overlay: Path, output: Path, rows: list[dict]) -> list[str]:
    (output / "frames").mkdir()
    (output / "contact_sheets").mkdir()
    source_cap, overlay_cap = cv2.VideoCapture(str(video)), cv2.VideoCapture(str(overlay))
    pages, tiles = [], []
    try:
        if not source_cap.isOpened() or not overlay_cap.isOpened():
            raise ValueError("Video or overlay cannot be opened")
        for row in rows:
            ok_source, original = source_cap.read()
            ok_overlay, predicted = overlay_cap.read()
            if not ok_source or not ok_overlay:
                raise ValueError(f"Missing decoded frame {row['frame_index']}")
            pair = pair_image(original, predicted, row)
            save_image(output / "frames" / f"frame_{row['frame_index']:04d}.jpg", pair)
            tile = np.full((430, 460, 3), 245, np.uint8)
            scale = min(460 / pair.shape[1], 400 / pair.shape[0])
            resized = cv2.resize(pair, (round(pair.shape[1] * scale), round(pair.shape[0] * scale)), interpolation=cv2.INTER_AREA)
            tile[30:30 + resized.shape[0], :resized.shape[1]] = resized
            cv2.putText(tile, f"Frame {row['frame_index']:04d} | {row['timestamp_ms']/1000:.3f} s", (8, 22), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(tile)
            if len(tiles) == 12 or row is rows[-1]:
                first = row["frame_index"] - len(tiles) + 1
                name = f"contact_sheets/frames_{first:04d}_{row['frame_index']:04d}.jpg"
                sheet = np.full((4 * 430, 3 * 460, 3), 245, np.uint8)
                for i, item in enumerate(tiles):
                    sheet[(i // 3)*430:(i // 3 + 1)*430, (i % 3)*460:(i % 3 + 1)*460] = item
                save_image(output / name, sheet)
                pages.append(name)
                tiles = []
        if source_cap.read()[0] or overlay_cap.read()[0]:
            raise ValueError("Video contains more frames than the recorded timeline")
    finally:
        source_cap.release()
        overlay_cap.release()
    return pages


def prepare(input_dir: Path, baseline: Path, output: Path) -> dict:
    input_dir, baseline = input_dir.resolve(strict=True), baseline.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"Review output already exists: {output}")
    summary = read_json(baseline / "evaluation_summary.json")
    jobs = []
    for item in summary["pitches"]:
        pitch = item["pitch_id"]
        video = input_dir / f"{pitch}.mp4"
        ground_truth = baseline / "ground_truth" / pitch / "ground_truth.json"
        annotation = load_ground_truth(ground_truth, source_video_path=video)
        expanded = expand_blank_review(annotation)
        prediction = baseline / "predictions" / summary["pitcher_id"] / pitch
        metadata = read_json(prediction / "video_metadata.json")
        if metadata["sha256"] != annotation["source_video"]["sha256"] or metadata["frame_count"] != annotation["source_video"]["total_frames"]:
            raise ValueError("Ground truth and prediction source disagree")
        pose = read_json(baseline / "reliability" / pitch / "pose_reliability.json")
        tracking = read_json(baseline / "reliability" / pitch / "tracking_reliability.json")
        processed = [json.loads(line) for line in (prediction / "processed_keypoints.jsonl").read_text().splitlines()]
        rows = timeline_rows(metadata, pose, tracking, processed)
        jobs.append((pitch, video, ground_truth, expanded, prediction, rows, pose["important_joints"]))
    # Record all baseline inputs before creating any output or updating blank templates.
    protected = {path: digest(path) for path in baseline.rglob("*") if path.is_file()}
    protected.update({job[1]: digest(job[1]) for job in jobs})
    output.mkdir(parents=True)
    backup = output / "template_backups"
    backup.mkdir()
    pitches = []
    for pitch, video, ground_truth, expanded, prediction, rows, joints in jobs:
        folder = output / pitch
        folder.mkdir()
        backup_path = backup / f"{pitch}.ground_truth.json"
        backup_path.write_bytes(ground_truth.read_bytes())
        pages = export_frames(video, prediction / "overlay.mp4", folder, rows)
        with (folder / "frame_index.csv").open("x", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        checklist = [f"# {pitch} 人工覆核", "", f"影格 0–{len(rows)-1}，區間兩端皆包含。以下方框尚未檢查；請只在 ground_truth.json 保存判斷。", "",
            f"- [原始影片](<{video.as_posix()}>)", f"- [Overlay](<{(prediction / 'overlay.mp4').as_posix()}>)",
            f"- [唯一人工標註檔](<{ground_truth.as_posix()}>)", "- [逐影格模型狀態](frame_index.csv)",
            "- [填寫說明](../START_HERE.md)", "", "## 檢查清單", ""]
        questions = ["主要 skeleton 是否為正確投手", "identity switch 區間", "明顯 track break 區間",
            "throwing shoulder 可靠性", "throwing elbow 可靠性", "throwing wrist 可靠性", "lead hip 可靠性", "lead knee 可靠性", "lead ankle 可靠性",
            "major pose failure 區間", "throwing arm 遮擋／不可信區間", "preparation start", "maximum / peak leg lift", "lead foot plant", "approximate release", "follow-through end"]
        checklist += [f"- [ ] {question}" for question in questions]
        checklist += ["", "## 解剖側別（來自既有 metadata，並非畫面左／右）", ""]
        checklist += [f"- {role}: `{name}`" for role, name in joints.items()]
        checklist += ["", "## 全部影格 contact sheets", "", "縮圖用於定位；關節判讀請開啟下方全尺寸影格，搭配影片前後動作。", ""]
        checklist += [f"- [{Path(page).stem}]({page})" for page in pages]
        checklist += ["", "## 全尺寸原片／overlay 對照", "", "| Frame | Clip timestamp | 圖片 |", "|---:|---:|---|"]
        checklist += [f"| {row['frame_index']} | {row['timestamp_ms']/1000:.3f} s | [開啟](frames/frame_{row['frame_index']:04d}.jpg) |" for row in rows]
        (folder / "review_checklist.md").write_text("\n".join(checklist) + "\n", encoding="utf-8")
        pitches.append({"pitch_id": pitch, "total_frames": len(rows), "frame_pair_count": len(rows), "contact_sheet_count": len(pages),
                        "video": str(video), "video_sha256": protected[video], "overlay": str(prediction / "overlay.mp4"),
                        "ground_truth": str(ground_truth), "template_backup": str(backup_path),
                        "template_original_sha256": protected[ground_truth]})
        print(f"Prepared {pitch}: {len(rows)} frame pairs, {len(pages)} sheets", flush=True)
    # Fail before template changes if any read-only source was changed concurrently.
    for path, sha in protected.items():
        if digest(path) != sha:
            raise ValueError(f"Source changed during export: {path}")
    for (_, _, path, expanded, _, _, _), item in zip(jobs, pitches):
        path.write_text(json.dumps(expanded, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        item["template_expanded_sha256"] = digest(path)
    result = {"purpose": "manual_review_preparation_only", "human_labels_filled": 0, "comparison_executed": False,
              "protected_source_files_verified": len(protected), "template_changes": "blank schema expansion only; originals backed up",
              "pitches": pitches, "source_sha256_before": {str(path): sha for path, sha in protected.items()}}
    write_json(output / "preparation_manifest.json", result)
    guidelines = Path(__file__).resolve().parents[1] / "docs" / "phase2_ground_truth.md"
    start = ["# Phase 2 Ground Truth Review", "", "人工覆核 0/5；沒有自動填寫人工判斷，也沒有執行 prediction comparison。", "",
             f"先讀 [欄位與逐支檢查流程](<{guidelines.as_posix()}>)。", "",
             "每支依序：原片完整播放 → overlay 完整播放 → 對照逐影格 → 填 JSON → 只驗證格式。", "",
             "observed / interpolated / missing 是既有處理後模型狀態；原 overlay 顯示 raw 骨架，因此可能仍畫出已被品質 gate 排除的關節。observed 不代表人工認定正確。", "",
             "所有模型警示只是線索。請看完整影片，不要只檢查模型標記區間。", ""]
    start += [f"- [{item['pitch_id']}：{item['total_frames']} frames]({item['pitch_id']}/review_checklist.md)" for item in pitches]
    start += ["", "原始空模板備份：`template_backups/`。這是歷史備份，不是另一套待填 ground truth。", ""]
    (output / "START_HERE.md").write_text("\n".join(start), encoding="utf-8")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("baseline_root", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    prepare(args.input_dir, args.baseline_root, args.output_dir)
