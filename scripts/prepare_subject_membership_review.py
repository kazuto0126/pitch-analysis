"""Export fixed raw-image membership questions, never human labels or masks."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def export(plan_path: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError("A fresh review directory is required")
    plan = read(plan_path)
    video = Path(plan["source_video"]["path"])
    if sha(video) != plan["source_video"]["sha256"]:
        raise ValueError("Source video changed")
    old_path = Path(plan["previous_query_snapshot"]["path"])
    if sha(old_path) != plan["previous_query_snapshot"]["sha256"]:
        raise ValueError("Previous query snapshot changed")
    old = {q["query_id"]: q for q in read(old_path)["queries"]}
    queries = plan["queries"]
    if not queries or len({q["query_id"] for q in queries}) != len(queries):
        raise ValueError("Empty or duplicate queries")
    width, height, count = plan["width"], plan["height"], plan["total_frames"]
    pairs = set()
    for q in queries:
        frame, number = q["frame_index"], q["display_number"]
        x, y = q["image_xy_px"]
        if not 0 <= frame < count or not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Invalid frame or coordinate")
        if not (0 <= x < width and 0 <= y < height) or (frame, number) in pairs:
            raise ValueError("Out-of-image or duplicate display question")
        pairs.add((frame, number))
        prior = q.get("previous_query_id")
        if prior and (old[prior]["frame_index"] != frame or
                      old[prior]["queried_image_xy_px"] != [x, y]):
            raise ValueError("Prior question coordinate/frame mismatch")
    output.mkdir(parents=True)
    (output / "raw_frames").mkdir()
    reader = cv2.VideoCapture(str(video))
    files, questions = [], []
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 21)
    small = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16)
    palette = ["#ffcf39", "#43d5ff", "#ff6596", "#ac9cff", "#9dea79", "#ffab6d"]
    try:
        for frame in range(count):
            ok, pixels = reader.read()
            if not ok or pixels.shape[:2] != (height, width):
                raise ValueError("Source decode/dimensions mismatch")
            chosen = sorted((q for q in queries if q["frame_index"] == frame),
                            key=lambda q: q["display_number"])
            if not chosen:
                continue
            timestamp = float(reader.get(cv2.CAP_PROP_POS_MSEC))
            raw = Image.fromarray(cv2.cvtColor(pixels, cv2.COLOR_BGR2RGB))
            raw_path = output / "raw_frames" / f"pitch_003_frame_{frame:04d}.png"
            raw.save(raw_path)
            # Full raw context stays untouched. Only separate, single-query crops are marked.
            columns, cell = 2, 270
            rows = math.ceil(len(chosen) / columns)
            panel = Image.new("RGB", (540, 100 + height + rows * 310 + 70), "#111723")
            draw = ImageDraw.Draw(panel)
            draw.text((12, 8), f"pitch_003 | frame {frame} | {len(chosen)} questions", font=font, fill="white")
            draw.text((12, 40), "Original above; ONE ring center in each crop below", font=small, fill="white")
            panel.paste(raw, (15, 75))
            for index, q in enumerate(chosen):
                x, y = q["image_xy_px"]
                left, top = math.floor(x) - 48, math.floor(y) - 48
                crop = raw.crop((left, top, left + 96, top + 96)).resize((240, 240), Image.Resampling.NEAREST)
                cx, cy = (x - left) * 2.5, (y - top) * 2.5
                ink = ImageDraw.Draw(crop)
                color = palette[index % len(palette)]
                ink.ellipse((cx-12, cy-12, cx+12, cy+12), outline="black", width=5)
                ink.ellipse((cx-12, cy-12, cx+12, cy+12), outline=color, width=3)
                px, py = (index % 2) * cell + 15, 90 + height + (index // 2) * 310
                draw.text((px, py), f"Question {q['display_number']}: center", font=font, fill=color)
                panel.paste(crop, (px, py + 31))
                previous = q.get("previous_query_id")
                caption = f"Prior {previous.split('_')[-1]} (same position)" if previous else "New image position; not a joint"
                draw.text((px, py + 279), caption, font=small, fill="white")
                questions.append({**q, "timestamp_ms": timestamp, "raw_image_sha256": sha(raw_path),
                                  "human_status": "unreviewed", "human_code": None,
                                  "confidence": None, "reviewer_note": None})
            draw.text((12, panel.height-48), "T torso | P other pitcher part | O others/background", font=small, fill="white")
            draw.text((12, panel.height-25), "? uncertain. Classify only the visible ring CENTER.", font=small, fill="white")
            display = output / f"pitch_003_frame_{frame:04d}_review.png"
            panel.save(display)
            files.append({"frame_index": frame, "raw_image": str(raw_path), "raw_sha256": sha(raw_path),
                          "display_image": str(display), "display_sha256": sha(display)})
    finally:
        reader.release()
    if len(questions) != len(queries) or sha(video) != plan["source_video"]["sha256"]:
        raise ValueError("Incomplete export or source changed")
    manifest = {"purpose": "Recheck five prior questions and three new fixed image centers",
                "source_video": plan["source_video"], "plan_path": str(plan_path),
                "plan_sha256": sha(plan_path), "generator_code_sha256": sha(Path(__file__)),
                "previous_query_snapshot": plan["previous_query_snapshot"],
                "width": width, "height": height, "total_frames": count,
                "questions": questions, "files": files, "reviewer": None, "reviewed_at_utc": None,
                "new_pose_or_segmentation_inference": False, "original_answers_modified": False,
                "human_review_status": "unreviewed", "limits": plan["limits"]}
    (output / "query_manifest.json").write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = export(args.plan, args.output)
    print(json.dumps({"queries": len(result["questions"]), "human_status": "unreviewed"}))
