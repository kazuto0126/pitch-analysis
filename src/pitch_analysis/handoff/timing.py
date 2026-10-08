"""Inspect every decoded frame and validate exact fractional-FPS presentation time."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

from .contract import HandoffError, validate_video_metadata


def _pts_fraction(value, index: int) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Fraction)):
        raise HandoffError("invalid_pts", "Every frame needs a finite presentation timestamp", {"frame_index": index})
    try:
        parsed = value if isinstance(value, Fraction) else Fraction(str(value))
        if not math.isfinite(float(parsed)):
            raise ValueError("Timestamp cannot be represented as a finite number")
        return parsed
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise HandoffError("invalid_pts", "Every frame needs a finite presentation timestamp", {"frame_index": index}) from exc


def validate_timeline(pts_ms, decoded_count: int, video_metadata) -> dict:
    """Require abs((PTS-first PTS)-frame/fractional FPS) < 1 ms for every frame.

    Native timestamps are checked with exact rational arithmetic. The separate
    contract timestamps deliberately use fps_float and never container start time.
    """
    fps = validate_video_metadata(video_metadata)
    if isinstance(decoded_count, bool) or not isinstance(decoded_count, int) or decoded_count < 1:
        raise HandoffError("invalid_frame_count", "Decoded frame count must be a positive integer")
    if decoded_count != video_metadata["frame_count"]:
        raise HandoffError("frame_count_mismatch", "Actual decoded frame count does not match metadata", {"decoded_frame_count": decoded_count, "metadata_frame_count": video_metadata["frame_count"]})
    if not isinstance(pts_ms, (list, tuple)) or len(pts_ms) != decoded_count:
        raise HandoffError("pts_count_mismatch", "Presentation timestamp count does not match actual decoded frame count", {"decoded_frame_count": decoded_count, "pts_count": len(pts_ms) if isinstance(pts_ms, (list, tuple)) else None})
    native = [_pts_fraction(value, index) for index, value in enumerate(pts_ms)]
    if any(right <= left for left, right in zip(native, native[1:])):
        raise HandoffError("nonmonotonic_pts", "Native presentation timestamps must strictly increase")
    normalized = [value - native[0] for value in native]
    expected = [Fraction(index * 1000, 1) / fps for index in range(decoded_count)]
    deviations = [actual - target for actual, target in zip(normalized, expected)]
    evidence = {
        "frame_count": decoded_count,
        "fps": float(video_metadata["fps_float"]),
        "fractional_fps": video_metadata["fps"],
        "timestamps_ms": [index * 1000.0 / video_metadata["fps_float"] for index in range(decoded_count)],
        "native_pts_ms": [float(value) for value in native],
        "normalized_pts_ms": [float(value) for value in normalized],
        "expected_fractional_timestamps_ms": [float(value) for value in expected],
        "deviations_ms": [float(value) for value in deviations],
        "max_abs_deviation_ms": float(max(abs(value) for value in deviations)),
        "container_start_time_sec": video_metadata["container_start_time_sec"],
        "container_start_time_applied": False,
        "tolerance_ms": 1.0,
        "tolerance_rule": "absolute deviation strictly less than 1 ms for every frame",
        "timestamp_origin": "native first frame PTS",
        "contract_frame_time_rule": video_metadata["frame_time_rule"],
    }
    if any(abs(value) >= 1 for value in deviations):
        evidence["failing_frame_indices"] = [index for index, value in enumerate(deviations) if abs(value) >= 1]
        raise HandoffError("pts_tolerance_exceeded", "Every normalized native PTS must differ from frame_index / fractional_fps by strictly less than 1 ms", evidence)
    return evidence


def ffprobe_executable(ffprobe_path: str | Path | None = None) -> str:
    """Find an existing configured ffprobe; do not install or download tools."""
    configured = ffprobe_path or os.environ.get("FFPROBE_PATH") or os.environ.get("FFPROBE_BINARY")
    if configured:
        located = shutil.which(str(configured))
        candidate = Path(str(configured)).expanduser()
        if located:
            return located
        if candidate.is_file():
            return str(candidate.resolve())
        raise HandoffError("ffprobe_unavailable", "Configured ffprobe executable was not found", {"configured_path": str(configured)})
    located = shutil.which("ffprobe")
    if located:
        return located
    # imageio-ffmpeg is an existing project dependency. A user-installed FFmpeg
    # directory may also contain ffprobe; bundled imageio builds often do not.
    try:
        import imageio_ffmpeg
        sibling = Path(imageio_ffmpeg.get_ffmpeg_exe()).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if sibling.is_file():
            return str(sibling)
    except (ImportError, OSError, RuntimeError):
        pass
    raise HandoffError("ffprobe_unavailable", "Native per-frame PTS validation requires an existing ffprobe executable")


def _probe(video: Path, executable: str) -> dict:
    try:
        result = subprocess.run(
            [executable, "-v", "error", "-select_streams", "v:0", "-show_frames", "-show_streams", "-show_format",
             "-show_entries", "frame=best_effort_timestamp_time,width,height:stream=codec_name,pix_fmt,width,height,sample_aspect_ratio:format=start_time",
             "-of", "json", str(video)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HandoffError("ffprobe_failed", "Native presentation timestamps could not be read", {"error": str(exc)}) from exc
    if result.returncode or result.stderr.strip():
        raise HandoffError("ffprobe_failed", "Native PTS probe reported a video decoding error", {"returncode": result.returncode, "stderr": result.stderr[-1000:]})
    try:
        payload = json.loads(result.stdout)
    except (ValueError, TypeError) as exc:
        raise HandoffError("ffprobe_failed", "ffprobe did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise HandoffError("ffprobe_failed", "ffprobe output must be an object")
    return payload


def verify_timing(video_path: str | Path, video_metadata, *, ffprobe_path: str | Path | None = None) -> dict:
    """Fully decode the local file and check its native PTS against metadata."""
    import cv2

    validate_video_metadata(video_metadata)
    try:
        video = Path(video_path).resolve(strict=True)
    except (OSError, ValueError) as exc:
        raise HandoffError("video_unavailable", "Handoff MP4 could not be read", {"path": str(video_path)}) from exc
    if not video.is_file() or video.suffix.lower() != ".mp4":
        raise HandoffError("invalid_video_path", "Handoff input must be an existing MP4 file")
    capture = cv2.VideoCapture(str(video))
    decoded_count = 0
    opencv_timestamps = []
    try:
        if not capture.isOpened():
            raise HandoffError("decode_failed", "Handoff MP4 could not be decoded")
        while True:
            okay, frame = capture.read()
            if not okay:
                break
            if frame is None or frame.shape[:2] != (video_metadata["height"], video_metadata["width"]):
                raise HandoffError("dimensions_mismatch", "Decoded frame dimensions disagree with metadata or change during decoding", {"frame_index": decoded_count})
            timestamp = capture.get(cv2.CAP_PROP_POS_MSEC)
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                raise HandoffError("invalid_decoder_timestamp", "Decoder did not provide a finite frame timestamp", {"frame_index": decoded_count})
            opencv_timestamps.append(float(timestamp))
            decoded_count += 1
    except cv2.error as exc:
        raise HandoffError("decode_failed", "Handoff MP4 failed full decoding", {"error": str(exc), "decoded_frame_count": decoded_count}) from exc
    finally:
        capture.release()
    if decoded_count != video_metadata["frame_count"]:
        raise HandoffError("frame_count_mismatch", "Actual decoded frame count does not match metadata", {"decoded_frame_count": decoded_count, "metadata_frame_count": video_metadata["frame_count"]})
    executable = ffprobe_executable(ffprobe_path)
    probed = _probe(video, executable)
    frames = probed.get("frames")
    if not isinstance(frames, list):
        raise HandoffError("invalid_pts", "ffprobe did not return per-frame presentation timestamps")
    native_pts = []
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict) or "best_effort_timestamp_time" not in frame:
            raise HandoffError("invalid_pts", "A decoded frame has no native presentation timestamp", {"frame_index": index})
        if frame.get("width") != video_metadata["width"] or frame.get("height") != video_metadata["height"]:
            raise HandoffError("dimensions_mismatch", "Native frame dimensions disagree with metadata or change during decoding", {"frame_index": index})
        native_pts.append(_pts_fraction(frame["best_effort_timestamp_time"], index) * 1000)
    report = validate_timeline(native_pts, decoded_count, video_metadata)
    streams = probed.get("streams")
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
        raise HandoffError("ffprobe_failed", "ffprobe did not identify the selected video stream")
    stream = streams[0]
    if any(stream.get(name) != video_metadata[name] for name in ("width", "height", "pix_fmt")) or stream.get("codec_name") != video_metadata["codec"]:
        raise HandoffError("video_metadata_mismatch", "Native video dimensions, codec, or pixel format disagree with metadata")
    # An absent aspect-ratio tag has the decoder's default square-pixel meaning.
    if stream.get("sample_aspect_ratio") not in (None, "N/A", "0:1", "1:1"):
        raise HandoffError("unsupported_video_format", "Native video must use square pixels")
    report.update({
        "width": video_metadata["width"], "height": video_metadata["height"],
        "opencv_timestamps_ms": opencv_timestamps,
        "pts_source": "ffprobe.best_effort_timestamp_time",
        "ffprobe_path": executable,
        "native_video_stream": stream,
        "probed_container_start_time_sec": probed.get("format", {}).get("start_time") if isinstance(probed.get("format"), dict) else None,
    })
    return report
