"""Decode every frame before passing a prepared pitch to the legacy CFR pipeline."""
from __future__ import annotations

import hashlib
import math
import subprocess
from pathlib import Path

from ..contracts import validate_contract


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ffmpeg_executable() -> str:
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def validate_mp4(path: str | Path, *, max_duration_seconds: float = 30.0) -> dict:
    import cv2

    video = Path(path).resolve(strict=True)
    if not video.is_file() or video.suffix.lower() != ".mp4":
        raise ValueError("Input must be a local prepared .mp4 file")
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise ValueError("MP4 cannot be opened or has an unsupported codec")
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        declared_count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        width, height = (int(capture.get(prop)) for prop in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT))
        if not math.isfinite(fps) or not 0 < fps <= 240 or not math.isfinite(declared_count) or declared_count < 2 or min(width, height) <= 0:
            raise ValueError("Invalid FPS, frame count or dimensions")
        if declared_count / fps > max_duration_seconds:
            raise ValueError(f"Prepared pitch exceeds {max_duration_seconds:g} seconds; provide one pitch MP4")
        rotation = capture.get(cv2.CAP_PROP_ORIENTATION_META)
        sar_num, sar_den = capture.get(cv2.CAP_PROP_SAR_NUM), capture.get(cv2.CAP_PROP_SAR_DEN)
        if rotation != 0 or (sar_num > 0 and sar_den > 0 and abs(sar_num / sar_den - 1) > 1e-6):
            raise ValueError("Rotation metadata or non-square pixels require an externally prepared display-correct MP4")
        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc >> (8 * index)) & 255) for index in range(4)).strip("\x00")
        timestamps = []
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame.shape[:2] != (height, width):
                raise ValueError("Video frame dimensions changed during decoding")
            timestamp = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            if not math.isfinite(timestamp) or timestamp < 0:
                raise ValueError("Video presentation timestamps are unavailable")
            timestamps.append(timestamp)
            if len(timestamps) > math.ceil(max_duration_seconds * fps) + 1:
                raise ValueError("Decoded video exceeds prepared-pitch duration limit")
        if len(timestamps) != round(declared_count):
            raise ValueError("MP4 decode ended early or frame count disagrees with its header")
        if len(timestamps) < 2:
            raise ValueError("MP4 needs at least two decoded frames")
        start = timestamps[0]
        timestamps = [value - start for value in timestamps]
        # Some MP4s expose an approximate average FPS in the header even though
        # their presentation timestamps form a precise CFR timeline.
        step = (timestamps[-1] - timestamps[0]) / (len(timestamps) - 1)
        tolerance = max(2.0, step * 0.05)
        if any(right <= left or abs(right - left - step) > tolerance for left, right in zip(timestamps, timestamps[1:])):
            raise ValueError("Variable or missing frame timestamps: Phase 0 requires constant-frame-rate prepared MP4")
        if any(abs(value - index * step) > tolerance for index, value in enumerate(timestamps)):
            raise ValueError("Variable or missing frame timestamps: presentation timeline is not constant-frame-rate")
        presentation_fps = 1000 / step
        if abs(presentation_fps - fps) / presentation_fps > 0.01:
            raise ValueError("MP4 header FPS differs from its presentation timeline by more than 1%")
        if len(timestamps) / presentation_fps > max_duration_seconds:
            raise ValueError(f"Prepared pitch exceeds {max_duration_seconds:g} seconds; provide one pitch MP4")
    finally:
        capture.release()
    # OpenCV may conceal damaged frames; FFmpeg's strict decode catches bitstream errors.
    decoded = subprocess.run(
        [ffmpeg_executable(), "-nostdin", "-hide_banner", "-v", "error", "-xerror", "-err_detect", "explode", "-i", str(video), "-map", "0:v:0", "-an", "-f", "null", "-"],
        capture_output=True, timeout=120,
    )
    if decoded.returncode:
        raise ValueError("MP4 failed strict full-video decode: " + decoded.stderr.decode("utf-8", errors="replace")[-500:])
    warnings = []
    if abs(presentation_fps - fps) / presentation_fps > 0.0005:
        warnings.append("header_fps_approximate: presentation timestamps determine the reported FPS; legacy pose capture may use header FPS")
    if presentation_fps < 29:
        warnings.append("low_fps: event/release timing has coarse temporal resolution")
    if presentation_fps < 59:
        warnings.append("release timing resolution is limited by native FPS; interpolation cannot add evidence")
    report = {
        "schema_version": "video-validation-v1", "status": "validated", "path": str(video),
        "sha256": sha256_file(video), "fps": presentation_fps, "header_fps": fps, "frame_count": len(timestamps),
        "width": width, "height": height, "codec_fourcc": codec,
        "duration_seconds": len(timestamps) / presentation_fps, "timestamps_ms": timestamps, "warnings": warnings,
        "content_validation": "single pitch, continuous shot, full body and playback speed are caller declarations; visual review required",
    }
    validate_contract(report, "video-validation-v1")
    return report
