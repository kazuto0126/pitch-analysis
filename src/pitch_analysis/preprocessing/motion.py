"""Coarse video-motion candidates used before pose-based review."""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from .probe import probe_video


def candidate_ranges_from_scores(
    times: Sequence[float],
    scores: Sequence[float],
    *,
    duration_seconds: float,
    pre_seconds: float = 4.0,
    post_seconds: float = 3.0,
    min_peak_interval_seconds: float = 4.0,
    max_candidates: int = 30,
) -> list[dict]:
    """Convert a sampled motion signal into broad, review-required clips."""
    if len(times) != len(scores):
        raise ValueError("times and scores must have the same length")
    if pre_seconds < 0 or post_seconds <= 0 or min_peak_interval_seconds <= 0:
        raise ValueError("motion candidate timing parameters are invalid")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")
    if len(scores) < 5 or duration_seconds <= 0:
        return []
    values = np.asarray(scores, dtype=float)
    if (
        not np.all(np.isfinite(values))
        or float(values.max()) <= 0
        or float(values.max() - values.min()) < 1e-9
    ):
        return []
    smoothed = np.convolve(values, np.ones(3, dtype=float) / 3.0, mode="same")
    median = float(np.median(smoothed))
    mad = float(np.median(np.abs(smoothed - median)))
    threshold = max(float(np.quantile(smoothed, 0.75)), median + 1.5 * mad)
    eligible = [
        index
        for index in range(1, len(smoothed) - 1)
        if smoothed[index] >= threshold
        and smoothed[index] >= smoothed[index - 1]
        and smoothed[index] >= smoothed[index + 1]
    ]
    selected: list[int] = []
    for index in sorted(eligible, key=lambda item: smoothed[item], reverse=True):
        if all(
            abs(float(times[index]) - float(times[other])) >= min_peak_interval_seconds
            for other in selected
        ):
            selected.append(index)
        if len(selected) >= max_candidates:
            break
    if not selected:
        return []
    peak_max = max(float(smoothed[index]) for index in selected)
    denominator = max(peak_max - threshold, 1e-12)
    candidates = []
    for index in sorted(selected, key=lambda item: float(times[item])):
        peak_time = float(times[index])
        start = max(0.0, peak_time - pre_seconds)
        end = min(duration_seconds, peak_time + post_seconds)
        if end <= start:
            continue
        candidates.append(
            {
                "start_second": start,
                "end_second": end,
                "motion_peak_second": peak_time,
                "motion_score": float(smoothed[index]),
                "threshold": threshold,
                "confidence": min(
                    1.0, max(0.0, (float(smoothed[index]) - threshold) / denominator)
                ),
                "method": "coarse-center-roi-frame-difference-v0.1",
                "review_status": "needs_human_review",
            }
        )
    return candidates


def detect_motion_candidates(
    video_path: str | Path,
    *,
    sample_fps: float = 6.0,
    pre_seconds: float = 4.0,
    post_seconds: float = 3.0,
    min_peak_interval_seconds: float = 4.0,
    max_candidates: int = 30,
) -> dict:
    """Sample the center field region and return broad motion candidates."""
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    probe = probe_video(video_path)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Cannot open video: {video_path}")
    step = max(1, round(probe["fps"] / sample_fps))
    times: list[float] = []
    scores: list[float] = []
    previous = None
    for frame_index in range(0, probe["frame_count"], step):
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok:
            continue
        height, width = frame.shape[:2]
        roi = frame[
            round(height * 0.10) : round(height * 0.95),
            round(width * 0.20) : round(width * 0.80),
        ]
        gray = cv2.cvtColor(cv2.resize(roi, (320, 180)), cv2.COLOR_BGR2GRAY)
        if previous is not None:
            scores.append(float(cv2.absdiff(gray, previous).mean() / 255.0))
            times.append(frame_index / probe["fps"])
        previous = gray
    capture.release()
    candidates = candidate_ranges_from_scores(
        times,
        scores,
        duration_seconds=probe["duration_seconds"],
        pre_seconds=pre_seconds,
        post_seconds=post_seconds,
        min_peak_interval_seconds=min_peak_interval_seconds,
        max_candidates=max_candidates,
    )
    return {
        "schema_version": "coarse-motion-candidates-v0.1",
        "video": str(video_path),
        "sample_fps_requested": sample_fps,
        "sample_step_frames": step,
        "sample_count": len(scores),
        "candidates": candidates,
        "note": "Full-frame/broadcast motion can create false positives. Every candidate requires visual review and later pose-quality checks.",
    }
