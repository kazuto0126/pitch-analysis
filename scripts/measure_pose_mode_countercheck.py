"""Isolated full-frame IMAGE/VIDEO sensitivity measurement; no human inputs.

The production VIDEO predictions and all capture/selector settings are retained.
IMAGE predictions are experimental raw outputs, never a replacement or warning.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import re
from statistics import median
import sys

from pitch_analysis.pose_capture import LANDMARK_NAMES
from pitch_analysis.subject import PitcherSelector


TORSO = ("LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_HIP", "RIGHT_HIP")
OPTIONS = {"num_poses": 4, "min_pose_detection_confidence": .5,
           "min_pose_presence_confidence": .5, "min_tracking_confidence": .5}
PARAMETERS = {"experimental_running_mode": "IMAGE", "baseline_running_mode": "VIDEO",
              "full_native_frames": True, "crop": None, "resize": None,
              "selector": "original_PitcherSelector_fresh_per_clip",
              "candidate_association": "none_across_arms",
              "coordinate_units": "original_image_pixels",
              "disagreement_gate": "saved_clean_visibility_and_presence",
              "torso_summary": "median_four_joint_distances_only_if_all_four_measured",
              "warning_threshold": None, "coordinate_correction": False}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def write(path, data):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, allow_nan=False)
        handle.write("\n")


def runtime():
    return {"python": platform.python_version(), "executable_sha256": sha(sys.executable),
            "mediapipe": version("mediapipe"), "opencv": version("opencv-contrib-python"),
            "numpy": version("numpy")}


def verify_hashes(root, hashes):
    for name, expected in hashes.items():
        if sha(root / name) != expected:
            raise ValueError("Frozen source changed: " + name)


def validate_plan(plan):
    clips = plan["clips"]
    names = [clip["pitch_id"] for clip in clips]
    if len(clips) != plan["expected_clip_count"] or len(set(names)) != len(names) or any(not re.fullmatch(r"[a-zA-Z0-9_-]+", name) for name in names):
        raise ValueError("Changed/unsafe clip denominator")
    if sum(clip["total_frames"] for clip in clips) != plan["expected_total_frames"]:
        raise ValueError("Changed original frame denominator")
    consumed = {plan["model_path"], "src/pitch_analysis/subject.py", "src/pitch_analysis/pose_capture.py", "src/pitch_analysis/pose_estimator.py"}
    for clip in clips:
        consumed.update(clip[key] for key in ("video", "metadata", "video_metadata", "raw_csv", "capture", "clean_config"))
    if not consumed <= plan["measurement_source_hashes"].keys():
        raise ValueError("Unbound consumed measurement source")
    if set(plan["measurement_source_hashes"]) != consumed:
        raise ValueError("Unexpected measurement input role")


def finite_point(point):
    return point is not None and all(math.isfinite(point[key]) for key in ("x", "y", "visibility", "presence"))


def gate(point, config):
    return finite_point(point) and point["visibility"] >= config["min_visibility"] and point["presence"] >= config["min_presence"]


def joint_comparison(before, after, width, height, config):
    available = finite_point(before) and finite_point(after)
    old_gate, new_gate = gate(before, config), gate(after, config)
    distance = math.hypot((before["x"] - after["x"]) * width,
                          (before["y"] - after["y"]) * height) if available else None
    reasons = []
    for label, point, passes in (("video", before, old_gate), ("image", after, new_gate)):
        if point is None:
            reasons.append(label + "_selected_point_missing")
        elif not finite_point(point):
            reasons.append(label + "_nonfinite_point")
        elif not passes:
            reasons.append(label + "_below_existing_gate")
    return {"video_gate_pass": old_gate, "image_gate_pass": new_gate,
            "both_finite_distance_px": distance,
            "gated_distance_px": distance if old_gate and new_gate else None,
            "gated_distance_image_height": distance / height if old_gate and new_gate else None,
            "unmeasured_reasons": reasons, "subject_alignment_verified": False}


def serialize_candidates(poses):
    result = []
    for pose in poses:
        if len(pose) != len(LANDMARK_NAMES):
            raise ValueError("Pose backend must return 33 ordered landmarks")
        value = [{key: float(getattr(point, key)) for key in ("x", "y", "z", "visibility", "presence")} for point in pose]
        if any(not math.isfinite(number) for point in value for number in point.values()):
            raise ValueError("Nonfinite experimental candidate")
        result.append(value)
    return result


def selected_points(candidates, selection):
    index = selection["index"]
    if index is None:
        return {}
    if selection["status"] != "selected" or not 0 <= index < len(candidates):
        raise ValueError("Invalid experimental selection")
    return dict(zip(LANDMARK_NAMES, candidates[index], strict=True))


def load_video_raw(path, capture, total):
    frames = [{} for _ in range(total)]
    if [row["frame_index"] for row in capture["selection_frames"]] != list(range(total)):
        raise ValueError("Incomplete original selection timeline")
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            index = int(row["frame"])
            name = row["landmark"]
            if not 0 <= index < total or name not in LANDMARK_NAMES or name in frames[index]:
                raise ValueError("Invalid/repeated original frame or landmark")
            if float(row["timestamp_ms"]) != capture["selection_frames"][index]["timestamp_ms"]:
                raise ValueError("Original raw/capture time mismatch")
            frames[index][name] = {key: float(row[key]) for key in ("x", "y", "z", "visibility", "presence")}
    for points, selection in zip(frames, capture["selection_frames"], strict=True):
        if (len(points) == len(LANDMARK_NAMES)) != (selection["status"] == "selected") or len(points) not in (0, len(LANDMARK_NAMES)):
            raise ValueError("Original raw/selection cardinality mismatch")
    return frames


def frame_measurement(index, timestamp, native_ms, pixel_hash, candidates, selection, before, original_choice, width, height, config):
    after = selected_points(candidates, selection)
    comparisons = {name: joint_comparison(before.get(name), after.get(name), width, height, config)
                   for name in LANDMARK_NAMES}
    torso = [comparisons[name]["gated_distance_px"] for name in TORSO]
    return {"frame_index": index, "timestamp_ms": timestamp, "native_timestamp_ms": native_ms, "decoded_bgr_sha256": pixel_hash,
            "image_candidates": candidates, "image_selection": selection,
            "video_selection": original_choice, "joint_disagreement": comparisons,
            "torso_median_distance_px": median(torso) if all(v is not None for v in torso) else None,
            "subject_alignment_verified": False, "warning_prediction": None}


def run(root, plan_path, output):
    import cv2
    import mediapipe as mp

    root, output = root.resolve(), output.resolve()
    plan = read(plan_path)
    validate_plan(plan)
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("Fresh output required inside analysis_results")
    if plan["parameters"] != PARAMETERS or plan["options"] != OPTIONS or plan["runtime"] != runtime():
        raise ValueError("Fixed parameters/runtime changed")
    if plan["producer_sha256"] != sha(__file__):
        raise ValueError("Producer changed after plan freeze")
    verify_hashes(root, plan["measurement_source_hashes"])
    output.mkdir(parents=True)
    receipts = []
    for clip in plan["clips"]:
        meta = read(root / clip["video_metadata"])
        context = read(root / clip["capture"])
        config = read(root / clip["clean_config"])
        total, width, height = meta["frame_count"], meta["width"], meta["height"]
        if total != clip["total_frames"] or context["subject_selection"] != "rear_centerfield_broadcast":
            raise ValueError("Original video/capture protocol mismatch")
        if meta["sha256"] != sha(root / clip["video"]):
            raise ValueError("Video metadata binding mismatch")
        raw = load_video_raw(root / clip["raw_csv"], context, total)
        capture = cv2.VideoCapture(str(root / clip["video"]))
        if not capture.isOpened() or (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(capture.get(cv2.CAP_PROP_FRAME_COUNT))) != (width, height, total):
            capture.release()
            raise ValueError("Native video dimensions/frame count mismatch")
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(root / plan["model_path"])),
            running_mode=mp.tasks.vision.RunningMode.IMAGE, **OPTIONS)
        selector = PitcherSelector()
        frames = []
        try:
            with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
                for index in range(total):
                    ok, frame = capture.read()
                    if not ok:
                        raise ValueError("Incomplete native frame decode")
                    native_ms = capture.get(cv2.CAP_PROP_POS_MSEC)
                    timestamp = context["selection_frames"][index]["timestamp_ms"]
                    if timestamp != round(native_ms) or not math.isclose(native_ms, meta["timestamps_ms"][index], abs_tol=1e-6):
                        raise ValueError("Native timeline differs from original baseline")
                    result = detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                        data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
                    candidates = serialize_candidates(result.pose_landmarks)
                    choice = asdict(selector.select(result.pose_landmarks))
                    frames.append(frame_measurement(index, timestamp, native_ms, hashlib.sha256(frame.tobytes()).hexdigest(),
                        candidates, choice, raw[index], context["selection_frames"][index], width, height, config))
                if capture.read()[0]:
                    raise ValueError("Extra decoded frames")
        finally:
            capture.release()
        result = {"pitch_id": clip["pitch_id"], "total_frames": total, "width": width, "height": height,
                  "video_sha256": meta["sha256"], "gate": {key: config[key] for key in ("min_visibility", "min_presence")},
                  "frames": frames, "human_annotation_inputs": [], "warning_threshold": None,
                  "original_predictions_modified": False, "image_output_semantics": "experimental_raw_not_observed_or_correct"}
        name = clip["pitch_id"] + ".json"
        write(output / name, result)
        receipts.append({"pitch_id": clip["pitch_id"], "path": name, "sha256": sha(output / name),
                         "frames": total, "selected": sum(f["image_selection"]["status"] == "selected" for f in frames),
                         "torso_disagreement_measured": sum(f["torso_median_distance_px"] is not None for f in frames)})
        print(json.dumps(receipts[-1]), flush=True)
    verify_hashes(root, plan["measurement_source_hashes"])
    report = {"status": "measurements_only", "plan_sha256": sha(plan_path), "producer_sha256": sha(__file__),
              "parameters": PARAMETERS, "options": OPTIONS, "runtime": runtime(), "clips": receipts,
              "measurement_source_hashes": plan["measurement_source_hashes"], "human_annotation_inputs": [],
              "warning_predictions_generated": False, "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "measurement_run.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    run(args.root, args.plan, args.output)
