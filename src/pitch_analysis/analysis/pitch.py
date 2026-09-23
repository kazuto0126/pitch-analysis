"""Phase 0 entry: validate a whole pitch, reuse core processing, export contracts."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from importlib.metadata import version
from pathlib import Path
from statistics import median

from ..config import FEATURE_COLUMNS, QualityConfig
from ..contracts import load_input, write_contract
from ..events import EVENTS
from ..io import read_pose_csv
from ..video.standardization import standardize_mp4
from ..video.validation import sha256_file, validate_mp4
from ..video.input_quality import scan_input_quality, refine_input_quality
from ..workflow import prepare_segment
from .debug import write_pose_debug


def _keypoints(raw_csv: Path, video: dict, ids: dict) -> dict:
    pose = read_pose_csv(raw_csv)
    frames = []
    for index, timestamp in enumerate(video["timestamps_ms"]):
        landmarks = [{"name": name, "x": point["x"], "y": point["y"], "z": point.get("z"),
                      "confidence": point.get("visibility"), "visibility": point.get("visibility"), "presence": point.get("presence")}
                     for name, point in pose.get(index, {}).items()]
        frames.append({"frame_index": index, "timestamp_ms": timestamp, "detected": bool(landmarks), "landmarks": landmarks})
    return {"schema_version": "keypoints-v1", **ids,
            "coordinate_system": "normalized_image_xy; z is model-estimated relative depth, not calibrated 3D",
            "confidence_semantics": "confidence equals MediaPipe visibility, not calibrated coordinate accuracy; presence is separate",
            "frames": frames}


def _metrics(core: Path, ids: dict, status: str, passed: bool) -> dict:
    metrics = {}
    if (core / "features.csv").exists():
        with (core / "features.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for feature in FEATURE_COLUMNS:
            values = [float(row[feature]) for row in rows if row.get(feature, "") != "" and row.get(feature + "_raw_observed", "").lower() == "true"]
            is_line = feature in {"hip_line_angle", "shoulder_line_angle"}
            metrics[feature] = {
                "unit": "image_height" if feature == "lateral_foot_separation" else "degree",
                "observability": "estimated_stride_proxy" if feature == "lateral_foot_separation" else "direct_2d_projection",
                "raw_coverage": len(values) / len(rows) if rows else 0, "observed_frames": len(values),
                # Linear extrema/median are misleading at the +/-90 degree orientation wrap.
                "min": min(values) if values and not is_line else None,
                "max": max(values) if values and not is_line else None,
                "median": median(values) if values and not is_line else None,
            }
    return {"schema_version": "pitch-metrics-v1", **ids, "status": status, "quality_gate_passed": passed,
            "scope": "full prepared clip; raw observed features only; not event-specific biomechanics", "metrics": metrics,
            "limitations": ["No calibrated 3D angles, torque, ball velocity or release-position estimate is produced.",
                            "Shoulder/hip lines are image-plane orientations, not axial rotations; circular summaries deferred.",
                            "Lateral foot separation uses image height, not body size; excluded from cross-pitch distance.",
                            "The rear-view subject selector is heuristic; visually verify pitcher identity and any occluded joints."]}


def analyze_pitch(video_path: str | Path, metadata_path: str | Path, *, output_root: str | Path = "analysis_results",
                  model_path: str | Path = "models/pose_landmarker_full.task", standardize: bool = False) -> dict:
    payload = load_input(video_path, metadata_path)
    source = Path(video_path).resolve(strict=True)
    model = Path(model_path).resolve(strict=True)
    output = Path(output_root).resolve() / payload["pitcher"]["id"] / payload["pitch_id"]
    if output.exists():
        raise FileExistsError(f"Analysis already exists; choose another output root: {output}")
    video = validate_mp4(source)
    ids = {"pitch_id": payload["pitch_id"], "pitcher_id": payload["pitcher"]["id"]}
    quality = QualityConfig()
    manifest = {
        "schema_version": "pitch-analysis-v1", **ids, "status": "running", "artifacts": {}, "failure": None,
        "provenance": {
            "input_sha256": video["sha256"], "analysis_video_sha256": video["sha256"],
            "model_path": str(model), "model_sha256": sha256_file(model),
            "packages": {name: version(name) for name in ("mediapipe", "opencv-contrib-python", "numpy", "jsonschema", "imageio-ffmpeg")},
            "standardization": "h264_yuv420p_native_fps" if standardize else "none",
            "subject_selection": "rear_centerfield_v1",
            "timebase": "zero-based clip frames; CFR checked against decoded presentation timestamps", "quality_config": asdict(quality),
        },
    }
    output.mkdir(parents=True, exist_ok=False)
    def save(name: str, value: dict, schema: str) -> None:
        write_contract(output / name, value, schema)
        manifest["artifacts"][name] = name
    try:
        save("input_manifest.json", payload, "pitch-input-v1")
        save("video_metadata.json", video, "video-validation-v1")
        preflight = scan_input_quality(video)
        save("input_quality_preflight.json", preflight, "input-quality-v1")
        save("input_quality.json", preflight, "input-quality-v1")
        write_contract(output / "analysis.json", manifest, "pitch-analysis-v1")
        if preflight["status"] == "rejected":
            manifest["status"] = "input_rejected"
            write_contract(output / "analysis.json", manifest, "pitch-analysis-v1")
            return {"status": manifest["status"], "input_quality_status": "rejected",
                    "output_dir": str(output), "manifest": str(output / "analysis.json"),
                    "quality_gate_passed": False, "review_required": True}
        analysis_video = source
        if standardize:
            analysis_video = output / "working.mp4"
            video = standardize_mp4(source, analysis_video, validated=video)
            save("working_video_metadata.json", video, "video-validation-v1")
            manifest["artifacts"]["working.mp4"] = "working.mp4"
            manifest["provenance"]["analysis_video_sha256"] = video["sha256"]
        context = {key: str(value) for key, value in payload.get("context", {}).items() if value is not None}
        context.update({"view": payload["video"]["camera_view"], "horizontal_mirror": False, "subject_framing": "full_body"})
        # A fresh child directory satisfies prepare_segment's non-overwrite contract.
        core = output / "core"
        prepared = prepare_segment(analysis_video, core, video_id=ids["pitcher_id"] + "__" + ids["pitch_id"],
                                   throwing_side=payload["pitcher"]["throws"], model_path=model,
                                   start_second=0.0, end_second=None,
                                   reference_context=context, quality=quality,
                                   subject_selection="rear_centerfield_broadcast")
        capture = json.loads((core / "pose_raw.capture.json").read_text(encoding="utf-8"))
        if capture["requested_frames"] != video["frame_count"]:
            raise ValueError("Pose capture timeline disagrees with validated input")
        if capture["processed_frames"] != video["frame_count"]:
            raise ValueError("Pose capture did not process every validated video frame")
        status = "no_pose" if prepared["detected_frames"] == 0 else "needs_event_review" if prepared["quality_gate_passed"] else "quality_gate_failed"
        save("keypoints.json", _keypoints(core / "pose_raw.csv", video, ids), "keypoints-v1")
        save("metrics.json", _metrics(core, ids, status, prepared["quality_gate_passed"]), "pitch-metrics-v1")
        if prepared["event_review"]:
            save("phases.json", {"schema_version": "pitch-events-v1", **ids, "status": "needs_human_review", "legacy_annotation": "events.json",
                                 "events": {name: {"frame_index": None, "timestamp_ms": None, "confidence": None,
                                                   "source": "not_detected_phase0", "uncertainty_frames": None} for name in EVENTS}}, "pitch-events-v1")
        # Flatten core artifacts so existing build-phases/revalidate/registry can read this folder.
        for artifact in sorted(core.iterdir()):
            if artifact.suffix == ".json":
                # Core sidecars use path references. Relocate only this newly-created output prefix.
                content = json.loads(artifact.read_text(encoding="utf-8"))
                def relocate(value):
                    if isinstance(value, str) and value.startswith(str(core) + str(Path('/'))):
                        return str(output) + value[len(str(core)):]
                    if isinstance(value, dict):
                        return {key: relocate(item) for key, item in value.items()}
                    if isinstance(value, list):
                        return [relocate(item) for item in value]
                    return value
                (output / artifact.name).write_text(json.dumps(relocate(content), indent=2, allow_nan=False), encoding="utf-8")
                artifact.unlink()
            else:
                artifact.rename(output / artifact.name)
            manifest["artifacts"][artifact.name] = artifact.name
        core.rmdir()
        write_pose_debug(output, video, capture, payload["pitcher"]["throws"], prepared["quality_gate_passed"])
        final_quality = refine_input_quality(preflight, capture, read_pose_csv(output / "pose_raw.csv"),
                                             throwing_side=payload["pitcher"]["throws"],
                                             quality_gate_passed=prepared["quality_gate_passed"])
        save("input_quality.json", final_quality, "input-quality-v1")
        for name in ("keypoints.jsonl", "processed_keypoints.jsonl", "keypoint_quality.json", "wrist_trajectory.json", "overlay.mp4",
                     "review/human_validation_template.json"):
            manifest["artifacts"][name] = name
        # Preserve established post-pose analysis statuses for existing callers.
        # Input eligibility is the separate, authoritative input_quality_status.
        manifest["status"] = status
        write_contract(output / "analysis.json", manifest, "pitch-analysis-v1")
    except Exception as error:
        manifest["status"], manifest["failure"] = "failed", f"{type(error).__name__}: {error}"
        write_contract(output / "analysis.json", manifest, "pitch-analysis-v1")
        raise
    return {"status": manifest["status"], "input_quality_status": final_quality["status"],
            "output_dir": str(output), "manifest": str(output / "analysis.json"),
            "quality_gate_passed": prepared["quality_gate_passed"], "review_required": True}
