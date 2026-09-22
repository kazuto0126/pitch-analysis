"""FFmpeg-backed MP4 standardization and exact clip extraction."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .probe import probe_video, resolve_ffmpeg, sha256_file


def _encode_command(
    ffmpeg: str,
    source: Path,
    output: Path,
    *,
    start: float | None = None,
    duration: float | None = None,
    target_fps: float | None = None,
) -> list[str]:
    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-n"]
    if start is not None:
        command.extend(["-ss", f"{start:.6f}"])
    command.extend(["-i", str(source)])
    if duration is not None:
        command.extend(["-t", f"{duration:.6f}"])
    command.extend(["-map", "0:v:0", "-map", "0:a?"])
    if target_fps is not None:
        command.extend(["-vf", f"fps={target_fps:g}"])
    command.extend(
        [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output),
        ]
    )
    return command


def _run_encode(
    command: list[str],
    temporary: Path,
    final: Path,
    *,
    expected_duration: float,
    duration_tolerance: float,
) -> dict:
    if final.exists():
        raise FileExistsError(f"Refusing to overwrite media output: {final}")
    if temporary.exists():
        raise FileExistsError(f"Temporary media output already exists: {temporary}")
    temporary.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=1800,
            check=False,
        )
        if result.returncode != 0:
            message = result.stderr.strip().splitlines()[-1:] or ["unknown FFmpeg error"]
            raise RuntimeError(f"FFmpeg failed: {message[0]}")
        output_probe = probe_video(temporary)
        if abs(output_probe["duration_seconds"] - expected_duration) > duration_tolerance:
            raise RuntimeError(
                "Encoded video duration differs unexpectedly from requested duration"
            )
        temporary.replace(final)
        return {**output_probe, "path": str(final)}
    except Exception:
        if temporary.exists():
            temporary.unlink()
        raise


def standardize_video(
    source: str | Path,
    output: str | Path,
    *,
    target_fps: float = 30.0,
    ffmpeg: str | Path | None = None,
) -> dict:
    if target_fps <= 0:
        raise ValueError("target_fps must be positive")
    source_path, output_path = Path(source), Path(output)
    executable = resolve_ffmpeg(ffmpeg)
    before = probe_video(source_path)
    temporary = output_path.with_name(output_path.stem + ".tmp.mp4")
    command = _encode_command(
        executable,
        source_path,
        temporary,
        target_fps=target_fps,
    )
    after = _run_encode(
        command,
        temporary,
        output_path,
        expected_duration=before["duration_seconds"],
        duration_tolerance=max(0.5, 2.0 / target_fps),
    )
    return {
        "path": str(output_path),
        "sha256": sha256_file(output_path),
        "ffmpeg": executable,
        "video_codec": "h264",
        "pixel_format": "yuv420p",
        "audio_codec": "aac_if_present",
        "target_fps": target_fps,
        "source_probe": before,
        "output_probe": after,
    }


def extract_clip(
    source: str | Path,
    output: str | Path,
    *,
    start_second: float,
    end_second: float,
    ffmpeg: str | Path | None = None,
) -> dict:
    if start_second < 0 or end_second <= start_second:
        raise ValueError("clip boundaries must satisfy 0 <= start < end")
    source_path, output_path = Path(source), Path(output)
    source_probe = probe_video(source_path)
    if end_second > source_probe["duration_seconds"] + max(0.1, 1 / source_probe["fps"]):
        raise ValueError(
            f"clip end {end_second:.3f}s exceeds video duration "
            f"{source_probe['duration_seconds']:.3f}s"
        )
    executable = resolve_ffmpeg(ffmpeg)
    temporary = output_path.with_name(output_path.stem + ".tmp.mp4")
    command = _encode_command(
        executable,
        source_path,
        temporary,
        start=start_second,
        duration=end_second - start_second,
    )
    output_probe = _run_encode(
        command,
        temporary,
        output_path,
        expected_duration=end_second - start_second,
        duration_tolerance=max(0.25, 2.0 / source_probe["fps"]),
    )
    return {
        "path": str(output_path),
        "sha256": sha256_file(output_path),
        "start_second": start_second,
        "end_second": end_second,
        "duration_seconds": end_second - start_second,
        "output_probe": output_probe,
        "review_status": "needs_human_review",
    }
