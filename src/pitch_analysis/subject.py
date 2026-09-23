"""Conservative subject selection for a prepared rear-centerfield single pitch.

This selects the *pitcher skeleton*, not a named MLB player. Rejections remain
visible to the review output instead of silently switching to another person.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot


MAJOR_JOINTS = (11, 12, 23, 24, 25, 26, 27, 28)


@dataclass(frozen=True)
class Selection:
    index: int | None
    status: str
    reason: str
    candidate_count: int
    score: float | None = None
    mean_confidence: float | None = None


class PitcherSelector:
    """Use spatial protocol, full-body scale and short-term hip continuity."""

    def __init__(self) -> None:
        self.previous: tuple[float, float, float] | None = None
        self.gap = 0

    def select(self, poses: list) -> Selection:
        candidates = []
        for index, pose in enumerate(poses):
            if len(pose) < 29:
                continue
            joints = [pose[i] for i in MAJOR_JOINTS]
            confidences = [min(float(getattr(p, "visibility", 0)), float(getattr(p, "presence", 0))) for p in joints]
            confidence = sum(confidences) / len(confidences)
            if confidence < .45 or sum(value >= .35 for value in confidences) < 6:
                continue
            hip_x = (pose[23].x + pose[24].x) / 2
            hip_y = (pose[23].y + pose[24].y) / 2
            shoulder_y = (pose[11].y + pose[12].y) / 2
            ankle_y = (pose[27].y + pose[28].y) / 2
            body_height = ankle_y - shoulder_y
            if not (.15 <= hip_x <= .85 and .12 <= hip_y <= .85 and .16 <= body_height <= .85):
                continue
            # Catcher/umpire are normally low and/or near the bottom of this view.
            # A broad ROI avoids assuming the pitcher is at the exact image centre.
            spatial = 1 - min(abs(hip_x - .5) / .35, 1)
            scale = min(body_height / .4, 1)
            score = .45 * confidence + .35 * spatial + .2 * scale
            if self.previous is not None and self.gap <= 6:
                prev_x, prev_y, prev_height = self.previous
                distance = hypot(hip_x - prev_x, hip_y - prev_y)
                if distance > max(.18, prev_height * .45):
                    continue
                score += .25 * (1 - min(distance / .18, 1))
            candidates.append((score, index, confidence, hip_x, hip_y, body_height))
        candidates.sort(reverse=True)
        if not candidates:
            self.gap += 1
            return Selection(None, "rejected", "no_reliable_pitcher_candidate", len(poses))
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .06:
            self.gap += 1
            return Selection(None, "ambiguous", "two_plausible_subjects", len(poses))
        score, index, confidence, hip_x, hip_y, body_height = candidates[0]
        self.previous = (hip_x, hip_y, body_height)
        self.gap = 0
        return Selection(index, "selected", "rear_centerfield_spatial_scale_continuity", len(poses), score, confidence)
