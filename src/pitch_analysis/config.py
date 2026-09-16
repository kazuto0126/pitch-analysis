from dataclasses import dataclass


@dataclass(frozen=True)
class QualityConfig:
    min_visibility: float = 0.5
    min_presence: float = 0.5
    max_interpolation_gap: int = 2
    max_interpolation_seconds: float | None = 2 / 30
    feature_smoothing_seconds: float = 2 / 30

    def interpolation_gap_frames(self, fps: float | None = None) -> int:
        """Use a time-bound gap when capture FPS is known; retain legacy fallback."""
        if fps and fps > 0 and self.max_interpolation_seconds is not None:
            return max(0, round(self.max_interpolation_seconds * fps))
        return self.max_interpolation_gap

    def feature_smoothing_radius_frames(self, fps: float | None = None) -> int:
        if fps and fps > 0:
            return max(0, round(self.feature_smoothing_seconds * fps))
        return 2


FEATURE_COLUMNS = (
    "throwing_knee_angle", "lead_knee_angle", "shoulder_line_angle",
    "throwing_elbow_angle", "hip_line_angle", "lateral_foot_separation",
)
