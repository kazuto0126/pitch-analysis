import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.registry import (
    EXPECTED_PHASE_COLUMNS,
    EXPECTED_PHASES,
    audit_references,
    discover_references,
    write_registry,
)


class RegistryValidationTests(unittest.TestCase):
    def _write_candidate(
        self,
        root: Path,
        name: str,
        *,
        metadata: bool = True,
        gate_passed: bool = True,
        event_gate_passed: bool = True,
        release: int = 4,
    ) -> Path:
        candidate = root / "example_pitcher" / "2026_centerfield" / name
        candidate.mkdir(parents=True)
        phase_path = candidate / "phase_sequence.csv"
        with phase_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=EXPECTED_PHASE_COLUMNS)
            writer.writeheader()
            for phase_index, phase in enumerate(EXPECTED_PHASES):
                for point in range(2):
                    writer.writerow({
                        "phase": phase,
                        "phase_index": point,
                        "source_frame_float": phase_index * 2 + point,
                        **{feature: "" for feature in EXPECTED_PHASE_COLUMNS[3:]},
                    })
        events = {
            "video_id": name,
            "throws": "RIGHT",
            "review_status": "human_reviewed",
            "events": {
                "pitch_start": 0,
                "peak_leg_lift": 2,
                "foot_strike": 3,
                "release": release,
                "follow_through_end": release + 1 if release > 4 else 8,
            },
        }
        (candidate / "events.json").write_text(json.dumps(events), encoding="utf-8")
        phase_ranges = {
            "windup": [0, 2],
            "stride": [2, 3],
            "arm_acceleration": [3, release],
            "follow_through": [release, events["events"]["follow_through_end"]],
        }
        phase_path.with_suffix(".quality.json").write_text(
            json.dumps(
                {
                    "schema_version": "phase-quality-v0.1",
                    "event_frame_range": [0, events["events"]["follow_through_end"]],
                    "event_window": {
                        "source_frames": 9,
                        "source_detection_coverage": 1.0,
                        "max_consecutive_missing_source_frames": 0,
                        "feature_coverage": {
                            feature: 1.0 for feature in EXPECTED_PHASE_COLUMNS[3:]
                        },
                        "raw_feature_coverage": {
                            feature: (1.0 if event_gate_passed else 0.0)
                            for feature in EXPECTED_PHASE_COLUMNS[3:]
                        },
                    },
                    "phases": {
                        phase: {
                            "frame_range": frame_range,
                            "source_frames": 2,
                            "feature_coverage": {
                                feature: 1.0 for feature in EXPECTED_PHASE_COLUMNS[3:]
                            },
                            "raw_feature_coverage": {
                                feature: 1.0 for feature in EXPECTED_PHASE_COLUMNS[3:]
                            },
                        }
                        for phase, frame_range in phase_ranges.items()
                    },
                }
            ),
            encoding="utf-8",
        )
        if metadata:
            payload = {
                "quality_gate": {"passed": gate_passed},
                "capture": {
                    "video": "raw/example.mp4",
                    "fps": 30.0,
                    "start_frame": 0,
                    "end_frame": 10,
                    "requested_frames": 11,
                    "detected_frames": 11,
                    "width": 1920,
                    "height": 1080,
                },
            }
            (candidate / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")
        return phase_path

    def test_only_complete_auditable_reference_is_discovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            accepted = self._write_candidate(root, "pitch_accepted")
            self._write_candidate(root, "pitch_missing_metadata", metadata=False)
            self._write_candidate(root, "pitch_quality_failed", gate_passed=False, event_gate_passed=False)

            pitchers, exclusions = audit_references(root)

            self.assertEqual([entry["phase_sequence"] for entry in pitchers["example_pitcher"]], [str(accepted)])
            by_relative_path = {item["relative_path"]: item for item in exclusions}
            missing = by_relative_path[str(Path("example_pitcher") / "2026_centerfield" / "pitch_missing_metadata" / "phase_sequence.csv")]
            self.assertEqual(missing["action"], "requires_revalidation")
            self.assertIn("metadata_missing_requires_revalidation", missing["reasons"])
            failed = by_relative_path[str(Path("example_pitcher") / "2026_centerfield" / "pitch_quality_failed" / "phase_sequence.csv")]
            self.assertIn("quality_gate_not_passed", failed["reasons"])
            self.assertEqual(discover_references(root), pitchers)

    def test_reviewed_event_window_can_replace_padding_damaged_segment_gate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = self._write_candidate(
                root,
                "pitch_event_window_passed",
                gate_passed=False,
                event_gate_passed=True,
            )

            pitchers, exclusions = audit_references(root)

            self.assertEqual(exclusions, [])
            entry = pitchers["example_pitcher"][0]
            self.assertEqual(entry["phase_sequence"], str(candidate))
            self.assertEqual(entry["validation"]["quality_gate"], "reviewed_event_window_quality_gate")

    def test_registry_records_invalid_event_range_without_deleting_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid = self._write_candidate(root, "pitch_bad_range", release=12)
            output = root / "registry.json"

            registry = write_registry(root, output)

            self.assertEqual(registry["pitchers"], {})
            self.assertEqual(registry["accepted_reference_count"], 0)
            self.assertEqual(registry["excluded_reference_count"], 1)
            self.assertTrue(invalid.exists())
            self.assertIn("event_boundaries_outside_capture_range", registry["exclusions"][0]["reasons"])
            on_disk = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["eligibility_policy"]["legacy_behavior"], registry["eligibility_policy"]["legacy_behavior"])


if __name__ == "__main__":
    unittest.main()
