"""End-to-end source URL/local file to reviewable pitch MP4 samples."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .media import extract_clip, standardize_video
from .motion import detect_motion_candidates
from .naming import clip_filename, slugify, source_fingerprint
from .probe import resolve_ffmpeg
from .reid import ClipReIdentifier, OpenClipBackend, reidentify_clip
from .source import acquire_source


def _write_manifest(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def preprocess_video(
    source: str | Path,
    output_dir: str | Path,
    *,
    pitcher_id: str,
    season: str,
    throws: str,
    view: str,
    clip_ranges: Sequence[tuple[float, float]] | None = None,
    auto_detect: bool = False,
    motion_sample_fps: float = 6.0,
    pre_seconds: float = 4.0,
    post_seconds: float = 3.0,
    min_peak_interval_seconds: float = 4.0,
    max_candidates: int = 30,
    reference_photos: Sequence[str | Path] | None = None,
    reid_threshold: float = 0.30,
    reid_samples: int = 8,
    target_fps: float = 30.0,
    ffmpeg: str | Path | None = None,
) -> dict:
    """Acquire, standardize, and clip a source without entering the registry."""
    if throws not in {"LEFT", "RIGHT"}:
        raise ValueError("throws must be LEFT or RIGHT")
    clip_ranges = list(clip_ranges or [])
    if bool(clip_ranges) == auto_detect:
        raise ValueError("choose exactly one of manual clip ranges or auto_detect")
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Preprocessing output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / "manifest.json"
    manifest = {
        "schema_version": "pitch-preprocessing-job-v0.1",
        "status": "running",
        "manifest": str(manifest_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pitcher": {
            "pitcher_id": slugify(pitcher_id, fallback="unknown_pitcher"),
            "season": str(season),
            "throws": throws,
            "view": slugify(view, fallback="unknown_view"),
        },
        "source": {"input_kind": "pending"},
        "standardization": None,
        "candidate_detection": None,
        "reidentification": {
            "enabled": bool(reference_photos),
            "reference_photo_count": len(reference_photos or []),
        },
        "clips": [],
    }
    _write_manifest(manifest_path, manifest)
    try:
        executable = resolve_ffmpeg(ffmpeg)
        acquired = acquire_source(source, output / "source", ffmpeg=executable)
        manifest["source"] = acquired
        standardized_path = output / "standardized" / "source.mp4"
        standardized = standardize_video(
            acquired["acquired_path"],
            standardized_path,
            target_fps=target_fps,
            ffmpeg=executable,
        )
        manifest["standardization"] = standardized
        candidate_details: list[dict]
        if auto_detect:
            motion_report = detect_motion_candidates(
                standardized_path,
                sample_fps=motion_sample_fps,
                pre_seconds=pre_seconds,
                post_seconds=post_seconds,
                min_peak_interval_seconds=min_peak_interval_seconds,
                max_candidates=max_candidates,
            )
            manifest["candidate_detection"] = motion_report
            candidate_details = list(motion_report["candidates"])
            clip_ranges = [
                (candidate["start_second"], candidate["end_second"])
                for candidate in candidate_details
            ]
        else:
            candidate_details = [
                {
                    "start_second": float(start),
                    "end_second": float(end),
                    "method": "human_supplied_time_range",
                    "review_status": "needs_human_review",
                }
                for start, end in clip_ranges
            ]
            manifest["candidate_detection"] = {
                "schema_version": "manual-clip-ranges-v0.1",
                "candidates": candidate_details,
            }
        remote_id = (acquired.get("remote_metadata") or {}).get("source_video_id")
        fallback_source_id = (
            Path(acquired["acquired_path"]).stem
            if acquired["kind"] == "local_file"
            else f"source_{source_fingerprint(acquired['source'])}"
        )
        source_id = slugify(
            str(remote_id or fallback_source_id),
            fallback=f"source_{source_fingerprint(acquired['source'])}",
        )
        matcher = None
        if reference_photos:
            matcher = ClipReIdentifier(OpenClipBackend(), threshold=reid_threshold)
            matcher.register(manifest["pitcher"]["pitcher_id"], list(reference_photos))
        candidates = output / "candidates"
        for index, (start, end) in enumerate(clip_ranges, start=1):
            filename = clip_filename(pitcher_id, season, view, source_id, index)
            clip = extract_clip(
                standardized_path,
                candidates / filename,
                start_second=float(start),
                end_second=float(end),
                ffmpeg=executable,
            )
            clip.update(
                {
                    "pitch_number": index,
                    "filename": filename,
                    "source_id": source_id,
                    "intended_pitcher_id": manifest["pitcher"]["pitcher_id"],
                    "candidate_evidence": candidate_details[index - 1],
                    "analysis_handoff": {
                        "command": "prepare-segment",
                        "video_path": clip["path"],
                        "video_id": Path(filename).stem,
                        "throwing_side": throws,
                        "start_second": 0.0,
                        "end_second": clip["output_probe"]["duration_seconds"],
                        "reference_context": {
                            "season": str(season),
                            "view": slugify(view, fallback="unknown_view"),
                        },
                    },
                }
            )
            if matcher is not None:
                clip["reidentification"] = reidentify_clip(
                    clip["path"], matcher, samples=reid_samples
                )
            manifest["clips"].append(clip)
            _write_manifest(manifest_path, manifest)
        manifest["status"] = (
            "clips_ready_for_human_review"
            if manifest["clips"]
            else "no_motion_candidates"
        )
        manifest["next_step"] = (
            {
                "command": "prepare-segment",
                "note": "Review each MP4 first, then pass an accepted clip to the existing pose-analysis workflow. Automatic preprocessing does not add registry references.",
            }
            if manifest["clips"]
            else {
                "command": "review-source-or-adjust-motion-parameters",
                "note": "No clips were fabricated because the coarse detector found no candidates.",
            }
        )
        _write_manifest(manifest_path, manifest)
        return manifest
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = {"type": type(error).__name__, "message": str(error)}
        _write_manifest(manifest_path, manifest)
        raise
