"""Run an explicitly approved local MP4 cohort through isolated native RTMPose."""
import argparse
import json
from pathlib import Path

from pitch_analysis.native_pose_live import run_live


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = run_live(args.root, args.config, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
