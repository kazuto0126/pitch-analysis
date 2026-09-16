from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Mapping


def _as_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() in {"1", "true", "yes"}


def read_pose_csv(path: str | Path) -> dict[int, dict[str, dict[str, float | bool]]]:
    """Load either legacy named pose CSV or a raw pose CSV into frame-indexed data."""
    frames: dict[int, dict[str, dict[str, float | bool]]] = defaultdict(dict)
    with Path(path).open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            landmark = row["landmark"]
            frames[int(row["frame"])][landmark] = {
                key: float(row[key]) for key in ("x", "y", "z", "visibility", "presence") if row.get(key, "") != ""
            }
            for key in ("usable", "source_frame_detected", "quality_valid", "interpolated"):
                value = _as_bool(row.get(key))
                if value is not None:
                    frames[int(row["frame"])][landmark][key] = value
    return dict(frames)


def load_pose_context(path: str | Path) -> dict:
    """Load the sidecar that defines a pose table's capture timeline and geometry.

    Raw captures write ``.capture.json`` and cleaned pose tables write
    ``.clean.json``.  Legacy CSVs intentionally return an empty context so they
    remain readable, but callers can then report that their geometry contract is
    inferred rather than verified.
    """
    pose_path = Path(path)
    candidates = (pose_path.with_suffix(".clean.json"), pose_path.with_suffix(".capture.json"))
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload["_context_path"] = str(candidate)
            return payload
    return {}


def timeline_bounds(frames: Mapping[int, object], context: Mapping | None = None) -> tuple[int, int]:
    """Return the declared capture bounds, falling back to observed CSV frames."""
    context = context or {}
    start = context.get("timeline_start_frame", context.get("start_frame"))
    end = context.get("timeline_end_frame", context.get("end_frame"))
    if start is not None and end is not None:
        start, end = int(start), int(end)
        if end < start:
            raise ValueError("pose context has an invalid frame range")
        return start, end
    if not frames:
        raise ValueError("pose CSV contains no detected landmarks and no capture timeline")
    return min(frames), max(frames)


def coordinate_x_scale(context: Mapping | None = None) -> float:
    """Return a height-normalized x scale for image-plane geometry.

    MediaPipe x is normalized by image width while y is normalized by height.
    Multiplying x by width / height makes both axes share the same unit before
    calculating angles or lateral distance.
    """
    context = context or {}
    explicit = context.get("coordinate_x_scale")
    if explicit is not None:
        try:
            scale = float(explicit)
            if scale > 0:
                return scale
        except (TypeError, ValueError):
            pass
    try:
        width, height = float(context["width"]), float(context["height"])
        if width > 0 and height > 0:
            return width / height
    except (KeyError, TypeError, ValueError):
        pass
    return 1.0


def write_rows(path: str | Path, fieldnames: Iterable[str], rows: Iterable[dict]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as sink:
        writer = csv.DictWriter(sink, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
