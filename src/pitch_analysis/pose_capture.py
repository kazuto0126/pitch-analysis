"""MediaPipe Pose Landmarker extraction with reusable video/segment parameters."""
from __future__ import annotations
import csv
import json
from pathlib import Path


LANDMARK_NAMES = (
    "NOSE", "LEFT_EYE_INNER", "LEFT_EYE", "LEFT_EYE_OUTER", "RIGHT_EYE_INNER", "RIGHT_EYE", "RIGHT_EYE_OUTER", "LEFT_EAR", "RIGHT_EAR", "MOUTH_LEFT", "MOUTH_RIGHT", "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW", "LEFT_WRIST", "RIGHT_WRIST", "LEFT_PINKY", "RIGHT_PINKY", "LEFT_INDEX", "RIGHT_INDEX", "LEFT_THUMB", "RIGHT_THUMB", "LEFT_HIP", "RIGHT_HIP", "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE", "LEFT_HEEL", "RIGHT_HEEL", "LEFT_FOOT_INDEX", "RIGHT_FOOT_INDEX",
)


def extract_pose(video_path: str | Path, model_path: str | Path, output_csv: str | Path, *, start_second: float = 0.0, end_second: float | None = None, subject_selection: str | None = None) -> dict:
    import cv2
    import mediapipe as mp

    from .subject import PitcherSelector

    if subject_selection not in (None, "rear_centerfield_broadcast"):
        raise ValueError("Unsupported subject-selection camera protocol")
    selector = PitcherSelector() if subject_selection else None

    video_path, model_path, output_csv = Path(video_path), Path(model_path), Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise ValueError(f"cannot open video: {video_path}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0:
        raise ValueError("video has invalid FPS")
    start_frame = max(0, round(start_second * fps))
    end_frame = min(total_frames - 1, round(end_second * fps)) if end_second is not None else total_frames - 1
    if end_frame < start_frame:
        raise ValueError("end_second must be after start_second")
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    BaseOptions = mp.tasks.BaseOptions
    options = mp.tasks.vision.PoseLandmarkerOptions(base_options=BaseOptions(model_asset_path=str(model_path)), running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=4 if selector else 1, min_pose_detection_confidence=.5, min_pose_presence_confidence=.5, min_tracking_confidence=.5)
    detected_frames = 0
    processed_frames = 0
    selection_frames = []
    try:
        with output_csv.open("w", newline="", encoding="utf-8-sig") as sink, mp.tasks.vision.PoseLandmarker.create_from_options(options) as landmarker:
            writer = csv.DictWriter(sink, fieldnames=("frame", "timestamp_ms", "landmark", "x", "y", "z", "visibility", "presence"))
            writer.writeheader()
            for frame_number in range(start_frame, end_frame + 1):
                ok, frame = capture.read()
                if not ok:
                    break
                processed_frames += 1
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                timestamp_ms = round(capture.get(cv2.CAP_PROP_POS_MSEC)) if selector else round(frame_number * 1000 / fps)
                result = landmarker.detect_for_video(image, timestamp_ms)
                if selector:
                    choice = selector.select(result.pose_landmarks)
                    selection_frames.append({"frame_index": frame_number, "timestamp_ms": timestamp_ms,
                                             "status": choice.status, "reason": choice.reason,
                                             "candidate_count": choice.candidate_count, "selected_index": choice.index,
                                             "score": choice.score, "mean_confidence": choice.mean_confidence})
                    if choice.index is None:
                        continue
                    landmarks = result.pose_landmarks[choice.index]
                elif not result.pose_landmarks:
                    continue
                else:
                    landmarks = result.pose_landmarks[0]
                detected_frames += 1
                for index, landmark in enumerate(landmarks):
                    writer.writerow({"frame": frame_number, "timestamp_ms": timestamp_ms, "landmark": LANDMARK_NAMES[index], "x": landmark.x, "y": landmark.y, "z": landmark.z, "visibility": landmark.visibility, "presence": getattr(landmark, "presence", "")})
    finally:
        capture.release()
    report = {"video": str(video_path), "model": str(model_path), "fps": fps, "start_frame": start_frame, "end_frame": end_frame, "requested_frames": end_frame - start_frame + 1, "processed_frames": processed_frames, "detected_frames": detected_frames, "width": width, "height": height,
              "subject_selection": subject_selection or "legacy_first_pose", "selection_frames": selection_frames}
    output_csv.with_suffix(".capture.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
