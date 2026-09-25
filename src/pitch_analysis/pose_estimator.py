"""Backend-neutral contract for single-frame pose estimates.

Backends return 33 ordered landmarks with normalized image X/Y. Z remains
backend-relative, not calibrated 3-D. Visibility and presence are distinct.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence, Self


class PoseLandmark(Protocol):
    x: float
    y: float
    z: float
    visibility: float
    presence: float


@dataclass(frozen=True)
class PoseEstimate:
    """One backend result in the project's ordered-landmark contract."""

    pose_landmarks: Sequence[Sequence[PoseLandmark]]


class PoseEstimator(Protocol):
    """Context-managed pose backend used by the capture pipeline."""

    backend_name: str

    def estimate(self, frame_bgr: Any, timestamp_ms: int) -> PoseEstimate: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...


class MediaPipePoseEstimator:
    """Current baseline backend, preserving the established model settings."""

    backend_name = "mediapipe_pose_landmarker"

    def __init__(self, model_path: str | Path, *, num_poses: int) -> None:
        import mediapipe as mp

        self._mp = mp
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=num_poses,
            min_pose_detection_confidence=.5,
            min_pose_presence_confidence=.5,
            min_tracking_confidence=.5,
        )
        self._landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self._landmarker.close()

    def estimate(self, frame_bgr: Any, timestamp_ms: int) -> PoseEstimate:
        import cv2

        image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB,
            data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB),
        )
        result = self._landmarker.detect_for_video(image, timestamp_ms)
        return PoseEstimate(result.pose_landmarks)
