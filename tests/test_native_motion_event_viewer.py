"""Event decorations preserve the accepted player's data and uncertainty."""
from copy import deepcopy
from fractions import Fraction
from importlib.resources import files
import json
from pathlib import Path
import tempfile
import unittest

from pitch_analysis.analysis.native_motion_events import describe_events
from pitch_analysis.analysis.native_motion_event_viewer import write_event_viewer
from pitch_analysis.ground_truth import EVENT_NAMES
from pitch_analysis.native_pose_io import reference

from test_native_motion_events import exact, ranged, rows


class NativeMotionEventViewerTests(unittest.TestCase):
    def clip(self):
        values = rows(3)
        events = {name: exact(frame) for name, frame in zip(EVENT_NAMES, [0, 0, 1, 1, 2], strict=True)}
        events["preparation_start"] = {"status": "not_observable", "frame_index": None,
                                       "note": "Already moving at frame zero"}
        events["leg_lift"] = ranged(0, 0, status="uncertain")
        events["approximate_release"] = ranged(1, 2)
        return {"pitch_id": "pitch_fixture", "frame_count": 3, "fps_fraction": "60000/1001",
                "overlay_url": "../../saved/overlay_native.mp4", "rows": values,
                **describe_events(events, Fraction(60000, 1001), values)}

    def test_packaging_preserves_rows_events_and_original_playback_asset(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            target = root / "analysis_results" / "viewer"
            clip = self.clip()
            before = deepcopy(clip)
            result = write_event_viewer(root, [clip], target)
            html = (target / "review_motion_events.html").read_text(encoding="utf-8")
            embedded = html.split('<script id="motion-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            self.assertEqual(json.loads(embedded), {"clips": [before]})
            self.assertEqual(clip, before)
            original = files("pitch_analysis").joinpath("review_assets/native_motion_viewer.js").read_bytes()
            self.assertEqual((target / "motion_viewer.js").read_bytes(), original)
            self.assertLess(html.index('src="motion_viewer.js"'), html.index('src="motion_events.js"'))
            self.assertFalse(result["browser_interaction_verified"])
            self.assertFalse(result["events_aligned"])
            self.assertFalse(result["legacy_joint_reliability_transferred"])
            self.assertEqual(result["new_inference_calls"], 0)
            self.assertIsNone(result["usable_for_analysis"])
            for key in ("html_ref", "script_ref", "event_script_ref"):
                self.assertEqual(reference(root, root / result[key]["path"]), result[key])

    def test_manual_notes_cannot_break_the_embedded_json_script(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            target = root / "analysis_results" / "viewer"
            clip = self.clip()
            note = '</script><script>alert("review note")</script>&'
            clip["events"]["leg_lift"]["note"] = note
            write_event_viewer(root, [clip], target)
            html = (target / "review_motion_events.html").read_text(encoding="utf-8")
            self.assertNotIn(note, html)
            embedded = html.split('<script id="motion-data" type="application/json">', 1)[1].split('</script>', 1)[0]
            self.assertEqual(json.loads(embedded)["clips"][0]["events"]["leg_lift"]["note"], note)

    def test_invalid_timeline_or_existing_target_never_overwrites_output(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp:
            root = Path(temp)
            target = root / "analysis_results" / "viewer"
            clip = self.clip()
            clip["rows"][1]["timestamp_sec"] = 999
            with self.assertRaises(ValueError):
                write_event_viewer(root, [clip], target)
            self.assertFalse(target.exists())
            write_event_viewer(root, [self.clip()], target)
            original = {path: path.read_bytes() for path in target.iterdir()}
            with self.assertRaises(FileExistsError):
                write_event_viewer(root, [self.clip()], target)
            self.assertEqual({path: path.read_bytes() for path in target.iterdir()}, original)


if __name__ == "__main__":
    unittest.main()
