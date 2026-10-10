"""Isolated CSRT continuation of one declared human-assisted initialization."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import math
from numbers import Real
from pathlib import Path
import platform
import sys

import cv2
import numpy as np


TARGET = {"pitch_id": "pitch_003", "total_frames": 115, "width": 510, "height": 628}
SEED_RECTANGLE = [85, 165, 217, 435]
PRODUCER_ROLES = {"video", "metadata", "video_technical", "initialization"}
FAILURE_POLICY = "terminal_abstention_no_reinit"
RAW_SCORE_POLICY = "diagnostic_only_no_cutoff_null_on_error"
INITIALIZATION_FAILURE_POLICY = "init_failed_then_not_attempted_after_initialization_failure"
INTEGRITY_FAILURE_POLICY = "abort_without_sealing_complete_result"
REVIEW_SAMPLING = {"frames": [38, 70, 78, 86, 87, 95, 104, 105, 112, 114],
                   "maximum_questions": 10, "fixed_sampling_slots": 10,
                   "max_boxes_per_frame": 1, "missing_slots_not_replaced": True}
PARAMETER_NAMES = (
    "use_hog", "use_color_names", "use_gray", "use_rgb", "use_channel_weights",
    "use_segmentation", "window_function", "kaiser_alpha", "cheb_attenuation",
    "template_size", "gsl_sigma", "hog_orientations", "hog_clip", "padding",
    "filter_lr", "weights_lr", "num_hog_channels_used", "admm_iterations",
    "histogram_bins", "histogram_lr", "background_ratio", "number_of_scales",
    "scale_sigma_factor", "scale_model_max_area", "scale_lr", "scale_step", "psr_threshold",
)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write(path, data):
    """Write a new strict-JSON artifact with identical LF bytes on Windows."""
    with Path(path).open("x", encoding="utf-8", newline="\n") as sink:
        json.dump(data, sink, indent=2, ensure_ascii=False, allow_nan=False)
        sink.write("\n")


def runtime():
    return {"python": platform.python_version(), "executable_sha256": sha(sys.executable),
            "opencv_distribution": version("opencv-contrib-python"), "numpy": np.__version__}


def default_parameters():
    """Inspect installed constructor defaults without opening images or videos."""
    parameters = cv2.TrackerCSRT.Params()
    return {name: getattr(parameters, name) for name in PARAMETER_NAMES}


def _inside(root, path):
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Frozen path outside workspace: " + str(path))
    return resolved


def verify_sources(root, sources):
    root = Path(root).resolve()
    for source in sources.values():
        if sha(_inside(root, source["path"])) != source["sha256"]:
            raise ValueError("Frozen source changed: " + source["path"])


def verify_execution(root, plan, *, evaluator=False):
    root = Path(root).resolve()
    if (plan["status"] != "frozen_before_measurement" or plan["target"] != TARGET or
            plan["failure_policy"] != FAILURE_POLICY or plan["parameters"] != default_parameters() or
            plan["raw_score_policy"] != RAW_SCORE_POLICY or
            plan["initialization_failure_policy"] != INITIALIZATION_FAILURE_POLICY or
            plan["integrity_failure_policy"] != INTEGRITY_FAILURE_POLICY or
            plan["review_sampling"] != REVIEW_SAMPLING or
            set(plan["parameters"]) != set(PARAMETER_NAMES) or plan["runtime"] != runtime()):
        raise ValueError("Unfrozen or changed execution settings")
    if set(plan["producer_sources"]) != PRODUCER_ROLES:
        raise ValueError("Unexpected producer source role")
    proposal_path = _inside(root, plan["proposal_manifest"])
    if sha(proposal_path) != plan["proposal_manifest_sha256"]:
        raise ValueError("Proposal changed")
    proposal = read(proposal_path)
    if (proposal["proposed_producer_sources"] != plan["producer_sources"] or
            proposal["proposed_parameters"] != plan["parameters"] or proposal["target"] != plan["target"] or
            proposal["failure_policy"] != plan["failure_policy"] or
            proposal["raw_score_policy"] != plan["raw_score_policy"] or
            proposal["initialization_failure_policy"] != plan["initialization_failure_policy"] or
            proposal["integrity_failure_policy"] != plan["integrity_failure_policy"] or
            proposal["runtime"] != plan["runtime"] or
            proposal["native_binding_hashes"] != plan["native_binding_hashes"] or
            proposal["review_sampling"] != plan["review_sampling"]):
        raise ValueError("Execution differs from proposed sources/parameters/cohort/policy")
    code = {"scripts/measure_seeded_subject.py": plan["producer_sha256"]}
    if evaluator:
        code.update({"scripts/evaluate_seeded_subject.py": plan["evaluator_sha256"],
                     "tests/test_seeded_subject.py": plan["test_sha256"]})
    for receipts in (code, plan["native_binding_hashes"]):
        for name, expected in receipts.items():
            if sha(_inside(root, name)) != expected:
                raise ValueError("Frozen code or native binding changed: " + name)
    if not plan["native_binding_hashes"]:
        raise ValueError("Native binding receipt required")
    verify_sources(root, plan["producer_sources"])


def _json_safe(value):
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("+Infinity" if value > 0 else "-Infinity")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return repr(value)


def rectangle_status(rectangle, width, height):
    """Keep valid native geometry unchanged; never clip or infer anatomy."""
    safe = _json_safe(rectangle)
    if not isinstance(rectangle, (list, tuple, np.ndarray)) or (isinstance(rectangle, np.ndarray) and rectangle.ndim != 1):
        return None, None, "invalid_native_rectangle", safe
    if len(rectangle) != 4 or any(isinstance(v, (bool, np.bool_)) or not isinstance(v, Real)
                                  or not math.isfinite(float(v)) for v in rectangle):
        return None, None, "invalid_native_rectangle", safe
    x, y, w, h = safe
    if w <= 0 or h <= 0:
        return None, None, "invalid_native_rectangle", safe
    truncated = x < 0 or y < 0 or x + w > width or y + h > height
    if x >= width or y >= height or x + w <= 0 or y + h <= 0:
        return safe, bool(truncated), "native_rectangle_fully_outside_image", None
    return safe, bool(truncated), None, None


def _pixel_hash(pixels):
    return hashlib.sha256(pixels.tobytes()).hexdigest()


def _score(tracker):
    try:
        value = tracker.getTrackingScore()
        if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
            return None, "invalid_native_tracking_score"
        value = float(value)
        if not math.isfinite(value):
            return None, "nonfinite_native_tracking_score"
        return value, None
    except Exception as error:
        return None, type(error).__name__ + ": " + str(error)


def validate_initialization(seed, plan):
    if (seed["status"] != "proposed_not_used" or seed["pitch_id"] != "pitch_003" or
            seed["frame_index"] != 0 or seed["native_timestamp_ms"] != 0.0 or
            seed["rectangle_xywh"] != SEED_RECTANGLE or seed["human_conclusion"] != "pitcher" or
            seed["source_kind"] != "model_proposed_human_confirmed" or
            seed["extent_observation"] is not None or seed["query_id"] != "pitch_003_f0000_box0" or
            seed["source_video"] != plan["producer_sources"]["video"] or
            seed["producer_must_not_open_lineage_sources"] is not True or
            seed["excluded_from_effectiveness_evaluation"] is not True):
        raise ValueError("Unexpected declared human-assisted initialization")
    digest = seed["decoded_bgr_sha256"]
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("Invalid initialization pixel receipt")


def measure_frames(capture, tracker, seed, technical, target):
    """Record one forward continuation; technical integrity failures prevent sealing."""
    frames = []
    terminal = None
    initialization_failure = False
    initialization_calls = 0
    update_calls = 0
    for index in range(target["total_frames"]):
        ok, pixels = capture.read()
        if (not ok or not isinstance(pixels, np.ndarray) or pixels.dtype != np.uint8 or
                pixels.shape != (target["height"], target["width"], 3)):
            raise ValueError("Missing or differently sized native uint8 BGR source frame")
        timestamp = float(capture.get(cv2.CAP_PROP_POS_MSEC))
        if not math.isfinite(timestamp) or not math.isclose(
                timestamp, technical["timestamps_ms"][index], rel_tol=0, abs_tol=1e-6):
            raise ValueError("Original fractional timestamp changed")
        before = _pixel_hash(pixels)
        frame = {"frame_index": index, "native_timestamp_ms": timestamp, "decoded_bgr_sha256": before,
                 "tracking_status": None, "native_update_success": None, "native_rectangle_xywh": None,
                 "native_rectangle_diagnostic": None, "usable_rectangle_xywh": None, "truncated": None,
                 "failure_reason": None, "raw_tracking_score": None, "score_error": None,
                 "subject_assignment": None, "warning_prediction": None}
        if index == 0:
            if before != seed["decoded_bgr_sha256"] or timestamp != seed["native_timestamp_ms"]:
                raise ValueError("Initialization frame pixel/timestamp receipt mismatch")
            initialization_calls += 1
            try:
                result = tracker.init(pixels, tuple(seed["rectangle_xywh"]))
                if result is not None and not (isinstance(result, (bool, np.bool_)) and bool(result)):
                    raise ValueError("Unexpected native init return: " + repr(result))
                frame.update(tracking_status="initialized", usable_rectangle_xywh=list(seed["rectangle_xywh"]),
                             truncated=False)
            except Exception as error:
                initialization_failure = True
                reason = "native_initialization_exception: " + type(error).__name__ + ": " + str(error)
                terminal = {"frame_index": 0, "reason": reason}
                frame.update(tracking_status="init_failed", failure_reason=reason)
        elif terminal is not None:
            status = ("not_attempted_after_initialization_failure" if initialization_failure
                      else "not_attempted_after_terminal_break")
            frame.update(tracking_status=status, failure_reason=status)
        else:
            update_calls += 1
            try:
                success, rectangle = tracker.update(pixels)
                if not isinstance(success, (bool, np.bool_)):
                    raise ValueError("Native update success is not boolean")
                native, truncated, reason, diagnostic = rectangle_status(rectangle, target["width"], target["height"])
                frame.update(native_update_success=bool(success), native_rectangle_xywh=native,
                             native_rectangle_diagnostic=diagnostic, truncated=truncated)
                frame["raw_tracking_score"], frame["score_error"] = _score(tracker)
                if not success:
                    reason = "native_update_false"
                if reason is None:
                    frame.update(tracking_status="native_success", usable_rectangle_xywh=list(native))
                else:
                    terminal = {"frame_index": index, "reason": reason}
                    frame.update(tracking_status="terminal_break", failure_reason=reason)
            except Exception as error:
                reason = "native_update_exception: " + type(error).__name__ + ": " + str(error)
                terminal = {"frame_index": index, "reason": reason}
                frame.update(tracking_status="terminal_break", failure_reason=reason)
        if _pixel_hash(pixels) != before:
            raise ValueError("Tracker mutated source pixels")
        frames.append(frame)
    if capture.read()[0]:
        raise ValueError("Extra decoded frames")
    return {"frames": frames, "initialization_calls": initialization_calls,
            "native_update_calls": update_calls, "terminal_break": terminal}


def run(root, plan_path, output):
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
    seed = read(root / sources["initialization"]["path"])
    validate_initialization(seed, plan)
    if (target != TARGET or metadata["schema_version"] != "pitch-input-v1" or
            metadata["pitch_id"] != target["pitch_id"] or technical["sha256"] != sources["video"]["sha256"] or
            (technical["frame_count"], technical["width"], technical["height"]) !=
            (target["total_frames"], target["width"], target["height"]) or
            len(technical["timestamps_ms"]) != target["total_frames"] or
            any(not isinstance(v, Real) or isinstance(v, bool) or not math.isfinite(float(v))
                for v in technical["timestamps_ms"])):
        raise ValueError("Source video identity/dimensions/timeline mismatch")
    parameters = cv2.TrackerCSRT.Params()
    if {name: getattr(parameters, name) for name in PARAMETER_NAMES} != plan["parameters"]:
        raise ValueError("CSRT defaults changed")
    tracker = cv2.TrackerCSRT.create(parameters)
    capture = cv2.VideoCapture(str(root / sources["video"]["path"]))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot open source video")
        output.mkdir(parents=True)
        measurements = measure_frames(capture, tracker, seed, technical, target)
    finally:
        capture.release()
    verify_execution(root, plan)
    if sha(plan_path) != plan_sha:
        raise ValueError("Execution manifest changed during measurement")
    report = {"status": "sealed_measurements_only", "plan_sha256": plan_sha,
              "proposal_manifest": plan["proposal_manifest"],
              "proposal_manifest_sha256": plan["proposal_manifest_sha256"],
              "producer_sha256": sha(__file__), "producer_sources": sources,
              "runtime": runtime(), "parameters": plan["parameters"], "target": target,
              "failure_policy": FAILURE_POLICY, **measurements,
              "raw_score_policy": RAW_SCORE_POLICY,
              "initialization_failure_policy": INITIALIZATION_FAILURE_POLICY,
              "integrity_failure_policy": INTEGRITY_FAILURE_POLICY,
              "human_annotation_inputs": [sources["initialization"]], "pose_inputs": [],
              "measurement_semantics": "Image continuation conditional on declared human-assisted initialization",
              "score_semantics": "Raw native tracking score diagnostic; not calibrated identity or anatomy confidence",
              "initialization_frame_excluded_from_effectiveness": True,
              "post_initialization_frame_denominator": target["total_frames"] - 1,
              "subject_assignment": None, "warning_policy": None, "calibrated_confidence": None,
              "phase2_automatic_reliability": "NOT PASSED"}
    write(output / "seeded_subject_measurements.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run(args.root, args.plan, args.output)
    print(json.dumps({"frames": len(result["frames"]), "initialization_calls": result["initialization_calls"],
                      "native_update_calls": result["native_update_calls"], "terminal_break": result["terminal_break"],
                      "subject_assignment": None, "warning_policy": None}))
