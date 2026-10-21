"""Run one source-bound, explicitly approved detector-conditioned native clip."""
import argparse
import json
from pathlib import Path

from pitch_analysis.native_person_box_live import run_person_box


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(run_person_box(args.root, args.config, args.output), ensure_ascii=False, indent=2))
