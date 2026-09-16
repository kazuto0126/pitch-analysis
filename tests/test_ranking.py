import unittest
import json
import tempfile
from pathlib import Path

from pitch_analysis.ranking import _check_query_readiness, _check_scaler_registry


class RankingProvenanceTests(unittest.TestCase):
    def test_query_requires_reviewed_phase_quality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory) / "query.csv"
            sequence.write_text("phase\n", encoding="utf-8")
            sequence.with_suffix(".quality.json").write_text(
                json.dumps(
                    {
                        "schema_version": "phase-quality-v0.1",
                        "event_review_status": "needs_human_review",
                    }
                ),
                encoding="utf-8",
            )

            result = _check_query_readiness(sequence)

            self.assertFalse(result["ready"])
            self.assertIn("query_event_review_status_not_accepted", result["reasons"])

    def test_reviewed_query_is_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sequence = Path(directory) / "query.csv"
            sequence.write_text("phase\n", encoding="utf-8")
            sequence.with_suffix(".quality.json").write_text(
                json.dumps(
                    {
                        "schema_version": "phase-quality-v0.1",
                        "event_review_status": "human_reviewed",
                    }
                ),
                encoding="utf-8",
            )

            self.assertTrue(_check_query_readiness(sequence)["ready"])

    def test_matching_scaler_registry_is_verified(self) -> None:
        scaler = {
            "provenance": {
                "registry": "registry.json",
                "registry_schema_version": "v4",
            }
        }
        registry = {"schema_version": "v4"}

        result = _check_scaler_registry(scaler, registry, "registry.json")

        self.assertEqual(result["status"], "verified")

    def test_mismatched_registry_schema_is_rejected(self) -> None:
        scaler = {
            "provenance": {
                "registry": "registry.json",
                "registry_schema_version": "v3",
            }
        }
        with self.assertRaises(ValueError):
            _check_scaler_registry(scaler, {"schema_version": "v4"}, "registry.json")

    def test_legacy_scaler_is_explicitly_unverified(self) -> None:
        result = _check_scaler_registry({"provenance": {}}, {"schema_version": "v4"}, "registry.json")

        self.assertEqual(result["status"], "legacy_unverified")
        self.assertTrue(result["warnings"])


if __name__ == "__main__":
    unittest.main()
