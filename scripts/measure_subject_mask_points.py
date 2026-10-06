"""Isolated same-model point measurements via public Image indexing; no human labels."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path

import cv2

from pitch_analysis.subject import PitcherSelector


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def validate_mask(image, width, height):
    if int(image.image_format) != 9 or image.channels != 1:
        raise ValueError("unexpected_pose_mask_format")
    if (image.width, image.height) != (width, height) or width <= 0 or height <= 0:
        raise ValueError("mask_source_dimensions_mismatch")


def sample_mask_point(image, x, y):
    """Bilinear point value; validate every native index before public access."""
    width, height = image.width, image.height
    validate_mask(image, width, height)
    if not (math.isfinite(x) and math.isfinite(y) and 0 <= x < width and 0 <= y < height):
        raise ValueError("query_outside_source_image")
    left, top = math.floor(x), math.floor(y)
    right, bottom = min(left + 1, width - 1), min(top + 1, height - 1)
    dx, dy = x - left, y - top
    weights = {}
    for row, col, weight in ((top, left, (1-dy)*(1-dx)), (top, right, (1-dy)*dx),
                             (bottom, left, dy*(1-dx)), (bottom, right, dy*dx)):
        weights[row, col] = weights.get((row, col), 0.0) + weight
    pixels = []
    for (row, col), weight in weights.items():
        # GetValue in some SDK versions does not check bounds itself.
        if not (0 <= row < height and 0 <= col < width):
            raise ValueError("native_index_outside_source_image")
        value = float(image[row, col])
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("invalid_mask_probability")
        pixels.append({"row": row, "column": col, "probability": value, "weight": weight})
    return sum(p["probability"] * p["weight"] for p in pixels), pixels


def selected_mask(masks, candidate_count, index, width, height):
    if index is None:
        return None, "no_selected_subject"
    if len(masks) != candidate_count:
        return None, "mask_candidate_count_mismatch"
    if not 0 <= index < len(masks):
        return None, "selected_mask_absent"
    try:
        validate_mask(masks[index], width, height)
    except ValueError as error:
        return None, str(error)
    return masks[index], None


def run(plan_path, output):
    import mediapipe as mp

    if output.exists():
        raise FileExistsError("Fresh experimental output required")
    plan = read(plan_path)
    for path, expected in plan["source_hashes"].items():
        if sha(path) != expected:
            raise ValueError("Frozen source changed: " + path)
    if version("mediapipe") != plan["mediapipe_version"]:
        raise ValueError("Pinned SDK changed")
    positions = {}
    for path in plan["question_snapshots"]:
        manifest = read(path)
        if manifest["source_video"]["sha256"] != plan["source_video"]["sha256"]:
            raise ValueError("Question/video mismatch")
        for q in manifest.get("queries", manifest.get("questions")):
            if q["human_status"] != "unreviewed" or q.get("human_code") is not None:
                raise ValueError("Producer accepts only blank question snapshots")
            xy = q.get("queried_image_xy_px", q.get("image_xy_px"))
            positions.setdefault((q["frame_index"], *xy), []).append(q["query_id"])
    capture = cv2.VideoCapture(plan["source_video"]["path"])
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not capture.isOpened() or (width, height, count) != (plan["width"], plan["height"], plan["total_frames"]):
        capture.release()
        raise ValueError("Video dimensions/timeline changed")
    output.mkdir(parents=True)
    cfg = plan["options"]
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=plan["model_path"]),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, **cfg)
    selector = PitcherSelector()
    frames, samples, files = [], [], []
    try:
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            for index in range(count):
                ok, frame = capture.read()
                if not ok:
                    raise ValueError("Incomplete clip decode")
                timestamp = round(capture.get(cv2.CAP_PROP_POS_MSEC))
                result = detector.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), timestamp)
                choice = selector.select(result.pose_landmarks)
                masks = result.segmentation_masks or []
                trace = {"frame_index": index, "timestamp_ms": timestamp, **asdict(choice),
                    "mask_count": len(masks), "candidates": [[{name: float(getattr(p, name))
                    for name in ("x", "y", "z", "visibility", "presence")} for p in pose]
                    for pose in result.pose_landmarks]}
                frames.append(trace)
                current = [(key, aliases) for key, aliases in positions.items() if key[0] == index]
                if not current:
                    continue
                trace["mask_metadata"] = [{"candidate_index": i, "format": int(m.image_format),
                    "width": m.width, "height": m.height, "channels": m.channels,
                    "step_bytes": m.step, "read_api": "Image[row,column]"} for i, m in enumerate(masks)]
                image, reason = selected_mask(masks, len(result.pose_landmarks), choice.index, width, height)
                for (_, x, y), aliases in current:
                    probability, pixels, missing = None, [], reason
                    if image is not None:
                        try:
                            probability, pixels = sample_mask_point(image, x, y)
                        except (ValueError, RuntimeError, IndexError) as error:
                            missing = str(error)
                    samples.append({"frame_index": index, "image_xy_px": [x, y], "source_query_ids": aliases,
                        "selected_candidate_index": choice.index, "mask_probability": probability,
                        "measurement_status": "available" if probability is not None else "missing",
                        "missing_reason": missing, "native_pixels": pixels})
                raw = output / f"frame_{index:04d}_raw.png"
                if not cv2.imwrite(str(raw), frame):
                    raise ValueError("Unable to save raw reference frame")
                files.append({"path": str(raw), "sha256": sha(raw)})
    finally:
        capture.release()
    if len(samples) != len(positions):
        raise ValueError("Fixed questions missing from output")
    for path, expected in plan["source_hashes"].items():
        if sha(path) != expected:
            raise ValueError("Source changed during measurement")
    available = sum(s["measurement_status"] == "available" for s in samples)
    report = {"status": "measured" if available == len(positions) else "insufficient_mask_evidence",
        "plan_path": str(plan_path), "plan_sha256": sha(plan_path), "producer_code_sha256": sha(__file__),
        "source_hashes": plan["source_hashes"], "options": cfg, "source_video": plan["source_video"],
        "mediapipe_version": version("mediapipe"), "frames": frames, "samples": samples, "files": files,
        "unique_image_queries": len(positions), "available_samples": available, "human_annotation_inputs": [],
        "read_api": "Image[row,column]; bilinear from recorded native neighbors", "whole_mask_read": False,
        "numpy_view_called": False, "private_pointer_used": False, "warning_thresholds": None,
        "warning_predictions_generated": False, "predictions_or_gt_modified": False,
        "association": "same SDK result ordinal; mismatch remains missing; no previous candidate index reused",
        "identity_verified": False, "phase2_acceptance": "IN PROGRESS"}
    (output / "mask_measurements.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = run(args.plan, args.output)
    print(json.dumps({"frames": len(result["frames"]), "queries": result["unique_image_queries"],
                      "available": result["available_samples"], "human_inputs": []}))
