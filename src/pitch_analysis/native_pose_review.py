"""Descriptive review of cached native outputs, without quality calibration.

Coordinate availability is not correctness or human observability.  This module
does not invoke a pose estimator, confidence gate, interpolation, or tracker.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Sequence

import cv2
import numpy as np

from .native_pose import NativePoseFrame, TOPOLOGIES, validate_manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _point_available(point: dict) -> bool:
    return (point.get("coordinate_state") == "model_observed"
            and _finite(point.get("x_px")) and _finite(point.get("y_px")))


def _inside(point: dict, width: int, height: int) -> bool:
    return (_point_available(point) and 0 <= point["x_px"] < width
            and 0 <= point["y_px"] < height)


def _records(manifest: dict, frames: Sequence[NativePoseFrame]) -> list[dict]:
    validate_manifest(manifest)
    records = [frame.to_dict() for frame in frames]
    if manifest.get("topology") not in TOPOLOGIES:
        raise ValueError("Unknown native topology")
    if len(records) != manifest["video"]["frame_count"]:
        raise ValueError("Native frame count differs from manifest")
    names = tuple(TOPOLOGIES[manifest["topology"]]["names"])
    for index, record in enumerate(records):
        if (record["frame_index"] != index or record["pitch_id"] != manifest["pitch_id"]
                or record["topology"] != manifest["topology"]
                or record["backend"] != manifest["backend"]["name"]
                or record["image_size"] != manifest["image_size"]
                or record["source_video_sha256"] != manifest["video"]["sha256"]):
            raise ValueError(f"Native frame {index} does not match its manifest")
        if (len(record["landmarks"]) != len(names)
                or tuple(point["name"] for point in record["landmarks"]) != names
                or tuple(point["index"] for point in record["landmarks"]) != tuple(range(len(names)))):
            raise ValueError(f"Native frame {index} has an inconsistent topology")
        if (record["quality_status"] != "not_calibrated"
                or record["usable_for_analysis"] is not None):
            raise ValueError("Native review requires explicitly uncalibrated outputs")
        if ((index == 0 and record["timestamp_ms"] != 0)
                or (index and record["timestamp_ms"] <= records[index - 1]["timestamp_ms"])):
            raise ValueError("Native frame timestamps must preserve zero origin and increasing source order")
    return records


def _statistics(values: list[float]) -> dict:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None,
                "median": None, "p05": None, "p95": None}
    array = np.asarray(values, dtype=np.float64)
    return {"count": len(values), "min": float(array.min()), "max": float(array.max()),
            "mean": float(array.mean()), "median": float(np.median(array)),
            "p05": float(np.percentile(array, 5)), "p95": float(np.percentile(array, 95))}


def summarize_native(manifest: dict, frames: Sequence[NativePoseFrame]) -> dict:
    """Report coordinates and native fields; never convert availability to reliable."""
    records = _records(manifest, frames)
    width, height = manifest["image_size"]["width"], manifest["image_size"]["height"]
    names = tuple(TOPOLOGIES[manifest["topology"]]["names"])
    total = len(records)
    joints = {}
    for index, name in enumerate(names):
        points = [record["landmarks"][index] for record in records]
        available = sum(_point_available(point) for point in points)
        in_image = sum(_inside(point, width, height) for point in points)
        run = longest = 0
        reasons: dict[str, int] = {}
        for point in points:
            if _point_available(point):
                run = 0
            else:
                run += 1
                longest = max(longest, run)
                reason = point.get("missing_reason") or "unspecified"
                reasons[reason] = reasons.get(reason, 0) + 1
        field_stats = {}
        for field in ("native_score", "visibility", "presence", "z"):
            supported = bool(manifest["capabilities"].get(field))
            values = [float(point[field]) for point in points if _finite(point.get(field))]
            if not supported and values:
                raise ValueError(f"Unsupported {field} contains a value")
            field_stats[field] = {"supported": supported, **_statistics(values),
                                  "missing_count": total - len(values) if supported else None}
        joints[name] = {
            "index": index, "provided_by_topology": True,
            "model_observed_coordinates": available, "missing_coordinates": total - available,
            "coordinate_availability_ratio": available / total if total else None,
            "coordinates_inside_image": in_image, "coordinates_outside_image": available - in_image,
            "longest_missing_span_frames": longest, "missing_reasons": reasons,
            "interpolated_coordinates": 0, "quality_status": "not_calibrated",
            "usable_for_analysis": None, "field_statistics": field_stats,
        }
    all_names = set()
    for topology in TOPOLOGIES.values():
        all_names.update(topology["names"])
    return {
        "schema_version": "native-pose-summary-v1", "pitch_id": manifest["pitch_id"],
        "backend": manifest["backend"], "topology": manifest["topology"],
        "total_frames": total, "native_landmark_count": len(names), "joints": joints,
        "unsupported_landmarks": sorted(all_names.difference(names)),
        "unsupported_fields": sorted(name for name, enabled in manifest["capabilities"].items() if not enabled),
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "new_inference_calls": 0, "interpolated_coordinates": 0,
        "score_semantics": manifest["backend"]["score_semantics"],
        "notes": [
            "Coordinate availability describes saved model output, not keypoint correctness or human visibility.",
            "Native scores remain uncalibrated and are not passed through a quality gate.",
            "Unsupported topology landmarks are separate from missing coordinates of provided landmarks.",
        ],
    }


def draw_native_frame(image_bgr: np.ndarray, record: dict) -> np.ndarray:
    """Draw in-image native points and edges on a copy, without clipping or score gates."""
    if record["quality_status"] != "not_calibrated" or record["usable_for_analysis"] is not None:
        raise ValueError("Overlay must describe uncalibrated native output")
    height, width = image_bgr.shape[:2]
    if record["image_size"] != {"width": width, "height": height}:
        raise ValueError("Overlay image dimensions differ from native record")
    topology = TOPOLOGIES[record["topology"]]
    result = image_bgr.copy()
    points = {}
    for point in record["landmarks"]:
        if _inside(point, width, height):
            # Flooring a point already in the image preserves bounds; outside points
            # are skipped above, never clipped into an apparently observed border.
            points[point["index"]] = (math.floor(point["x_px"]), math.floor(point["y_px"]))
    for first, second in topology["connections"]:
        if first in points and second in points:
            cv2.line(result, points[first], points[second], (0, 220, 80), 2, cv2.LINE_AA)
    for location in points.values():
        cv2.circle(result, location, 3, (0, 220, 255), -1, cv2.LINE_AA)
    model_label = "cached RTMPose / COCO17" if record["topology"] == "coco_17" else "cached MediaPipe / 33 points"
    cv2.rectangle(result, (0, 0), (width - 1, min(height - 1, 52)), (0, 0, 0), -1)
    scale = min(.43, max(.20, width / 1100))
    cv2.putText(result, f"{model_label} / NOT CALIBRATED", (5, 18),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 220, 255), 1, cv2.LINE_AA)
    cv2.putText(result, f"frame {record['frame_index']} / {record['timestamp_ms']:.3f} ms",
                (5, 40), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)
    return result


def _open_video(path: Path):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise ValueError(f"Could not open video: {path}")
    return capture


def _decode_verified(video_path: Path, records: list[dict], width: int, height: int):
    capture = _open_video(video_path)
    try:
        for index, record in enumerate(records):
            ok, image = capture.read()
            if not ok:
                raise ValueError(f"Source decode ended before frame {index}")
            if image.shape != (height, width, 3):
                raise ValueError(f"Decoded image dimensions differ at frame {index}")
            if hashlib.sha256(image.tobytes()).hexdigest() != record["decoded_bgr_sha256"]:
                raise ValueError(f"Decoded source pixel SHA mismatch at frame {index}")
            native_time = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            if not math.isfinite(native_time) or round(native_time) != record["timestamp_ms"]:
                raise ValueError(f"Decoded timestamp differs from preserved source timestamp at frame {index}")
            yield image, native_time
        ok, _ = capture.read()
        if ok:
            raise ValueError("Source decode contains more frames than the native manifest")
    finally:
        capture.release()


def _inspect_overlay(path: Path, records: list[dict], width: int, height: int, fps: float) -> dict:
    capture = _open_video(path)
    try:
        actual_fps = float(capture.get(cv2.CAP_PROP_FPS))
        fourcc = int(capture.get(cv2.CAP_PROP_FOURCC))
        codec = "".join(chr((fourcc >> (8 * shift)) & 255) for shift in range(4))
        actual_count = 0
        max_time_difference = 0.0
        while True:
            ok, image = capture.read()
            if not ok:
                break
            if image.shape != (height, width, 3):
                raise ValueError("Encoded overlay dimensions differ from the source")
            if actual_count >= len(records):
                raise ValueError("Encoded overlay has extra frames")
            overlay_time = float(capture.get(cv2.CAP_PROP_POS_MSEC))
            if not math.isfinite(overlay_time) or round(overlay_time) != records[actual_count]["timestamp_ms"]:
                raise ValueError(f"Encoded overlay timestamp differs from saved source frame {actual_count}")
            max_time_difference = max(max_time_difference, abs(overlay_time - records[actual_count]["timestamp_ms"]))
            actual_count += 1
        if actual_count != len(records) or not math.isclose(actual_fps, fps, rel_tol=0, abs_tol=1e-6):
            raise ValueError("Encoded overlay frame count or FPS differs from native source")
        if codec.lower() not in ("avc1", "h264"):
            raise ValueError(f"Encoded overlay is not H.264: {codec!r}")
        return {"decoded_frame_count": actual_count, "width": width, "height": height,
                "fps": actual_fps, "codec": codec, "encoder": "libx264", "pixel_format": "yuv420p",
                "overlay_timestamps_verified_frames": actual_count,
                "max_overlay_timestamp_rounding_difference_ms": max_time_difference}
    finally:
        capture.release()


def write_native_overlay(video_path: Path, manifest: dict, frames: Sequence[NativePoseFrame], target: Path) -> dict:
    """Create one new cached COCO17 overlay, validating source pixels and timestamps.

    A temporary encode is fully decoded before a new, exclusive output is
    published.  Existing overlays and source files are never overwritten.
    """
    import imageio_ffmpeg

    video_path, target = Path(video_path), Path(target)
    if target.exists() or target.resolve() == video_path.resolve():
        raise FileExistsError(f"Native overlay target must be new: {target}")
    if manifest["topology"] != "coco_17" or "rtmpose" not in manifest["backend"]["name"].lower():
        raise ValueError("MediaPipe uses its existing overlay; only cached RTMPose overlays are generated")
    records = _records(manifest, frames)
    if not records:
        raise ValueError("An overlay requires at least one native frame")
    source_sha = _sha256(video_path)
    if source_sha != manifest["video"]["sha256"]:
        raise ValueError("Source video SHA mismatch")
    width, height = manifest["image_size"]["width"], manifest["image_size"]["height"]
    fps = float(manifest["video"]["fps"])
    if width % 2 or height % 2 or not math.isfinite(fps) or fps <= 0:
        raise ValueError("H.264 yuv420p overlay requires even image dimensions and positive finite FPS")
    capture = _open_video(video_path)
    try:
        source_fps = float(capture.get(cv2.CAP_PROP_FPS))
    finally:
        capture.release()
    if not math.isclose(source_fps, fps, rel_tol=0, abs_tol=1e-6):
        raise ValueError("Source FPS differs from native manifest")
    target.parent.mkdir(parents=True, exist_ok=True)
    max_time_difference = 0.0
    with tempfile.TemporaryDirectory(prefix="native_overlay_", dir=target.parent) as staging:
        temporary = Path(staging) / "overlay.mp4"
        command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-n",
                   "-f", "rawvideo", "-pix_fmt", "bgr24", "-s:v", f"{width}x{height}",
                   "-r", str(fps), "-i", "pipe:0", "-an", "-c:v", "libx264",
                   "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                   "-movflags", "+faststart", str(temporary)]
        with tempfile.TemporaryFile(mode="w+b") as error_stream:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=error_stream)
            try:
                for index, (image, native_time) in enumerate(_decode_verified(video_path, records, width, height)):
                    max_time_difference = max(max_time_difference, abs(native_time - records[index]["timestamp_ms"]))
                    process.stdin.write(draw_native_frame(image, records[index]).tobytes())
                process.stdin.close()
                code = process.wait()
                if code:
                    error_stream.seek(0)
                    raise ValueError(f"Native overlay encoder failed ({code}): {error_stream.read().decode('utf-8', errors='replace')}")
            except BaseException:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.poll() is None:
                    process.terminate()
                    process.wait()
                raise
        inspection = _inspect_overlay(temporary, records, width, height, fps)
        if _sha256(video_path) != source_sha:
            raise ValueError("Source video changed during overlay generation")
        with temporary.open("rb") as source, target.open("xb") as destination:
            shutil.copyfileobj(source, destination)
    return {
        "schema_version": "native-overlay-review-v1", "path": str(target.resolve()),
        "sha256": _sha256(target), "source_video_sha256": source_sha,
        "source_pixel_sha_verified_frames": len(records), "source_timestamps_verified_frames": len(records),
        "max_source_timestamp_rounding_difference_ms": max_time_difference,
        "timestamp_semantics": manifest["timebase"]["timestamp_semantics"],
        "saved_timestamps_preserved": True, "source_timestamp_shift_ms": 0,
        "quality_status": "not_calibrated", "usable_for_analysis": None,
        "topology": "coco_17", "new_inference_calls": 0, "interpolated_coordinates": 0,
        **inspection,
    }
