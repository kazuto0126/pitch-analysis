"""Build Phase 2 reliability evidence from five already analyzed formal pitches.

Usage (after run_real_baseline.py writes the predictions subdirectory):
  python -B scripts/run_phase2_reliability.py INPUT_DIR OUTPUT_ROOT

The runner never edits Phase 1 outputs or a human annotation. A new output
root is required for each baseline run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pitch_analysis.contracts import load_input
from pitch_analysis.ground_truth import create_blank_ground_truth, load_ground_truth
from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth
from pitch_analysis.pose_reliability import write_pose_reliability
from pitch_analysis.tracking_reliability import write_tracking_reliability
from pitch_analysis.video.validation import sha256_file


def build_baseline(input_dir: Path, output_root: Path) -> Path:
    input_dir, output_root = input_dir.resolve(strict=True), output_root.resolve()
    summary_path = output_root / "evaluation_summary.json"
    if summary_path.exists():
        raise FileExistsError(f"Phase 2 evaluation already exists: {summary_path}")
    predictions = output_root / "predictions"
    run = json.loads((predictions / "validation_summary.json").read_text(encoding="utf-8"))
    if run["pitcher_id"] != "yoshinobu_yamamoto" or run["pitch_count"] != 5:
        raise ValueError("Phase 2 baseline requires the five formal Yamamoto pitches")
    results = run["results"]
    if [Path(item["video"]).stem for item in results] != [f"pitch_{i:03d}" for i in range(1, 6)]:
        raise ValueError("Prediction summary does not contain formal pitch_001 through pitch_005")

    pitches = []
    for index, item in enumerate(results, 1):
        pitch_id = f"pitch_{index:03d}"
        video = input_dir / f"{pitch_id}.mp4"
        metadata = input_dir / f"{pitch_id}.json"
        load_input(video, metadata)
        analysis = predictions / "yoshinobu_yamamoto" / pitch_id
        if Path(item["analysis_dir"]).resolve() != analysis.resolve():
            raise ValueError(f"Analysis output mismatch for {pitch_id}")
        if item["status"] != "success" or item["input_quality_status"] != "accepted":
            raise ValueError(f"Source analysis is not Phase 1 accepted: {pitch_id}")
        technical = json.loads((analysis / "video_metadata.json").read_text(encoding="utf-8"))
        if technical["status"] != "validated" or technical["sha256"] != sha256_file(video):
            raise ValueError(f"Formal MP4 does not match analyzed video: {pitch_id}")
        if technical["frame_count"] != item["total_frames"]:
            raise ValueError(f"Decoded timeline mismatch for {pitch_id}")

        reliability_dir = output_root / "reliability" / pitch_id
        reliability_dir.mkdir(parents=True, exist_ok=False)
        pose_path = reliability_dir / "pose_reliability.json"
        tracking_path = reliability_dir / "tracking_reliability.json"
        write_pose_reliability(analysis, pose_path)
        tracking = write_tracking_reliability(analysis, tracking_path)
        pose = json.loads(pose_path.read_text(encoding="utf-8"))
        ground_truth_path = create_blank_ground_truth(
            video, pitch_id, technical["frame_count"], output_root / "ground_truth"
        )
        ground_truth = load_ground_truth(ground_truth_path, source_video_path=video)
        comparison = evaluate_against_ground_truth(ground_truth, pose, tracking)
        elbow_angle = json.loads((analysis / "metrics.json").read_text(encoding="utf-8"))[
            "metrics"]["throwing_elbow_angle"]["raw_coverage"]
        important_joints = {}
        for role, landmark in pose["important_joints"].items():
            joint = pose["joints"][landmark]
            important_joints[role] = {
                "landmark": landmark,
                "status": joint["status"],
                "reasons": joint["reasons"],
                "raw_coverage": joint["raw_coverage"],
                "raw_prediction_coverage": joint["raw_prediction_coverage"],
                "longest_missing_span_frames": joint["longest_missing_span_frames"],
                "longest_not_observed_span_frames": joint["longest_not_observed_span_frames"],
                "interpolated_frames": joint["interpolated_frames"],
                "jump_candidate_count": joint["frame_to_frame_jump"]["candidate_count"],
            }
        pitches.append({
            "pitch_id": pitch_id,
            "video_sha256": technical["sha256"],
            "total_frames": technical["frame_count"],
            "phase1_input_quality": item["input_quality_status"],
            "phase1_pose_status": item["status"],
            "valid_pose_ratio": pose["valid_pose_ratio"],
            "pose_reliability_status": pose["status"],
            "pose_reliability_reasons": pose["reasons"],
            "tracking_reliability_status": tracking["status"],
            "tracking_reliability_reasons": tracking["reasons"],
            "track_breaks": tracking["track_breaks"],
            "identity_switch_warning": tracking["identity_switch_warning"],
            "identity_switch_confirmed": tracking["identity_switch_confirmed"],
            "throwing_elbow_angle_raw_coverage": elbow_angle,
            "important_joints": important_joints,
            "ground_truth_status": ground_truth["annotation_status"],
            "ground_truth_comparison": comparison,
            "artifacts": {
                "prediction_overlay": str(analysis / "overlay.mp4"),
                "pose_reliability": str(pose_path),
                "tracking_reliability": str(tracking_path),
                "ground_truth": str(ground_truth_path),
            },
        })
    result = {
        "schema_version": "phase2-evaluation-v1",
        "phase": "pitcher_tracking_and_pose_reliability",
        "phase2_status": "pending_human_ground_truth",
        "pitcher_id": "yoshinobu_yamamoto",
        "pitch_count": len(pitches),
        "model_backend": "mediapipe_pose_landmarker",
        "predictions_root": str(predictions),
        "ground_truth_root": str(output_root / "ground_truth"),
        "predictions_and_ground_truth_separate": True,
        "human_ground_truth_reviewed_count": 0,
        "limitations": [
            "Signal continuity and visibility flags are provisional, not calibrated keypoint accuracy.",
            "Identity correctness and warning sensitivity cannot be measured until human annotations are reviewed.",
            "No automatic event estimates or reference X/Y coordinates are available for event or localization error.",
            "Phase 1 clip acceptance remains separate from Phase 2 joint reliability.",
        ],
        "pitches": pitches,
    }
    summary_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                            encoding="utf-8")
    return summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path, help="Five formal pitch_001..005 MP4/JSON pairs")
    parser.add_argument("output_root", type=Path, help="New Phase 2 root containing predictions/")
    args = parser.parse_args()
    print(build_baseline(args.input_dir, args.output_root))


if __name__ == "__main__":
    main()
