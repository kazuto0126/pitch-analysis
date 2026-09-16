import csv
import json
import tempfile
import unittest
from pathlib import Path

from pitch_analysis.comparison import FEATURE_SCALES
from pitch_analysis.validation import leave_one_reference_out


class LeaveOneOutValidationTests(unittest.TestCase):
    def _write_sequence(self, path: Path, base: float) -> None:
        fields = ["phase", "phase_index", "source_frame_float", *FEATURE_SCALES]
        with path.open("w", encoding="utf-8", newline="") as sink:
            writer = csv.DictWriter(sink, fieldnames=fields)
            writer.writeheader()
            frame = 0
            for phase in ("windup", "stride", "arm_acceleration", "follow_through"):
                for phase_index in range(3):
                    row = {"phase": phase, "phase_index": phase_index, "source_frame_float": frame}
                    for offset, feature in enumerate(FEATURE_SCALES):
                        row[feature] = base + offset + phase_index
                    writer.writerow(row)
                    frame += 1

    def test_leave_one_out_fits_without_query_and_ranks_expected_pitcher(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pitchers = {"pitcher_a": [], "pitcher_b": []}
            for pitcher_id, bases in {"pitcher_a": (10.0, 12.0), "pitcher_b": (70.0, 72.0)}.items():
                for index, base in enumerate(bases):
                    path = root / f"{pitcher_id}_{index}.csv"
                    self._write_sequence(path, base)
                    pitchers[pitcher_id].append(
                        {
                            "phase_sequence": str(path),
                            "video_id": f"{pitcher_id}_{index}",
                            "throws": "RIGHT",
                            "context": {"view": "rear_centerfield_broadcast", "season": "2026"},
                            "camera_context": {
                                "view": "rear_centerfield_broadcast",
                                "horizontal_mirror": None,
                                "subject_framing": "unknown",
                            },
                        }
                    )
            registry_path = root / "registry.json"
            output_path = root / "validation.json"
            registry_path.write_text(
                json.dumps({"schema_version": "test", "pitchers": pitchers}),
                encoding="utf-8",
            )

            result = leave_one_reference_out(registry_path, output_path, throws="RIGHT")

            self.assertEqual(result["scored_fold_count"], 4)
            self.assertEqual(result["unscored_fold_count"], 0)
            self.assertEqual(result["validation_coverage"], 1.0)
            self.assertEqual(result["top1_accuracy"], 1.0)
            self.assertEqual(result["per_pitcher"]["pitcher_a"]["scored_fold_count"], 2)
            self.assertTrue(output_path.exists())


if __name__ == "__main__":
    unittest.main()
