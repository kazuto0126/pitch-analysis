"""Create reproducible intake records and contact sheets for candidate videos.

This module deliberately does not move, rename, or delete source media.  It is
used to decide which files should become curated reference material.
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np


def _frame_at(capture: cv2.VideoCapture, frame_index: int) -> np.ndarray | None:
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    return frame if ok else None


def contact_sheet(video_path: str | Path, output_path: str | Path, samples: int = 12, start_second: float = 0.0, end_second: float | None = None) -> dict:
    """Sample a video uniformly and write a labelled visual review sheet."""
    source = Path(video_path)
    output = Path(output_path)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise OSError(f"Cannot open video: {source}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = frame_count / fps if fps > 0 else None
    first = max(0, round(start_second * fps))
    last = min(frame_count - 1, round(end_second * fps)) if end_second is not None else frame_count - 1
    if last < first:
        raise ValueError("end_second must be after start_second")
    indices = np.linspace(first, last, num=min(samples, last - first + 1), dtype=int)
    tile_width, tile_height = 320, 240
    tiles: list[np.ndarray] = []
    for index in indices:
        frame = _frame_at(capture, int(index))
        if frame is None:
            continue
        resized = cv2.resize(frame, (tile_width, tile_height), interpolation=cv2.INTER_AREA)
        seconds = index / fps if fps > 0 else 0.0
        cv2.rectangle(resized, (0, 0), (tile_width, 26), (0, 0, 0), thickness=-1)
        cv2.putText(resized, f"{seconds:05.1f}s  frame {index}", (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(resized)
    capture.release()
    if not tiles:
        raise OSError(f"No frames decoded from: {source}")
    columns = 4
    rows = (len(tiles) + columns - 1) // columns
    blank = np.zeros_like(tiles[0])
    tiles.extend([blank] * (rows * columns - len(tiles)))
    grid = np.vstack([np.hstack(tiles[row * columns:(row + 1) * columns]) for row in range(rows)])
    banner = np.full((42, grid.shape[1], 3), 28, dtype=np.uint8)
    title = f"{source.name} | {width}x{height}, {fps:.3f} fps, {duration:.1f}s" if duration is not None else source.name
    cv2.putText(banner, title, (10, 27), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), np.vstack([banner, grid])):
        raise OSError(f"Cannot write contact sheet: {output}")
    return {
        "source_path": str(source), "filename": source.name, "fps": fps,
        "frame_count": frame_count, "duration_seconds": duration,
        "sampled_range_seconds": {"start": first / fps, "end": last / fps},
        "width": width, "height": height, "contact_sheet": str(output),
        "audit_status": "needs_visual_review",
    }


def audit_videos(video_paths: list[str | Path], output_dir: str | Path, samples: int = 12, start_second: float = 0.0, end_second: float | None = None) -> dict:
    """Write contact sheets and a machine-readable review manifest."""
    output_dir = Path(output_dir)
    records = []
    for video in video_paths:
        source = Path(video)
        sheet = output_dir / f"{source.stem}_contact_sheet.jpg"
        try:
            records.append(contact_sheet(source, sheet, samples=samples, start_second=start_second, end_second=end_second))
        except OSError as exc:
            records.append({"source_path": str(source), "filename": source.name, "audit_status": "unreadable", "error": str(exc)})
    manifest = {"schema_version": "0.1", "purpose": "candidate video visual intake; source media is unmodified", "records": records}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "intake_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
