"""Synthetic hand-annotation import and visible-only coordinate evaluation contracts."""
import copy
import hashlib
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

from pitch_analysis.manual_keypoints import JOINT_NAMES


def script(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parents[1] / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


importer = script("import_manual_keypoints")
evaluator = script("evaluate_manual_keypoints")


class ManualKeypointBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "pitch_003.mp4"
        writer = cv2.VideoWriter(str(self.video), cv2.VideoWriter_fourcc(*"mp4v"), 30, (64, 64))
        self.assertTrue(writer.isOpened())
        for index in range(3):
            writer.write(np.full((64, 64, 3), index * 50, np.uint8))
        writer.release()
        self.manifest = {
            "schema_version": "manual-pose-package-v1", "pitch_id": "pitch_003",
            "source_video": {"pitch_id": "pitch_003", "filename": self.video.name,
                             "sha256": importer.digest(self.video), "total_frames": 3, "frame_index_base": 0},
            "image_width": 64, "image_height": 64, "joint_names": list(JOINT_NAMES),
            "frames": [{"frame_index": i, "timestamp_ms": i * 1000 / 30,
                        "image_name": f"pitch_003_frame_{i:04d}.png", "image_sha256": "a" * 64}
                       for i in range(3)],
        }
        capture = cv2.VideoCapture(str(self.video))
        for frame in self.manifest["frames"]:
            ok, image = capture.read()
            self.assertTrue(ok)
            ok, encoded = cv2.imencode(".png", image, [cv2.IMWRITE_PNG_COMPRESSION, 3])
            self.assertTrue(ok)
            frame["image_sha256"] = hashlib.sha256(encoded.tobytes()).hexdigest()
        capture.release()
        self.xml = ET.Element("annotations")
        for i, frame in enumerate(self.manifest["frames"]):
            image = ET.SubElement(self.xml, "image", id=str(i), name=frame["image_name"], width="64", height="64")
            skeleton = ET.SubElement(image, "skeleton", label="PITCHER_2D", source="manual")
            for name in JOINT_NAMES:
                point = ET.SubElement(skeleton, "points", label=name, points="10,10", occluded="0", outside="0", source="manual")
                ET.SubElement(point, "attribute", name="human_state").text = "visible"
                ET.SubElement(point, "attribute", name="review_note").text = ""

    def convert(self, **overrides):
        return importer.convert_cvat(ET.tostring(self.xml), self.manifest, reviewer="SYNTHETIC_REVIEWER", **overrides)

    def point(self, frame, name):
        return self.xml.findall("image")[frame].find(f"skeleton/points[@label='{name}']")

    def set_state(self, frame, name, state, note=""):
        point = self.point(frame, name)
        point.find("attribute[@name='human_state']").text = state
        point.find("attribute[@name='review_note']").text = note
        return point

    def model(self):
        return {"schema_version": "keypoints-v1", "pitch_id": "pitch_003",
                "coordinate_system": "normalized_image_xy; z is model-estimated relative depth, not calibrated 3D",
                "frames": [{"frame_index": i, "timestamp_ms": i * 1000 / 30, "detected": True,
                            "landmarks": [{"name": name, "x": 13/64, "y": 14/64, "visibility": .01}
                                          for name in JOINT_NAMES]} for i in range(3)]}

    def metadata(self):
        return {"sha256": self.manifest["source_video"]["sha256"], "frame_count": 3, "width": 64, "height": 64}

    def test_visible_coordinates_and_complete_review_keep_human_provenance(self):
        payload = self.convert(status="reviewed", reviewed_at_utc="2026-10-04T00:00:00Z")
        self.assertEqual(payload["provenance"]["reviewer"], "SYNTHETIC_REVIEWER")
        self.assertEqual(payload["provenance"]["source_annotation_sha256"], hashlib.sha256(ET.tostring(self.xml)).hexdigest())
        self.assertEqual(payload["frames"][0]["joints"][0]["x_px"], 10)
        self.assertEqual(payload["annotation_status"], "reviewed")

    def test_nonvisible_placeholder_coordinates_are_discarded_and_missing_not_guessed(self):
        point = self.set_state(0, "RIGHT_ELBOW", "not_observable", "Body occlusion; fixture only")
        point.set("occluded", "1")
        point.set("points", "999,999")
        self.set_state(1, "RIGHT_WRIST", "uncertain", "Blurred fixture")
        self.xml.remove(self.xml.findall("image")[2])
        payload = self.convert()
        joints0 = {j["name"]: j for j in payload["frames"][0]["joints"]}
        self.assertIsNone(joints0["RIGHT_ELBOW"]["x_px"])
        self.assertIsNone(joints0["RIGHT_ELBOW"]["y_px"])
        self.assertEqual(payload["frames"][2]["joints"][0]["status"], "unreviewed")
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            self.convert(status="reviewed", reviewed_at_utc="2026-10-04T00:00:00Z")

    def test_occluded_visible_auto_track_or_duplicate_points_refused(self):
        original = ET.tostring(self.xml)
        for mutation in ("occluded", "auto", "track", "duplicate"):
            with self.subTest(mutation=mutation):
                self.xml = ET.fromstring(original)
                if mutation == "occluded":
                    self.point(0, "RIGHT_ELBOW").set("occluded", "1")
                elif mutation == "auto":
                    self.point(0, "RIGHT_ELBOW").set("source", "auto")
                elif mutation == "track":
                    ET.SubElement(self.xml, "track")
                else:
                    self.xml.findall("image")[0].find("skeleton").append(copy.deepcopy(self.point(0, "RIGHT_ELBOW")))
                with self.assertRaises(ValueError):
                    self.convert()

    def test_changed_names_dimensions_frame_ids_or_unconfirmed_state_refused(self):
        original = ET.tostring(self.xml)
        for attr, value in (("name", "other_frame.png"), ("width", "128"), ("id", "9")):
            self.xml = ET.fromstring(original)
            self.xml.findall("image")[0].set(attr, value)
            with self.assertRaises(ValueError):
                self.convert()
        self.xml = ET.fromstring(original)
        self.set_state(0, "RIGHT_ELBOW", "probably_correct")
        with self.assertRaises(ValueError):
            self.convert()
        with self.assertRaisesRegex(ValueError, "DTD"):
            importer.convert_cvat(b'<!DOCTYPE annotations [<!ENTITY x "value">]><annotations/>', self.manifest, reviewer="fixture")

    def test_zip_import_preserves_export_and_cannot_replace_canonical_or_duplicate(self):
        export = self.root / "cvat_export.zip"
        xml_bytes = ET.tostring(self.xml)
        with zipfile.ZipFile(export, "w") as archive:
            archive.writestr("annotations.xml", xml_bytes)
        manifest_path = self.root / "frame_manifest.json"
        manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")
        canonical = self.root / "baseline" / "ground_truth" / "pitch_003" / "ground_truth.json"
        canonical.parent.mkdir(parents=True)
        canonical.write_bytes(b"HSU original human judgments")
        output_root = self.root / "annotations" / "manual_keypoints"
        with patch.object(importer, "REPOSITORY_ROOT", self.root):
            target = importer.import_cvat(export, manifest_path, self.video, review_id="FIXTURE_REVIEW", reviewer="fixture", output_root=output_root)
            self.assertEqual((target.parent / "source_annotations.xml").read_bytes(), xml_bytes)
            self.assertEqual(canonical.read_bytes(), b"HSU original human judgments")
            with self.assertRaises(FileExistsError):
                importer.import_cvat(export, manifest_path, self.video, review_id="FIXTURE_REVIEW", reviewer="fixture", output_root=output_root)
            with self.assertRaises(ValueError):
                importer.output_path(canonical.parent, "NEW_REVIEW", "pitch_003")
            with self.assertRaises(ValueError):
                importer.output_path(output_root, "../escape", "pitch_003")
            with patch.object(Path, "is_junction", return_value=True):
                with self.assertRaises(ValueError):
                    importer.output_path(output_root, "NEW_REVIEW", "pitch_003")

    def test_manifest_and_original_source_are_bound_to_timeline(self):
        importer.verify_source_timeline(self.manifest, self.video)
        changed = copy.deepcopy(self.manifest)
        changed["pitch_id"] = changed["source_video"]["pitch_id"] = "pitch_005"
        with self.assertRaisesRegex(ValueError, "same pitch"):
            importer.validate_manifest(changed)
        changed = copy.deepcopy(self.manifest)
        changed["source_video"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            importer.verify_source_timeline(changed, self.video)
        changed = copy.deepcopy(self.manifest)
        changed["frames"][1]["timestamp_ms"] += 2
        with self.assertRaisesRegex(ValueError, "timestamps"):
            importer.verify_source_timeline(changed, self.video)
        changed = copy.deepcopy(self.manifest)
        changed["frames"][0]["image_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "PNG hash"):
            importer.verify_source_timeline(changed, self.video)

    def test_known_pixel_error_missing_prediction_and_excluded_states_use_right_denominators(self):
        self.set_state(0, "RIGHT_ELBOW", "not_observable", "Occluded fixture")
        self.set_state(1, "RIGHT_ELBOW", "uncertain", "Ambiguous fixture")
        model = self.model()
        model["frames"][1]["landmarks"] = [j for j in model["frames"][1]["landmarks"] if j["name"] != "RIGHT_WRIST"]
        result = evaluator.evaluate(self.convert(), model, self.metadata())
        elbow = result["joints"]["RIGHT_ELBOW"]
        wrist = result["joints"]["RIGHT_WRIST"]
        self.assertEqual(elbow["eligible_visible_frames"], 1)
        self.assertEqual(elbow["mean_error_px"], 5)
        self.assertEqual(wrist["eligible_visible_frames"], 3)
        self.assertEqual(wrist["missing_predictions_on_visible_frames"], 1)
        self.assertAlmostEqual(wrist["prediction_presence_ratio_on_visible_frames"], 2/3)
        self.assertEqual(wrist["mean_error_px"], 5)
        self.assertEqual(wrist["p95_error_px"], 5)
        # Raw low-visibility points remain measured; no new confidence gate is introduced.
        self.assertEqual(result["joints"]["LEFT_SHOULDER"]["predicted_visible_frames"], 3)

    def test_evaluation_rejects_unbound_or_misaligned_predictions_and_no_visible_is_not_pass(self):
        for field, value in (("sha256", "0"*64), ("width", 128), ("frame_count", 4)):
            changed = self.metadata()
            changed[field] = value
            with self.assertRaises(ValueError):
                evaluator.evaluate(self.convert(), self.model(), changed)
        changed = self.model()
        changed["frames"][1]["timestamp_ms"] += 10
        with self.assertRaises(ValueError):
            evaluator.evaluate(self.convert(), changed, self.metadata())
        for i in range(3):
            for name in JOINT_NAMES:
                self.set_state(i, name, "not_observable", "Synthetic occlusion only")
        result = evaluator.evaluate(self.convert(), self.model(), self.metadata())
        self.assertEqual(result["evaluation_status"], "no_visible_reference")
        self.assertIsNone(result["joints"]["RIGHT_ELBOW"]["mean_error_px"])


if __name__ == "__main__":
    unittest.main()
