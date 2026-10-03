import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.manual_keypoints import (
    JOINT_NAMES,
    load_manual_keypoints,
    validate_manual_keypoints,
)


class ManualKeypointsTests(unittest.TestCase):
    """Synthetic validation fixtures; these are not real human annotations."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.video = self.root / "pitch_001.mp4"
        self.video.write_bytes(b"synthetic video identity bytes")

    def _annotation(self, *, reviewed=True):
        return {
            "schema_version": "manual-keypoints-v1",
            "annotation_status": "reviewed" if reviewed else "in_progress",
            "source_video": {
                "pitch_id": "pitch_001",
                "filename": self.video.name,
                "sha256": hashlib.sha256(self.video.read_bytes()).hexdigest(),
                "total_frames": 3,
                "frame_index_base": 0,
            },
            "coordinate_system": "original_image_pixels_xy",
            "image_size": {"width": 640, "height": 480},
            "provenance": {
                "reviewer": "Synthetic fixture reviewer" if reviewed else None,
                "reviewed_at_utc": "2026-10-04T02:30:00Z" if reviewed else None,
                "method": "manual_cvat_keypoints",
                "guidelines_version": "manual-keypoints-guidelines-v1",
                "annotation_mode": "independent",
                "source_annotation_sha256": hashlib.sha256(b"synthetic CVAT export").hexdigest(),
            },
            "frames": [
                {
                    "frame_index": index,
                    "timestamp_ms": index * 40.0,
                    "image_name": f"frame_{index:06d}.png",
                    "image_sha256": hashlib.sha256(f"synthetic image {index}".encode()).hexdigest(),
                    "joints": [
                        {
                            "name": name,
                            "status": "visible" if reviewed else "unreviewed",
                            "x_px": 100.0 + joint_index if reviewed else None,
                            "y_px": 200.5 if reviewed else None,
                            "confidence": None,
                            "note": "",
                        }
                        for joint_index, name in enumerate(JOINT_NAMES)
                    ],
                }
                for index in range(3)
            ],
            "notes": ["Synthetic validation fixture only."],
        }

    def test_joint_names_are_anatomical_bilateral_mediapipe_names(self):
        self.assertEqual(JOINT_NAMES, (
            "LEFT_SHOULDER", "RIGHT_SHOULDER", "LEFT_ELBOW", "RIGHT_ELBOW",
            "LEFT_WRIST", "RIGHT_WRIST", "LEFT_HIP", "RIGHT_HIP",
            "LEFT_KNEE", "RIGHT_KNEE", "LEFT_ANKLE", "RIGHT_ANKLE",
        ))

    def test_review_can_complete_with_explicit_uncertainty_and_occlusion(self):
        annotation = self._annotation()
        for index, status in enumerate(("uncertain", "not_observable")):
            annotation["frames"][index]["joints"][0].update(
                status=status, x_px=None, y_px=None, confidence=0.25,
                note="Motion blur" if status == "uncertain" else "Behind torso",
            )
        original = deepcopy(annotation)
        validate_manual_keypoints(annotation, source_video_path=self.video)
        self.assertEqual(annotation, original)

    def test_unfinished_full_frame_template_is_valid_only_in_progress(self):
        annotation = self._annotation(reviewed=False)
        validate_manual_keypoints(annotation, self.video)
        annotation["annotation_status"] = "reviewed"
        annotation["provenance"].update(
            reviewer="Synthetic fixture reviewer", reviewed_at_utc="2026-10-04T02:30:00Z",
        )
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            validate_manual_keypoints(annotation)

    def test_nonvisible_joint_cannot_supply_invented_coordinates(self):
        for status in ("uncertain", "not_observable", "unreviewed"):
            for coordinate in ("x_px", "y_px"):
                with self.subTest(status=status, coordinate=coordinate):
                    annotation = self._annotation(reviewed=False)
                    joint = annotation["frames"][0]["joints"][0]
                    joint.update(status=status, note="Occluded or undecidable")
                    joint[coordinate] = 123.4
                    with self.assertRaises(ValueError):
                        validate_manual_keypoints(annotation)

    def test_uncertain_and_hidden_joints_need_explanations(self):
        for status in ("uncertain", "not_observable"):
            for note in ("", " \t\n"):
                with self.subTest(status=status, note=note):
                    annotation = self._annotation()
                    annotation["frames"][0]["joints"][0].update(
                        status=status, x_px=None, y_px=None, note=note,
                    )
                    with self.assertRaisesRegex(ValueError, "note"):
                        validate_manual_keypoints(annotation)

    def test_visible_coordinates_require_both_axes_and_original_image_bounds(self):
        for coordinate, bad_values in (
            ("x_px", (None, -0.1, 640, 640.1, True)),
            ("y_px", (None, -0.1, 480, 480.1, True)),
        ):
            for value in bad_values:
                with self.subTest(coordinate=coordinate, value=value):
                    annotation = self._annotation()
                    annotation["frames"][0]["joints"][0][coordinate] = value
                    with self.assertRaises(ValueError):
                        validate_manual_keypoints(annotation)
        annotation = self._annotation()
        annotation["frames"][0]["joints"][0].update(x_px=0, y_px=0)
        annotation["frames"][1]["joints"][0].update(x_px=639.999, y_px=479.999)
        validate_manual_keypoints(annotation)

    def test_every_original_frame_is_required_in_order(self):
        for mutation in (
            lambda frames: frames.pop(),
            lambda frames: frames.reverse(),
            lambda frames: frames[1].update(frame_index=0),
            lambda frames: frames[2].update(frame_index=3),
        ):
            annotation = self._annotation()
            mutation(annotation["frames"])
            with self.assertRaisesRegex(ValueError, "frame|timeline"):
                validate_manual_keypoints(annotation)

    def test_each_joint_is_present_once_even_when_positions_differ(self):
        annotation = self._annotation()
        annotation["frames"][0]["joints"].pop()
        with self.assertRaises(ValueError):
            validate_manual_keypoints(annotation)
        annotation = self._annotation()
        # Different coordinates must not conceal a duplicated anatomical name.
        annotation["frames"][0]["joints"][1]["name"] = "LEFT_SHOULDER"
        with self.assertRaises(ValueError):
            validate_manual_keypoints(annotation)
        annotation = self._annotation()
        annotation["frames"][0]["joints"][0]["name"] = "throwing_shoulder"
        with self.assertRaises(ValueError):
            validate_manual_keypoints(annotation)

    def test_review_completion_requires_reviewer_and_real_utc_time(self):
        cases = (
            ("reviewer", None), ("reviewer", " \t"),
            ("reviewed_at_utc", None), ("reviewed_at_utc", "not a timeZ"),
            ("reviewed_at_utc", "2026-10-04T02:30:00+08:00"),
            ("reviewed_at_utc", "2026-02-30T02:30:00Z"),
        )
        for name, value in cases:
            with self.subTest(name=name, value=value):
                annotation = self._annotation()
                annotation["provenance"][name] = value
                with self.assertRaisesRegex(ValueError, name):
                    validate_manual_keypoints(annotation)
        annotation = self._annotation(reviewed=False)
        annotation["provenance"]["reviewed_at_utc"] = "2026-10-04T02:30:00Z"
        with self.assertRaisesRegex(ValueError, "reviewed_at_utc|completed review time"):
            validate_manual_keypoints(annotation)
        annotation = self._annotation()
        annotation["provenance"]["reviewed_at_utc"] = "2026-10-04T02:30:00+00:00"
        validate_manual_keypoints(annotation)

    def test_model_assisted_provenance_cannot_be_imported_as_independent(self):
        for name, value in (
            ("annotation_mode", "model_assisted"), ("method", "model_predictions"),
            ("source_annotation_sha256", "missing"),
        ):
            with self.subTest(name=name):
                annotation = self._annotation()
                annotation["provenance"][name] = value
                with self.assertRaisesRegex(ValueError, name):
                    validate_manual_keypoints(annotation)

    def test_nonfinite_numbers_and_bad_confidence_are_rejected(self):
        for section, name in (
            ("frame", "timestamp_ms"), ("joint", "x_px"),
            ("joint", "y_px"), ("joint", "confidence"),
        ):
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(section=section, name=name, value=value):
                    annotation = self._annotation()
                    target = annotation["frames"][0]
                    if section == "joint":
                        target = target["joints"][0]
                    target[name] = value
                    with self.assertRaises(ValueError):
                        validate_manual_keypoints(annotation)
        for value in (-0.01, 1.01, True):
            annotation = self._annotation()
            annotation["frames"][0]["joints"][0]["confidence"] = value
            with self.assertRaises(ValueError):
                validate_manual_keypoints(annotation)
        annotation = self._annotation()
        annotation["frames"][0]["joints"][0]["confidence"] = 0
        annotation["frames"][1]["joints"][0]["confidence"] = 1
        validate_manual_keypoints(annotation)

    def test_frame_images_and_timestamps_remain_distinct_and_in_order(self):
        annotation = self._annotation()
        annotation["frames"][2]["timestamp_ms"] = 10
        with self.assertRaisesRegex(ValueError, "timestamp"):
            validate_manual_keypoints(annotation)
        annotation = self._annotation()
        annotation["frames"][1]["image_name"] = annotation["frames"][0]["image_name"]
        with self.assertRaisesRegex(ValueError, "image_name"):
            validate_manual_keypoints(annotation)
        annotation = self._annotation()
        annotation["frames"][0]["image_name"] = "../frame.png"
        with self.assertRaisesRegex(ValueError, "image_name"):
            validate_manual_keypoints(annotation)

    def test_video_hash_and_filename_changes_are_rejected(self):
        annotation = self._annotation()
        other = self.root / "different_pitch.mp4"
        other.write_bytes(self.video.read_bytes())
        with self.assertRaisesRegex(ValueError, "filename"):
            validate_manual_keypoints(annotation, source_video_path=other)
        self.video.write_bytes(b"changed source video bytes")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            validate_manual_keypoints(annotation, source_video_path=self.video)

    def test_load_checks_json_sidecar_without_mutating_or_creating_labels(self):
        annotation = self._annotation(reviewed=False)
        sidecar = self.root / "manual_keypoints.json"
        sidecar.write_text(json.dumps(annotation), encoding="utf-8-sig")
        before = sidecar.read_bytes()
        loaded = load_manual_keypoints(sidecar, source_video_path=self.video)
        self.assertEqual(loaded, annotation)
        self.assertEqual(sidecar.read_bytes(), before)
        self.assertTrue(all(
            joint["x_px"] is None and joint["y_px"] is None
            for frame in loaded["frames"] for joint in frame["joints"]
        ))
        annotation["frames"].pop()
        sidecar.write_text(json.dumps(annotation), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "every source frame"):
            load_manual_keypoints(sidecar)

    def test_standalone_schema_enforces_joint_completeness_and_state_semantics(self):
        schema_path = Path(__file__).resolve().parents[1] / "src" / "pitch_analysis" / "contracts" / "schemas" / "manual-keypoints-v1.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertTrue(validator.is_valid(self._annotation()))
        annotation = self._annotation()
        annotation["frames"][0]["joints"][1]["name"] = "LEFT_SHOULDER"
        self.assertFalse(validator.is_valid(annotation))
        annotation = self._annotation(reviewed=False)
        annotation["frames"][0]["joints"][0]["x_px"] = 10
        self.assertFalse(validator.is_valid(annotation))
        annotation = self._annotation()
        annotation["frames"][0]["joints"][0].update(status="unreviewed", x_px=None, y_px=None)
        self.assertFalse(validator.is_valid(annotation))


if __name__ == "__main__":
    unittest.main()
