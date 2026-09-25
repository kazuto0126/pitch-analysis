"""Score Phase 2 predictions against independently reviewed annotations.

Writes a new comparison JSON; never edits source predictions, ground truth,
or the original baseline evaluation summary.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pitch_analysis.ground_truth import load_ground_truth
from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth


def evaluate_baseline(input_dir: Path, baseline_root: Path, output_path: Path) -> dict:
    input_dir = input_dir.resolve(strict=True)
    baseline_root = baseline_root.resolve(strict=True)
    if output_path.exists():
        raise FileExistsError(f"Comparison output already exists: {output_path}")
    baseline = json.loads((baseline_root / "evaluation_summary.json").read_text(encoding="utf-8"))
    comparisons = []
    for pitch in baseline["pitches"]:
        pitch_id = pitch["pitch_id"]
        video = input_dir / f"{pitch_id}.mp4"
        reliability_dir = baseline_root / "reliability" / pitch_id
        pose = json.loads((reliability_dir / "pose_reliability.json").read_text(encoding="utf-8"))
        tracking = json.loads((reliability_dir / "tracking_reliability.json").read_text(encoding="utf-8"))
        ground_truth = load_ground_truth(
            baseline_root / "ground_truth" / pitch_id / "ground_truth.json",
            source_video_path=video,
        )
        comparisons.append({
            "pitch_id": pitch_id,
            "ground_truth_status": ground_truth["annotation_status"],
            "comparison": evaluate_against_ground_truth(ground_truth, pose, tracking),
        })
    reviewed = sum(item["ground_truth_status"] == "reviewed" for item in comparisons)
    result = {
        "schema_version": "phase2-ground-truth-comparison-v1",
        "status": "human_comparison_available" if reviewed == len(comparisons) else "pending_human_ground_truth",
        "pitch_count": len(comparisons),
        "reviewed_count": reviewed,
        "baseline_root": str(baseline_root),
        "pitches": comparisons,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as target:
        json.dump(result, target, indent=2, ensure_ascii=False, allow_nan=False)
        target.write("\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("baseline_root", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    result = evaluate_baseline(args.input_dir, args.baseline_root, args.output_path)
    print(json.dumps({"status": result["status"], "reviewed_count": result["reviewed_count"],
                      "pitch_count": result["pitch_count"], "output": str(args.output_path)}))


if __name__ == "__main__":
    main()
