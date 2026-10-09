"""Reject redirected or invalid review targets before creating any local lock."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import unittest
from contextlib import contextmanager, redirect_stderr
from pathlib import Path
from unittest.mock import patch

import test_handoff_reader as fixtures

from pitch_analysis.handoff import review


ROOT = Path(__file__).resolve().parents[1]
INTERNAL_ID = "h_" + "a" * 64
RECORD = {
    "item": "pitcher_identity",
    "reviewer": "Synthetic reviewer",
    "reviewed_at_utc": "2026-10-09T10:00:00+08:00",
    "conclusion": "pass",
    "note": "Synthetic fixture finding for a boundary regression.",
}


class HandoffReviewBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.HandoffReaderTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.output = self.fixture.output
        self.output.mkdir(parents=True)
        specification = importlib.util.spec_from_file_location(
            "handoff_review_boundary_cli", ROOT / "scripts" / "import_handoff.py",
        )
        self.cli = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(self.cli)

    def _candidate(self, parent: Path) -> Path:
        candidate = parent / INTERNAL_ID
        source = candidate / "source"
        source.mkdir(parents=True)
        video_data = b"synthetic source video"
        json_data = b'{"pitch_id":"synthetic_pitch"}\n'
        (source / "synthetic_pitch.mp4").write_bytes(video_data)
        (source / "synthetic_pitch.json").write_bytes(json_data)
        provenance = {
            "schema": "handoff-candidate-v1", "status": "candidate",
            "internal_pitch_id": INTERNAL_ID, "original_pitch_id": "synthetic_pitch",
            "original_batch_id": "synthetic_batch",
            "video": {"file": "synthetic_pitch.mp4", "sha256": fixtures.digest(video_data)},
            "delivery_json": {"file": "synthetic_pitch.json", "sha256": fixtures.digest(json_data)},
            "required_reviews": ["pitcher_identity", "preparation_complete", "follow_through_complete"],
        }
        fixtures.write_json(candidate / "provenance.json", provenance)
        fixtures.write_json(candidate / "review.json", review.blank_review(provenance))
        return candidate

    @staticmethod
    def _inventory(root: Path) -> dict:
        return {".": ("directory", None, root.stat().st_mtime_ns), **fixtures.inventory(root)}

    def _directory_link(self, link: Path, target: Path) -> None:
        sandbox = self.fixture.sandbox.resolve(strict=True)
        self.assertIn(sandbox, link.absolute().parents)
        self.assertIn(sandbox, target.resolve(strict=True).parents)
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
    def _remove_directory_link(link: Path) -> None:
        if link.is_symlink():
            link.unlink()
        elif hasattr(link, "is_junction") and link.is_junction():
            link.rmdir()

    def _assert_no_mutation(self, target: Path, before: dict) -> None:
        self.assertEqual(self._inventory(target), before)
        self.assertEqual(list(target.rglob(".review.lock")), [])
        self.assertEqual(list(target.rglob(".review.*.tmp")), [])

    def test_cli_refuses_linked_candidates_before_calling_review(self):
        outside = self.fixture.sandbox / "external_delivery"
        self._candidate(outside)
        before = self._inventory(outside)
        self._directory_link(self.output / "candidates", outside)
        arguments = [
            "--intake-root", str(self.output), "review", INTERNAL_ID,
            "--item", RECORD["item"], "--reviewer", RECORD["reviewer"],
            "--reviewed-at", RECORD["reviewed_at_utc"],
            "--conclusion", RECORD["conclusion"], "--note", RECORD["note"],
        ]
        with patch.object(self.cli, "PROJECT_ROOT", self.fixture.project), \
                patch.object(self.cli, "record_review", wraps=review.record_review) as recorder, \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as refused:
            self.cli.main(arguments)
        self.assertEqual(refused.exception.code, 2)
        recorder.assert_not_called()
        self._assert_no_mutation(outside, before)

    def test_api_refuses_linked_parent_before_lock_creation_or_deletion(self):
        outside = self.fixture.sandbox / "external_delivery"
        self._candidate(outside)
        before = self._inventory(outside)
        self._directory_link(self.output / "candidates", outside)
        with patch.object(review, "_review_lock", wraps=review._review_lock) as lock, \
                self.assertRaisesRegex(ValueError, "symbolic links or junctions"):
            review.record_review(self.output / "candidates" / INTERNAL_ID, **RECORD)
        lock.assert_not_called()
        self._assert_no_mutation(outside, before)

    def test_api_refuses_linked_higher_ancestor_before_lock_creation_or_deletion(self):
        outside = self.fixture.sandbox / "external_delivery"
        self._candidate(outside / "nested" / "candidates")
        before = self._inventory(outside)
        alias = self.output / "redirected"
        self._directory_link(alias, outside)
        with patch.object(review, "_review_lock", wraps=review._review_lock) as lock, \
                self.assertRaisesRegex(ValueError, "symbolic links or junctions"):
            review.record_review(alias / "nested" / "candidates" / INTERNAL_ID, **RECORD)
        lock.assert_not_called()
        self._assert_no_mutation(outside, before)

    def test_invalid_candidate_evidence_and_unknown_item_never_acquire_lock(self):
        candidate = self._candidate(self.output / "candidates")
        provenance_path = candidate / "provenance.json"
        review_path = candidate / "review.json"
        source_path = candidate / "source" / "synthetic_pitch.mp4"
        originals = {path: path.read_bytes() for path in (provenance_path, review_path, source_path)}
        invalid_provenance = json.loads(originals[provenance_path])
        invalid_provenance["status"] = "formal"
        invalid_review = json.loads(originals[review_path])
        invalid_review["overall_status"] = "review_complete"
        cases = (
            (provenance_path, b"not JSON", RECORD),
            (provenance_path, json.dumps(invalid_provenance).encode(), RECORD),
            (review_path, json.dumps(invalid_review).encode(), RECORD),
            (source_path, b"changed source", RECORD),
            (None, None, {**RECORD, "item": "not_required"}),
        )
        for index, (path, data, arguments) in enumerate(cases):
            for original_path, original_data in originals.items():
                original_path.write_bytes(original_data)
            if path is not None:
                path.write_bytes(data)
            before = self._inventory(candidate)
            with self.subTest(case=index), \
                    patch.object(review, "_review_lock", wraps=review._review_lock) as lock, \
                    self.assertRaises(ValueError):
                review.record_review(candidate, **arguments)
            lock.assert_not_called()
            self._assert_no_mutation(candidate, before)

    def test_evidence_is_revalidated_after_lock_acquisition(self):
        candidate = self._candidate(self.output / "candidates")
        before = (candidate / "review.json").read_bytes()
        original_lock = review._review_lock

        @contextmanager
        def change_source_after_lock(root):
            with original_lock(root):
                (root / "source" / "synthetic_pitch.mp4").write_bytes(b"changed while acquiring lock")
                yield

        with patch.object(review, "_review_lock", change_source_after_lock), \
                self.assertRaisesRegex(ValueError, "SHA-256"):
            review.record_review(candidate, **RECORD)
        self.assertEqual((candidate / "review.json").read_bytes(), before)
        self.assertFalse((candidate / ".review.lock").exists())
        self.assertEqual(list(candidate.glob(".review.*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
