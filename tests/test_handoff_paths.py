"""Check local containment and durable recovery using synthetic deliveries."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pitch_analysis.handoff import reader
from pitch_analysis.handoff.contract import HandoffError

import test_handoff_reader as fixtures


class HandoffPathTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.HandoffReaderTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def _directory_link(self, link: Path, target: Path):
        """Use a directory junction when Windows cannot create symlinks."""
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt":
                self.skipTest("directory links are unavailable")
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(link), str(target)],
                capture_output=True, check=False,
            )
            if result.returncode or not link.is_junction():
                self.skipTest("directory junctions are unavailable")
        self.addCleanup(self._remove_directory_link, link)

    @staticmethod
    def _remove_directory_link(link: Path):
        # Remove only the link itself before TemporaryDirectory removes fixtures.
        if link.is_symlink():
            link.unlink()
        elif hasattr(link, "is_junction") and link.is_junction():
            link.rmdir()

    def _interrupted_candidate(self, **batch_options):
        fixture = self.fixture.add_batch(**batch_options)
        with patch.object(reader, "_persist_pitch", side_effect=RuntimeError("synthetic interruption after rename")):
            with self.assertRaisesRegex(RuntimeError, "synthetic interruption"):
                self.fixture.run_import()
        candidate = self.fixture.candidates()[0].parent
        provenance = json.loads((candidate / "provenance.json").read_text(encoding="utf-8"))
        return fixture, candidate, provenance

    def test_snapshot_refuses_linked_batch_directory_without_touching_target(self):
        output = self.fixture.output
        output.mkdir(parents=True)
        outside = self.fixture.sandbox / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"preserve outside target")
        before = fixtures.inventory(outside)
        self._directory_link(output / "batches", outside)
        with self.assertRaisesRegex(HandoffError, "symbolic links or junctions"):
            reader._snapshot_batch(output.resolve(), "BATCH", {"batch_id": "BATCH"}, b"batch", b"contract")
        self.assertEqual(fixtures.inventory(outside), before)

    def test_local_path_refuses_link_component_even_when_target_is_inside_intake(self):
        output = self.fixture.output
        output.mkdir(parents=True)
        target = output / "protected"
        target.mkdir()
        (target / "keep.txt").write_bytes(b"keep this directory unchanged")
        before = fixtures.inventory(target)
        self._directory_link(output / ".staging", target)
        with self.assertRaisesRegex(HandoffError, "symbolic links or junctions"):
            reader._local_path(output.resolve(), ".staging/new_candidate")
        self.assertEqual(fixtures.inventory(target), before)

    def test_snapshot_refuses_linked_child_contract_before_skipping_existing_copy(self):
        output = self.fixture.output
        snapshot = output / "batches" / reader._identifier("BATCH", "b_")
        snapshot.mkdir(parents=True)
        outside = self.fixture.sandbox / "outside"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"leave external directory unchanged")
        before = fixtures.inventory(outside)
        self._directory_link(snapshot / "CONTRACT.md", outside)
        with self.assertRaisesRegex(HandoffError, "symbolic links or junctions"):
            reader._snapshot_batch(output.resolve(), "BATCH", {"batch_id": "BATCH"}, b"batch", b"contract")
        self.assertEqual(fixtures.inventory(outside), before)

    def test_dangling_snapshot_file_link_cannot_create_external_target_when_supported(self):
        output = self.fixture.output
        snapshot = output / "batches" / reader._identifier("BATCH", "b_")
        snapshot.mkdir(parents=True)
        outside = self.fixture.sandbox / "outside"
        outside.mkdir()
        target = outside / "missing_contract.md"
        link = snapshot / "CONTRACT.md"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("file symlink creation is unavailable")
        self.addCleanup(link.unlink)
        with self.assertRaisesRegex(HandoffError, "symbolic links or junctions"):
            reader._snapshot_batch(output.resolve(), "BATCH", {"batch_id": "BATCH"}, b"batch", b"contract")
        self.assertFalse(target.exists())
        self.assertEqual(list(outside.iterdir()), [])

    def test_project_intake_link_outside_project_is_refused_before_local_mutation(self):
        project = self.fixture.project
        (project / "data").mkdir()
        outside = self.fixture.sandbox / "external_store"
        outside.mkdir()
        (outside / "keep.txt").write_bytes(b"no intake outside the project")
        before = fixtures.inventory(outside)
        self._directory_link(project / "data" / "intake", outside)
        with self.assertRaises(ValueError):
            self.fixture.run_import()
        self.assertEqual(fixtures.inventory(outside), before)

    def test_project_intake_link_to_code_directory_is_refused_before_local_mutation(self):
        project = self.fixture.project
        (project / "data").mkdir()
        code = project / "src"
        code.mkdir()
        (code / "existing.py").write_bytes(b"# existing project code\n")
        before = fixtures.inventory(code)
        self._directory_link(project / "data" / "intake", code)
        with self.assertRaises(ValueError):
            self.fixture.run_import()
        self.assertEqual(fixtures.inventory(code), before)

    def test_imported_timeline_rehash_cannot_replace_ledger_bound_evidence(self):
        self.fixture.add_batch()
        self.fixture.run_import()
        candidate = self.fixture.candidates()[0].parent
        timeline_path = candidate / "timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline["native_pts_ms"][1] += 1000
        fixtures.write_json(timeline_path, timeline)
        provenance_path = candidate / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["timeline_sha256"] = hashlib.sha256(timeline_path.read_bytes()).hexdigest()
        fixtures.write_json(provenance_path, provenance)
        before = fixtures.inventory(candidate)
        report = self.fixture.run_import()
        results = self.fixture.pitch_results(report)
        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(report["already_imported"], 2)
        self.assertEqual(report["imported_candidates"], 0)
        self.assertEqual([item["code"] for item in results if item["status"] == "conflict"], ["local_candidate_conflict"])
        self.assertEqual(fixtures.inventory(candidate), before)

    def test_unledgered_recovery_reruns_timing_and_refuses_self_rehashed_bad_evidence(self):
        _, candidate, provenance = self._interrupted_candidate()
        timeline_path = candidate / "timeline.json"
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline["native_pts_ms"][1] += 1000
        fixtures.write_json(timeline_path, timeline)
        provenance["timeline_sha256"] = hashlib.sha256(timeline_path.read_bytes()).hexdigest()
        fixtures.write_json(candidate / "provenance.json", provenance)
        before = fixtures.inventory(candidate)
        verifier = Mock(side_effect=fixtures.valid_timing)
        report = self.fixture.run_import(timing_verifier=verifier)
        self.assertEqual(verifier.call_count, 3)
        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(report["imported_candidates"], 2)
        self.assertEqual(fixtures.inventory(candidate), before)
        refused = [item for item in self.fixture.pitch_results(report) if item["status"] == "conflict"]
        self.assertEqual(refused[0]["code"], "local_candidate_conflict")
        self.assertIn("fresh verification", refused[0]["details"]["error"])

    def test_unledgered_recovery_cannot_replace_unknown_source_facts_with_local_guesses(self):
        _, candidate, provenance = self._interrupted_candidate(throws="unknown", unknown_game=True)
        self.assertIsNone(provenance["throws"])
        self.assertTrue(all(value is None for value in provenance["context"].values()))
        provenance["throws"] = "RIGHT"
        fixtures.write_json(candidate / "provenance.json", provenance)
        before = fixtures.inventory(candidate)
        source_before = fixtures.inventory(self.fixture.handoff)
        report = self.fixture.run_import()
        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(report["imported_candidates"], 2)
        self.assertEqual(fixtures.inventory(candidate), before)
        self.assertEqual(fixtures.inventory(self.fixture.handoff), source_before)
        refused = [item for item in self.fixture.pitch_results(report) if item["status"] == "conflict"]
        self.assertEqual(refused[0]["code"], "local_candidate_conflict")

    def test_non_object_candidate_evidence_is_a_logged_conflict(self):
        _, candidate, provenance = self._interrupted_candidate()
        timeline_path = candidate / "timeline.json"
        original_timeline = timeline_path.read_bytes()
        for name, value in (("provenance.json", []), ("provenance.json", None), ("timeline.json", []), ("timeline.json", None)):
            with self.subTest(name=name, value=value):
                timeline_path.write_bytes(original_timeline)
                fixtures.write_json(candidate / "provenance.json", provenance)
                fixtures.write_json(candidate / name, value)
                if name == "timeline.json":
                    changed = dict(provenance)
                    changed["timeline_sha256"] = hashlib.sha256(timeline_path.read_bytes()).hexdigest()
                    fixtures.write_json(candidate / "provenance.json", changed)
                report = self.fixture.run_import()
                self.assertEqual(report["conflicts"], 1)
                refused = [item for item in self.fixture.pitch_results(report) if item["status"] == "conflict"]
                self.assertEqual(refused[0]["code"], "local_candidate_conflict")
                self.assertIn("must be an object", refused[0]["details"]["error"])


if __name__ == "__main__":
    unittest.main()
