import csv
import json
import tempfile
import unittest
from pathlib import Path

from pitch_analysis.comparison import FEATURE_SCALES
from pitch_analysis.reference import fit_registry_scaler


class RegistryScalerTests(unittest.TestCase):
    def _write_sequence(self, path: Path, base: float) -> None:
        fields = ["phase", "phase_index", "source_frame_float", *FEATURE_SCALES]
        with path.open("w", encoding="utf-8", newline="") as sink:
            writer = csv.DictWriter(sink, fieldnames=fields)
            writer.writeheader()
            for index in range(3):
                row = {"phase": "windup", "phase_index": index, "source_frame_float": index}
                row.update({feature: base + index for feature in FEATURE_SCALES})
                writer.writerow(row)

    def test_scaler_uses_only_matching_registry_entries(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            right = root / "right.csv"
            left = root / "left.csv"
            fields = ["phase", "phase_index", "source_frame_float", *FEATURE_SCALES]
            for path, base in ((right, 10.0), (left, 80.0)):
                with path.open("w", encoding="utf-8", newline="") as sink:
                    writer = csv.DictWriter(sink, fieldnames=fields)
                    writer.writeheader()
                    for index in range(3):
                        row = {"phase": "windup", "phase_index": index, "source_frame_float": index}
                        row.update({feature: base + index for feature in FEATURE_SCALES})
                        writer.writerow(row)
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "test-registry",
                        "pitchers": {
                            "right_pitcher": [{"throws": "RIGHT", "phase_sequence": str(right)}],
                            "left_pitcher": [{"throws": "LEFT", "phase_sequence": str(left)}],
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = root / "right_scaler.json"

            result = fit_registry_scaler(registry, output, throws="RIGHT")

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["reference_sequences"], 1)
            self.assertEqual(payload["reference_scope"]["throws"], "RIGHT")
            self.assertEqual(payload["provenance"]["registry_schema_version"], "test-registry")
            self.assertEqual(payload["scalers"]["throwing_knee_angle_smoothed"]["mean"], 11.0)

    def test_scaler_gives_each_pitcher_equal_total_weight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sparse = root / "sparse.csv"
            crowded = [root / f"crowded_{index}.csv" for index in range(3)]
            self._write_sequence(sparse, 0.0)
            for path in crowded:
                self._write_sequence(path, 9.0)
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "test-registry",
                        "pitchers": {
                            "sparse_pitcher": [
                                {"throws": "RIGHT", "phase_sequence": str(sparse)}
                            ],
                            "crowded_pitcher": [
                                {"throws": "RIGHT", "phase_sequence": str(path)}
                                for path in crowded
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            output = root / "balanced.json"

            fit_registry_scaler(registry, output, throws="RIGHT")

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["method"], "reference-z-score-equal-pitcher-weight")
            self.assertAlmostEqual(
                payload["scalers"]["throwing_knee_angle_smoothed"]["mean"],
                5.5,
            )
            self.assertEqual(
                payload["provenance"]["pitcher_sequence_counts"],
                {"crowded_pitcher": 3, "sparse_pitcher": 1},
            )


if __name__ == "__main__":
    unittest.main()
