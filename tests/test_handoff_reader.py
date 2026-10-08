"""Exercise read-only handoff intake with synthetic, contract-valid deliveries."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
import stat
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pitch_analysis.handoff import reader
from pitch_analysis.handoff.contract import CHECK_NAMES, HandoffError
from pitch_analysis.handoff.review import record_review


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def inventory(root: Path) -> dict:
    """Include every source entry, its contents, and its modification time."""
    return {
        str(path.relative_to(root)): (
            "directory" if path.is_dir() else "file",
            None if path.is_dir() else digest(path.read_bytes()),
            path.stat().st_mtime_ns,
        )
        for path in root.rglob("*")
    }


def valid_timing(path, metadata, *, ffprobe_path=None) -> dict:
    """A pure replacement for decoding synthetic MP4 fixture bytes."""
    count, fps = metadata["frame_count"], metadata["fps_float"]
    timestamps = [index * 1000 / fps for index in range(count)]
    origin = metadata["container_start_time_sec"] * 1000
    return {
        "frame_count": count,
        "fps": fps,
        "fractional_fps": metadata["fps"],
        "timestamps_ms": timestamps,
        "native_pts_ms": [origin + value for value in timestamps],
        "normalized_pts_ms": timestamps,
        "deviations_ms": [0.0] * count,
        "max_abs_deviation_ms": 0.0,
        "container_start_time_sec": metadata["container_start_time_sec"],
        "width": metadata["width"],
        "height": metadata["height"],
        "opencv_timestamps_ms": timestamps,
    }


class HandoffReaderTests(unittest.TestCase):
    def setUp(self):
        cache = ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="handoff_reader_", dir=cache)
        self.addCleanup(self.temporary.cleanup)
        self.sandbox = Path(self.temporary.name)
        self.project = self.sandbox / "project"
        self.project.mkdir()
        self.handoff = self.sandbox / "handoff"
        self.handoff.mkdir()
        self.contract_bytes = b"# Synthetic handoff CONTRACT\n\ncontract_version: 2\n"
        (self.handoff / "CONTRACT.md").write_bytes(self.contract_bytes)
        self.output = self.project / "data" / "intake" / "handoff"
        self.index_rows = []
        self.write_index()

    def write_index(self):
        (self.handoff / "index.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in self.index_rows),
            encoding="utf-8",
        )

    def add_batch(self, batch_id="MLB_Test_20261008", *, location=None, throws="R", unknown_game=False, declared_reviews=True):
        folder = self.handoff / (location or f"thrower/{batch_id}")
        folder.mkdir(parents=True)
        source = {
            "video_id": "synthetic-video", "title": "Synthetic delivery",
            "url": "https://example.invalid/synthetic", "channel": "Fixture channel",
            "source_type": "youtube",
        }
        game = {
            "season": "unknown" if unknown_game else 2026,
            "season_confidence": "unknown" if unknown_game else "high",
            "team": "unknown" if unknown_game else "A",
            "opponent": "unknown" if unknown_game else "B",
            "game_id": "unknown" if unknown_game else "fixture-game",
            "pitch_type": "unknown",
        }
        row = {
            "contract_version": 2, "batch_id": batch_id, "pitcher_name": "測試投手",
            "pitch_count": 3, "batch_json": (folder / "batch.json").relative_to(self.handoff).as_posix(),
            "created_utc": "2026-10-08T01:00:00Z",
        }
        batch = {
            "contract_version": 2, "batch_id": batch_id, "created_utc": row["created_utc"],
            "pitcher_name": row["pitcher_name"], "throws": throws,
            "view": "rear_centerfield_broadcast", "pitch_count": 3, "pitches": [],
            "source": source, "game": game, "viewing_video": None,
            "excluded_by_operator": [], "quality_warning": None, "warnings": [],
        }
        payloads = []
        for number in range(1, 4):
            pitch_id = f"{batch_id}_p{number:02d}"
            item = {"pitch_id": pitch_id, "video_file": pitch_id + ".mp4", "json": pitch_id + ".json"}
            batch["pitches"].append(item)
            video_bytes = f"synthetic MP4 payload for {pitch_id}".encode("utf-8")
            (folder / item["video_file"]).write_bytes(video_bytes)
            reviews = ["pitcher_identity", "full_body_in_frame"] if declared_reviews else []
            payload = {
                "contract_version": 2, "pitch_id": pitch_id, "batch_id": batch_id, "index": number,
                "pitcher_name": row["pitcher_name"], "throws": throws, "view": batch["view"],
                "video_file": item["video_file"], "sha256": digest(video_bytes),
                "video": {
                    "fps": "30000/1001", "fps_float": 30000 / 1001,
                    "constant_frame_rate": True, "frame_count": 6, "duration_sec": 6 * 1001 / 30000,
                    "width": 96, "height": 64, "codec": "h264", "pix_fmt": "yuv420p",
                    "square_pixels": True, "container_start_time_sec": 0.05,
                    "frame_time_rule": "decoded frame index / fps", "has_audio": False,
                },
                "source": {**source, "start_sec": 10.0, "end_sec": 10.2002},
                "game": copy.deepcopy(game),
                "pipeline_anchors_sec": {"motion_onset": 0.0, "motion_peak": 0.1, "settle": 0.2},
                "checks": {
                    name: {"status": "not_verified" if name in reviews else "verified_by_pipeline", "how": "Synthetic fixture declaration"}
                    for name in CHECK_NAMES
                },
                "requires_human_review": reviews,
            }
            payloads.append(payload)
            write_json(folder / item["json"], payload)
        write_json(folder / "batch.json", batch)
        self.index_rows.append(row)
        self.write_index()
        return {"folder": folder, "row": row, "batch": batch, "payloads": payloads}

    def save_pitch(self, fixture, position=0):
        item = fixture["batch"]["pitches"][position]
        write_json(fixture["folder"] / item["json"], fixture["payloads"][position])

    def run_import(self, **kwargs):
        return reader.import_handoff(
            self.handoff, kwargs.pop("intake_root", self.output),
            project_root=self.project, timing_verifier=kwargs.pop("timing_verifier", valid_timing),
            **kwargs,
        )

    def pitch_results(self, report):
        return [pitch for batch in report["results"] for pitch in batch.get("pitches", [])]

    def candidates(self):
        return sorted(self.output.glob("candidates/*/provenance.json"))

    def ledger_count(self, table):
        with closing(sqlite3.connect(self.output / "state.sqlite3")) as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_import_preserves_source_bytes_and_keeps_every_pitch_a_pending_candidate(self):
        fixture = self.add_batch()
        # An unindexed directory is deliberately not a deliverable.
        orphan = self.handoff / "unindexed" / "orphan"
        orphan.mkdir(parents=True)
        (orphan / "batch.json").write_bytes(b"invalid orphan metadata")
        (orphan / "orphan.mp4").write_bytes(b"not indexed")
        before = inventory(self.handoff)
        readonly_files = [path for path in self.handoff.rglob("*") if path.is_file()]
        try:
            for path in readonly_files:
                path.chmod(stat.S_IREAD)
            with patch("pitch_analysis.analysis.pitch.analyze_pitch", side_effect=AssertionError("intake must not analyze")):
                report = self.run_import()
        finally:
            for path in readonly_files:
                path.chmod(stat.S_IREAD | stat.S_IWRITE)
        self.assertEqual(inventory(self.handoff), before)
        self.assertEqual(report["batches_seen"], 1)
        self.assertEqual(report["imported_candidates"], 3)
        self.assertEqual(report["rejected"], 0)
        self.assertEqual(len(self.candidates()), 3)
        for result in self.pitch_results(report):
            candidate = Path(result["candidate_dir"])
            original_id = result["pitch_id"]
            self.assertRegex(result["internal_pitch_id"], r"\Ah_[a-f0-9]{64}\Z")
            provenance = json.loads((candidate / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["status"], "candidate")
            self.assertEqual(provenance["original_pitch_id"], original_id)
            self.assertEqual(provenance["original_batch_id"], fixture["batch"]["batch_id"])
            for field, suffix in (("video", ".mp4"), ("delivery_json", ".json")):
                copied = candidate / "source" / (original_id + suffix)
                self.assertEqual(copied.read_bytes(), (fixture["folder"] / copied.name).read_bytes())
                self.assertEqual(provenance[field]["file"], copied.name)
                self.assertEqual(provenance[field]["sha256"], digest(copied.read_bytes()))
            review = json.loads((candidate / "review.json").read_text(encoding="utf-8"))
            self.assertEqual(review["overall_status"], "pending")
            self.assertEqual(set(review["items"]), {"pitcher_identity", "full_body_in_frame", "preparation_complete", "follow_through_complete"})
            self.assertTrue(all(entry == {"history": [], "latest": None} for entry in review["items"].values()))
            timeline = json.loads((candidate / "timeline.json").read_text(encoding="utf-8"))
            self.assertEqual(timeline["fractional_fps"], "30000/1001")
            self.assertAlmostEqual(timeline["timestamps_ms"][1], 1001 / 30)
        self.assertEqual(self.ledger_count("batches"), 1)
        self.assertEqual(self.ledger_count("pitches"), 3)
        self.assertGreaterEqual(self.ledger_count("events"), 1)
        all_files = [path for path in self.output.rglob("*") if path.is_file()]
        self.assertFalse(any(path.name in {"pitch-input.json", "input.json", "pose_raw.csv", "features.csv"} for path in all_files))
        json_objects = [json.loads(path.read_text(encoding="utf-8")) for path in all_files if path.suffix == ".json"]
        self.assertFalse(any(value.get("schema_version") == "pitch-input-v1" for value in json_objects))
        contract_copies = [path for path in all_files if path.name == "CONTRACT.md"]
        self.assertTrue(contract_copies)
        self.assertTrue(all(path.read_bytes() == self.contract_bytes for path in contract_copies))
        self.assertIn(digest(self.contract_bytes), "\n".join(path.read_text(encoding="utf-8") for path in all_files if path.suffix == ".json"))

    def test_repeated_delivery_does_not_duplicate_candidates_or_pitch_ledger(self):
        self.add_batch()
        first = self.run_import()
        source_before = inventory(self.handoff)
        candidate_before = {str(path): path.read_bytes() for path in self.output.glob("candidates/**/*") if path.is_file()}
        second = self.run_import()
        self.assertEqual(first["imported_candidates"], 3)
        self.assertEqual(second["imported_candidates"], 0)
        self.assertEqual(second["already_imported"], 3)
        self.assertEqual(second["conflicts"], 0)
        self.assertEqual(self.ledger_count("batches"), 1)
        self.assertEqual(self.ledger_count("pitches"), 3)
        self.assertEqual(inventory(self.handoff), source_before)
        self.assertEqual({str(path): path.read_bytes() for path in self.output.glob("candidates/**/*") if path.is_file()}, candidate_before)

    def test_original_full_ids_are_stable_case_distinct_and_preserved(self):
        self.add_batch("MLB_LONG_SOURCE_20261008_123456", location="thrower/upper_case")
        self.add_batch("mlb_long_source_20261008_123456", location="thrower/lower_case")
        first = self.run_import()
        mapping = {item["pitch_id"]: item["internal_pitch_id"] for item in self.pitch_results(first)}
        self.assertEqual(len(mapping), 6)
        self.assertEqual(len(set(mapping.values())), 6)
        self.assertTrue(all(re.fullmatch(r"h_[a-f0-9]{64}", identifier) for identifier in mapping.values()))
        second = self.run_import(intake_root=self.project / "data" / "intake" / "second")
        self.assertEqual({item["pitch_id"]: item["internal_pitch_id"] for item in self.pitch_results(second)}, mapping)

    def test_unknown_game_and_throwing_side_remain_null_and_map_is_explicit(self):
        self.add_batch(throws="unknown", unknown_game=True, declared_reviews=False)
        self.run_import()
        for path in self.candidates():
            provenance = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsNone(provenance["throws"])
            self.assertTrue(all(value is None for value in provenance["context"].values()))
            self.assertIsNone(provenance["pitcher_id"])
            self.assertEqual(provenance["required_reviews"], ["preparation_complete", "follow_through_complete"])
        explicit = self.run_import(
            intake_root=self.project / "data" / "intake" / "mapped",
            pitcher_map={"測試投手": "known_pitcher"},
        )
        for result in self.pitch_results(explicit):
            provenance = json.loads((Path(result["candidate_dir"]) / "provenance.json").read_text(encoding="utf-8"))
            self.assertEqual(provenance["pitcher_id"], "known_pitcher")
            self.assertIsNone(provenance["throws"])

    def test_version_refusal_at_index_batch_and_pitch_is_logged(self):
        for position, level in enumerate(("index", "batch", "pitch")):
            with self.subTest(level=level):
                fixture = self.add_batch(f"VERSION_{level}")
                self.index_rows = [fixture["row"]]
                if level == "index":
                    fixture["row"]["contract_version"] = 1
                elif level == "batch":
                    fixture["batch"]["contract_version"] = 3
                    write_json(fixture["folder"] / "batch.json", fixture["batch"])
                else:
                    fixture["payloads"][0]["contract_version"] = 1
                    self.save_pitch(fixture)
                self.write_index()
                destination = self.project / "data" / "intake" / f"version_{position}"
                report = self.run_import(intake_root=destination)
                codes = [batch.get("code") for batch in report["results"]] + [item.get("code") for item in self.pitch_results(report)]
                self.assertIn("unsupported_contract_version", codes)
                self.assertGreaterEqual(report["rejected"], 1)
                self.assertEqual(report["imported_candidates"], 2 if level == "pitch" else 0)
                with closing(sqlite3.connect(destination / "state.sqlite3")) as connection:
                    self.assertGreater(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 0)

    def test_sha_mismatch_rejects_only_offending_pitch_before_timing(self):
        fixture = self.add_batch()
        fixture["payloads"][0]["sha256"] = "0" * 64
        self.save_pitch(fixture)
        verifier = unittest.mock.Mock(side_effect=valid_timing)
        report = self.run_import(timing_verifier=verifier)
        self.assertEqual(report["imported_candidates"], 2)
        self.assertEqual(report["rejected"], 1)
        rejected = [item for item in self.pitch_results(report) if item["status"] == "rejected"]
        self.assertEqual(rejected[0]["pitch_id"], fixture["payloads"][0]["pitch_id"])
        self.assertIn("sha", rejected[0]["code"].lower())
        self.assertEqual(verifier.call_count, 2)
        self.assertNotIn(fixture["payloads"][0]["video_file"], [Path(call.args[0]).name for call in verifier.call_args_list])

    def test_timing_refusal_and_non_cfr_metadata_leave_other_candidates_importable(self):
        fixture = self.add_batch()
        fixture["payloads"][0]["video"]["constant_frame_rate"] = False
        self.save_pitch(fixture)

        def verifier(path, metadata, *, ffprobe_path=None):
            if Path(path).name.endswith("_p02.mp4"):
                raise HandoffError("decoded_frame_count_mismatch", "Synthetic frame count differs")
            return valid_timing(path, metadata, ffprobe_path=ffprobe_path)

        report = self.run_import(timing_verifier=verifier)
        self.assertEqual(report["imported_candidates"], 1)
        self.assertEqual(report["rejected"], 2)
        self.assertEqual({item["code"] for item in self.pitch_results(report) if item["status"] == "rejected"}, {"not_constant_frame_rate", "decoded_frame_count_mismatch"})
        self.assertEqual(report["results"][0]["status"], "partial")
        repeat = self.run_import(timing_verifier=verifier)
        self.assertEqual(repeat["imported_candidates"], 0)
        self.assertEqual(repeat["already_imported"], 1)
        self.assertEqual(len(self.candidates()), 1)

    def test_immutable_pitch_json_and_video_changes_conflict_without_overwriting(self):
        for position, changed in enumerate(("pitch_json", "video", "batch_json", "index")):
            with self.subTest(changed=changed):
                fixture = self.add_batch(f"IMMUTABLE_{position}")
                self.index_rows = [fixture["row"]]
                self.write_index()
                destination = self.project / "data" / "intake" / f"immutable_{position}"
                self.run_import(intake_root=destination)
                before = inventory(destination / "candidates")
                if changed == "pitch_json":
                    fixture["payloads"][0]["checks"]["single_motion_event"]["how"] = "Changed immutable declaration"
                    self.save_pitch(fixture)
                elif changed == "video":
                    (fixture["folder"] / fixture["batch"]["pitches"][0]["video_file"]).write_bytes(b"changed immutable source")
                elif changed == "batch_json":
                    fixture["batch"]["warnings"] = ["Changed immutable batch declaration"]
                    write_json(fixture["folder"] / "batch.json", fixture["batch"])
                else:
                    fixture["row"]["note"] = "Changed immutable index declaration"
                    self.write_index()
                report = self.run_import(intake_root=destination)
                self.assertGreaterEqual(report["conflicts"], 1)
                self.assertEqual(report["imported_candidates"], 0)
                self.assertEqual(inventory(destination / "candidates"), before)

    def test_duplicate_batch_identity_at_another_location_is_a_conflict(self):
        first = self.add_batch("SHARED_BATCH", location="thrower/first")
        second = self.add_batch("SHARED_BATCH", location="thrower/second")
        second["payloads"][0]["checks"]["single_motion_event"]["how"] = "Conflicting second delivery"
        self.save_pitch(second)
        report = self.run_import()
        self.assertEqual(report["imported_candidates"], 3)
        self.assertGreaterEqual(report["conflicts"], 1)
        self.assertEqual(len(self.candidates()), 3)
        self.assertEqual(self.ledger_count("pitches"), 3)
        self.assertEqual(first["payloads"][0]["pitch_id"], second["payloads"][0]["pitch_id"])

    def test_missing_and_malformed_batches_are_reported_and_orphans_stay_ignored(self):
        missing = self.add_batch("MISSING_BATCH")
        malformed = self.add_batch("MALFORMED_BATCH")
        (missing["folder"] / "batch.json").unlink()
        (malformed["folder"] / "batch.json").write_bytes(b"{malformed")
        before = inventory(self.handoff)
        report = self.run_import()
        self.assertEqual(report["batches_seen"], 2)
        self.assertEqual(report["imported_candidates"], 0)
        self.assertEqual(report["rejected"], 2)
        self.assertTrue(all(batch.get("code") for batch in report["results"]))
        self.assertEqual(inventory(self.handoff), before)
        self.assertEqual(self.candidates(), [])

    def test_malformed_index_line_does_not_hide_a_valid_batch(self):
        self.add_batch()
        index_path = self.handoff / "index.jsonl"
        index_path.write_bytes(b"{invalid index line\n" + index_path.read_bytes())
        report = self.run_import()
        self.assertEqual(report["imported_candidates"], 3)
        self.assertGreaterEqual(report["rejected"], 1)
        self.assertTrue(any(batch.get("code") for batch in report["results"]))

    def test_recovery_after_candidate_rename_preserves_copies_and_human_review(self):
        self.add_batch()
        source_before = inventory(self.handoff)
        with patch.object(reader, "_persist_pitch", side_effect=RuntimeError("simulated interruption after rename")):
            with self.assertRaisesRegex(RuntimeError, "simulated interruption"):
                self.run_import()
        self.assertEqual(len(self.candidates()), 1)
        candidate = self.candidates()[0].parent
        record_review(
            candidate, item="pitcher_identity", reviewer="Synthetic human reviewer",
            reviewed_at_utc="2026-10-08T02:00:00Z", conclusion="uncertain",
            note="Preserve the finding across interrupted intake recovery.",
        )
        candidate_before = inventory(candidate)
        report = self.run_import()
        self.assertEqual(report["rejected"], 0)
        self.assertEqual(report["conflicts"], 0)
        self.assertEqual(len(self.candidates()), 3)
        self.assertEqual(self.ledger_count("pitches"), 3)
        self.assertEqual(inventory(candidate), candidate_before)
        self.assertEqual(inventory(self.handoff), source_before)

    def test_recovery_refuses_a_modified_candidate_instead_of_replacing_it(self):
        self.add_batch()
        with patch.object(reader, "_persist_pitch", side_effect=RuntimeError("simulated interruption")):
            with self.assertRaises(RuntimeError):
                self.run_import()
        candidate = self.candidates()[0].parent
        copied_video = next((candidate / "source").glob("*.mp4"))
        copied_video.write_bytes(b"tampered candidate after interruption")
        candidate_before = inventory(candidate)
        report = self.run_import()
        self.assertEqual(report["imported_candidates"], 2)
        self.assertGreaterEqual(report["conflicts"] + report["rejected"], 1)
        self.assertEqual(inventory(candidate), candidate_before)

    def test_recovery_cannot_accept_fabricated_timing_rehashed_into_provenance(self):
        self.add_batch()
        with patch.object(reader, "_persist_pitch", side_effect=RuntimeError("simulated interruption")):
            with self.assertRaises(RuntimeError):
                self.run_import()
        candidate = self.candidates()[0].parent
        provenance_path, timeline_path = candidate / "provenance.json", candidate / "timeline.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        forged = [index * 17.0 for index in range(timeline["frame_count"])]
        timeline.update(
            timestamps_ms=forged, native_pts_ms=[100.0 + value for value in forged],
            normalized_pts_ms=forged, deviations_ms=[0.0] * len(forged), max_abs_deviation_ms=0.0,
        )
        write_json(timeline_path, timeline)
        provenance["timeline_sha256"] = digest(timeline_path.read_bytes())
        write_json(provenance_path, provenance)
        before = inventory(candidate)
        verifier = unittest.mock.Mock(side_effect=valid_timing)
        report = self.run_import(timing_verifier=verifier)
        pitch = next(item for item in self.pitch_results(report) if item["pitch_id"] == provenance["original_pitch_id"])
        if pitch["status"] in {"imported", "already_imported"}:
            checked_names = [Path(call.args[0]).name for call in verifier.call_args_list]
            self.assertIn(provenance["video"]["file"], checked_names)
            verified = json.loads(timeline_path.read_text(encoding="utf-8"))
            expected = valid_timing(None, json.loads(next((candidate / "source").glob("*.json")).read_text(encoding="utf-8"))["video"])
            for field in ("timestamps_ms", "native_pts_ms", "normalized_pts_ms", "deviations_ms", "max_abs_deviation_ms"):
                self.assertEqual(verified[field], expected[field])
        else:
            self.assertEqual(pitch["code"], "local_candidate_conflict")
            self.assertEqual(inventory(candidate), before)
        self.assertEqual(len(self.candidates()), 3)

    def test_malformed_local_provenance_or_timeline_is_logged_and_other_pitches_continue(self):
        fixture = self.add_batch()
        for name in ("provenance.json", "timeline.json"):
            with self.subTest(local_file=name):
                destination = self.project / "data" / "intake" / name.replace(".json", "")
                with patch.object(reader, "_persist_pitch", side_effect=RuntimeError("simulated interruption")):
                    with self.assertRaises(RuntimeError):
                        self.run_import(intake_root=destination)
                candidate = next(destination.glob("candidates/*/provenance.json")).parent
                (candidate / name).write_bytes(b"[]\n")
                if name == "timeline.json":
                    provenance_path = candidate / "provenance.json"
                    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
                    provenance["timeline_sha256"] = digest((candidate / name).read_bytes())
                    write_json(provenance_path, provenance)
                report = self.run_import(intake_root=destination)
                self.assertEqual(report["conflicts"], 1)
                self.assertEqual(report["imported_candidates"], 2)
                rejected = next(item for item in self.pitch_results(report) if item["pitch_id"] == fixture["payloads"][0]["pitch_id"])
                self.assertEqual(rejected["code"], "local_candidate_conflict")
                with closing(sqlite3.connect(destination / "state.sqlite3")) as connection:
                    self.assertEqual(connection.execute(
                        "SELECT COUNT(*) FROM events WHERE code=?", ("local_candidate_conflict",),
                    ).fetchone()[0], 1)

    def test_ledger_refuses_joint_timeline_and_provenance_mutation(self):
        self.add_batch()
        self.run_import()
        candidate = self.candidates()[0].parent
        timeline_path, provenance_path = candidate / "timeline.json", candidate / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        pitch_id = provenance["original_pitch_id"]

        def immutable_hashes():
            with closing(sqlite3.connect(self.output / "state.sqlite3")) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute("SELECT * FROM pitches WHERE original_pitch_id=?", (pitch_id,)).fetchone()
                return {key: row[key] for key in row.keys() if "sha256" in key}

        ledger_before = immutable_hashes()
        self.assertIn(digest(timeline_path.read_bytes()), ledger_before.values())
        self.assertIn(digest(provenance_path.read_bytes()), ledger_before.values())
        timeline = json.loads(timeline_path.read_text(encoding="utf-8"))
        timeline["timestamps_ms"][1] += 10.0
        write_json(timeline_path, timeline)
        provenance["timeline_sha256"] = digest(timeline_path.read_bytes())
        write_json(provenance_path, provenance)
        before = inventory(candidate)
        report = self.run_import()
        self.assertEqual(report["conflicts"], 1)
        self.assertEqual(report["already_imported"], 2)
        self.assertEqual(report["imported_candidates"], 0)
        conflict = next(item for item in self.pitch_results(report) if item["pitch_id"] == pitch_id)
        self.assertEqual(conflict["code"], "local_candidate_conflict")
        self.assertEqual(immutable_hashes(), ledger_before)
        self.assertEqual(inventory(candidate), before)

    def test_index_and_pitch_path_escapes_are_refused_without_reading_external_files(self):
        fixture = self.add_batch()
        external = self.sandbox / "external" / "batch.json"
        external.parent.mkdir()
        external.write_bytes(b"must never become imported")
        fixture["row"]["batch_json"] = "../external/batch.json"
        self.write_index()
        report = self.run_import()
        self.assertGreaterEqual(report["rejected"], 1)
        self.assertEqual(report["imported_candidates"], 0)
        fixture["row"]["batch_json"] = (fixture["folder"] / "batch.json").relative_to(self.handoff).as_posix()
        fixture["batch"]["pitches"][0]["video_file"] = "../../../external/" + fixture["payloads"][0]["video_file"]
        fixture["payloads"][0]["video_file"] = fixture["batch"]["pitches"][0]["video_file"]
        self.save_pitch(fixture)
        write_json(fixture["folder"] / "batch.json", fixture["batch"])
        self.write_index()
        report = self.run_import(intake_root=self.project / "data" / "intake" / "escape_pitch")
        self.assertGreaterEqual(report["rejected"], 1)
        self.assertEqual(external.read_bytes(), b"must never become imported")

    def test_destination_must_be_inside_project_and_disjoint_from_handoff(self):
        self.add_batch()
        before = inventory(self.sandbox)
        forbidden = (
            self.sandbox / "outside", self.handoff / "intake", self.handoff,
            self.project, self.project.parent, self.project / "data" / "intake",
        )
        for destination in forbidden:
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    self.run_import(intake_root=destination)
        self.assertEqual(inventory(self.sandbox), before)

    def test_destination_ancestor_or_descendant_of_project_local_handoff_is_refused(self):
        self.add_batch()
        group = self.project / "data" / "intake" / "group"
        group.mkdir(parents=True)
        local_handoff = group / "delivery"
        self.handoff.rename(local_handoff)
        self.handoff = local_handoff
        before = inventory(self.project)
        for destination in (group, local_handoff, local_handoff / "imported"):
            with self.subTest(destination=destination):
                with self.assertRaises(ValueError):
                    self.run_import(intake_root=destination)
        self.assertEqual(inventory(self.project), before)


if __name__ == "__main__":
    unittest.main()
