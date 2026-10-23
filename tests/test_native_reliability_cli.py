"""The native description CLI must remain separate from model execution."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pitch_analysis.cli import main


class NativeReliabilityCliTests(unittest.TestCase):
    def test_reports_saved_bundle_without_legacy_processing(self):
        args = ["pitch-analysis", "report-native-reliability", "saved_bundle",
                "--output", "analysis_results/report"]
        result = {"status": "descriptive_report_complete", "pitch_id": "fixture",
                  "total_frames": 3, "new_inference_calls": 0}
        with patch("sys.argv", args), \
                patch("pitch_analysis.analysis.native_reliability.write_native_reliability", return_value=result) as report, \
                patch("pitch_analysis.cli.extract_pose", side_effect=AssertionError("inference invoked")), \
                patch("pitch_analysis.cli.prepare_segment", side_effect=AssertionError("legacy pipeline invoked")), \
                redirect_stdout(StringIO()) as output:
            main()
        report.assert_called_once_with(Path.cwd(), "saved_bundle", "analysis_results/report")
        self.assertEqual(json.loads(output.getvalue()), {**result, "output_dir": "analysis_results/report"})

    def test_invalid_source_returns_failure(self):
        with patch("sys.argv", ["pitch-analysis", "report-native-reliability", "bad_bundle",
                                "--output", "analysis_results/report"]), \
                patch("pitch_analysis.analysis.native_reliability.write_native_reliability",
                      side_effect=ValueError("Changed source")), redirect_stdout(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:
                main()
        self.assertEqual(raised.exception.code, 1)
        self.assertEqual(json.loads(output.getvalue()), {"status": "failed", "error": "Changed source"})


if __name__ == "__main__":
    unittest.main()
