"""Read-only schema/source validation; no inference or prediction comparison."""
import argparse
from pathlib import Path

from pitch_analysis.ground_truth import load_ground_truth


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("source_video", type=Path)
    args = parser.parse_args()
    annotation = load_ground_truth(args.ground_truth, source_video_path=args.source_video)
    print(f"Schema/source VALID; annotation_status={annotation['annotation_status']}; no comparison performed")
