"""Deterministic, filesystem-safe names and timestamp parsing."""
from __future__ import annotations

import hashlib
import math
import re
import unicodedata


def slugify(value: str | None, *, fallback: str = "unknown") -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    return slug or fallback


def source_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def parse_timestamp(value: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS into non-negative seconds."""
    text = value.strip()
    if not text:
        raise ValueError("timestamp cannot be empty")
    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid timestamp: {value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as error:
        raise ValueError(f"invalid timestamp: {value}") from error
    if any(not math.isfinite(number) or number < 0 for number in numbers):
        raise ValueError(f"timestamp must be finite and non-negative: {value}")
    seconds = 0.0
    for number in numbers:
        seconds = seconds * 60.0 + number
    return seconds


def parse_clip_range(value: str) -> tuple[float, float]:
    if "-" not in value:
        raise ValueError("clip range must use START-END, for example 00:11-00:30")
    start_text, end_text = value.split("-", 1)
    start, end = parse_timestamp(start_text), parse_timestamp(end_text)
    if end <= start:
        raise ValueError(f"clip end must be after start: {value}")
    return start, end


def clip_filename(
    pitcher_id: str,
    season: str,
    view: str,
    source_id: str,
    pitch_number: int,
) -> str:
    if pitch_number < 1:
        raise ValueError("pitch_number must be positive")
    return (
        f"{slugify(pitcher_id, fallback='unknown_pitcher')}_"
        f"{slugify(season, fallback='unknown_season')}_"
        f"{slugify(view, fallback='unknown_view')}_"
        f"{slugify(source_id, fallback='source')}_pitch_{pitch_number:02d}.mp4"
    )
