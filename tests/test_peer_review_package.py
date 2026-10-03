"""Portable export contracts, using synthetic evidence and no model runs."""
import csv
import importlib.util
import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path


spec = importlib.util.spec_from_file_location(
    "export_peer_review_package", Path(__file__).resolve().parents[1] / "scripts" / "export_peer_review_package.py"
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class PeerReviewPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.baseline = self.root / "baseline"
        self.source = self.root / "source"
        self.helper = self.baseline / "review_helper_synthetic"
        self.source.mkdir()
        self.output = self.root / "portable_review"
        self.canonical_bytes = {}
        for pitch in ("pitch_003", "pitch_005"):
            self.make_pitch(pitch, 3)

    def make_pitch(self, pitch, count):
        source = self.source / f"{pitch}.mp4"
        source.write_bytes(f"synthetic video bytes for {pitch}".encode())
        canonical = exporter.expand_blank_review(exporter.blank_ground_truth(source, pitch, count))
        canonical["annotation_status"] = "in_progress"
        canonical["provenance"]["reviewer"] = "SECRET_REVIEWER"
        canonical["notes"] = ["SECRET_HUMAN_NOTES"]
        canonical["labels"]["pitcher_correctly_selected"] = True
        canonical["labels"]["events"]["leg_lift"] = {
            "status": "uncertain", "frame_index": 1, "note": "SECRET_EVENT_ANSWER"
        }
        target = self.baseline / "ground_truth" / pitch / "ground_truth.json"
        target.parent.mkdir(parents=True)
        exporter.write_json(target, canonical)
        self.canonical_bytes[pitch] = target.read_bytes()
        folder = self.helper / pitch
        (folder / "browser_playback").mkdir(parents=True)
        (folder / "browser_playback" / "source_browser.mp4").write_bytes(source.read_bytes())
        (folder / "browser_playback" / "overlay_browser.mp4").write_bytes(b"existing synthetic overlay")
        (folder / "browser_playback" / "server.pid").write_text("12345")
        (folder / "browser_playback" / "playback_manifest.json").write_text('{"path":"D:\\\\PRIVATE"}')
        (folder / "review_all.html").write_text("SECRET_HUMAN_NOTES absolute path D:/PRIVATE http://localhost:99")
        (folder / "frames").mkdir()
        (folder / "contact_sheets").mkdir()
        for index in range(count):
            (folder / "frames" / f"frame_{index:04d}.jpg").write_bytes(f"synthetic existing pair {index}".encode())
        for index in range(0, count, 12):
            (folder / "contact_sheets" / f"frames_{index:04d}_{min(index+11,count-1):04d}.jpg").write_bytes(b"synthetic existing sheet")
        self.write_rows(pitch, [{"frame_index": str(i), "timestamp_ms": i * 1000/30, "selection_status": "selected",
                                "model_warnings": "", **{name: "observed" for name in exporter.JOINT_ROLES}} for i in range(count)])

    def write_rows(self, pitch, rows):
        with (self.helper / pitch / "frame_index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=exporter.CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    def export(self, **overrides):
        options = {"full_review": ["pitch_003"], "events_supplement": ["pitch_005"], "verify_video_timing": False}
        options.update(overrides)
        return exporter.export_package(self.baseline, self.source, self.output, **options)

    def test_blank_templates_preserve_source_binding_and_canonical_files(self):
        manifest = self.export(producer_git_commit="a02f1900d4b3eb77214cbf12bdfc37eb98fa1153")
        self.assertEqual(manifest["schema_version"], "peer-review-package-v1")
        self.assertEqual(manifest["frame_index_base"], 0)
        self.assertEqual([task["task_scope"] for task in manifest["tasks"]], ["full_review", "events_supplement"])
        for task in manifest["tasks"]:
            pitch = task["pitch_id"]
            blank = exporter.read_json(self.output / task["ground_truth_path"])
            self.assertEqual(blank["annotation_status"], "unreviewed")
            self.assertEqual(blank["review_profile"], "phase2_full_review")
            self.assertIsNone(blank["provenance"]["reviewer"])
            self.assertIsNone(blank["provenance"]["reviewed_at_utc"])
            self.assertEqual(blank["notes"], [])
            self.assertTrue(all(value is None for name, value in blank["labels"].items() if name != "events"))
            self.assertTrue(all(value is None for value in blank["labels"]["events"].values()))
            source_asset = task["assets"]["source_video"]
            packaged_source = self.output / source_asset["path"]
            self.assertEqual(packaged_source.name, blank["source_video"]["filename"])
            exporter.expand_blank_review(blank)  # validates the existing canonical schema
            self.assertEqual(exporter.digest(packaged_source), blank["source_video"]["sha256"])
            self.assertEqual(task["source_video"], blank["source_video"])
            self.assertEqual(exporter.digest(self.output / task["ground_truth_path"]), task["ground_truth_template_sha256"])
            self.assertEqual((self.baseline / "ground_truth" / pitch / "ground_truth.json").read_bytes(), self.canonical_bytes[pitch])
            self.assertEqual(task["frame_pair_count"], 3)
            self.assertEqual(task["contact_sheet_count"], 1)
        for path in self.output.rglob("*"):
            if path.suffix in (".json", ".html", ".md", ".csv", ".py"):
                self.assertNotIn("SECRET_", path.read_text(encoding="utf-8-sig"))
        with zipfile.ZipFile(self.output.with_suffix(".zip")) as package_zip:
            names = package_zip.namelist()
            self.assertTrue(all(name.startswith("portable_review/") for name in names))
            self.assertFalse(any("server.pid" in name or "playback_manifest" in name for name in names))
            self.assertIn("portable_review/pitch_003/browser_playback/pitch_003.mp4", names)

    def test_html_links_are_relative_and_resolve_after_package_is_moved(self):
        self.export()
        moved = self.root / "other computer" / "review"
        moved.parent.mkdir()
        self.output.rename(moved)
        for page in moved.rglob("*.html"):
            body = page.read_text(encoding="utf-8")
            self.assertNotIn("localhost", body)
            self.assertNotIn(self.root.as_posix(), body)
            self.assertNotIn("D:/", body)
            self.assertNotIn("fetch(", body)
            for reference in re.findall(r'(?:href|src)="([^"]+)"', body):
                self.assertFalse(reference.startswith(("/", "http:", "https:", "file:")), reference)
                self.assertTrue((page.parent / reference).is_file(), f"Broken link: {page}: {reference}")
        self.assertIn("模型狀態", (moved / "pitch_003" / "review_all.html").read_text(encoding="utf-8"))
        self.assertIn("127.0.0.1", (moved / "serve_review.py").read_text(encoding="utf-8"))

    def test_refuses_existing_directory_or_zip_without_modifying_them(self):
        for kind in ("directory", "zip"):
            with self.subTest(kind=kind):
                if kind == "directory":
                    self.output.mkdir()
                    sentinel = self.output / "keep.txt"
                else:
                    sentinel = self.output.with_suffix(".zip")
                sentinel.write_bytes(b"existing user work")
                with self.assertRaises(FileExistsError):
                    self.export()
                self.assertEqual(sentinel.read_bytes(), b"existing user work")
                sentinel.unlink()
                if kind == "directory":
                    self.output.rmdir()

    def test_missing_frame_or_contact_sheet_fails_before_any_export(self):
        frame = self.helper / "pitch_003" / "frames" / "frame_0001.jpg"
        saved = frame.read_bytes()
        frame.unlink()
        with self.assertRaisesRegex(ValueError, "Missing frame pair"):
            self.export()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_suffix(".zip").exists())
        frame.write_bytes(saved)
        (self.helper / "pitch_005" / "contact_sheets" / "frames_0000_0002.jpg").unlink()
        with self.assertRaisesRegex(ValueError, "Missing contact sheet"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_wrong_source_hash_or_unordered_csv_is_rejected(self):
        browser_source = self.helper / "pitch_003" / "browser_playback" / "source_browser.mp4"
        original = browser_source.read_bytes()
        browser_source.write_bytes(b"different source")
        with self.assertRaisesRegex(ValueError, "Browser source copy differs"):
            self.export()
        browser_source.write_bytes(original)
        rows = exporter.read_frame_index(self.helper / "pitch_003" / "frame_index.csv", 3)
        rows[0], rows[1] = rows[1], rows[0]
        self.write_rows("pitch_003", rows)
        with self.assertRaisesRegex(ValueError, "ordered frames"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_only_explicit_nonoverlapping_task_scopes_can_be_exported(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            self.export(full_review=[], events_supplement=[])
        with self.assertRaisesRegex(ValueError, "only one task scope"):
            self.export(events_supplement=["pitch_003"])
        with self.assertRaisesRegex(ValueError, "Invalid pitch ID"):
            self.export(full_review=["../pitch_003"], events_supplement=[])
        self.assertFalse(self.output.exists())

    def test_notes_template_placeholders_and_input_anatomy_are_portable(self):
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "REVIEW_NOTES_TEMPLATE.md").write_text("{{PITCH_ID}} {{TASK_SCOPE}} {{TOTAL_FRAMES}} 0–{{LAST_FRAME}}", encoding="utf-8")
        (docs / "START_HERE.md").write_text("Generic reusable guide", encoding="utf-8")
        exporter.write_json(self.source / "pitch_003.json", {"schema_version": "pitch-input-v1", "pitch_id": "pitch_003",
            "pitcher": {"id": "synthetic", "display_name": "Synthetic pitcher", "throws": "RIGHT", "note": "SECRET_INPUT_NOTE"},
            "video": {"file": "C:/private/path.mp4", "horizontal_mirror": False}})
        manifest = self.export(documentation_root=docs)
        self.assertEqual((self.output / "pitch_003" / "REVIEW_NOTES.md").read_text(encoding="utf-8"), "pitch_003 full_review 3 0–2")
        self.assertEqual((self.output / "START_HERE.md").read_text(encoding="utf-8"), "Generic reusable guide")
        self.assertEqual(manifest["tasks"][0]["input_metadata"]["pitcher"]["throws"], "RIGHT")
        self.assertNotIn("SECRET_INPUT_NOTE", json.dumps(manifest))
        self.assertNotIn("C:/private", json.dumps(manifest))
        self.assertIn("右手投球", (self.output / "pitch_003" / "review_all.html").read_text(encoding="utf-8"))

    def test_video_timing_rejects_truncated_existing_overlay(self):
        import cv2
        import numpy as np

        source, overlay = self.root / "decoded_source.avi", self.root / "decoded_overlay.avi"
        for path, frames in ((source, 3), (overlay, 2)):
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 30, (64, 64))
            self.assertTrue(writer.isOpened())
            for frame in range(frames):
                writer.write(np.full((64, 64, 3), frame * 50, np.uint8))
            writer.release()
        rows = exporter.read_frame_index(self.helper / "pitch_003" / "frame_index.csv", 3)
        with self.assertRaisesRegex(ValueError, "Missing overlay decoded frame"):
            exporter.verify_timing(source, overlay, rows)
        result = exporter.verify_timing(source, source, rows)
        self.assertEqual(result["source"]["decoded_frames"], 3)
        self.assertAlmostEqual(result["source"]["fps"], 30)


if __name__ == "__main__":
    unittest.main()
