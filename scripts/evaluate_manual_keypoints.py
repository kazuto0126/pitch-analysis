"""Measure existing raw 2D predictions against visible manual joint coordinates only."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pitch_analysis.manual_keypoints import JOINT_NAMES, load_manual_keypoints, validate_manual_keypoints


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def quantile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def evaluate(manual: dict, model: dict, model_metadata: dict) -> dict:
    validate_manual_keypoints(manual)
    source = manual["source_video"]
    width, height = manual["image_size"]["width"], manual["image_size"]["height"]
    if model.get("schema_version") != "keypoints-v1" or model.get("pitch_id") != source["pitch_id"]:
        raise ValueError("Model keypoints contract/pitch ID does not match manual reference")
    if not model.get("coordinate_system", "").startswith("normalized_image_xy;"):
        raise ValueError("Expected raw normalized image XY predictions")
    if (model_metadata.get("sha256") != source["sha256"]
        or model_metadata.get("frame_count") != source["total_frames"]
        or model_metadata.get("width") != width or model_metadata.get("height") != height):
        raise ValueError("Model source hash, frame count or dimensions differ from the manual reference")
    model_frames = model["frames"]
    if len(model_frames) != source["total_frames"]:
        raise ValueError("Model frame count differs from manual reference")
    errors = {name: [] for name in JOINT_NAMES}
    states = {name: Counter() for name in JOINT_NAMES}
    missing = Counter()
    comparisons = []
    diagonal = math.hypot(width, height)
    for index, (human_frame, model_frame) in enumerate(zip(manual["frames"], model_frames)):
        if type(model_frame["detected"]) is not bool:
            raise ValueError("Model detected state must be boolean")
        if model_frame["frame_index"] != index:
            raise ValueError("Model frames must have unique ordered indices")
        timestamp = model_frame["timestamp_ms"]
        if type(timestamp) not in (int, float) or not math.isfinite(timestamp) or abs(timestamp - human_frame["timestamp_ms"]) > 1.0:
            raise ValueError("Model and manual timestamps are not aligned")
        landmarks = {}
        for point in model_frame["landmarks"]:
            if point["name"] in landmarks:
                raise ValueError("Duplicate model landmark")
            for coordinate in ("x", "y"):
                if type(point[coordinate]) not in (int, float) or not math.isfinite(point[coordinate]):
                    raise ValueError("Model coordinates must be finite numbers")
            landmarks[point["name"]] = point
        for joint in human_frame["joints"]:
            name, state = joint["name"], joint["status"]
            states[name][state] += 1
            if state != "visible":
                continue
            prediction = landmarks.get(name) if model_frame["detected"] else None
            record = {"frame_index": index, "timestamp_ms": human_frame["timestamp_ms"],
                      "joint": name, "manual_x_px": joint["x_px"], "manual_y_px": joint["y_px"]}
            if prediction is None:
                missing[name] += 1
                record.update({"prediction_status": "missing", "error_px": None,
                               "error_image_diagonal_ratio": None})
            else:
                x, y = prediction["x"] * width, prediction["y"] * height
                error = math.hypot(x - joint["x_px"], y - joint["y_px"])
                errors[name].append(error)
                record.update({"prediction_status": "present", "model_x_px": x, "model_y_px": y,
                               "error_px": error, "error_image_diagonal_ratio": error / diagonal,
                               "model_visibility": prediction.get("visibility")})
            comparisons.append(record)
    joints = {}
    for name in JOINT_NAMES:
        values = errors[name]
        eligible = states[name]["visible"]
        joints[name] = {
            "human_state_counts": {state: states[name][state] for state in
                                   ("visible", "uncertain", "not_observable", "unreviewed")},
            "eligible_visible_frames": eligible, "predicted_visible_frames": len(values),
            "missing_predictions_on_visible_frames": missing[name],
            "prediction_presence_ratio_on_visible_frames": len(values) / eligible if eligible else None,
            "mean_error_px": statistics.fmean(values) if values else None,
            "median_error_px": statistics.median(values) if values else None,
            "p95_error_px": quantile(values, .95), "max_error_px": max(values) if values else None,
            "mean_error_image_diagonal_ratio": statistics.fmean(values) / diagonal if values else None,
        }
    return {
        "schema_version": "manual-keypoint-evaluation-v1", "pitch_id": source["pitch_id"],
        "source_video_sha256": source["sha256"], "reviewer": manual["provenance"]["reviewer"],
        "manual_annotation_status": manual["annotation_status"],
        "evaluation_status": "measured" if comparisons else "no_visible_reference",
        "comparison_scope": "existing raw predictions against human-visible 2D joints; no new acceptance threshold",
        "nonvisible_policy": "uncertain/not_observable/unreviewed excluded; no inferred coordinates or interpolation",
        "missing_prediction_policy": "reported separately, never treated as zero error",
        "model_confidence_policy": "raw point presence evaluated without adding a visibility gate; confidence is not correctness",
        "limitations": ["No automatic learning or model changes.",
                        "One reviewed clip measures this clip only; it is not independent generalization evidence.",
                        "No 3D accuracy or event timing accuracy is measured."],
        "joints": joints, "frame_comparisons": comparisons,
    }


def write_evaluation(manual_path: Path, model_path: Path, output_path: Path,
                     model_metadata_path: Path | None = None) -> dict:
    metadata_path = model_metadata_path or model_path.parent / "video_metadata.json"
    manual = load_manual_keypoints(manual_path)
    model = json.loads(model_path.read_text(encoding="utf-8-sig"))
    metadata = json.loads(metadata_path.read_text(encoding="utf-8-sig"))
    result = evaluate(manual, model, metadata)
    result["input_hashes"] = {"manual_keypoints": digest(manual_path),
                              "model_keypoints": digest(model_path), "model_video_metadata": digest(metadata_path)}
    target = output_path.resolve()
    if target in {manual_path.resolve(), model_path.resolve(), metadata_path.resolve()}:
        raise ValueError("Evaluation output cannot replace input evidence")
    if target.exists():
        raise FileExistsError("Evaluation output already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manual_json", type=Path)
    parser.add_argument("model_keypoints", type=Path)
    parser.add_argument("output_json", type=Path)
    parser.add_argument("--model-video-metadata", type=Path)
    args = parser.parse_args()
    try:
        result = write_evaluation(args.manual_json, args.model_keypoints, args.output_json,
                                  args.model_video_metadata)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    print(f"Wrote per-joint coordinate evaluation: {args.output_json} ({result['evaluation_status']})")
