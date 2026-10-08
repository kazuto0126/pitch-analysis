"""Version 2 reader validation and exact native-PTS acceptance boundaries."""
from __future__ import annotations

import copy
import subprocess
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from pitch_analysis.handoff.contract import (
    CHECK_NAMES, HandoffError, validate_batch, validate_index, validate_pitch,
)
from pitch_analysis.handoff.timing import ffprobe_executable, validate_timeline, verify_timing


def video_metadata(**changes):
    value = {
        "fps": "30/1", "fps_float": 30.0, "constant_frame_rate": True,
        "frame_count": 12, "duration_sec": .4, "width": 96, "height": 128,
        "codec": "h264", "pix_fmt": "yuv420p", "square_pixels": True,
        "container_start_time_sec": .033333, "frame_time_rule": "frame_index / fps_float",
        "has_audio": False,
    }
    value.update(changes)
    return value


def contract_fixture():
    batch_id = "run_source"
    source = {"video_id": "source", "title": "Pitcher video", "url": "https://example.test/video", "channel": "channel", "source_type": "broadcast"}
    game = {"season": "unknown", "season_confidence": "unknown", "team": "unknown", "opponent": "unknown", "game_id": "unknown", "pitch_type": "unknown"}
    row = {"contract_version": 2, "batch_id": batch_id, "pitcher_name": "Example Pitcher", "pitch_count": 3, "batch_json": "example-pitcher/run_source/batch.json", "created_utc": "2026-10-08T00:00:00Z"}
    items = [{"pitch_id": f"{batch_id}_p{index:02d}", "video_file": f"{batch_id}_p{index:02d}.mp4", "json": f"{batch_id}_p{index:02d}.json"} for index in range(1, 4)]
    batch = {"contract_version": 2, "batch_id": batch_id, "created_utc": row["created_utc"], "pitcher_name": row["pitcher_name"], "throws": "R", "view": "rear_centerfield_broadcast", "pitch_count": 3, "pitches": items, "source": source, "game": game, "viewing_video": "viewing/Example_Pitcher_unknown.mp4", "excluded_by_operator": [], "quality_warning": False, "warnings": []}
    unverified = {"pitch_delivery_visible", "not_replay_or_slow_motion", "not_mirrored", "full_body_in_frame", "pitcher_identity"}
    checks = {name: {"status": "not_verified" if name in unverified else "verified_by_pipeline", "how": "public contract fixture"} for name in CHECK_NAMES}
    pitch = {"contract_version": 2, "pitch_id": items[0]["pitch_id"], "batch_id": batch_id, "index": 1, "pitcher_name": row["pitcher_name"], "throws": "R", "view": batch["view"], "video_file": items[0]["video_file"], "sha256": "a" * 64, "video": video_metadata(), "source": {**source, "start_sec": 10.0, "end_sec": 10.4}, "game": copy.deepcopy(game), "pipeline_anchors_sec": {"motion_onset": .05, "motion_peak": .1, "settle": .3}, "checks": checks, "requires_human_review": [name for name in CHECK_NAMES if name in unverified]}
    return row, batch, pitch


class HandoffContractTests(unittest.TestCase):
    def setUp(self):
        self.row, self.batch, self.pitch = contract_fixture()
        self.item = self.batch["pitches"][0]

    def test_all_three_levels_valid_and_mapping_preserves_original(self):
        original = copy.deepcopy(self.pitch)
        self.assertIsNone(validate_index(self.row))
        self.assertIsNone(validate_batch(self.batch, self.row))
        mapped = validate_pitch(self.pitch, self.batch, self.item)
        self.assertEqual(mapped["throws"], "RIGHT")
        self.assertEqual(mapped["pitcher_name"], "Example Pitcher")
        self.assertTrue(all(value is None for value in mapped["context"].values()))
        self.assertEqual(mapped["required_reviews"], self.pitch["requires_human_review"] + ["preparation_complete", "follow_through_complete"])
        self.assertEqual(mapped["source_identity"]["video_id"], "source")
        self.assertEqual(self.pitch, original)

    def test_left_and_unknown_handedness_have_no_guess(self):
        for original, expected in (("L", "LEFT"), ("unknown", None)):
            self.batch["throws"] = self.pitch["throws"] = original
            self.assertEqual(validate_pitch(self.pitch, self.batch, self.item)["throws"], expected)
        self.batch["throws"] = self.pitch["throws"] = "RIGHT"
        with self.assertRaises(HandoffError):
            validate_pitch(self.pitch, self.batch, self.item)

    def test_known_season_kept_only_when_confidence_is_sufficient(self):
        for game in (self.batch["game"], self.pitch["game"]):
            game.update(season="2024", season_confidence="medium")
        self.assertEqual(validate_pitch(self.pitch, self.batch, self.item)["context"]["season"], 2024)
        self.pitch["game"]["season_confidence"] = "low"
        with self.assertRaises(HandoffError):
            validate_pitch(self.pitch, self.batch, self.item)

    def test_unknown_version_rejected_at_every_level(self):
        for version in (1, 3, "2", True, None):
            with self.subTest(version=version, level="index"):
                changed = {**self.row, "contract_version": version}
                with self.assertRaises(HandoffError) as raised:
                    validate_index(changed)
                self.assertEqual(raised.exception.code, "unsupported_contract_version")
            with self.subTest(version=version, level="batch"):
                with self.assertRaises(HandoffError):
                    validate_batch({**self.batch, "contract_version": version}, self.row)
            with self.subTest(version=version, level="pitch"):
                with self.assertRaises(HandoffError):
                    validate_pitch({**self.pitch, "contract_version": version}, self.batch, self.item)

    def test_batch_count_positive_integer_at_least_three(self):
        for count in (True, 2, 0, -1, 3.0, "3"):
            with self.subTest(count=count), self.assertRaises(HandoffError):
                validate_index({**self.row, "pitch_count": count})
        self.batch["pitches"].pop()
        with self.assertRaises(HandoffError) as raised:
            validate_batch(self.batch, self.row)
        self.assertEqual(raised.exception.code, "pitch_count_mismatch")

    def test_duplicate_ids_and_mismatched_names_rejected(self):
        self.batch["pitches"][1] = copy.deepcopy(self.item)
        with self.assertRaises(HandoffError) as raised:
            validate_batch(self.batch, self.row)
        self.assertEqual(raised.exception.code, "duplicate_pitch_id")
        self.batch["pitches"][1] = {"pitch_id": "run_source_p02", "video_file": "another.mp4", "json": "run_source_p02.json"}
        with self.assertRaises(HandoffError) as raised:
            validate_batch(self.batch, self.row)
        self.assertEqual(raised.exception.code, "filename_mismatch")

    def test_batch_index_and_pitch_item_identity_must_match(self):
        with self.assertRaises(HandoffError):
            validate_batch({**self.batch, "pitcher_name": "Another Pitcher"}, self.row)
        with self.assertRaises(HandoffError):
            validate_pitch({**self.pitch, "batch_id": "another"}, self.batch, self.item)
        with self.assertRaises(HandoffError):
            validate_pitch({**self.pitch, "pitch_id": "run_source_p02"}, self.batch, self.item)
        with self.assertRaises(HandoffError):
            validate_pitch({**self.pitch, "video_file": "viewing/all.mp4"}, self.batch, self.item)

    def test_missing_fields_and_wrong_objects_raise_handoff_error(self):
        for validator, args, field in ((validate_index, [self.row], "pitcher_name"), (validate_batch, [self.batch, self.row], "pitches"), (validate_pitch, [self.pitch, self.batch, self.item], "video")):
            changed = copy.deepcopy(args)
            del changed[0][field]
            with self.subTest(field=field), self.assertRaises(HandoffError):
                validator(*changed)
        for value in (None, [], 3, "value"):
            with self.subTest(value=value), self.assertRaises(HandoffError):
                validate_index(value)

    def test_malformed_checks_rejected_safely(self):
        mutations = [None, [], {"status": "not_verified"}, {"status": "unexpected", "how": "test"}, {"status": None, "how": "test"}, {"status": "not_verified", "how": None}]
        for check in mutations:
            changed = copy.deepcopy(self.pitch)
            changed["checks"]["pitcher_identity"] = check
            with self.subTest(check=check), self.assertRaises(HandoffError):
                validate_pitch(changed, self.batch, self.item)
        del self.pitch["checks"]["pitcher_identity"]
        with self.assertRaises(HandoffError):
            validate_pitch(self.pitch, self.batch, self.item)

    def test_requires_review_matches_every_unverified_check_exactly_once(self):
        for reviews in ([], self.pitch["requires_human_review"][:-1], self.pitch["requires_human_review"] + ["pitcher_identity"], self.pitch["requires_human_review"] + ["continuous_shot"], None, [dict(status="not_verified")]):
            changed = {**self.pitch, "requires_human_review": reviews}
            with self.subTest(reviews=reviews), self.assertRaises(HandoffError) as raised:
                validate_pitch(changed, self.batch, self.item)
            self.assertEqual(raised.exception.code, "review_list_mismatch")
        self.pitch["checks"]["extra_public_check"] = {"status": "not_verified", "how": "unknown"}
        with self.assertRaises(HandoffError):
            validate_pitch(self.pitch, self.batch, self.item)
        self.pitch["requires_human_review"].append("extra_public_check")
        self.assertIn("extra_public_check", validate_pitch(self.pitch, self.batch, self.item)["required_reviews"])

    def test_source_game_hash_and_anchors_are_validated(self):
        mutations = [("source", {**self.pitch["source"], "video_id": "different"}), ("source", {**self.pitch["source"], "start_sec": True}), ("game", {**self.pitch["game"], "season": False}), ("sha256", "x" * 64), ("pipeline_anchors_sec", {"motion_onset": .3, "motion_peak": .1, "settle": .2})]
        for name, value in mutations:
            with self.subTest(field=name), self.assertRaises(HandoffError):
                validate_pitch({**self.pitch, name: value}, self.batch, self.item)


class HandoffTimelineTests(unittest.TestCase):
    def test_fractional_fps_controls_validation_fps_float_controls_contract_time(self):
        metadata = video_metadata(fps="30000/1001", fps_float=30.0, frame_count=60, duration_sec=2.002)
        points = [Fraction(index * 1000 * 1001, 30000) for index in range(60)]
        report = validate_timeline(points, 60, metadata)
        self.assertEqual(report["max_abs_deviation_ms"], 0)
        self.assertEqual(report["timestamps_ms"][30], 1000)
        self.assertEqual(report["normalized_pts_ms"][30], 1001)
        # A rounded float-FPS native timeline drifts beyond the approved limit.
        with self.assertRaises(HandoffError) as raised:
            validate_timeline([Fraction(index * 1000, 30) for index in range(60)], 60, metadata)
        self.assertEqual(raised.exception.code, "pts_tolerance_exceeded")

    def test_native_first_pts_is_zero_origin_container_start_is_recorded_only(self):
        metadata = video_metadata(container_start_time_sec=2.25)
        native = [Fraction(9750) + Fraction(index * 1000, 30) for index in range(12)]
        report = validate_timeline(native, 12, metadata)
        self.assertEqual(report["native_pts_ms"][0], 9750)
        self.assertEqual(report["normalized_pts_ms"][0], 0)
        self.assertEqual(report["timestamps_ms"][0], 0)
        self.assertEqual(report["container_start_time_sec"], 2.25)
        self.assertFalse(report["container_start_time_applied"])

    def test_strict_one_millisecond_boundary_on_every_frame(self):
        metadata = video_metadata(fps="1000/1", fps_float=1000.0, frame_count=4, duration_sec=.004)
        for deviation in (Fraction(999, 1000), Fraction(-999, 1000)):
            points = [Fraction(0), Fraction(1) + deviation, Fraction(2), Fraction(3)]
            self.assertLess(validate_timeline(points, 4, metadata)["max_abs_deviation_ms"], 1)
        for points in ([0, 2, 3, 4], [0, 1, 2, 4], [0, 1, 2, Fraction(4001, 1000)]):
            with self.subTest(points=points), self.assertRaises(HandoffError) as raised:
                validate_timeline(points, 4, metadata)
            self.assertEqual(raised.exception.code, "pts_tolerance_exceeded")
            self.assertIn("deviations_ms", raised.exception.details)
        # A negative exact boundary remains strictly monotonic at a slower FPS.
        slow = video_metadata(fps="100/1", fps_float=100.0, frame_count=3, duration_sec=.03)
        with self.assertRaises(HandoffError) as raised:
            validate_timeline([0, 9, 20], 3, slow)
        self.assertEqual(raised.exception.code, "pts_tolerance_exceeded")

    def test_nonmonotonic_and_missing_native_pts_refused(self):
        metadata = video_metadata(frame_count=3, duration_sec=.1)
        for points in ([0, 0, 66.666], [0, -1, 66.666], [0, float("nan"), 66.666], [0, float("inf"), 66.666], [0, True, 66.666], [0, None, 66.666], [0, "N/A", 66.666], [0, 33.333]):
            with self.subTest(points=points), self.assertRaises(HandoffError):
                validate_timeline(points, 3, metadata)

    def test_actual_count_and_cfr_flag_are_required(self):
        points = [Fraction(index * 1000, 30) for index in range(12)]
        with self.assertRaises(HandoffError) as raised:
            validate_timeline(points, 11, video_metadata())
        self.assertEqual(raised.exception.code, "frame_count_mismatch")
        for flag in (False, 1, "true", None):
            with self.subTest(flag=flag), self.assertRaises(HandoffError) as raised:
                validate_timeline(points, 12, video_metadata(constant_frame_rate=flag))
            self.assertEqual(raised.exception.code, "not_constant_frame_rate")
        with self.assertRaises(HandoffError):
            validate_timeline(points, True, video_metadata())

    def test_invalid_fraction_and_video_facts_refused(self):
        points = [Fraction(index * 1000, 30) for index in range(12)]
        for fps in (True, 30, "0/1", "-30/1", "30/0", "NaN", ""):
            with self.subTest(fps=fps), self.assertRaises(HandoffError):
                validate_timeline(points, 12, video_metadata(fps=fps))
        for changes in ({"fps_float": True}, {"fps_float": float("nan")}, {"frame_count": True}, {"height": True}, {"duration_sec": float("nan")}, {"container_start_time_sec": float("inf")}):
            with self.subTest(changes=changes), self.assertRaises(HandoffError):
                validate_timeline(points, 12, video_metadata(**changes))
        missing = video_metadata()
        del missing["fps"]
        with self.assertRaises(HandoffError):
            validate_timeline(points, 12, missing)


class HandoffDecodeTests(unittest.TestCase):
    def setUp(self):
        cache = Path(__file__).resolve().parents[1] / ".cache"
        cache.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=cache, prefix="handoff-validation-")
        self.addCleanup(self.temporary.cleanup)
        self.video = Path(self.temporary.name) / "fixture.mp4"
        self.video.write_bytes(b"mocked decode")
        self.metadata = video_metadata(frame_count=3, duration_sec=.1)

    def capture(self, *, count=3, changed_dimensions=False):
        import numpy as np
        import cv2

        class Capture:
            index = 0
            released = False

            def isOpened(self):
                return True

            def read(self):
                if self.index == count:
                    return False, None
                self.index += 1
                height = 130 if changed_dimensions and self.index == 2 else 128
                return True, np.zeros((height, 96, 3), np.uint8)

            def get(self, prop):
                self.assert_property = prop == cv2.CAP_PROP_POS_MSEC
                return (self.index - 1) * 1000 / 30

            def release(self):
                self.released = True

        return Capture()

    def probe(self):
        return {"frames": [{"best_effort_timestamp_time": value, "width": 96, "height": 128} for value in ("2.000000", "2.033333", "2.066667")], "streams": [{"codec_name": "h264", "pix_fmt": "yuv420p", "width": 96, "height": 128, "sample_aspect_ratio": "1:1"}], "format": {"start_time": "9.0"}}

    def test_full_decode_and_authoritative_native_pts(self):
        capture = self.capture()
        with patch("cv2.VideoCapture", return_value=capture), patch("pitch_analysis.handoff.timing.ffprobe_executable", return_value="ffprobe"), patch("pitch_analysis.handoff.timing._probe", return_value=self.probe()):
            result = verify_timing(self.video, self.metadata)
        self.assertTrue(capture.released)
        self.assertEqual(result["frame_count"], 3)
        self.assertEqual(result["native_pts_ms"][0], 2000)
        self.assertEqual(result["timestamps_ms"][0], 0)
        self.assertEqual(result["probed_container_start_time_sec"], "9.0")
        self.assertEqual(result["pts_source"], "ffprobe.best_effort_timestamp_time")
        self.assertEqual(len(result["opencv_timestamps_ms"]), 3)

    def test_actual_count_ignores_header_claim_and_requires_full_decode(self):
        capture = self.capture(count=2)
        with patch("cv2.VideoCapture", return_value=capture), patch("pitch_analysis.handoff.timing._probe") as probe:
            with self.assertRaises(HandoffError) as raised:
                verify_timing(self.video, self.metadata)
        self.assertEqual(raised.exception.code, "frame_count_mismatch")
        self.assertTrue(capture.released)
        probe.assert_not_called()

    def test_dimension_drift_stops_import(self):
        capture = self.capture(changed_dimensions=True)
        with patch("cv2.VideoCapture", return_value=capture), self.assertRaises(HandoffError) as raised:
            verify_timing(self.video, self.metadata)
        self.assertEqual(raised.exception.code, "dimensions_mismatch")
        self.assertTrue(capture.released)

    def test_native_missing_pts_count_and_codec_mismatch_refused(self):
        for mutation in (lambda p: p["frames"].pop(), lambda p: p["frames"][1].pop("best_effort_timestamp_time"), lambda p: p["streams"][0].update(codec_name="mpeg4"), lambda p: p["frames"][1].update(best_effort_timestamp_time="2.034334")):
            probe = self.probe()
            mutation(probe)
            with patch("cv2.VideoCapture", return_value=self.capture()), patch("pitch_analysis.handoff.timing.ffprobe_executable", return_value="ffprobe"), patch("pitch_analysis.handoff.timing._probe", return_value=probe), self.assertRaises(HandoffError):
                verify_timing(self.video, self.metadata)

    def test_real_fractional_h264_decode_and_ffprobe_pts(self):
        try:
            executable = ffprobe_executable()
        except HandoffError as exc:
            self.skipTest(str(exc))
        import imageio_ffmpeg

        encoded = subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-v", "error", "-y",
             "-f", "lavfi", "-i", "color=c=blue:size=96x128:rate=30000/1001",
             "-frames:v", "12", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             "-vf", "setsar=1", str(self.video)],
            capture_output=True, timeout=30,
        )
        self.assertEqual(encoded.returncode, 0, encoded.stderr.decode("utf-8", errors="replace"))
        fps = Fraction(30000, 1001)
        metadata = video_metadata(fps="30000/1001", fps_float=float(fps), duration_sec=float(12 / fps))
        result = verify_timing(self.video, metadata, ffprobe_path=executable)
        self.assertEqual(result["frame_count"], 12)
        self.assertEqual(result["native_video_stream"]["codec_name"], "h264")
        self.assertLess(result["max_abs_deviation_ms"], .001)
        self.assertEqual(result["timestamps_ms"][0], 0)


if __name__ == "__main__":
    unittest.main()
