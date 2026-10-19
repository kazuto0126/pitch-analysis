"""Run one explicitly confirmed pitcher-region pilot in a fresh output directory.

The region selects among full-image model candidates; this runner does not crop
the model input, alter predictions, create annotations, or choose quality gates.
Every configured source is checked before any output is created or model runs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re

from pitch_analysis.analysis.pitch import analyze_pitch
from pitch_analysis.contracts import load_input
from pitch_analysis.video.validation import sha256_file


REGION_SEMANTICS = "all_four_torso_landmarks_inside_original_image_roi"
ID_PATTERN = re.compile(r"[a-z0-9][a-z0-9_]{0,79}")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")
EXECUTION_TYPE = "explicit_operator_region_pilot"


def _nonempty_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _identifier(value: object, field: str) -> str:
    if not isinstance(value, str) or not ID_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be a safe pitch-input-v1 identifier")
    return value


def _region(value: object, pitch_id: str) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError(f"{pitch_id}: subject_roi must contain xmin, ymin, xmax, ymax")
    if any(isinstance(number, bool) or not isinstance(number, (int, float))
           or not 0 <= number <= 1 or not math.isfinite(number) for number in value):
        raise ValueError(f"{pitch_id}: subject_roi must contain finite numbers in [0, 1], not booleans")
    xmin, ymin, xmax, ymax = (float(number) for number in value)
    if not xmin < xmax or not ymin < ymax:
        raise ValueError(f"{pitch_id}: subject_roi requires xmin < xmax and ymin < ymax")
    return xmin, ymin, xmax, ymax


def _config(path: Path) -> tuple[dict, bytes, list[tuple[str, tuple[float, float, float, float]]]]:
    content = path.read_bytes()
    payload = json.loads(content.decode("utf-8-sig"))
    if not isinstance(payload, dict) or payload.get("schema_version") != "pitcher-region-pilot-v1":
        raise ValueError("Expected a pitcher-region-pilot-v1 configuration")
    if not isinstance(payload.get("status"), str) or payload["status"] not in {"proposed", "operator_confirmed"}:
        raise ValueError("Configuration status must be proposed or operator_confirmed")
    if payload["status"] != "operator_confirmed":
        raise ValueError("Operator confirmation is required before any analysis: configuration is proposed")
    confirmation = payload.get("operator_confirmation")
    if not isinstance(confirmation, dict):
        raise ValueError("operator_confirmation must record reviewer, reviewed_at_utc, and note")
    _nonempty_text(confirmation.get("reviewer"), "operator_confirmation.reviewer")
    _nonempty_text(confirmation.get("note"), "operator_confirmation.note")
    reviewed_at = _nonempty_text(confirmation.get("reviewed_at_utc"), "operator_confirmation.reviewed_at_utc")
    try:
        reviewed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("operator_confirmation.reviewed_at_utc must be a timezone-aware datetime") from error
    if reviewed.tzinfo is None or reviewed.utcoffset() is None:
        raise ValueError("operator_confirmation.reviewed_at_utc must include a timezone")
    _identifier(payload.get("pitcher_id"), "pitcher_id")
    if payload.get("region_semantics") != REGION_SEMANTICS:
        raise ValueError(f"region_semantics must be {REGION_SEMANTICS}")
    clips = payload.get("clips")
    if not isinstance(clips, list) or not 3 <= len(clips) <= 5:
        raise ValueError("The pilot requires 3–5 configured clips")
    checked, seen = [], set()
    for item in clips:
        if not isinstance(item, dict):
            raise ValueError("Every configured clip must be an object")
        pitch_id = _identifier(item.get("pitch_id"), "clips.pitch_id")
        if pitch_id in seen:
            raise ValueError(f"Duplicate configured pitch_id: {pitch_id}")
        seen.add(pitch_id)
        digest = item.get("video_sha256")
        if not isinstance(digest, str) or not SHA_PATTERN.fullmatch(digest):
            raise ValueError(f"{pitch_id}: video_sha256 must be a lowercase SHA-256 digest")
        checked.append((pitch_id, _region(item.get("subject_roi"), pitch_id)))
    return payload, content, checked


def _durable_json(path: Path, payload: dict) -> None:
    """Update only this run's own summary atomically after each attempted clip."""
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def run_pilot(input_dir: str | Path, config_json: str | Path, output_root: str | Path, *,
              model_path: str | Path = "models/pose_landmarker_full.task") -> Path:
    config_path = Path(config_json).resolve(strict=True)
    config, config_bytes, regions = _config(config_path)
    # Validate the entire batch before resolving the model or creating output.
    source_root = Path(input_dir).resolve(strict=True)
    if not source_root.is_dir():
        raise ValueError("input_dir must be a directory")
    sources = []
    for item, (pitch_id, region) in zip(config["clips"], regions, strict=True):
        video = source_root / f"{pitch_id}.mp4"
        metadata = source_root / f"{pitch_id}.json"
        payload = load_input(video, metadata)
        if payload["pitch_id"] != pitch_id:
            raise ValueError(f"{pitch_id}: metadata pitch_id does not match the configured clip")
        if payload["pitcher"]["id"] != config["pitcher_id"]:
            raise ValueError(f"{pitch_id}: metadata pitcher_id does not match configuration")
        digest = sha256_file(video)
        if digest != item["video_sha256"]:
            raise ValueError(f"{pitch_id}: video SHA-256 does not match configuration")
        sources.append({"pitch_id": pitch_id, "video_path": str(video.resolve(strict=True)),
                        "metadata_path": str(metadata.resolve(strict=True)), "video_sha256": digest,
                        "metadata_sha256": sha256_file(metadata), "subject_roi": list(region)})
    output = Path(output_root).resolve()
    if output.exists():
        raise FileExistsError(f"Pilot output already exists; choose a new output_root: {output}")
    model = Path(model_path).resolve(strict=True)
    if not model.is_file():
        raise ValueError("model_path must be a file")
    model_digest = sha256_file(model)
    mapping = {"schema_version": "pitcher-region-source-mapping-v1", "execution_type": EXECUTION_TYPE,
               "pitcher_id": config["pitcher_id"], "region_semantics": REGION_SEMANTICS,
               "config_path": str(config_path), "config_sha256": hashlib.sha256(config_bytes).hexdigest(),
               "operator_confirmation": config["operator_confirmation"],
               "model_path": str(model), "model_sha256": model_digest, "clips": sources,
               "input_metadata_modified": False, "formal_promotion": False}
    output.mkdir(parents=True, exist_ok=False)
    with (output / "subject_region_config.json").open("xb") as stream:
        stream.write(config_bytes)
    _durable_json(output / "source_mapping.json", mapping)
    summary_path = output / "validation_summary.json"
    summary = {"schema_version": "pitcher-region-pilot-summary-v1", "execution_type": EXECUTION_TYPE,
               "pitcher_id": config["pitcher_id"], "pitch_count": len(sources), "attempted_count": 0,
               "state": "running", "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "source_mapping": str(output / "source_mapping.json"),
               "predictions_root": str(output / "predictions"), "results": [],
               "human_overlay_review": "pending", "formal_promotion": False}
    _durable_json(summary_path, summary)
    for source in sources:
        entry = {"pitch_id": source["pitch_id"], "video": source["video_path"],
                 "subject_roi": source["subject_roi"]}
        try:
            analysis = analyze_pitch(source["video_path"], source["metadata_path"],
                                     output_root=output / "predictions", model_path=model,
                                     subject_roi=tuple(source["subject_roi"]), record_candidates=True)
            # Keep the existing analysis statuses and gate; no new acceptance threshold.
            entry["analysis"] = analysis
            entry["status"] = analysis["status"]
            entry["input_quality_status"] = analysis["input_quality_status"]
            entry["quality_gate_passed"] = analysis["quality_gate_passed"]
        except Exception as error:
            entry.update(status="failed", failure_reason=f"{type(error).__name__}: {error}")
        summary["results"].append(entry)
        summary["attempted_count"] += 1
        _durable_json(summary_path, summary)
    summary["state"] = ("completed_with_failures" if any(item["status"] == "failed" for item in summary["results"])
                        else "completed")
    summary["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    _durable_json(summary_path, summary)
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Prepared MP4/metadata pairs")
    parser.add_argument("config_json", type=Path, help="Operator-confirmed pitcher-region-pilot-v1 JSON")
    parser.add_argument("output_root", type=Path, help="New output directory; never overwritten")
    parser.add_argument("--model", type=Path, default=Path("models/pose_landmarker_full.task"))
    args = parser.parse_args()
    try:
        summary_path = run_pilot(args.input_dir, args.config_json, args.output_root, model_path=args.model)
    except (OSError, ValueError) as error:
        parser.exit(2, f"Pilot rejected before analysis: {type(error).__name__}: {error}\n")
    print(summary_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary["state"] == "completed_with_failures":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
