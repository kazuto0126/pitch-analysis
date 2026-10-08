"""Candidate intake and explicit human review; never runs pose analysis."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from pitch_analysis.handoff.reader import PROJECT_ROOT, import_handoff, list_candidates, local_intake_root
from pitch_analysis.handoff.review import CONCLUSIONS, record_review


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intake-root", type=Path, default=PROJECT_ROOT / "data/intake/handoff")
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser("import", help="Import indexed v2 clips as candidates")
    ingest.add_argument("--handoff-root", type=Path, default=Path("D:/project/pitch-video-handoff"))
    ingest.add_argument("--pitcher-map", type=Path, default=PROJECT_ROOT / "config/handoff_pitchers.json")
    ingest.add_argument("--ffprobe", type=Path)
    commands.add_parser("status", help="Show local candidate and review statuses")
    review = commands.add_parser("review", help="Record one explicit human finding")
    review.add_argument("internal_pitch_id")
    review.add_argument("--item", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--reviewed-at", required=True, help="ISO datetime including timezone")
    review.add_argument("--conclusion", choices=sorted(CONCLUSIONS), required=True)
    review.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "import":
            result = import_handoff(args.handoff_root, args.intake_root, pitcher_map_path=args.pitcher_map, ffprobe_path=args.ffprobe)
        elif args.command == "status":
            result = list_candidates(args.intake_root)
        else:
            if not re.fullmatch(r"h_[0-9a-f]{64}", args.internal_pitch_id):
                raise ValueError("internal_pitch_id must be a local h_ SHA-256 identifier")
            intake = local_intake_root(args.intake_root)
            result = record_review(intake / "candidates" / args.internal_pitch_id, item=args.item, reviewer=args.reviewer, reviewed_at_utc=args.reviewed_at, conclusion=args.conclusion, note=args.note)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return int(isinstance(result, dict) and result.get("status") == "needs_attention")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Handoff intake refused: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
