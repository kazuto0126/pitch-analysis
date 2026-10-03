"""Manual annotation exports use decoded source pixels, with no pose inference."""
import csv
import importlib.util
import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np


spec = importlib.util.spec_from_file_location(
    "export_manual_pose_package", Path(__file__).resolve().parents[1] / "scripts" / "export_manual_pose_package.py"
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class ManualPosePackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source_folder = self.root / "source"
        self.source_folder.mkdir()
        self.source, self.metadata, self.decoded_frames = self.make_video("pitch_003", 4)
        self.metadata_path = self.root / "video_metadata.json"
        exporter.write_json(self.metadata_path, self.metadata)
        self.output = self.root / "manual_review"
        self.docs = self.root / "docs"
        self.docs.mkdir()
        (self.docs / "START_HERE.md").write_text("# CVAT manual annotation\nUse original PNGs and the blank skeleton label configuration.\n", encoding="utf-8")

    def make_video(self, pitch, count):
        path = self.source_folder / f"{pitch}.mp4"
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 25, (64, 48))
        self.assertTrue(writer.isOpened(), "OpenCV test MP4 writer must be available")
        try:
            for index in range(count):
                frame = np.zeros((48, 64, 3), dtype=np.uint8)
                frame[:] = (index * 31, index * 17, index * 11)
                frame[4 + index:12 + index, 9:23] = (27, 190, 233)
                writer.write(frame)
        finally:
            writer.release()
        decoded_frames = []
        timestamps = []
        capture = cv2.VideoCapture(str(path))
        try:
            fps = capture.get(cv2.CAP_PROP_FPS)
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                decoded_frames.append(frame)
                timestamps.append(capture.get(cv2.CAP_PROP_POS_MSEC))
        finally:
            capture.release()
        self.assertEqual(len(decoded_frames), count)
        origin = timestamps[0]
        metadata = {"schema_version": "video-validation-v1", "status": "validated", "path": str(path),
                    "sha256": exporter.digest(path), "fps": fps, "frame_count": count,
                    "width": 64, "height": 48, "timestamps_ms": [stamp - origin for stamp in timestamps]}
        exporter.write_json(path.with_suffix(".json"), {
            "schema_version": "pitch-input-v1", "pitch_id": pitch,
            "pitcher": {"id": "synthetic", "display_name": "Synthetic Pitcher", "throws": "RIGHT"},
            "video": {"file": path.name, "camera_view": "rear_centerfield_broadcast", "horizontal_mirror": False},
            "notes": ["PRIVATE input notes must not be copied"],
        })
        return path, metadata, decoded_frames

    def export(self, **overrides):
        options = {"documentation_root": self.docs}
        options.update(overrides)
        return exporter.export_package(self.source, self.metadata_path, self.output, **options)

    def write_metadata(self, metadata):
        self.metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    def assert_no_export(self):
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.with_name(self.output.name + ".zip").exists())
        self.assertFalse(list(self.root.glob(".manual_pose_*")))

    def make_prior_package(self):
        peer = exporter._peer_exporter()
        source_005, metadata_005, frames_005 = self.make_video("pitch_005", 3)
        baseline = self.root / "baseline"
        helper = baseline / "review_helper_synthetic"
        for source, metadata, decoded in ((self.source, self.metadata, self.decoded_frames), (source_005, metadata_005, frames_005)):
            pitch = source.stem
            canonical = peer.expand_blank_review(peer.blank_ground_truth(source, pitch, len(decoded)))
            canonical["annotation_status"] = "in_progress"
            canonical["provenance"]["reviewer"] = "HSU_PRIVATE_REVIEWER"
            canonical["notes"] = ["HSU_PRIVATE_NOTE"]
            canonical["labels"]["events"]["leg_lift"] = {"status": "confirmed", "frame_index": 1, "note": "HSU_PRIVATE_ANSWER"}
            target = baseline / "ground_truth" / pitch / "ground_truth.json"
            target.parent.mkdir(parents=True)
            peer.write_json(target, canonical)
            folder = helper / pitch
            (folder / "browser_playback").mkdir(parents=True)
            (folder / "frames").mkdir()
            (folder / "contact_sheets").mkdir()
            (folder / "browser_playback" / "source_browser.mp4").write_bytes(source.read_bytes())
            (folder / "browser_playback" / "overlay_browser.mp4").write_bytes(b"existing synthetic overlay")
            for index, frame in enumerate(decoded):
                self.assertTrue(cv2.imwrite(str(folder / "frames" / f"frame_{index:04d}.jpg"), frame))
            self.assertTrue(cv2.imwrite(str(folder / "contact_sheets" / f"frames_0000_{len(decoded)-1:04d}.jpg"), decoded[0]))
            with (folder / "frame_index.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=peer.CSV_FIELDS)
                writer.writeheader()
                for index, stamp in enumerate(metadata["timestamps_ms"]):
                    writer.writerow({"frame_index": index, "timestamp_ms": stamp, "selection_status": "selected",
                                     "model_warnings": "", **{role: "observed" for role in peer.JOINT_ROLES}})
        prior = self.root / "prior_portable"
        peer.export_package(baseline, self.source_folder, prior, full_review=["pitch_003"],
                            events_supplement=["pitch_005"], verify_video_timing=False)
        return prior, baseline

    def test_complete_original_pixels_timing_hashes_and_portable_archives(self):
        original = self.source.read_bytes()
        manifest = self.export(producer_git_commit="abc1234")
        self.assertEqual(manifest["schema_version"], "manual-pose-package-v1")
        self.assertEqual(manifest["source_video"], {"pitch_id": "pitch_003", "filename": "pitch_003.mp4",
            "sha256": exporter.digest(self.source), "total_frames": 4, "frame_index_base": 0})
        self.assertEqual((manifest["image_width"], manifest["image_height"]), (64, 48))
        self.assertEqual(manifest["joint_names"], list(exporter.JOINT_NAMES))
        self.assertEqual(manifest["producer_git_commit"], "abc1234")
        self.assertEqual(manifest["video_metadata_sha256"], exporter.digest(self.metadata_path))
        self.assertEqual((self.output / "pitch_003.mp4").read_bytes(), original)
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual([row["frame_index"] for row in manifest["frames"]], list(range(4)))
        self.assertEqual([row["timestamp_ms"] for row in manifest["frames"]], self.metadata["timestamps_ms"])
        self.assertEqual(len(list((self.output / "raw_frames").iterdir())), 4)
        with zipfile.ZipFile(self.output / "raw_frames_pitch_003.zip") as images:
            self.assertEqual(images.namelist(), [f"pitch_003_frame_{index:04d}.png" for index in range(4)])
            for row, decoded in zip(manifest["frames"], self.decoded_frames):
                path = self.output / "raw_frames" / row["image_name"]
                self.assertEqual(exporter.digest(path), row["image_sha256"])
                self.assertEqual(images.read(row["image_name"]), path.read_bytes())
                np.testing.assert_array_equal(cv2.imread(str(path)), decoded)
                self.assertEqual(set(row), {"frame_index", "timestamp_ms", "image_name", "image_sha256"})
        self.assertLess(manifest["decoded_timing_verification"]["max_timestamp_error_ms"], 0.001)
        with zipfile.ZipFile(self.output.with_name("manual_review.zip")) as archive:
            names = archive.namelist()
            self.assertTrue(all(name.startswith("manual_review/") for name in names))
            self.assertIn("manual_review/raw_frames_pitch_003.zip", names)
            self.assertIn("manual_review/pitch_003/ground_truth.json", names)
            self.assertFalse(any("overlay" in name or "annotations" in name for name in names))
        self.assertNotIn("PRIVATE", json.dumps(manifest))
        self.assertIsNone(manifest["events_supplement"])

    def test_raw_label_schema_contains_all_anatomical_joints_and_blank_states(self):
        labels = exporter.cvat_labels()
        self.assertIsInstance(labels, list)
        self.assertEqual(len(labels), 1)
        skeleton = labels[0]
        self.assertEqual((skeleton["name"], skeleton["type"]), ("PITCHER_2D", "skeleton"))
        self.assertEqual(skeleton["attributes"], [])
        self.assertEqual([point["name"] for point in skeleton["sublabels"]], list(exporter.JOINT_NAMES))
        for point in skeleton["sublabels"]:
            self.assertEqual(point["type"], "points")
            self.assertNotIn("id", point)
            attributes = {attribute["name"]: attribute for attribute in point["attributes"]}
            state = attributes["human_state"]
            self.assertEqual(state["values"], ["unreviewed", "visible", "uncertain", "not_observable"])
            self.assertEqual(state["default_value"], "unreviewed")
            self.assertEqual(state["input_type"], "select")
            self.assertTrue(state["mutable"])
            note = attributes["review_note"]
            self.assertEqual((note["input_type"], note["default_value"], note["values"]), ("text", "", [""]))
            self.assertTrue(note["mutable"])
            self.assertNotIn("points", point)  # Config never contains frame coordinates.
        svg = ET.fromstring(f'<svg>{skeleton["svg"]}</svg>')
        circles = svg.findall("circle")
        lines = svg.findall("line")
        self.assertEqual([node.attrib["data-label-name"] for node in circles], list(exporter.JOINT_NAMES))
        self.assertEqual({node.attrib["data-node-id"] for node in circles}, {str(i) for i in range(1, 13)})
        self.assertEqual(len(lines), 12)
        self.assertEqual({(int(edge.attrib["data-node-from"]), int(edge.attrib["data-node-to"])) for edge in lines}, set(exporter.SKELETON_EDGES))
        self.assertNotIn("data-label-id", skeleton["svg"])

    def test_rejects_source_binding_dimensions_count_and_bad_metadata_timing(self):
        cases = {
            "source hash": {"sha256": "0" * 64},
            "source filename": {"path": "C:\\elsewhere\\pitch_999.mp4"},
            "dimensions": {"width": 65},
            "count": {"frame_count": 5, "timestamps_ms": [0, 40, 80, 120, 160]},
            "lost timestamp": {"timestamps_ms": [0, 40, 40, 120]},
            "bad actual timing": {"timestamps_ms": [0, 40, 80, 126]},
            "unvalidated": {"status": "unvalidated"},
            "nonfinite timing": {"timestamps_ms": [0, 40, 80, float("nan")]},
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                self.write_metadata({**self.metadata, **overrides})
                with self.assertRaises(ValueError):
                    self.export()
                self.assert_no_export()

    def test_rejects_unavailable_decoded_timestamps_and_removes_staging(self):
        real_capture = cv2.VideoCapture

        class LostTimingCapture:
            def __init__(self, path):
                self.capture = real_capture(path)

            def get(self, prop):
                return 0.0 if prop == cv2.CAP_PROP_POS_MSEC else self.capture.get(prop)

            def __getattr__(self, name):
                return getattr(self.capture, name)

        with patch.object(cv2, "VideoCapture", LostTimingCapture):
            with self.assertRaisesRegex(ValueError, "timestamps are missing"):
                self.export()
        self.assert_no_export()

    def test_refuses_existing_directory_or_archive_without_modifying_work(self):
        for kind in ("directory", "zip"):
            with self.subTest(kind=kind):
                if kind == "directory":
                    self.output.mkdir()
                    sentinel = self.output / "keep.txt"
                else:
                    sentinel = self.output.with_name(self.output.name + ".zip")
                sentinel.write_bytes(b"existing reviewer work")
                with self.assertRaises(FileExistsError):
                    self.export()
                self.assertEqual(sentinel.read_bytes(), b"existing reviewer work")
                sentinel.unlink()
                if kind == "directory":
                    self.output.rmdir()

    def test_clean_supplement_and_event_templates_exclude_canonical_human_answers(self):
        prior, baseline = self.make_prior_package()
        baseline_bytes = (baseline / "ground_truth" / "pitch_003" / "ground_truth.json").read_bytes()
        manifest = self.export(supplement_folder=prior / "pitch_005", event_template_folder=prior / "pitch_003")
        self.assertEqual(manifest["events_supplement"]["task_scope"], "events_supplement")
        self.assertEqual(manifest["event_review"]["task_scope"], "events_supplement")
        for pitch in ("pitch_003", "pitch_005"):
            blank = exporter.read_json(self.output / pitch / "ground_truth.json")
            self.assertEqual(blank["annotation_status"], "unreviewed")
            self.assertEqual(blank["notes"], [])
            self.assertIsNone(blank["provenance"]["reviewer"])
            self.assertTrue(all(value is None for value in blank["labels"]["events"].values()))
        self.assertEqual({path.name for path in (self.output / "pitch_003").iterdir()}, {"ground_truth.json", "REVIEW_NOTES.md"})
        self.assertEqual((baseline / "ground_truth" / "pitch_003" / "ground_truth.json").read_bytes(), baseline_bytes)
        for source in (prior / "pitch_005").rglob("*"):
            if source.is_file():
                target = self.output / "pitch_005" / source.relative_to(prior / "pitch_005")
                self.assertEqual(target.read_bytes(), source.read_bytes())
        for path in self.output.rglob("*"):
            if path.suffix in (".json", ".html", ".md", ".csv"):
                self.assertNotIn("HSU_PRIVATE", path.read_text(encoding="utf-8-sig"))
        with zipfile.ZipFile(self.output / "raw_frames_pitch_003.zip") as images:
            self.assertTrue(all(name.startswith("pitch_003_frame_") and name.endswith(".png") for name in images.namelist()))
        self.assertIn("events_supplement", (self.output / "pitch_003" / "REVIEW_NOTES.md").read_text(encoding="utf-8"))

    def test_rejects_completed_supplement_answers_and_extra_private_files(self):
        prior, _ = self.make_prior_package()
        folder = prior / "pitch_005"
        original = (folder / "ground_truth.json").read_bytes()
        payload = exporter.read_json(folder / "ground_truth.json")
        payload["provenance"]["reviewer"] = "HSU_PRIVATE_REVIEWER"
        (folder / "ground_truth.json").write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "entirely blank"):
            self.export(supplement_folder=folder)
        self.assert_no_export()
        (folder / "ground_truth.json").write_bytes(original)
        (folder / "HSU_answers.md").write_text("PRIVATE answers")
        with self.assertRaisesRegex(ValueError, "unexpected files"):
            self.export(supplement_folder=folder)
        self.assert_no_export()

    def test_rejects_filled_event_worksheet(self):
        prior, _ = self.make_prior_package()
        notes = prior / "pitch_003" / "REVIEW_NOTES.md"
        notes.write_text(notes.read_text(encoding="utf-8") + "\nHSU_PRIVATE_ANSWER: leg lift frame 2\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "blank worksheet"):
            self.export(event_template_folder=prior / "pitch_003")
        self.assert_no_export()


if __name__ == "__main__":
    unittest.main()
