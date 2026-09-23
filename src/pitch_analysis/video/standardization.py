"""Optional local working copy, preserving native FPS and all clip frames."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .validation import ffmpeg_executable, validate_mp4


def standardize_mp4(source: str | Path, output: str | Path, *, validated: dict | None = None) -> dict:
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    before = validated or validate_mp4(source)
    if source == output or output.exists():
        raise FileExistsError("Standardization requires a new working-copy path")
    if output.suffix.lower() != ".mp4":
        raise ValueError("Working copy must be MP4")
    if before["width"] % 2 or before["height"] % 2:
        raise ValueError("H.264 yuv420p working copies require even dimensions; use native analysis for this input")
    output.parent.mkdir(parents=True, exist_ok=True)
    encoded = subprocess.run(
        [ffmpeg_executable(), "-nostdin", "-hide_banner", "-v", "error", "-n", "-noautorotate", "-i", str(source),
         "-map", "0:v:0", "-an", "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-fps_mode", "passthrough", "-movflags", "+faststart", str(output)],
        capture_output=True, timeout=120,
    )
    if encoded.returncode:
        raise ValueError("Working-copy encoding failed: " + encoded.stderr.decode("utf-8", errors="replace")[-500:])
    after = validate_mp4(output)
    if any(after[key] != before[key] for key in ("frame_count", "width", "height")) or abs(after["fps"] - before["fps"]) > 0.01:
        raise ValueError("Working copy changed video geometry or frame timing")
    return after
