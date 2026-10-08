"""Validate the public version 2 handoff without inferring missing context."""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from fractions import Fraction
from pathlib import PurePosixPath


CONTRACT_VERSION = 2
VIEW = "rear_centerfield_broadcast"
CHECK_NAMES = (
    "single_motion_event", "pitch_delivery_visible", "continuous_shot",
    "view_rear_centerfield", "normal_speed_export", "not_replay_or_slow_motion",
    "not_mirrored", "full_body_in_frame", "pitcher_identity",
)
LOCAL_REVIEWS = ("preparation_complete", "follow_through_complete")


class HandoffError(ValueError):
    """A refusal with a stable machine-readable reason and optional evidence."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details


def _object(value, field: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise HandoffError("invalid_contract", f"{field} must be an object", {"field": field})
    return value


def _required(value: Mapping, fields, label: str) -> None:
    missing = [field for field in fields if field not in value]
    if missing:
        raise HandoffError("missing_fields", f"{label} is missing required fields", {"object": label, "fields": missing})


def _text(value, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HandoffError("invalid_contract", f"{field} must be a nonempty string", {"field": field})
    return value


def _integer(value, field: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise HandoffError("invalid_contract", f"{field} must be an integer >= {minimum}", {"field": field})
    return value


def _number(value, field: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HandoffError("invalid_contract", f"{field} must be a finite number", {"field": field})
    try:
        finite = math.isfinite(value)
    except (OverflowError, TypeError, ValueError):
        finite = False
    if not finite or (minimum is not None and value < minimum):
        raise HandoffError("invalid_contract", f"{field} must be a finite number >= {minimum}", {"field": field})
    return float(value)


def _version(value: Mapping, label: str) -> None:
    _required(value, ("contract_version",), label)
    version = value["contract_version"]
    if isinstance(version, bool) or not isinstance(version, int) or version != CONTRACT_VERSION:
        raise HandoffError("unsupported_contract_version", f"{label} has an unsupported contract_version", {"object": label, "contract_version": version})


def _throws(value, field: str) -> None:
    if not isinstance(value, str) or value not in ("R", "L", "unknown"):
        raise HandoffError("invalid_contract", f"{field} must be R, L, or unknown", {"field": field})


def _view(value, field: str) -> None:
    if value != VIEW:
        raise HandoffError("unsupported_view", f"{field} must be {VIEW}", {"field": field})


def _filename(value, expected: str, field: str) -> None:
    path = _text(value, field)
    if PurePosixPath(path.replace("\\", "/")).name != expected:
        raise HandoffError("filename_mismatch", f"{field} must name {expected}", {"field": field, "expected": expected, "actual": path})


def _pitch_id(value, batch_id: str) -> str:
    pitch_id = _text(value, "pitch_id")
    prefix = _text(batch_id, "batch_id") + "_p"
    suffix = pitch_id.removeprefix(prefix)
    if not pitch_id.startswith(prefix) or not re.fullmatch(r"[0-9]{2,}", suffix) or not suffix.lstrip("0"):
        raise HandoffError("pitch_id_mismatch", "pitch_id must be <batch_id>_pNN", {"pitch_id": pitch_id})
    return pitch_id


def _source(value, label: str, *, pitch: bool) -> Mapping:
    source = _object(value, label)
    _required(source, ("video_id", "title", "url", "channel", "source_type"), label)
    for field in ("video_id", "title", "url", "channel", "source_type"):
        _text(source[field], f"{label}.{field}")
    if pitch:
        _required(source, ("start_sec", "end_sec"), label)
        start = _number(source["start_sec"], f"{label}.start_sec", minimum=0)
        end = _number(source["end_sec"], f"{label}.end_sec", minimum=0)
        if end <= start:
            raise HandoffError("invalid_contract", f"{label}.end_sec must follow start_sec")
    return source


def _game(value, label: str) -> Mapping:
    game = _object(value, label)
    _required(game, ("season", "season_confidence", "team", "opponent", "game_id", "pitch_type"), label)
    season = game["season"]
    try:
        valid_season = (isinstance(season, int) and not isinstance(season, bool) and season > 0) or (isinstance(season, str) and (season == "unknown" or (re.fullmatch(r"[0-9]+", season) is not None and int(season) > 0)))
    except (ValueError, OverflowError):
        valid_season = False
    if not valid_season:
        raise HandoffError("invalid_contract", f"{label}.season must be a positive year or unknown")
    confidence = _text(game["season_confidence"], f"{label}.season_confidence")
    if confidence not in ("high", "medium", "low", "unknown"):
        raise HandoffError("invalid_contract", f"{label}.season_confidence is unsupported")
    if season != "unknown" and confidence not in ("high", "medium"):
        raise HandoffError("invalid_contract", f"{label}.season requires high or medium confidence")
    for field in ("team", "opponent", "game_id", "pitch_type"):
        _text(game[field], f"{label}.{field}")
    return game


def validate_video_metadata(value) -> Fraction:
    """Return the exact declared FPS after validating required video facts."""
    video = _object(value, "video")
    _required(video, ("fps", "fps_float", "constant_frame_rate", "frame_count", "duration_sec", "width", "height", "codec", "pix_fmt", "square_pixels", "container_start_time_sec", "frame_time_rule", "has_audio"), "video")
    fps_string = _text(video["fps"], "video.fps")
    try:
        fps = Fraction(fps_string)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise HandoffError("invalid_fps", "video.fps must be a positive fraction string") from exc
    if fps <= 0:
        raise HandoffError("invalid_fps", "video.fps must be a positive fraction string")
    fps_float = _number(video["fps_float"], "video.fps_float", minimum=0)
    if fps_float <= 0:
        raise HandoffError("invalid_fps", "video.fps_float must be positive")
    if video["constant_frame_rate"] is not True:
        raise HandoffError("not_constant_frame_rate", "video.constant_frame_rate must be true")
    _integer(video["frame_count"], "video.frame_count")
    duration = _number(video["duration_sec"], "video.duration_sec", minimum=0)
    if not 0 < duration <= 30 or Fraction(video["frame_count"], 1) / fps > 30:
        raise HandoffError("invalid_duration", "A handoff pitch must have duration > 0 and <= 30 seconds")
    _integer(video["width"], "video.width")
    _integer(video["height"], "video.height")
    if video["width"] > 1280 or video["height"] > 720:
        raise HandoffError("unsupported_dimensions", "Handoff video exceeds 720p dimensions")
    if video["codec"] != "h264" or video["pix_fmt"] != "yuv420p":
        raise HandoffError("unsupported_video_format", "Handoff video must use h264 and yuv420p")
    if video["square_pixels"] is not True:
        raise HandoffError("unsupported_video_format", "Handoff video must have square pixels")
    _number(video["container_start_time_sec"], "video.container_start_time_sec")
    _text(video["frame_time_rule"], "video.frame_time_rule")
    if not isinstance(video["has_audio"], bool):
        raise HandoffError("invalid_contract", "video.has_audio must be boolean")
    return fps


def validate_index(row) -> None:
    row = _object(row, "index")
    _version(row, "index")
    _required(row, ("batch_id", "pitcher_name", "pitch_count", "batch_json", "created_utc"), "index")
    for field in ("batch_id", "pitcher_name", "created_utc"):
        _text(row[field], f"index.{field}")
    _integer(row["pitch_count"], "index.pitch_count", minimum=3)
    _filename(row["batch_json"], "batch.json", "index.batch_json")


def validate_batch(batch, index) -> None:
    validate_index(index)
    batch = _object(batch, "batch")
    _version(batch, "batch")
    _required(batch, ("batch_id", "created_utc", "pitcher_name", "throws", "view", "pitch_count", "pitches", "source", "game", "viewing_video", "excluded_by_operator", "quality_warning", "warnings"), "batch")
    for field in ("batch_id", "created_utc", "pitcher_name"):
        _text(batch[field], f"batch.{field}")
        if batch[field] != index[field]:
            raise HandoffError("batch_index_mismatch", f"batch.{field} does not match index", {"field": field})
    _throws(batch["throws"], "batch.throws")
    _view(batch["view"], "batch.view")
    count = _integer(batch["pitch_count"], "batch.pitch_count", minimum=3)
    pitches = batch["pitches"]
    if not isinstance(pitches, list) or len(pitches) != count or count != index["pitch_count"]:
        raise HandoffError("pitch_count_mismatch", "batch pitch_count must match index and pitches length")
    seen = set()
    for position, value in enumerate(pitches):
        item = _object(value, f"batch.pitches[{position}]")
        _required(item, ("pitch_id", "video_file", "json"), f"batch.pitches[{position}]")
        pitch_id = _pitch_id(item["pitch_id"], batch["batch_id"])
        if pitch_id in seen:
            raise HandoffError("duplicate_pitch_id", "pitch_ids must be unique within a batch", {"pitch_id": pitch_id})
        seen.add(pitch_id)
        _filename(item["video_file"], pitch_id + ".mp4", "video_file")
        _filename(item["json"], pitch_id + ".json", "json")
    _source(batch["source"], "batch.source", pitch=False)
    _game(batch["game"], "batch.game")
    if batch["viewing_video"] is not None:
        _text(batch["viewing_video"], "batch.viewing_video")
    if not isinstance(batch["excluded_by_operator"], list) or not all(isinstance(item, Mapping) for item in batch["excluded_by_operator"]):
        raise HandoffError("invalid_contract", "batch.excluded_by_operator must be a list of objects")
    if not isinstance(batch["quality_warning"], (str, bool)) and batch["quality_warning"] is not None:
        raise HandoffError("invalid_contract", "batch.quality_warning must be a string, boolean, or null")
    if not isinstance(batch["warnings"], list) or not all(isinstance(item, str) for item in batch["warnings"]):
        raise HandoffError("invalid_contract", "batch.warnings must be a list of strings")


def validate_pitch(payload, batch, item) -> dict:
    """Map validated upstream facts; retain the original JSON separately."""
    payload = _object(payload, "pitch")
    batch = _object(batch, "batch")
    item = _object(item, "item")
    _version(payload, "pitch")
    _version(batch, "batch")
    _required(payload, ("pitch_id", "batch_id", "index", "pitcher_name", "throws", "view", "video_file", "sha256", "video", "source", "game", "pipeline_anchors_sec", "checks", "requires_human_review"), "pitch")
    _required(batch, ("batch_id", "pitcher_name", "throws", "view", "source", "game"), "batch")
    _required(item, ("pitch_id", "video_file", "json"), "item")
    for field in ("batch_id", "pitcher_name", "throws", "view"):
        if payload[field] != batch[field]:
            raise HandoffError("pitch_batch_mismatch", f"pitch.{field} does not match batch", {"field": field})
    _text(payload["pitcher_name"], "pitch.pitcher_name")
    _throws(payload["throws"], "pitch.throws")
    _view(payload["view"], "pitch.view")
    pitch_id = _pitch_id(payload["pitch_id"], payload["batch_id"])
    if pitch_id != item["pitch_id"] or payload["video_file"] != item["video_file"]:
        raise HandoffError("pitch_item_mismatch", "pitch_id and video_file must match batch item")
    _filename(payload["video_file"], pitch_id + ".mp4", "pitch.video_file")
    _filename(item["json"], pitch_id + ".json", "item.json")
    _integer(payload["index"], "pitch.index", minimum=0)
    if not isinstance(payload["sha256"], str) or not re.fullmatch(r"[a-fA-F0-9]{64}", payload["sha256"]):
        raise HandoffError("invalid_sha256", "pitch.sha256 must contain 64 hexadecimal characters")
    validate_video_metadata(payload["video"])
    source = _source(payload["source"], "pitch.source", pitch=True)
    batch_source = _source(batch["source"], "batch.source", pitch=False)
    for field in ("video_id", "title", "url", "channel", "source_type"):
        if source[field] != batch_source[field]:
            raise HandoffError("pitch_batch_mismatch", f"pitch.source.{field} does not match batch", {"field": f"source.{field}"})
    game = _game(payload["game"], "pitch.game")
    batch_game = _game(batch["game"], "batch.game")
    for field in ("season", "season_confidence", "team", "opponent", "game_id", "pitch_type"):
        if game[field] != batch_game[field]:
            raise HandoffError("pitch_batch_mismatch", f"pitch.game.{field} does not match batch", {"field": f"game.{field}"})
    anchors = _object(payload["pipeline_anchors_sec"], "pitch.pipeline_anchors_sec")
    _required(anchors, ("motion_onset", "motion_peak", "settle"), "pitch.pipeline_anchors_sec")
    anchor_values = [_number(anchors[name], f"pipeline_anchors_sec.{name}", minimum=0) for name in ("motion_onset", "motion_peak", "settle")]
    if anchor_values != sorted(anchor_values) or anchor_values[-1] > payload["video"]["duration_sec"]:
        raise HandoffError("invalid_contract", "Pipeline anchors must be chronological and within the pitch")
    checks = _object(payload["checks"], "pitch.checks")
    _required(checks, CHECK_NAMES, "pitch.checks")
    reviews = []
    for name, value in checks.items():
        _text(name, "checks name")
        check = _object(value, f"checks.{name}")
        _required(check, ("status", "how"), f"checks.{name}")
        if check["status"] not in ("verified_by_pipeline", "not_verified"):
            raise HandoffError("invalid_checks", f"checks.{name}.status is unsupported")
        _text(check["how"], f"checks.{name}.how")
        if check["status"] == "not_verified":
            reviews.append(name)
    declared = payload["requires_human_review"]
    if not isinstance(declared, list) or not all(isinstance(name, str) for name in declared) or len(declared) != len(set(declared)) or set(declared) != set(reviews):
        raise HandoffError("review_list_mismatch", "requires_human_review must list every not_verified check exactly once")
    required_reviews = list(declared)
    required_reviews.extend(name for name in LOCAL_REVIEWS if name not in required_reviews)
    context = {name: None if value == "unknown" else value for name, value in game.items()}
    if isinstance(context["season"], str) and context["season"].isdigit():
        context["season"] = int(context["season"])
    return {
        "pitcher_name": payload["pitcher_name"],
        "throws": {"R": "RIGHT", "L": "LEFT", "unknown": None}[payload["throws"]],
        "context": context,
        "required_reviews": required_reviews,
        "source_identity": {**dict(source), "batch_id": payload["batch_id"], "pitch_id": pitch_id, "index": payload["index"]},
    }
