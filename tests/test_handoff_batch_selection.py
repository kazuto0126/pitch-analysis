"""Select indexed delivery batches without touching unrelated batches."""
from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
import unittest
from contextlib import closing, redirect_stdout
from unittest.mock import patch

import test_handoff_reader as fixtures

from pitch_analysis.handoff import reader
from pitch_analysis.handoff.contract import HandoffError


class HandoffBatchSelectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.HandoffReaderTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_single_selection_never_opens_unselected_batch_and_repeat_deduplicates(self):
        excluded = self.fixture.add_batch("UNSELECTED")
        selected = self.fixture.add_batch("SELECTED")
        source_before = fixtures.inventory(self.fixture.handoff)
        original_source_file = reader._source_file

        def selected_source_only(root, relative):
            path = (root / relative).resolve()
            self.assertNotEqual(path, excluded["folder"].resolve())
            self.assertNotIn(excluded["folder"].resolve(), path.parents)
            return original_source_file(root, relative)

        with patch.object(reader, "_source_file", side_effect=selected_source_only):
            first = self.fixture.run_import(batch_ids=["SELECTED"])
            candidate_before = fixtures.inventory(self.fixture.output / "candidates")
            second = self.fixture.run_import(batch_ids=["SELECTED"])
        self.assertEqual(first["requested_batch_ids"], ["SELECTED"])
        self.assertEqual(first["batches_seen"], 1)
        self.assertEqual(first["results"][0]["index_line"], 2)
        self.assertEqual(first["imported_candidates"], 3)
        self.assertEqual(first["rejected"], 0)
        self.assertEqual(second["imported_candidates"], 0)
        self.assertEqual(second["already_imported"], 3)
        self.assertEqual(self.fixture.ledger_count("batches"), 1)
        self.assertEqual(self.fixture.ledger_count("pitches"), 3)
        with closing(sqlite3.connect(self.fixture.output / "state.sqlite3")) as connection:
            self.assertEqual(connection.execute("SELECT DISTINCT batch_id FROM events").fetchall(), [("SELECTED",)])
        for provenance_path in self.fixture.candidates():
            value = json.loads(provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(value["original_batch_id"], selected["batch"]["batch_id"])
            self.assertEqual(value["status"], "candidate")
        self.assertEqual(fixtures.inventory(self.fixture.output / "candidates"), candidate_before)
        self.assertEqual(fixtures.inventory(self.fixture.handoff), source_before)
        self.assertEqual(len(list((self.fixture.output / "batches").iterdir())), 1)

    def test_unknown_selected_id_refuses_before_any_import_or_local_mutation(self):
        self.fixture.add_batch("KNOWN")
        self.fixture.run_import(batch_ids=["KNOWN"])
        before = fixtures.inventory(self.fixture.sandbox)
        with self.assertRaises(HandoffError) as caught:
            self.fixture.run_import(batch_ids=["KNOWN", "NOT_INDEXED"])
        self.assertEqual(caught.exception.code, "batch_not_indexed")
        self.assertEqual(caught.exception.details["batch_ids"], ["NOT_INDEXED"])
        self.assertIn("NOT_INDEXED", str(caught.exception))
        self.assertEqual(fixtures.inventory(self.fixture.sandbox), before)

    def test_selection_still_rejects_unsupported_index_version(self):
        selected = self.fixture.add_batch("WRONG_VERSION")
        selected["row"]["contract_version"] = 3
        self.fixture.write_index()
        report = self.fixture.run_import(batch_ids=["WRONG_VERSION"])
        self.assertEqual(report["status"], "needs_attention")
        self.assertEqual(report["rejected"], 1)
        self.assertEqual(report["imported_candidates"], 0)
        self.assertEqual(report["results"][0]["code"], "unsupported_contract_version")
        self.assertEqual(self.fixture.ledger_count("pitches"), 0)

    def test_multiple_selections_are_exact_and_duplicate_request_does_not_import_twice(self):
        for identifier in ("ONE", "TWO", "THREE"):
            self.fixture.add_batch(identifier)
        report = self.fixture.run_import(batch_ids=["THREE", "ONE", "ONE"])
        self.assertEqual(report["requested_batch_ids"], ["ONE", "THREE"])
        self.assertEqual([value["batch_id"] for value in report["results"]], ["ONE", "THREE"])
        self.assertEqual(report["imported_candidates"], 6)
        self.assertEqual(self.fixture.ledger_count("batches"), 2)

    def test_empty_or_invalid_selection_is_not_an_unfiltered_import(self):
        self.fixture.add_batch("KNOWN")
        before = fixtures.inventory(self.fixture.sandbox)
        for value in ([], [""], [None], "KNOWN"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.fixture.run_import(batch_ids=value)
        self.assertEqual(fixtures.inventory(self.fixture.sandbox), before)

    def test_cli_repeatable_batch_id_and_default_are_forwarded(self):
        specification = importlib.util.spec_from_file_location(
            "handoff_batch_selection_cli", fixtures.ROOT / "scripts" / "import_handoff.py",
        )
        cli = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(cli)
        for arguments, expected in ((["import", "--batch-id", "ONE", "--batch-id", "TWO"], ["ONE", "TWO"]), (["import"], None)):
            with self.subTest(arguments=arguments), patch.object(cli, "import_handoff", return_value={"status": "complete"}) as importer, redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(arguments), 0)
                self.assertEqual(importer.call_args.kwargs["batch_ids"], expected)


if __name__ == "__main__":
    unittest.main()
