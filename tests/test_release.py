import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pitch_analysis.release import build_library_release


class LibraryReleaseTests(unittest.TestCase):
    def test_release_packages_registry_scalers_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "references"
            release = Path(directory) / "release"
            root.mkdir()

            def fake_registry(_root, path):
                payload = {
                    "schema_version": "test-v5",
                    "accepted_reference_count": 3,
                    "excluded_reference_count": 1,
                    "pitchers": {
                        "right": [{"throws": "RIGHT", "phase_sequence": "right.csv"}],
                        "left": [{"throws": "LEFT", "phase_sequence": "left.csv"}],
                    },
                }
                Path(path).write_text(json.dumps(payload), encoding="utf-8")
                return payload

            with (
                patch(
                    "pitch_analysis.release.rebuild_library",
                    return_value={"segment_count": 4},
                ),
                patch("pitch_analysis.release.write_registry", side_effect=fake_registry),
                patch(
                    "pitch_analysis.release.fit_registry_scaler",
                    return_value={"reference_sequences": 1},
                ) as scaler,
                patch(
                    "pitch_analysis.release.leave_one_reference_out",
                    return_value={
                        "scored_fold_count": 0,
                        "unscored_fold_count": 1,
                        "top1_accuracy": None,
                    },
                ) as validation,
            ):
                manifest = build_library_release(root, release)

            self.assertEqual(manifest["pitcher_count"], 2)
            self.assertEqual(manifest["accepted_reference_count"], 3)
            self.assertEqual(scaler.call_count, 2)
            self.assertEqual(validation.call_count, 2)
            self.assertTrue((release / "manifest.json").exists())

    def test_release_refuses_to_overwrite_nonempty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release = root / "release"
            release.mkdir()
            (release / "existing.json").write_text("{}", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                build_library_release(root, release)


if __name__ == "__main__":
    unittest.main()
