"""Isolated IMAGE pose inference on sealed, human-initialized tracked rectangles."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
import math
from numbers import Real
from pathlib import Path
import platform
from types import SimpleNamespace
import sys

import cv2
import numpy as np

from measure_seeded_subject import read, sha, write, verify_sources
from pitch_analysis.pose_capture import LANDMARK_NAMES
from pitch_analysis.subject import PitcherSelector


TARGET = {"pitch_id": "pitch_003", "total_frames": 115, "width": 510, "height": 628}
PRODUCER_ROLES = {"video", "metadata", "video_technical", "tracked_roi", "model"}
DEPENDENCY_PATHS = {"scripts/measure_seeded_subject.py", "src/pitch_analysis/subject.py",
                    "src/pitch_analysis/pose_capture.py", "src/pitch_analysis/pose_estimator.py"}
POINT_FIELDS = ("x", "y", "z", "visibility", "presence")
OPTIONS = {"num_poses": 4, "min_pose_detection_confidence": .5,
           "min_pose_presence_confidence": .5, "min_tracking_confidence": .5,
           "output_segmentation_masks": False}
PARAMETERS = {"running_mode": "IMAGE", "crop": "sealed_csrt_rectangle_integer_floor_ceil_intersection",
              "external_resize": None, "padding": 0, "mirror": False, "map_before_selector": True,
              "selector": "original_PitcherSelector_fresh_per_clip", "candidate_association": None,
              "coordinate_correction": False, "interpolation": False, "fallback": None,
              "seed_frame_excluded": 0, "warning_policy": None, "image_processing_options": None,
              "xy_mapping": "crop_affine_to_original_image_normalized",
              "z_mapping": "crop_width_over_original_width_backend_relative_bookkeeping",
              "output_semantics": "experimental_raw_not_observed_or_correct"}


def runtime():
    return {"python": platform.python_version(), "executable_sha256": sha(sys.executable),
            "mediapipe": version("mediapipe"), "opencv": version("opencv-contrib-python"),
            "numpy": version("numpy")}


def _inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Frozen path outside workspace: " + str(name))
    return path


def verify_execution(root, plan, *, evaluator=False):
    root = Path(root).resolve()
    if (plan["status"] != "frozen_before_measurement" or plan["parameters"] != PARAMETERS or
            plan["options"] != OPTIONS or plan["target"] != TARGET or plan["runtime"] != runtime()):
        raise ValueError("Unfrozen or changed execution settings")
    if set(plan["producer_sources"]) != PRODUCER_ROLES:
        raise ValueError("Unexpected producer source role")
    if {ref["path"] for ref in plan["producer_dependencies"].values()} != DEPENDENCY_PATHS:
        raise ValueError("Unexpected or missing producer dependency")
    proposal_path = _inside(root, plan["proposal_manifest"])
    if sha(proposal_path) != plan["proposal_manifest_sha256"]:
        raise ValueError("Proposal changed")
    proposal = read(proposal_path)
    for proposed, execution in (("proposed_producer_sources", "producer_sources"),
                                ("proposed_producer_dependencies", "producer_dependencies"),
                                ("proposed_parameters", "parameters"), ("proposed_options", "options"),
                                ("target", "target"), ("runtime", "runtime"),
                                ("native_binding_hashes", "native_binding_hashes")):
        if proposal[proposed] != plan[execution]:
            raise ValueError("Execution differs from proposed " + execution)
    verify_sources(root, plan["producer_sources"])
    verify_sources(root, plan["producer_dependencies"])
    code = {"scripts/measure_tracked_roi_pose.py": plan["producer_sha256"]}
    if evaluator:
        code.update({"scripts/evaluate_tracked_roi_pose.py": plan["evaluator_sha256"],
                     "tests/test_tracked_roi_pose.py": plan["producer_test_sha256"]})
    if not plan["native_binding_hashes"]:
        raise ValueError("Native binding receipts required")
    for receipts in (code, plan["native_binding_hashes"]):
        for name, expected in receipts.items():
            if sha(_inside(root, name)) != expected:
                raise ValueError("Frozen code or native binding changed: " + name)


def crop_bounds(rectangle, width, height):
    """Derive the exact half-open source slice, without padding or resampling."""
    if rectangle is None:
        return None
    if (not isinstance(rectangle, (tuple, list, np.ndarray)) or len(rectangle) != 4 or
            any(isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or
                not math.isfinite(float(value)) for value in rectangle)):
        raise ValueError("Malformed/nonfinite sealed tracking rectangle")
    x, y, w, h = rectangle
    if w <= 0 or h <= 0:
        return None
    left, top = max(0, math.floor(x)), max(0, math.floor(y))
    right, bottom = min(width, math.ceil(x + w)), min(height, math.ceil(y + h))
    if right <= left or bottom <= top:
        return None
    return [left, top, right, bottom]


def serialize_candidates(poses):
    candidates = []
    for pose in poses:
        if len(pose) != len(LANDMARK_NAMES):
            raise ValueError("Pose backend must return 33 ordered landmarks")
        points = []
        for landmark in pose:
            point = {}
            for name in POINT_FIELDS:
                value = getattr(landmark, name)
                if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real) or not math.isfinite(float(value)):
                    raise ValueError("Nonfinite or malformed experimental landmark")
                point[name] = float(value)
            points.append(point)
        candidates.append(points)
    return candidates


def map_candidates(candidates, bounds, width, height):
    """Map XY once and rescale relative Z units; preserve all confidence values."""
    left, top, right, bottom = bounds
    cw, ch = right - left, bottom - top
    if cw <= 0 or ch <= 0 or width <= 0 or height <= 0:
        raise ValueError("Invalid crop mapping dimensions")
    mapped = []
    for pose in candidates:
        if len(pose) != len(LANDMARK_NAMES):
            raise ValueError("Pose backend must return 33 ordered landmarks")
        full_pose = []
        for point in pose:
            full = {"x": (left + point["x"] * cw) / width,
                    "y": (top + point["y"] * ch) / height,
                    "z": point["z"] * cw / width,
                    "visibility": point["visibility"], "presence": point["presence"]}
            if any(not math.isfinite(value) for value in full.values()):
                raise ValueError("Nonfinite mapped experimental landmark")
            full_pose.append(full)
        mapped.append(full_pose)
    return mapped


def _pixel_hash(pixels):
    return hashlib.sha256(pixels.tobytes()).hexdigest()


def validate_tracked_roi(tracked, sources, target):
    if (tracked["status"] != "sealed_measurements_only" or tracked["target"] != target or
            len(tracked["frames"]) != target["total_frames"] or
            tracked["producer_sources"]["video"] != sources["video"] or
            tracked["producer_sources"]["metadata"] != sources["metadata"] or
            tracked["producer_sources"]["video_technical"] != sources["video_technical"] or
            tracked["initialization_frame_excluded_from_effectiveness"] is not True):
        raise ValueError("Sealed tracking cohort/source mismatch")
    if [frame["frame_index"] for frame in tracked["frames"]] != list(range(target["total_frames"])):
        raise ValueError("Incomplete sealed tracking timeline")


def measure_frames(capture, detector, selector, tracked, technical, target, *, image_factory):
    """Process synthetic or native source arrays; call the original selector once per frame."""
    frames = []
    inference_calls = 0
    for index in range(target["total_frames"]):
        ok, pixels = capture.read()
        if (not ok or not isinstance(pixels, np.ndarray) or pixels.dtype != np.uint8 or
                pixels.shape != (target["height"], target["width"], 3)):
            raise ValueError("Missing or differently sized native uint8 BGR source frame")
        original_hash = _pixel_hash(pixels)
        tracker_frame = tracked["frames"][index]
        native_ms = float(capture.get(cv2.CAP_PROP_POS_MSEC))
        if (tracker_frame["frame_index"] != index or tracker_frame["decoded_bgr_sha256"] != original_hash or
                not math.isfinite(native_ms) or not math.isclose(native_ms, technical["timestamps_ms"][index],
                    rel_tol=0, abs_tol=1e-6) or not math.isclose(native_ms, tracker_frame["native_timestamp_ms"],
                    rel_tol=0, abs_tol=1e-6)):
            raise ValueError("Source pixel/PTS or sealed tracking receipt mismatch")
        rectangle = tracker_frame["usable_rectangle_xywh"]
        bounds = crop_bounds(rectangle, target["width"], target["height"])
        crop_candidates, full_candidates = [], []
        bgr_hash, rgb_hash, shape = None, None, None
        status = "roi_unavailable"
        if bounds is not None:
            left, top, right, bottom = bounds
            bgr = np.ascontiguousarray(pixels[top:bottom, left:right].copy())
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            bgr_hash, rgb_hash, shape = _pixel_hash(bgr), _pixel_hash(rgb), list(bgr.shape)
            inference_calls += 1
            result = detector.detect(image_factory(rgb))
            if _pixel_hash(bgr) != bgr_hash or _pixel_hash(rgb) != rgb_hash:
                raise ValueError("Inference mutated input crop pixels")
            crop_candidates = serialize_candidates(result.pose_landmarks)
            full_candidates = map_candidates(crop_candidates, bounds, target["width"], target["height"])
            status = "measured"
        selector_poses = [[SimpleNamespace(**point) for point in pose] for pose in full_candidates]
        selection = asdict(selector.select(selector_poses))
        if _pixel_hash(pixels) != original_hash:
            raise ValueError("Inference mutated original source pixels")
        frames.append({"frame_index": index, "native_timestamp_ms": native_ms, "timestamp_ms": round(native_ms),
                       "decoded_bgr_sha256": original_hash,
                       "tracker_rectangle_xywh": None if rectangle is None else list(rectangle),
                       "crop_bounds_xyxy": bounds, "crop_bgr_sha256": bgr_hash, "crop_rgb_sha256": rgb_hash,
                       "crop_shape": shape, "crop_candidates": crop_candidates,
                       "full_image_candidates": full_candidates, "selection": selection,
                       "inference_status": status, "warning_prediction": None,
                       "subject_alignment_verified": False})
    if capture.read()[0]:
        raise ValueError("Extra decoded frames")
    return {"frames": frames, "inference_calls": inference_calls}


def run(root, plan_path, output):
    import mediapipe as mp

    root, output = Path(root).resolve(), Path(output).resolve()
    plan_path = _inside(root, Path(plan_path))
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("New output required within analysis_results")
    plan = read(plan_path)
    plan_sha = sha(plan_path)
    verify_execution(root, plan)
    sources, target = plan["producer_sources"], plan["target"]
    metadata = read(root / sources["metadata"]["path"])
    technical = read(root / sources["video_technical"]["path"])
    tracked = read(root / sources["tracked_roi"]["path"])
    validate_tracked_roi(tracked, sources, target)
    if (target != TARGET or metadata["schema_version"] != "pitch-input-v1" or
            metadata["pitch_id"] != target["pitch_id"] or technical["sha256"] != sources["video"]["sha256"] or
            (technical["frame_count"], technical["width"], technical["height"]) !=
            (target["total_frames"], target["width"], target["height"]) or
            len(technical["timestamps_ms"]) != target["total_frames"] or
            any(isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value))
                for value in technical["timestamps_ms"])):
        raise ValueError("Source video identity/dimensions/timeline mismatch")
    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(root / sources["model"]["path"])),
        running_mode=mp.tasks.vision.RunningMode.IMAGE, **OPTIONS)
    capture = cv2.VideoCapture(str(root / sources["video"]["path"]))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot open source video")
        output.mkdir(parents=True)
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            measurements = measure_frames(capture, detector, PitcherSelector(), tracked, technical, target,
                image_factory=lambda rgb: mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    finally:
        capture.release()
    verify_execution(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Execution manifest changed during measurement")
    report = {"status": "sealed_measurements_only", "plan_sha256": plan_sha, "producer_sha256": sha(__file__),
              "producer_sources": sources, "producer_dependencies": plan["producer_dependencies"],
              "runtime": runtime(), "parameters": PARAMETERS, "options": OPTIONS, "target": target,
              **measurements, "human_annotation_inputs": [], "upstream_roi_requires_human_initialization": True,
              "measurement_semantics": "Crop sensitivity conditional on sealed human-initialized tracking; not end-to-end GT-blind",
              "calibrated_confidence": None, "warning_policy": None, "original_predictions_modified": False,
              "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "roi_pose_measurements.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run(args.root, args.plan, args.output)
    print(json.dumps({"frames": len(result["frames"]), "inference_calls": result["inference_calls"],
                      "warning_policy": None, "phase2_automatic_reliability": "NOT PASSED"}))
