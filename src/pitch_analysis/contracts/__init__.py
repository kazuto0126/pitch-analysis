"""Versioned local contracts. Validation never retrieves remote schemas."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator


SCHEMAS = {"pitch-input-v1", "video-validation-v1", "keypoints-v1", "pitch-events-v1", "pitch-metrics-v1", "pitch-analysis-v1", "pitcher-profile-v1", "pitcher-comparison-v1"}


def validate_contract(payload: dict, schema_name: str) -> None:
    if schema_name not in SCHEMAS:
        raise ValueError(f"Unknown contract: {schema_name}")
    schema = json.loads(files(__package__).joinpath("schemas", schema_name + ".json").read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda error: str(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.path) or "$"
        raise ValueError(f"{schema_name} at {location}: {error.message}")


def load_input(video_path: str | Path, metadata_path: str | Path) -> dict:
    metadata = Path(metadata_path).resolve(strict=True)
    payload = json.loads(metadata.read_text(encoding="utf-8-sig"))
    validate_contract(payload, "pitch-input-v1")
    video = Path(video_path).resolve(strict=True)
    declared = (metadata.parent / payload["video"]["file"]).resolve(strict=True)
    if video != declared:
        raise ValueError("MP4 argument must match video.file beside the metadata file")
    return payload


def write_contract(path: str | Path, payload: dict, schema_name: str) -> None:
    validate_contract(payload, schema_name)
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
