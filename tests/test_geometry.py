import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pitch_analysis.geometry import joint_angle, line_angle
from pitch_analysis.temporal import interpolate_short_gaps
from pitch_analysis.normalization import fit_scalers
from pitch_analysis.alignment import constrained_dtw
from pitch_analysis.events import make_annotation_template, validate_events
from pitch_analysis.comparison import FEATURE_SCALES, _phase_eligibility
from pitch_analysis.reference import fit_reference_scaler
from pitch_analysis.reference_set import compare_reference_set
from pitch_analysis.workflow import quality_gate
from pitch_analysis.features import extract_frame_features


class GeometryTests(unittest.TestCase):
    def test_phase_keeps_reliable_features_when_elbow_coverage_is_low(self):
        query = {feature: 1.0 for feature in FEATURE_SCALES}
        reference = {feature: 1.0 for feature in FEATURE_SCALES}
        query["throwing_elbow_angle_smoothed"] = 0.2
        reference["throwing_elbow_angle_smoothed"] = 0.1

        eligible, failures, shared, notes = _phase_eligibility(query, reference)

        self.assertTrue(eligible)
        self.assertEqual(failures, [])
        self.assertNotIn("throwing_elbow_angle_smoothed", shared)
        self.assertEqual(len(shared), 4)
        self.assertTrue(notes)

    def test_event_template_carries_reviewable_motion_windows(self):
        quality = {
            "throwing_side": "RIGHT",
            "motion_candidates": {
                "candidates": [
                    {"start_frame": 10, "end_frame": 60, "peak_activity_frame": 35}
                ]
            },
        }

        template = make_annotation_template(video_id="sample", quality_report=quality)

        self.assertEqual(template["automatic_motion_windows"][0]["start_frame"], 10)
        self.assertEqual(template["review_status"], "needs_human_review")

    def test_joint_angle_right_angle(self):
        self.assertEqual(joint_angle((1, 0), (0, 0), (0, 1)), 90.0)


    def test_line_angle_has_no_pi_wrap(self):
        self.assertEqual(abs(line_angle((0, 0), (-1, 0))), 0.0)


    def test_only_short_internal_gaps_are_interpolated(self):
        values, mask = interpolate_short_gaps([0.0, None, 2.0, None, None, None, 6.0])
        self.assertEqual(values, [0.0, 1.0, 2.0, None, None, None, 6.0])
        self.assertEqual(mask, [False, True, False, False, False, False, False])

    def test_scaler_is_fitted_from_reference_rows(self):
        scaler = fit_scalers([{"elbow": 10.0}, {"elbow": 20.0}], ["elbow"])["elbow"]
        self.assertAlmostEqual(scaler.transform(15.0), 0.0)

    def test_dtw_is_path_normalized_and_ignores_missing_features(self):
        result = constrained_dtw([{"a": 0.0, "b": None}], [{"a": 0.0, "b": 9.0}], {"a": 1.0, "b": 1.0})
        self.assertEqual(result, (0.0, 1))

    def test_events_must_be_chronological(self):
        events = {"events": {"pitch_start": 1, "peak_leg_lift": 2, "foot_strike": 3, "release": 4, "follow_through_end": 5}}
        self.assertEqual(validate_events(events)["release"], 4)

    def test_comparison_uses_fixed_non_zero_feature_scales(self):
        self.assertTrue(all(scale > 0 for scale in FEATURE_SCALES.values()))

    def test_quality_gate_requires_throwing_elbow_coverage(self):
        report = {
            "timeline_frames": 100,
            "input_frames_detected": 95,
            "invalid_feature_frames": {
                "throwing_knee_angle": 0, "lead_knee_angle": 0,
                "shoulder_line_angle": 0, "throwing_elbow_angle": 49,
                "hip_line_angle": 0, "lateral_foot_separation": 0,
            },
        }
        self.assertTrue(quality_gate(report)["passed"])
        report["invalid_feature_frames"]["throwing_elbow_angle"] = 51
        self.assertFalse(quality_gate(report)["passed"])

    def test_presence_gates_raw_landmarks_but_legacy_rows_remain_compatible(self):
        frame = {
            "RIGHT_HIP": {"x": 1.0, "y": 0.0, "visibility": 0.9, "presence": 0.1},
            "RIGHT_KNEE": {"x": 0.0, "y": 0.0, "visibility": 0.9, "presence": 0.1},
            "RIGHT_ANKLE": {"x": 0.0, "y": 1.0, "visibility": 0.9, "presence": 0.1},
        }
        self.assertIsNone(extract_frame_features(frame, "RIGHT", 0.5, 0.5)["throwing_knee_angle"])
        for value in frame.values():
            value.pop("presence")
        self.assertIsNotNone(extract_frame_features(frame, "RIGHT", 0.5, 0.5)["throwing_knee_angle"])


if __name__ == "__main__":
    unittest.main()
