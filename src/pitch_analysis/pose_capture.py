"""Pose extraction through the shared backend contract."""
from __future__ import annotations
import csv
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
from typing import Callable

from .pose_estimator import MediaPipePoseEstimator, PoseEstimator
from .pose_crop import build_input_transform, map_crop_candidates, validate_input_crop


LANDMARK_NAMES = (
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER", "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER", "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT", "MOUTH_RIGHT", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY", "LEFT_INDEX", "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB", "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _raw_candidates(poses) -> list[dict]:
    """Copy every model value to the sidecar without changing its coordinates."""
    return [{"candidate_index": candidate_index,
             "landmarks": [{"index": index, "name": LANDMARK_NAMES[index],
                            "x": point.x, "y": point.y, "z": point.z,
                            "visibility": point.visibility,
                            "presence": getattr(point, "presence", None)}
                           for index, point in enumerate(pose)]}
            for candidate_index, pose in enumerate(poses)]


def extract_pose(video_path: str | Path, model_path: str | Path, output_csv: str | Path, *, start_second: float = 0.0, end_second: float | None = None, subject_selection: str | None = None, subject_roi: tuple[float, float, float, float] | None = None, record_candidates: bool = False, input_crop: tuple[float, float, float, float] | None = None, estimator_factory: Callable[[Path, int], PoseEstimator] | None = None) -> dict:
    import cv2

    from .subject import PitcherSelector

    if subject_selection not in (None, "rear_centerfield_broadcast"):
        raise ValueError("Unsupported subject-selection camera protocol")
    if not isinstance(record_candidates, bool):
        raise ValueError("record_candidates must be a boolean")
    if subject_roi is not None and subject_selection is None:
        raise ValueError("subject_roi requires rear_centerfield_broadcast subject selection")
    input_crop = validate_input_crop(input_crop)
    selector = (PitcherSelector(subject_roi=subject_roi) if subject_roi is not None else PitcherSelector()) if subject_selection else None

    video_path, model_path, output_csv = Path(video_path), Path(model_path), Path(output_csv)
    trace_enabled = record_candidates or subject_roi is not None or input_crop is not None
    trace_path = output_csv.with_suffix(".candidates.jsonl")
    trace_binding = ({"source_video_sha256": _file_sha256(video_path),
                      "model_sha256": _file_sha256(model_path)} if trace_enabled else None)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"cannot open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0:
        raise ValueError("video has invalid FPS")
    input_transform = build_input_transform(input_crop, width, height) if input_crop is not None else None
    start_frame = max(0, round(start_second * fps))
    end_frame = min(total_frames - 1, round(end_second * fps)) if end_second is not None else total_frames - 1
    if end_frame < start_frame:
        raise ValueError("end_second must be after start_second")
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    factory = estimator_factory or (lambda path, count: MediaPipePoseEstimator(path, num_poses=count))
    detected_frames = 0
    processed_frames = 0
    candidate_records = 0
    selection_frames = []
    try:
        with output_csv.open("w", newline="", encoding="utf-8-sig") as sink, factory(model_path, 4 if selector else 1) as estimator, (trace_path.open("w", encoding="utf-8") if trace_enabled else nullcontext()) as trace:
            writer = csv.DictWriter(sink, fieldnames=("frame", "timestamp_ms", "landmark", "x", "y", "z", "visibility", "presence"))
            writer.writeheader()
            for frame_number in range(start_frame, end_frame + 1):
                ok, frame = capture.read()
                if not ok:
                    break
                processed_frames += 1
                timestamp_ms = round(capture.get(cv2.CAP_PROP_POS_MSEC)) if selector else round(frame_number * 1000 / fps)
                model_frame = frame
                if input_transform is not None:
                    if frame.shape[:2] != (height, width):
                        raise ValueError("Decoded frame dimensions disagree with input_crop transform")
                    left, top, right, bottom = input_transform["pixel_bounds_xyxy"]
                    model_frame = frame[top:bottom, left:right]
                result = estimator.estimate(model_frame, timestamp_ms)
                if any(len(pose) != len(LANDMARK_NAMES) for pose in result.pose_landmarks):
                    raise ValueError("Pose backend must return 33 ordered landmarks per subject")
                poses = (map_crop_candidates(result.pose_landmarks, input_transform)
                         if input_transform is not None else result.pose_landmarks)
                if selector:
                    choice = selector.select(poses)
                    selection_frames.append({"frame_index": frame_number, "timestamp_ms": timestamp_ms,
                                             "status": choice.status, "reason": choice.reason,
                                             "candidate_count": choice.candidate_count, "selected_index": choice.index,
                                             "score": choice.score, "mean_confidence": choice.mean_confidence})
                    selected_index, status, reason = choice.index, choice.status, choice.reason
                else:
                    selected_index = 0 if poses else None
                    status = "selected" if selected_index is not None else "rejected"
                    reason = "legacy_first_pose" if selected_index is not None else "no_pose_detected"
                if trace is not None:
                    record = {"schema_version": 1, "frame_index": frame_number,
                              "timestamp_ms": timestamp_ms,
                              "coordinate_system": "original_image_normalized",
                              "candidate_index_semantics": "frame_local",
                              "candidates": _raw_candidates(poses),
                              "selection": {"selected_index": selected_index,
                                            "status": status, "reason": reason},
                              "selector_decision": selector.last_decision if selector else None}
                    if input_transform is not None:
                        record["input_transform"] = input_transform
                        record["native_candidates"] = _raw_candidates(result.pose_landmarks)
                    trace.write(json.dumps(record, ensure_ascii=False) + "\n")
                    candidate_records += 1
                if selector:
                    if choice.index is None:
                        continue
                    landmarks = poses[choice.index]
                elif not poses:
                    continue
                else:
                    landmarks = poses[0]
                detected_frames += 1
                for index, landmark in enumerate(landmarks):
                    writer.writerow({"frame": frame_number, "timestamp_ms": timestamp_ms, "landmark": LANDMARK_NAMES[index], "x": landmark.x, "y": landmark.y, "z": landmark.z, "visibility": landmark.visibility, "presence": getattr(landmark, "presence", "")})
    finally:
        capture.release()
    report = {"video": str(video_path), "model": str(model_path), "fps": fps, "start_frame": start_frame, "end_frame": end_frame, "requested_frames": end_frame - start_frame + 1, "processed_frames": processed_frames, "detected_frames": detected_frames, "width": width, "height": height,
              "subject_selection": subject_selection or "legacy_first_pose", "selection_frames": selection_frames}
    if trace_enabled:
        report["subject_roi"] = list(subject_roi) if subject_roi is not None else None
        report["candidate_trace"] = {"path": str(trace_path), "record_count": candidate_records,
                                     "coordinate_system": "original_image_normalized",
                                     "candidate_index_semantics": "frame_local",
                                     "landmarks_per_candidate": len(LANDMARK_NAMES),
                                     "semantics": "All raw model candidates, including rejected and ambiguous frames; no coordinate correction, padding or interpolation. Model values do not establish visibility or identity.",
                                     **trace_binding}
    if input_transform is not None:
        report["input_crop"] = list(input_crop)
        report["input_transform"] = input_transform
        report["candidate_trace"]["semantics"] = "All model candidates; native_candidates preserve crop-native model values, candidates and raw CSV map to original-image coordinates without clamping or interpolation. Model values do not establish visibility or identity."
        report["candidate_trace"]["native_coordinate_system"] = "crop_image_normalized_xy"
    output_csv.with_suffix(".capture.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
