"""Frozen HOG person-candidate feasibility measurement; no pose or human inputs."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import sys

import cv2
import numpy as np


PARAMETERS = {"hitThreshold": 0., "winStride": [0, 0], "padding": [0, 0],
              "scale": 1.05, "groupThreshold": 2., "useMeanshiftGrouping": False}
PRODUCER_ROLES = {"video", "metadata", "video_technical"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write(path, data):
    with Path(path).open("x", encoding="utf-8") as sink:
        json.dump(data, sink, indent=2, allow_nan=False)
        sink.write("\n")


def runtime():
    return {"python": platform.python_version(), "executable_sha256": sha(sys.executable),
            "opencv_distribution": version("opencv-contrib-python"), "numpy": np.__version__}


def detector_signature(hog, weights):
    weights = np.asarray(weights, dtype="<f4")
    return {"opencv": cv2.__version__, "detector_coefficients": int(weights.size),
            "detector_sha256": hashlib.sha256(weights.tobytes()).hexdigest(),
            "win_size": list(hog.winSize), "block_size": list(hog.blockSize),
            "block_stride": list(hog.blockStride), "cell_size": list(hog.cellSize),
            "nbins": hog.nbins, "gamma_correction": hog.gammaCorrection, "nlevels": hog.nlevels,
            "detector_size_valid": hog.checkDetectorSize(),
            "deriv_aperture": hog.derivAperture, "histogram_norm_type": hog.histogramNormType,
            "win_sigma": hog.winSigma, "l2_hys_threshold": hog.L2HysThreshold,
            "signed_gradient": hog.signedGradient}


def create_detector():
    weights = cv2.HOGDescriptor.getDefaultPeopleDetector()
    hog = cv2.HOGDescriptor()
    hog.setSVMDetector(weights)
    return hog, detector_signature(hog, weights)


def verify_sources(root, sources):
    for source in sources.values():
        path = root / source["path"]
        if not path.resolve().is_relative_to(root) or sha(path) != source["sha256"]:
            raise ValueError("Frozen source changed or outside workspace: " + source["path"])


def verify_execution(root, plan, *, evaluator=False):
    if plan["status"] != "frozen_before_measurement" or plan["parameters"] != PARAMETERS or plan["runtime"] != runtime():
        raise ValueError("Unfrozen or changed execution settings")
    if set(plan["producer_sources"]) != PRODUCER_ROLES:
        raise ValueError("Unexpected producer source role")
    proposal = read(root / plan["proposal_manifest"])
    if sha(root / plan["proposal_manifest"]) != plan["proposal_manifest_sha256"]:
        raise ValueError("Proposal changed")
    if (proposal["proposed_producer_sources"] != plan["producer_sources"] or
        proposal["proposed_parameters"] != plan["parameters"] or proposal["target"] != plan["target"]):
        raise ValueError("Execution differs from proposed sources/parameters/cohort")
    if sha(root / "scripts/measure_person_support.py") != plan["producer_sha256"]:
        raise ValueError("Producer changed after freeze")
    if evaluator and sha(root / "scripts/evaluate_person_support.py") != plan["evaluator_sha256"]:
        raise ValueError("Evaluator changed after freeze")
    if evaluator and sha(root / "tests/test_person_support.py") != plan["test_sha256"]:
        raise ValueError("Frozen tests changed")
    for name, expected in plan["native_binding_hashes"].items():
        if sha(root / name) != expected:
            raise ValueError("Native binding changed")
    verify_sources(root, plan["producer_sources"])


def serialize_candidates(rectangles, scores, width, height):
    if len(rectangles) != len(scores):
        raise ValueError("Rectangle/score cardinality mismatch")
    candidates = []
    for index, (rectangle, raw_score) in enumerate(zip(rectangles, scores, strict=True)):
        if len(rectangle) != 4 or any(isinstance(v, (bool, np.bool_)) or not math.isfinite(float(v)) or not float(v).is_integer() for v in rectangle):
            raise ValueError("Invalid native integer rectangle")
        x, y, w, h = (int(value) for value in rectangle)
        score = float(raw_score)
        if w <= 0 or h <= 0 or not math.isfinite(score):
            raise ValueError("Invalid rectangle size or SVM score")
        candidates.append({"candidate_index": index, "rectangle_xywh": [x, y, w, h],
                           "raw_svm_score": score,
                           "entirely_inside_image": 0 <= x and 0 <= y and x + w <= width and y + h <= height,
                           "subject_assignment": None})
    return candidates


def detect(hog, frame):
    if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
        raise ValueError("Expected native uint8 BGR frame")
    config = {**PARAMETERS, "winStride": tuple(PARAMETERS["winStride"]), "padding": tuple(PARAMETERS["padding"])}
    rectangles, scores = hog.detectMultiScale(frame, **config)
    return serialize_candidates(rectangles, scores, frame.shape[1], frame.shape[0])


def run(root, plan_path, output):
    root, output = root.resolve(), output.resolve()
    plan = read(plan_path)
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("New output required within analysis_results")
    verify_execution(root, plan)
    metadata = read(root / plan["producer_sources"]["metadata"]["path"])
    technical = read(root / plan["producer_sources"]["video_technical"]["path"])
    target = plan["target"]
    if (metadata["schema_version"] != "pitch-input-v1" or metadata["pitch_id"] != target["pitch_id"] or
        technical["sha256"] != plan["producer_sources"]["video"]["sha256"] or
        (technical["frame_count"], technical["width"], technical["height"]) != (target["total_frames"], target["width"], target["height"])):
        raise ValueError("Source video identity/dimensions/timeline mismatch")
    hog, signature = create_detector()
    if signature != plan["detector_signature"]:
        raise ValueError("HOG coefficients or properties changed")
    capture = cv2.VideoCapture(str(root / plan["producer_sources"]["video"]["path"]))
    if not capture.isOpened():
        raise ValueError("Cannot open source video")
    output.mkdir(parents=True)
    frames = []
    try:
        for index in range(target["total_frames"]):
            ok, pixels = capture.read()
            if not ok or pixels.shape != (target["height"], target["width"], 3):
                raise ValueError("Missing or differently sized source frame")
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC)
            if not math.isclose(timestamp, technical["timestamps_ms"][index], rel_tol=0, abs_tol=1e-6):
                raise ValueError("Original fractional timestamp changed")
            before = hashlib.sha256(pixels.tobytes()).hexdigest()
            candidates = detect(hog, pixels)
            if hashlib.sha256(pixels.tobytes()).hexdigest() != before:
                raise ValueError("Detector mutated source pixels")
            frames.append({"frame_index": index, "native_timestamp_ms": timestamp,
                           "decoded_bgr_sha256": before, "candidates": candidates,
                           "warning_prediction": None, "subject_assignment": None})
        if capture.read()[0]:
            raise ValueError("Extra decoded frames")
    finally:
        capture.release()
    verify_execution(root, plan)
    report = {"status": "sealed_measurements_only", "plan_sha256": sha(plan_path),
              "producer_sha256": sha(__file__), "producer_sources": plan["producer_sources"],
              "runtime": runtime(), "detector_signature": signature, "parameters": PARAMETERS,
              "target": target, "frames": frames, "human_annotation_inputs": [], "pose_inputs": [],
              "candidate_semantics": "All grouped rectangles returned by HOG API, not all sliding windows",
              "score_semantics": "Raw returned SVM value, not calibrated probability",
              "subject_assignment": None, "warning_policy": None, "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "person_measurements.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run(args.root, args.plan, args.output)
    print(json.dumps({"frames": len(result["frames"]), "frames_with_candidates": sum(bool(f["candidates"]) for f in result["frames"]),
                      "candidates": sum(len(f["candidates"]) for f in result["frames"]), "subject_assignment": None}))
