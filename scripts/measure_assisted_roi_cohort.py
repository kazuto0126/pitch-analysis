"""Isolated five-clip cohort using frozen, human-initialized ROI helpers."""
from __future__ import annotations

import argparse
import math
from numbers import Real
from pathlib import Path

import cv2

import measure_seeded_subject as tracking
import measure_tracked_roi_pose as roi
from measure_seeded_subject import read, sha, write, verify_sources
from pitch_analysis.subject import PitcherSelector


CLIP_IDS = tuple(f"pitch_{index:03d}" for index in range(1, 6))
SOURCE_ROLES = {"video", "metadata", "video_technical", "initialization"}
TARGET_FIELDS = {"pitch_id", "total_frames", "width", "height"}
DEPENDENCY_PATHS = {
    "scripts/measure_seeded_subject.py", "scripts/measure_tracked_roi_pose.py",
    "src/pitch_analysis/subject.py", "src/pitch_analysis/pose_capture.py",
    "src/pitch_analysis/pose_estimator.py",
}
NATIVE_BINDING_PATHS = {
    ".venv-analysis/Lib/site-packages/cv2/cv2.pyd",
    ".venv-analysis/Lib/site-packages/mediapipe/tasks/c/libmediapipe.dll",
}
FROZEN_FIELDS = (
    "clips", "model", "tracker_parameters", "pose_options", "crop_parameters",
    "runtime", "native_binding_hashes", "producer_dependencies",
)
VISIBLE_EXTENT = "all_presently_visible_head_arms_legs_inside_rectangle"


def runtime():
    return roi.runtime()


def _inside(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("Expected a workspace-relative frozen path")
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Frozen path outside workspace: " + name)
    return path


def _digest(value):
    return (isinstance(value, str) and len(value) == 64 and
            all(character in "0123456789abcdef" for character in value))


def _reference(root, reference):
    if (not isinstance(reference, dict) or set(reference) != {"path", "sha256"} or
            not _digest(reference["sha256"])):
        raise ValueError("Malformed frozen source reference")
    _inside(root, reference["path"])


def _positive_integer(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _finite(value):
    return isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(float(value))


def validate_initialization(seed, clip):
    """Validate the confirmed frame-0 input without opening its review lineage."""
    target, sources = clip["target"], clip["sources"]
    reply = seed.get("raw_user_reply", seed.get("actual_reply_token"))
    if (seed.get("status") != "human_confirmed_initialization" or
            seed.get("source_kind") != "assistant_visual_proposed_human_confirmed" or
            seed.get("human_conclusion") != "pitcher" or
            seed.get("extent_observation") != VISIBLE_EXTENT or reply != "全部正確" or
            seed.get("pitch_id") != target["pitch_id"] or
            seed.get("frame_index") != 0 or isinstance(seed.get("frame_index"), bool) or
            not _finite(seed.get("native_timestamp_ms")) or seed["native_timestamp_ms"] != 0.0 or
            seed.get("source_video") != sources["video"] or
            seed.get("producer_must_not_open_lineage_sources") is not True or
            seed.get("excluded_from_effectiveness_evaluation") is not True or
            not _digest(seed.get("decoded_bgr_sha256"))):
        raise ValueError("Unexpected or unreviewed human-assisted initialization")
    rectangle = seed.get("rectangle_xywh")
    if (not isinstance(rectangle, list) or len(rectangle) != 4 or
            not all(_finite(value) for value in rectangle)):
        raise ValueError("Invalid confirmed initialization rectangle")
    x, y, width, height = rectangle
    if (x < 0 or y < 0 or width <= 0 or height <= 0 or
            x + width > target["width"] or y + height > target["height"]):
        raise ValueError("Confirmed initialization rectangle must be inside source image")


def _load_source_clip(root, clip):
    sources, target = clip["sources"], clip["target"]
    metadata = read(_inside(root, sources["metadata"]["path"]))
    technical = read(_inside(root, sources["video_technical"]["path"]))
    if (metadata.get("schema_version") != "pitch-input-v1" or
            metadata.get("pitch_id") != target["pitch_id"] or
            metadata.get("video", {}).get("file") != Path(sources["video"]["path"]).name or
            technical.get("sha256") != sources["video"]["sha256"] or
            (technical.get("frame_count"), technical.get("width"), technical.get("height")) !=
            (target["total_frames"], target["width"], target["height"])):
        raise ValueError("Source video identity/dimensions/timeline mismatch")
    timestamps = technical.get("timestamps_ms")
    if (not isinstance(timestamps, list) or len(timestamps) != target["total_frames"] or
            not all(_finite(value) for value in timestamps) or timestamps[0] != 0.0 or
            any(after <= before for before, after in zip(timestamps, timestamps[1:]))):
        raise ValueError("Invalid original fractional source timeline")
    if clip["kind"] == "new_measurement":
        seed = read(_inside(root, sources["initialization"]["path"]))
        validate_initialization(seed, clip)
    else:
        seed = None
    return technical, seed


def _validate_reused(root, plan, clip, technical):
    target, sources = clip["target"], clip["sources"]
    tracked = read(_inside(root, clip["reused_tracking"]["path"]))
    measured = read(_inside(root, clip["reused_pose"]["path"]))
    roi.validate_tracked_roi(tracked, sources, target)
    if (tracked["producer_sources"].get("initialization") != sources["initialization"] or
            tracked.get("parameters") != plan["tracker_parameters"] or
            tracked.get("failure_policy") != tracking.FAILURE_POLICY or
            tracked.get("raw_score_policy") != tracking.RAW_SCORE_POLICY or
            tracked.get("initialization_failure_policy") != tracking.INITIALIZATION_FAILURE_POLICY or
            tracked.get("integrity_failure_policy") != tracking.INTEGRITY_FAILURE_POLICY or
            measured.get("status") != "sealed_measurements_only" or measured.get("target") != target or
            measured.get("parameters") != plan["crop_parameters"] or
            measured.get("options") != plan["pose_options"] or measured.get("runtime") != plan["runtime"] or
            measured.get("upstream_roi_requires_human_initialization") is not True or
            len(measured.get("frames", [])) != target["total_frames"] or
            set(measured.get("producer_sources", {})) != roi.PRODUCER_ROLES or
            any(measured["producer_sources"].get(role) != sources[role]
                for role in ("video", "metadata", "video_technical")) or
            measured["producer_sources"].get("model") != plan["model"] or
            measured["producer_sources"].get("tracked_roi") != clip["reused_tracking"]):
        raise ValueError("Reused sealed tracking/pose settings or sources differ")
    for index, (tracker_frame, frame) in enumerate(zip(tracked["frames"], measured["frames"])):
        timestamp = technical["timestamps_ms"][index]
        if (frame.get("frame_index") != index or not _digest(frame.get("decoded_bgr_sha256")) or
                frame["decoded_bgr_sha256"] != tracker_frame.get("decoded_bgr_sha256") or
                not _finite(frame.get("native_timestamp_ms")) or
                not _finite(tracker_frame.get("native_timestamp_ms")) or
                not math.isclose(frame["native_timestamp_ms"], timestamp, rel_tol=0, abs_tol=1e-6) or
                not math.isclose(tracker_frame["native_timestamp_ms"], timestamp, rel_tol=0, abs_tol=1e-6)):
            raise ValueError("Reused sealed pixel/timeline receipt mismatch")


def verify_execution(root, plan):
    """Verify only declared producer inputs, configuration, code and sealed reuse."""
    root = Path(root).resolve()
    if (plan.get("status") != "frozen_before_measurement" or
            plan.get("tracker_parameters") != tracking.default_parameters() or
            plan.get("pose_options") != roi.OPTIONS or plan.get("crop_parameters") != roi.PARAMETERS or
            plan.get("runtime") != runtime()):
        raise ValueError("Unfrozen or changed execution settings")
    clips = plan.get("clips")
    if (not isinstance(clips, list) or len(clips) != 5 or
            not all(isinstance(clip, dict) and isinstance(clip.get("target"), dict) for clip in clips) or
            [clip.get("target", {}).get("pitch_id") for clip in clips] != list(CLIP_IDS)):
        raise ValueError("Expected exactly the five ordered source clip IDs")
    for clip in clips:
        reused = clip["target"]["pitch_id"] == "pitch_003"
        expected = {"kind", "target", "sources"} | ({"reused_tracking", "reused_pose"} if reused else set())
        if set(clip) != expected or clip["kind"] != ("reuse_sealed" if reused else "new_measurement"):
            raise ValueError("Unexpected clip kind or record role")
        if (set(clip["target"]) != TARGET_FIELDS or
                not all(_positive_integer(clip["target"][field]) for field in TARGET_FIELDS - {"pitch_id"})):
            raise ValueError("Invalid declared source target dimensions/count")
        if set(clip["sources"]) != SOURCE_ROLES:
            raise ValueError("Unexpected producer source role")
        for reference in clip["sources"].values():
            _reference(root, reference)
        if reused:
            for role in ("reused_tracking", "reused_pose"):
                _reference(root, clip[role])
    counts = [clip["target"]["total_frames"] for clip in clips]
    if sum(counts) != 592 or counts[2] != 115 or sum(counts[:2] + counts[3:]) != 477:
        raise ValueError("Frozen five-clip source denominator differs")
    _reference(root, plan["model"])
    dependencies = plan.get("producer_dependencies")
    if (not isinstance(dependencies, dict) or len(dependencies) != len(DEPENDENCY_PATHS) or
            not all(isinstance(reference, dict) for reference in dependencies.values()) or
            {reference.get("path") for reference in dependencies.values()} != DEPENDENCY_PATHS):
        raise ValueError("Unexpected or missing frozen producer dependency")
    for reference in dependencies.values():
        _reference(root, reference)
    if set(plan.get("native_binding_hashes", {})) != NATIVE_BINDING_PATHS:
        raise ValueError("Unexpected or missing native binding receipts")
    receipts = {
        "scripts/measure_assisted_roi_cohort.py": plan.get("producer_sha256"),
        "tests/test_assisted_roi_cohort.py": plan.get("producer_test_sha256"),
        **plan["native_binding_hashes"],
    }
    proposal_path = _inside(root, plan["proposal_manifest"])
    if not _digest(plan.get("proposal_manifest_sha256")) or sha(proposal_path) != plan["proposal_manifest_sha256"]:
        raise ValueError("Proposal changed")
    proposal = read(proposal_path)
    if proposal.get("status") != "proposal_only" or any(proposal.get(key) != plan[key] for key in FROZEN_FIELDS):
        raise ValueError("Execution differs from frozen proposal")
    for name, expected in receipts.items():
        if not _digest(expected) or sha(_inside(root, name)) != expected:
            raise ValueError("Frozen code/test or native binding changed: " + name)
    verify_sources(root, dependencies)
    verify_sources(root, {"model": plan["model"]})
    for clip in clips:
        verify_sources(root, clip["sources"])
        technical, _ = _load_source_clip(root, clip)
        if clip["kind"] == "reuse_sealed":
            verify_sources(root, {role: clip[role] for role in ("reused_tracking", "reused_pose")})
            _validate_reused(root, plan, clip, technical)


def _ref(root, path):
    return {"path": path.relative_to(root).as_posix(), "sha256": sha(path)}


def _new_clip(root, plan, clip, directory, plan_sha, check_frozen):
    target, sources = clip["target"], clip["sources"]
    technical, seed = _load_source_clip(root, clip)
    directory.mkdir()
    parameters = cv2.TrackerCSRT.Params()
    if {name: getattr(parameters, name) for name in tracking.PARAMETER_NAMES} != plan["tracker_parameters"]:
        raise ValueError("CSRT defaults changed")
    tracker = cv2.TrackerCSRT.create(parameters)
    capture = cv2.VideoCapture(str(_inside(root, sources["video"]["path"])))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot open source video")
        measurements = tracking.measure_frames(capture, tracker, seed, technical, target)
    finally:
        capture.release()
    tracking_report = {
        "status": "sealed_measurements_only", "plan_sha256": plan_sha,
        "proposal_manifest": plan["proposal_manifest"],
        "proposal_manifest_sha256": plan["proposal_manifest_sha256"],
        "producer_sha256": plan["producer_sha256"], "producer_sources": sources,
        "producer_dependencies": plan["producer_dependencies"], "runtime": tracking.runtime(),
        "parameters": plan["tracker_parameters"], "target": target, **measurements,
        "failure_policy": tracking.FAILURE_POLICY, "raw_score_policy": tracking.RAW_SCORE_POLICY,
        "initialization_failure_policy": tracking.INITIALIZATION_FAILURE_POLICY,
        "integrity_failure_policy": tracking.INTEGRITY_FAILURE_POLICY,
        "human_annotation_inputs": [sources["initialization"]], "pose_inputs": [],
        "measurement_semantics": "Image continuation conditional on declared human-assisted initialization",
        "score_semantics": "Raw native tracking score diagnostic; not calibrated identity or anatomy confidence",
        "initialization_frame_excluded_from_effectiveness": True,
        "post_initialization_frame_denominator": target["total_frames"] - 1,
        "subject_assignment": None, "warning_policy": None, "calibrated_confidence": None,
        "phase2_automatic_reliability": "NOT PASSED",
    }
    check_frozen()
    tracking_path = directory / "seeded_subject_measurements.json"
    write(tracking_path, tracking_report)
    tracked_ref = _ref(root, tracking_path)
    pose_sources = {role: sources[role] for role in ("video", "metadata", "video_technical")}
    pose_sources.update(tracked_roi=tracked_ref, model=plan["model"])
    roi.validate_tracked_roi(tracking_report, pose_sources, target)

    import mediapipe as mp

    options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(_inside(root, plan["model"]["path"]))),
        running_mode=mp.tasks.vision.RunningMode.IMAGE, **plan["pose_options"])
    capture = cv2.VideoCapture(str(_inside(root, sources["video"]["path"])))
    try:
        if not capture.isOpened():
            raise ValueError("Cannot reopen source video")
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as detector:
            measured = roi.measure_frames(capture, detector, PitcherSelector(), tracking_report, technical, target,
                image_factory=lambda rgb: mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
    finally:
        capture.release()
    pose_report = {
        "status": "sealed_measurements_only", "plan_sha256": plan_sha,
        "producer_sha256": plan["producer_sha256"], "producer_sources": pose_sources,
        "producer_dependencies": plan["producer_dependencies"], "runtime": runtime(),
        "parameters": plan["crop_parameters"], "options": plan["pose_options"], "target": target,
        **measured, "human_annotation_inputs": [], "upstream_roi_requires_human_initialization": True,
        "measurement_semantics": "Crop sensitivity conditional on sealed human-initialized tracking; not end-to-end GT-blind",
        "calibrated_confidence": None, "warning_policy": None, "original_predictions_modified": False,
        "phase2_automatic_reliability": "NOT PASSED",
    }
    check_frozen()
    verify_sources(root, {"tracked_roi": tracked_ref})
    pose_path = directory / "roi_pose_measurements.json"
    write(pose_path, pose_report)
    return {
        "pitch_id": target["pitch_id"], "kind": clip["kind"], "target": target,
        "tracking": tracked_ref, "pose": _ref(root, pose_path),
        "new_tracker_initialization_calls": measurements["initialization_calls"],
        "new_tracker_update_calls": measurements["native_update_calls"],
        "new_pose_inference_calls": measured["inference_calls"],
    }


def run(root, plan_path, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    supplied_plan = Path(plan_path)
    resolved_plan = supplied_plan.resolve() if supplied_plan.is_absolute() else (root / supplied_plan).resolve()
    if not resolved_plan.is_relative_to(root):
        raise ValueError("Execution manifest outside workspace")
    plan_path = _inside(root, resolved_plan.relative_to(root).as_posix())
    if output.exists() or not output.is_relative_to(root / "analysis_results"):
        raise ValueError("New output required within analysis_results")
    plan, plan_sha = read(plan_path), sha(plan_path)

    def check_frozen():
        verify_execution(root, plan)
        if sha(plan_path) != plan_sha:
            raise ValueError("Execution manifest changed during measurement")

    check_frozen()
    output.mkdir(parents=True)
    entries = []
    for clip in plan["clips"]:
        check_frozen()
        target = clip["target"]
        if clip["kind"] == "reuse_sealed":
            entries.append({
                "pitch_id": target["pitch_id"], "kind": clip["kind"], "target": target,
                "tracking": clip["reused_tracking"], "pose": clip["reused_pose"],
                "new_tracker_initialization_calls": 0, "new_tracker_update_calls": 0,
                "new_pose_inference_calls": 0,
            })
        else:
            entries.append(_new_clip(root, plan, clip, output / target["pitch_id"], plan_sha, check_frozen))
    report = {
        "status": "sealed_cohort_measurements", "plan_sha256": plan_sha,
        "producer_sha256": plan["producer_sha256"], "clips": entries,
        "source_frames": sum(entry["target"]["total_frames"] for entry in entries),
        "non_seed_frames": sum(entry["target"]["total_frames"] - 1 for entry in entries),
        "new_source_frames": sum(entry["target"]["total_frames"] for entry in entries if entry["kind"] == "new_measurement"),
        "reused_source_frames": sum(entry["target"]["total_frames"] for entry in entries if entry["kind"] == "reuse_sealed"),
        **{key: sum(entry[key] for entry in entries) for key in (
            "new_tracker_initialization_calls", "new_tracker_update_calls", "new_pose_inference_calls")},
        "human_initialized": True, "warning_policy": None, "phase2_automatic_reliability": "NOT PASSED",
    }
    check_frozen()
    for entry in entries:
        verify_sources(root, {role: entry[role] for role in ("tracking", "pose")})
    write(output / "cohort_measurements.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = run(args.root, args.plan, args.output)
    print({key: result[key] for key in (
        "source_frames", "non_seed_frames", "new_tracker_initialization_calls",
        "new_tracker_update_calls", "new_pose_inference_calls", "phase2_automatic_reliability")})
