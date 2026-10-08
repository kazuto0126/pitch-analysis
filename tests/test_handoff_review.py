import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pitch_analysis.handoff.review import blank_review, load_review, record_review


class HandoffReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "candidate"
        (self.root / "source").mkdir(parents=True)
        self.video = self.root / "source" / "original_pitch.mp4"
        self.delivery = self.root / "source" / "original_pitch.json"
        self.video.write_bytes(b"synthetic source video bytes")
        self.delivery.write_bytes(b'{"pitch_id": "original_pitch"}\n')
        self.provenance = {
            "schema": "handoff-candidate-v1",
            "internal_pitch_id": "candidate_000001",
            "original_pitch_id": "original_pitch",
            "original_batch_id": "delivery_batch",
            "status": "candidate",
            "video": {"file": self.video.name, "sha256": hashlib.sha256(self.video.read_bytes()).hexdigest()},
            "delivery_json": {"file": self.delivery.name, "sha256": hashlib.sha256(self.delivery.read_bytes()).hexdigest()},
            "required_reviews": ["scoreboard_hidden", "preparation_complete", "follow_through_complete"],
            "pitcher_mapping": None,
            "throws": None,
            "blockers": ["pitcher mapping unconfirmed", "throwing side unconfirmed"],
        }
        self._write("provenance.json", self.provenance)
        self._write("review.json", blank_review(self.provenance))

    def _write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _record(self, item="scoreboard_hidden", **changes):
        arguments = {
            "item": item,
            "reviewer": "Local reviewer",
            "reviewed_at_utc": "2026-10-08T17:30:00+08:00",
            "conclusion": "pass",
            "note": "I inspected this item in the copied source video.",
        }
        arguments.update(changes)
        return record_review(self.root, **arguments)

    def test_blank_review_has_no_human_findings_and_binds_all_ids_and_hashes(self):
        saved = copy.deepcopy(self.provenance)
        result = blank_review(self.provenance)
        self.assertEqual(saved, self.provenance)
        self.assertEqual(result["overall_status"], "pending")
        for key in ("internal_pitch_id", "original_pitch_id", "original_batch_id"):
            self.assertEqual(result[key], self.provenance[key])
        self.assertEqual(result["source_video_sha256"], self.provenance["video"]["sha256"])
        self.assertEqual(result["source_json_sha256"], self.provenance["delivery_json"]["sha256"])
        self.assertEqual(list(result["items"]), self.provenance["required_reviews"])
        self.assertTrue(all(entry == {"history": [], "latest": None} for entry in result["items"].values()))
        self.assertEqual(load_review(self.root), result)

    def test_explicit_review_normalizes_timezone_and_preserves_submission_history(self):
        first = self._record(conclusion="fail", note="The scoreboard was visible.")
        self.assertEqual(first["overall_status"], "rejected")
        self.assertEqual(first["items"]["scoreboard_hidden"]["latest"]["reviewed_at_utc"], "2026-10-08T09:30:00Z")
        second = self._record(
            reviewer="Second reviewer", reviewed_at_utc="2026-10-07T12:05:04.123456Z",
            note="I checked the original crop and verified the scoreboard is hidden.",
        )
        history = second["items"]["scoreboard_hidden"]["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0], first["items"]["scoreboard_hidden"]["latest"])
        self.assertEqual(history[1]["reviewed_at_utc"], "2026-10-07T12:05:04.123456Z")
        self.assertEqual(second["items"]["scoreboard_hidden"]["latest"], history[-1])
        self.assertEqual(second["overall_status"], "pending")
        self.assertEqual(load_review(self.root), second)

    def test_conclusions_retain_uncertainty_and_failure_takes_priority(self):
        self._record(conclusion="uncertain")
        self.assertEqual(load_review(self.root)["overall_status"], "pending")
        self._record("preparation_complete")
        self._record("follow_through_complete", conclusion="not_observable", note="The clip ends before follow-through.")
        review = load_review(self.root)
        self.assertEqual(review["overall_status"], "requires_review")
        self.assertEqual(review["items"]["follow_through_complete"]["latest"]["conclusion"], "not_observable")
        self._record("preparation_complete", conclusion="fail")
        self.assertEqual(load_review(self.root)["overall_status"], "rejected")

    def test_all_pass_does_not_promote_candidate_or_fill_unknown_identity(self):
        provenance_before = (self.root / "provenance.json").read_bytes()
        sources_before = {path.name: path.read_bytes() for path in (self.video, self.delivery)}
        for item in self.provenance["required_reviews"]:
            self._record(item)
        self.assertEqual(load_review(self.root)["overall_status"], "review_complete")
        self.assertEqual((self.root / "provenance.json").read_bytes(), provenance_before)
        self.assertEqual({path.name: path.read_bytes() for path in (self.video, self.delivery)}, sources_before)
        unchanged = json.loads(provenance_before)
        self.assertEqual(unchanged["status"], "candidate")
        self.assertIsNone(unchanged["pitcher_mapping"])
        self.assertIsNone(unchanged["throws"])
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["provenance.json", "review.json", "source"])

    def test_invalid_human_fields_never_write(self):
        before = (self.root / "review.json").read_bytes()
        invalid = [
            {"reviewer": " "}, {"reviewer": None}, {"note": "\n\t"}, {"note": 1},
            {"reviewed_at_utc": "2026-10-08T09:30:00"},
            {"reviewed_at_utc": "2026-10-08"}, {"reviewed_at_utc": "not a date"},
            {"reviewed_at_utc": "2026-10-08 09:30:00Z"}, {"reviewed_at_utc": None},
            {"conclusion": "PASS"}, {"conclusion": "pending"}, {"conclusion": True},
            {"item": "unknown_item"}, {"item": ""},
        ]
        for arguments in invalid:
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                self._record(**arguments)
            self.assertEqual((self.root / "review.json").read_bytes(), before)
            self.assertFalse((self.root / ".review.lock").exists())

    def test_every_load_and_record_rejects_source_tampering_or_missing_file(self):
        before = (self.root / "review.json").read_bytes()
        for path in (self.video, self.delivery):
            original = path.read_bytes()
            path.write_bytes(original + b" changed")
            with self.subTest(path=path.name), self.assertRaisesRegex(ValueError, "SHA-256"):
                load_review(self.root)
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                self._record()
            self.assertEqual((self.root / "review.json").read_bytes(), before)
            path.write_bytes(original)
        self.delivery.unlink()
        with self.assertRaisesRegex(ValueError, "inside candidate_dir"):
            load_review(self.root)
        with self.assertRaisesRegex(ValueError, "inside candidate_dir"):
            self._record()

    def test_review_identity_hash_and_required_item_binding_are_checked(self):
        original = load_review(self.root)
        for field in ("internal_pitch_id", "original_pitch_id", "original_batch_id", "source_video_sha256", "source_json_sha256"):
            changed = copy.deepcopy(original)
            changed[field] = "changed"
            self._write("review.json", changed)
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                load_review(self.root)
        for direction in ("missing", "extra"):
            changed = copy.deepcopy(original)
            if direction == "missing":
                del changed["items"]["preparation_complete"]
            else:
                changed["items"]["not_required"] = {"history": [], "latest": None}
            self._write("review.json", changed)
            with self.subTest(direction=direction), self.assertRaisesRegex(ValueError, "all required_reviews"):
                load_review(self.root)
        self._write("review.json", original)
        provenance = copy.deepcopy(self.provenance)
        provenance["original_batch_id"] = "different_batch"
        self._write("provenance.json", provenance)
        with self.assertRaisesRegex(ValueError, "original_batch_id"):
            load_review(self.root)

    def test_changed_provenance_hash_cannot_rebind_an_existing_review(self):
        self.video.write_bytes(b"replacement video")
        provenance = copy.deepcopy(self.provenance)
        provenance["video"]["sha256"] = hashlib.sha256(self.video.read_bytes()).hexdigest()
        self._write("provenance.json", provenance)
        with self.assertRaisesRegex(ValueError, "source_video_sha256"):
            load_review(self.root)
        with self.assertRaisesRegex(ValueError, "source_video_sha256"):
            self._record()

    def test_malformed_or_inconsistent_review_history_is_rejected(self):
        valid = self._record()
        malformed = []
        changed = copy.deepcopy(valid)
        changed["schema"] = "other"
        malformed.append(changed)
        changed = copy.deepcopy(valid)
        changed["overall_status"] = "review_complete"
        malformed.append(changed)
        changed = copy.deepcopy(valid)
        changed["items"]["scoreboard_hidden"]["latest"] = None
        malformed.append(changed)
        changed = copy.deepcopy(valid)
        changed["items"]["scoreboard_hidden"]["history"][0]["reviewer"] = ""
        malformed.append(changed)
        changed = copy.deepcopy(valid)
        changed["items"]["scoreboard_hidden"]["history"][0]["reviewed_at_utc"] = "2026-10-08T09:30:00"
        malformed.append(changed)
        changed = copy.deepcopy(valid)
        changed["items"]["scoreboard_hidden"]["history"][0].pop("note")
        malformed.append(changed)
        for index, changed in enumerate(malformed):
            self._write("review.json", changed)
            with self.subTest(index=index), self.assertRaises(ValueError):
                load_review(self.root)
            with self.assertRaises(ValueError):
                self._record()
        self.assertFalse((self.root / ".review.lock").exists())

    def test_blank_requires_candidate_schema_and_complete_local_review_requirements(self):
        cases = []
        for field, value in (("schema", "other"), ("status", "formal"), ("internal_pitch_id", None)):
            changed = copy.deepcopy(self.provenance)
            changed[field] = value
            cases.append(changed)
        for required in ([], ["preparation_complete"], ["preparation_complete", "follow_through_complete", "preparation_complete"]):
            changed = copy.deepcopy(self.provenance)
            changed["required_reviews"] = required
            cases.append(changed)
        for name in ("../outside.mp4", "..\\outside.mp4", "D:outside.mp4", ".", ""):
            changed = copy.deepcopy(self.provenance)
            changed["video"]["file"] = name
            cases.append(changed)
        changed = copy.deepcopy(self.provenance)
        changed["video"]["sha256"] = "not a hash"
        cases.append(changed)
        for index, provenance in enumerate(cases):
            with self.subTest(index=index), self.assertRaises(ValueError):
                blank_review(provenance)

    def test_lock_serializes_writes_without_deleting_an_existing_lock(self):
        lock = self.root / ".review.lock"
        lock.write_text("another writer", encoding="utf-8")
        before = (self.root / "review.json").read_bytes()
        with self.assertRaisesRegex(FileExistsError, "locked"):
            self._record()
        self.assertEqual(lock.read_text(encoding="utf-8"), "another writer")
        self.assertEqual((self.root / "review.json").read_bytes(), before)
        lock.unlink()
        self._record()
        self.assertFalse(lock.exists())

    def test_atomic_replace_failure_preserves_previous_review_and_cleans_only_owned_files(self):
        before = (self.root / "review.json").read_bytes()
        unrelated = self.root / ".review.unrelated.tmp"
        unrelated.write_text("leave this file", encoding="utf-8")
        with patch("pitch_analysis.handoff.review.os.replace", side_effect=OSError("synthetic replacement failure")):
            with self.assertRaisesRegex(OSError, "synthetic replacement failure"):
                self._record()
        self.assertEqual((self.root / "review.json").read_bytes(), before)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "leave this file")
        self.assertEqual(list(self.root.glob(".review.*.tmp")), [unrelated])
        self.assertFalse((self.root / ".review.lock").exists())
        self.assertEqual(load_review(self.root)["overall_status"], "pending")

    def test_source_symlink_outside_candidate_is_rejected_when_supported(self):
        outside = Path(self.temporary.name) / "outside.mp4"
        outside.write_bytes(self.video.read_bytes())
        self.video.unlink()
        try:
            self.video.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("creating symbolic links is unavailable")
        with self.assertRaisesRegex(ValueError, "inside candidate_dir"):
            load_review(self.root)
        with self.assertRaisesRegex(ValueError, "inside candidate_dir"):
            self._record()
        self.assertEqual(outside.read_bytes(), b"synthetic source video bytes")


if __name__ == "__main__":
    unittest.main()
