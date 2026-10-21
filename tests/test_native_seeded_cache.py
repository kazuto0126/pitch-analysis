"""Exact seeded-track cache checks use synthetic contracts and no real data."""
from copy import deepcopy
import unittest

from pitch_analysis.native_seeded_cache import cache_geometry_matches
from test_native_pose_contract import make_frame, make_live_manifest


def fixture():
    manifest = make_live_manifest()
    manifest["video"].update(frame_count=3, fps=30.0)
    manifest["timebase"]["fps_fraction"] = "30/1"
    record = make_frame(index=1)
    record["backend"] = manifest["backend"]["name"]
    box = [20.0, 30.0, 80.0, 180.0]
    geometry = record["input_geometry"]
    geometry["sdk_geometry"].update(person_bbox_xyxy_px=deepcopy(box), crop_xyxy=[0, 0, 100, 200],
                                    padding=1.25, person_bbox_clamped=False)
    record["model_selection"] = {
        "inference_mode": "live_stateless_roi", "pose_not_run": False,
        "pose_not_run_reason": None, "isolated_worker_attempt_index": 1,
        "person_box_selection": {"status": "selected", "selected_bbox_xyxy_px": deepcopy(box)},
    }
    expected = {"model_sha256": "a"*64, "source_video_sha256": "b"*64,
                "frame_index": 1, "timestamp_ms": 1000/30, "decoded_bgr_sha256": "c"*64,
                "person_bbox_xyxy": deepcopy(box), "input_geometry": deepcopy(geometry)}
    return manifest, record, expected


class SeededCacheTests(unittest.TestCase):
    def test_exact_match_is_pure_and_does_not_upgrade_quality(self):
        manifest, record, expected = fixture()
        before = deepcopy((manifest, record, expected))
        self.assertEqual(cache_geometry_matches(manifest, record, **expected), (True, []))
        self.assertEqual((manifest, record, expected), before)
        self.assertIsNone(record["usable_for_analysis"])

    def test_expected_source_model_frame_time_or_pixels_must_match(self):
        for name, replacement, reason in (
                ("model_sha256", "d"*64, "source_model_mismatch"),
                ("source_video_sha256", "d"*64, "source_video_mismatch"),
                ("frame_index", 2, "frame_index_mismatch"),
                ("timestamp_ms", 1000/30 + 1e-12, "timestamp_mismatch"),
                ("decoded_bgr_sha256", "d"*64, "decoded_pixels_mismatch")):
            manifest, record, expected = fixture()
            expected[name] = replacement
            with self.subTest(name=name):
                matched, reasons = cache_geometry_matches(manifest, record, **expected)
                self.assertFalse(matched)
                self.assertIn(reason, reasons)

    def test_record_source_and_manifest_envelope_must_agree(self):
        for mutate, reason in (
                (lambda r: r.update(source_video_sha256="d"*64), "source_video_mismatch"),
                (lambda r: r.update(pitch_id="another"), "cached_envelope_mismatch"),
                (lambda r: r.update(backend="rtmpose_other"), "cached_envelope_mismatch"),
                (lambda r: r["image_size"].update(width=101), "cached_envelope_mismatch")):
            manifest, record, expected = fixture(); mutate(record)
            with self.subTest(reason=reason):
                matched, reasons = cache_geometry_matches(manifest, record, **expected)
                self.assertFalse(matched); self.assertIn(reason, reasons)

    def test_bbox_both_selection_and_sdk_must_match_exactly(self):
        for location in ("selection", "sdk", "expected"):
            manifest, record, expected = fixture()
            if location == "selection":
                record["model_selection"]["person_box_selection"]["selected_bbox_xyxy_px"][0] += 1e-12
            elif location == "sdk":
                record["input_geometry"]["sdk_geometry"]["person_bbox_xyxy_px"][0] += 1e-12
            else:
                expected["person_bbox_xyxy"][0] += 1e-12
            with self.subTest(location=location):
                self.assertFalse(cache_geometry_matches(manifest, record, **expected)[0])

    def test_entire_geometry_including_affine_padding_and_extra_fields_is_exact(self):
        for mutate in (lambda g: g["affine_src_to_input"][0].__setitem__(0, 2.000000000001),
                       lambda g: g["affine_input_to_src"][1].__setitem__(2, 1e-12),
                       lambda g: g["sdk_geometry"].update(padding=1.250000000001),
                       lambda g: g["sdk_geometry"].update(extra_provenance=True),
                       lambda g: g["sdk_geometry"]["crop_xyxy"].__setitem__(0, 0.0),
                       lambda g: g["sdk_geometry"].update(person_bbox_clamped=0)):
            manifest, record, expected = fixture(); mutate(expected["input_geometry"])
            with self.subTest(geometry=expected["input_geometry"]):
                matched, reasons = cache_geometry_matches(manifest, record, **expected)
                self.assertFalse(matched); self.assertIn("input_geometry_mismatch", reasons)

    def test_execution_provenance_cannot_be_missing_false_or_faked_numeric(self):
        for mutate in (lambda s: s.pop("pose_not_run"),
                       lambda s: s.update(pose_not_run=True),
                       lambda s: s.update(pose_not_run=0),
                       lambda s: s.update(isolated_worker_attempt_index=0),
                       lambda s: s.update(isolated_worker_attempt_index=True),
                       lambda s: s.update(inference_mode="cached_read_only")):
            manifest, record, expected = fixture(); mutate(record["model_selection"])
            with self.subTest(selection=record["model_selection"]):
                self.assertFalse(cache_geometry_matches(manifest, record, **expected)[0])

    def test_full_not_run_frame_cannot_supply_a_reusable_prediction(self):
        manifest, record, expected = fixture()
        reason = "ambiguous_subject_boxes"
        record["input_geometry"] = {"input_mode":"not_run", "roi_xywh":None,
            "affine_src_to_input":None,"affine_input_to_src":None,"sdk_geometry":None}
        record["model_selection"].update(pose_not_run=True, pose_not_run_reason=reason,
                                        isolated_worker_attempt_index=None)
        for point in record["landmarks"]:
            point.update(x_px=None, y_px=None, native_score=None, coordinate_state="missing", missing_reason=reason)
        matched, reasons = cache_geometry_matches(manifest, record, **expected)
        self.assertFalse(matched); self.assertIn("cached_pose_not_executed", reasons)

    def test_genuine_missing_points_from_an_executed_model_remain_reusable_as_missing(self):
        manifest, record, expected = fixture()
        for point in record["landmarks"]:
            point.update(x_px=None, y_px=None, coordinate_state="missing", missing_reason="nonpositive_native_response")
        self.assertTrue(cache_geometry_matches(manifest, record, **expected)[0])
        self.assertTrue(all(point["coordinate_state"]=="missing" for point in record["landmarks"]))

    def test_invalid_contract_and_nonfinite_or_boolean_expected_facts_are_rejected(self):
        for name, value in (("frame_index", True), ("timestamp_ms", True), ("timestamp_ms", float("nan")),
                            ("timestamp_ms", 10**400), ("person_bbox_xyxy", [0.,30.,10**400,180.]),
                            ("model_sha256", "invalid"), ("person_bbox_xyxy", [True,30.,80.,180.]),
                            ("input_geometry", {"x":float("inf")})):
            manifest, record, expected = fixture(); expected[name] = value
            with self.subTest(name=name, value=value):
                self.assertEqual(cache_geometry_matches(manifest,record,**expected),
                                 (False,["invalid_expected_reuse_facts"]))
        manifest, record, expected = fixture(); record["landmarks"][0]["x_px"] = float("nan")
        self.assertEqual(cache_geometry_matches(manifest,record,**expected), (False,["invalid_cached_contract"]))


if __name__ == "__main__": unittest.main()
