"""Conservative subject selection for a prepared rear-centerfield single pitch.

This selects the *pitcher skeleton*, not a named MLB player. Rejections remain
visible to the review output instead of silently switching to another person.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from numbers import Real


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

    def __init__(self, *, subject_roi: tuple[float, float, float, float] | None = None) -> None:
        self.subject_roi = self._validate_roi(subject_roi)
        self.previous: tuple[float, float, float] | None = None
        self.gap = 0
        self.last_decision: dict = {}

    @staticmethod
    def _validate_roi(roi) -> tuple[float, float, float, float] | None:
        if roi is None:
            return None
        if not isinstance(roi, (tuple, list)) or len(roi) != 4:
            raise ValueError("subject_roi must contain four normalized image coordinates")
        if any(isinstance(value, bool) or not isinstance(value, Real)
               or not isfinite(float(value)) for value in roi):
            raise ValueError("subject_roi coordinates must be finite numbers, not booleans")
        xmin, ymin, xmax, ymax = (float(value) for value in roi)
        if not (0 <= xmin < xmax <= 1 and 0 <= ymin < ymax <= 1):
            raise ValueError("subject_roi must satisfy 0 <= min < max <= 1 on both axes")
        return xmin, ymin, xmax, ymax

    def _matches_roi(self, pose) -> bool:
        """All four raw torso anchors must be inside the original-image ROI."""
        if self.subject_roi is None:
            return True
        xmin, ymin, xmax, ymax = self.subject_roi
        for index in (11, 12, 23, 24):
            x, y = float(pose[index].x), float(pose[index].y)
            if not (isfinite(x) and isfinite(y) and xmin <= x <= xmax and ymin <= y <= ymax):
                return False
        return True

    @staticmethod
    def _number(value):
        """Keep diagnostics strict-JSON safe without changing selection arithmetic."""
        if value is None:
            return None
        value = float(value)
        return value if isfinite(value) else None

    def _record_decision(self, selection, anchor_before, gap_before, details):
        self.last_decision = {
            "subject_roi": list(self.subject_roi) if self.subject_roi is not None else None,
            "anchor_before": [self._number(value) for value in anchor_before]
            if anchor_before is not None else None,
            "anchor_after": [self._number(value) for value in self.previous]
            if self.previous is not None else None,
            "gap_before": gap_before,
            "gap_after": self.gap,
            "selected_index": selection.index,
            "status": selection.status,
            "reason": selection.reason,
            "candidate_count": selection.candidate_count,
            "candidates": details,
        }
        return selection

    def select(self, poses: list) -> Selection:
        anchor_before, gap_before = self.previous, self.gap
        details = []
        candidates = []
        for index, pose in enumerate(poses):
            detail = {"index": index, "eligible": False, "rejection_reason": None}
            details.append(detail)
            if len(pose) < 29:
                detail["rejection_reason"] = "too_few_landmarks"
                continue
            joints = [pose[i] for i in MAJOR_JOINTS]
            confidences = [min(float(getattr(p, "visibility", 0)), float(getattr(p, "presence", 0))) for p in joints]
            confidence = sum(confidences) / len(confidences)
            detail["confidence"] = self._number(confidence)
            if confidence < .45 or sum(value >= .35 for value in confidences) < 6:
                detail["rejection_reason"] = "insufficient_major_joint_confidence"
                continue
            hip_x = (pose[23].x + pose[24].x) / 2
            hip_y = (pose[23].y + pose[24].y) / 2
            shoulder_y = (pose[11].y + pose[12].y) / 2
            ankle_y = (pose[27].y + pose[28].y) / 2
            body_height = ankle_y - shoulder_y
            detail["hip_xy"] = [self._number(hip_x), self._number(hip_y)]
            detail["body_height"] = self._number(body_height)
            if not (.15 <= hip_x <= .85 and .12 <= hip_y <= .85 and .16 <= body_height <= .85):
                detail["rejection_reason"] = "outside_rear_centerfield_protocol"
                continue
            if not self._matches_roi(pose):
                detail["rejection_reason"] = "outside_subject_roi"
                continue
            # Catcher/umpire are normally low and/or near the bottom of this view.
            # A broad ROI avoids assuming the pitcher is at the exact image centre.
            spatial = 1 - min(abs(hip_x - .5) / .35, 1)
            scale = min(body_height / .4, 1)
            score = .45 * confidence + .35 * spatial + .2 * scale
            detail.update(spatial=self._number(spatial), scale=self._number(scale),
                          base_total=self._number(score), continuity=None)
            if self.previous is not None and self.gap <= 6:
                prev_x, prev_y, prev_height = self.previous
                distance = hypot(hip_x - prev_x, hip_y - prev_y)
                detail["continuity_distance"] = self._number(distance)
                if distance > max(.18, prev_height * .45):
                    detail["rejection_reason"] = "outside_short_term_continuity"
                    continue
                continuity = .25 * (1 - min(distance / .18, 1))
                score += continuity
                detail["continuity"] = self._number(continuity)
            detail.update(eligible=True, score=self._number(score), final_score=self._number(score))
            candidates.append((score, index, confidence, hip_x, hip_y, body_height))
        candidates.sort(reverse=True)
        if not candidates:
            self.gap += 1
            return self._record_decision(
                Selection(None, "rejected", "no_reliable_pitcher_candidate", len(poses)),
                anchor_before, gap_before, details)
        if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < .06:
            self.gap += 1
            return self._record_decision(
                Selection(None, "ambiguous", "two_plausible_subjects", len(poses)),
                anchor_before, gap_before, details)
        score, index, confidence, hip_x, hip_y, body_height = candidates[0]
        self.previous = (hip_x, hip_y, body_height)
        self.gap = 0
        return self._record_decision(
            Selection(index, "selected", "rear_centerfield_spatial_scale_continuity", len(poses), score, confidence),
            anchor_before, gap_before, details)
