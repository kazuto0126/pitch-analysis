import unittest

from pitch_analysis.phase2_evaluation import evaluate_against_ground_truth


class Phase2EvaluationTests(unittest.TestCase):
    def test_unreviewed_template_never_counts_as_negative_ground_truth(self):
        result = evaluate_against_ground_truth({"annotation_status": "unreviewed"}, {}, {})
        self.assertEqual(result["status"], "pending_human_ground_truth")
        self.assertIsNone(result["identity_switch_warning_agreement"])
        self.assertIsNone(result["joint_reliability_agreement"])

    def test_reviewed_intervals_compare_without_inventing_coordinate_accuracy(self):
        ground_truth = {
            "annotation_status": "reviewed", "source_video": {"total_frames": 3},
            "labels": {
                "pitcher_correctly_selected": False,
                "identity_switch_intervals": [{"start_frame": 1, "end_frame": 1}],
                "major_pose_failure_intervals": [{"start_frame": 2, "end_frame": 2}],
                "throwing_elbow_reliability": [
                    {"start_frame": 0, "end_frame": 0, "status": "reliable"},
                    {"start_frame": 1, "end_frame": 2, "status": "unreliable"},
                ],
                "lead_knee_reliability": [
                    {"start_frame": 0, "end_frame": 2, "status": "reliable"},
                ],
                "events": {name: {"status": "uncertain", "frame_index": None}
                           for name in ("preparation_start", "leg_lift", "foot_plant",
                                        "approximate_release", "follow_through_end")},
            },
        }
        pose = {"total_frames": 3,
                "important_joints": {"throwing_elbow": "RIGHT_ELBOW", "lead_knee": "LEFT_KNEE"},
                "joints": {"RIGHT_ELBOW": {"frame_states": ["observed", "observed", "missing"]},
                           "LEFT_KNEE": {"frame_states": ["observed", "interpolated", "observed"]}}}
        tracking = {"total_frames": 3,
                    "warning_events": [{"type": "body_center_jump", "frame_index": 1}],
                    "frames": [{"frame_index": 0, "selection_status": "selected", "warnings": []},
                               {"frame_index": 1, "selection_status": "selected", "warnings": ["body_center_jump"]},
                               {"frame_index": 2, "selection_status": "rejected", "warnings": []}]}
        result = evaluate_against_ground_truth(ground_truth, pose, tracking)
        self.assertEqual(result["status"], "human_comparison_available")
        self.assertEqual(result["identity_switch_warning_agreement"]["warning_on_human_switch_frames"], 1)
        self.assertEqual(result["joint_reliability_agreement"]["throwing_elbow"]["observed_but_human_unreliable_frames"], 1)
        self.assertIsNone(result["keypoint_coordinate_accuracy"])
        self.assertIsNone(result["event_accuracy"])


if __name__ == "__main__":
    unittest.main()
