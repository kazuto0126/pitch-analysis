"""Small video probing and FFmpeg discovery helpers."""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import cv2


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def probe_video(path: str | Path) -> dict:
    source = Path(path)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise OSError(f"Cannot open video: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    capture.release()
    if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
        raise OSError(f"Video metadata is incomplete: {source}")
    return {
        "path": str(source),
        "fps": fps,
        "frame_count": frame_count,
        "duration_seconds": frame_count / fps,
        "width": width,
        "height": height,
    }


def resolve_ffmpeg(explicit: str | Path | None = None) -> str:
    if explicit:
        explicit_text = str(explicit)
        candidate = Path(explicit_text)
        if candidate.exists():
            return str(candidate.resolve())
        discovered = shutil.which(explicit_text)
        if discovered:
            return discovered
        raise FileNotFoundError(f"FFmpeg executable not found: {explicit}")
    try:
        import imageio_ffmpeg

        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and Path(bundled).exists():
            return str(Path(bundled).resolve())
    except (ImportError, RuntimeError, OSError):
        pass
    discovered = shutil.which("ffmpeg")
    if discovered:
        return discovered
    raise FileNotFoundError(
        "FFmpeg is required. Install imageio-ffmpeg or provide --ffmpeg PATH."
    )
