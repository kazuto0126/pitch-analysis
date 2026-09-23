"""Run and preserve Phase 1 validation for 3–5 prepared pitches of one MLB pitcher.

This does not collect, download, cut or identify source footage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pitch_analysis.analysis.pitch import analyze_pitch
from pitch_analysis.contracts import load_input


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Directory with 3–5 matching .mp4/.json pairs")
    parser.add_argument("--output-root", type=Path, default=Path("analysis_results/phase1_baseline"))
    parser.add_argument("--model", type=Path, default=Path("models/pose_landmarker_full.task"))
    args = parser.parse_args()
    metadata_paths = sorted(args.input_dir.glob("*.json"))
    if not 3 <= len(metadata_paths) <= 5:
        parser.error("Phase 1 requires 3–5 prepared MP4/JSON pairs from one pitcher")
    pairs = [(path.with_suffix(".mp4"), path) for path in metadata_paths]
    pitchers = {load_input(video, metadata)["pitcher"]["id"] for video, metadata in pairs}
    if len(pitchers) != 1:
        parser.error("Phase 1 baseline requires exactly one pitcher ID")
    summary = args.output_root / "validation_summary.json"
    if summary.exists():
        parser.error(f"Validation summary already exists; use a new --output-root: {summary}")
    results = []
    for video, metadata in pairs:
        try:
            analysis = analyze_pitch(video, metadata, output_root=args.output_root, model_path=args.model)
            analysis_dir = Path(analysis["output_dir"])
            input_quality = json.loads((analysis_dir / "input_quality.json").read_text(encoding="utf-8"))
            entry = {"video": str(video), "analysis_dir": str(analysis_dir),
                     "analysis_status": analysis["status"], "input_quality_status": input_quality["status"],
                     "input_quality_reasons": input_quality["reasons"],
                     "status": "rejected" if input_quality["status"] == "rejected" else "degraded"}
            quality_path = analysis_dir / "keypoint_quality.json"
            if quality_path.exists():
                quality = json.loads(quality_path.read_text(encoding="utf-8"))
                entry.update({key: quality[key] for key in (
                    "failure_reason", "total_frames", "frames_with_valid_pitcher_pose",
                    "valid_pose_ratio", "interpolated_frame_count", "rejected_frame_count",
                    "mean_landmark_confidence", "longest_missing_pose_gap")})
                if input_quality["status"] != "rejected":
                    entry["status"] = quality["status"]
            results.append(entry)
        except Exception as error:
            results.append({"video": str(video), "status": "failed", "failure_reason": f"{type(error).__name__}: {error}"})
    args.output_root.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps({"phase": "single-pitch-real-mlb-baseline", "pitcher_id": next(iter(pitchers)),
                                   "pitch_count": len(pairs), "results": results,
                                   "human_review": "pending; inspect each overlay and fill review/human_validation_template.json separately",
                                   "registry_inserted": False}, indent=2, allow_nan=False), encoding="utf-8")
    print(summary.resolve())
    if any(item["status"] == "failed" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
