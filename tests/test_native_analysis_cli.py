"""The analysis-input entry consumes saved native data without invoking inference."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from pitch_analysis.cli import main


class NativeAnalysisCliTests(unittest.TestCase):
    def arguments(self):
        return ['pitch-analysis', 'prepare-analysis-input', 'native', 'pitch.json',
                '--subject-track', 'track.jsonl', '--human-review', 'review.json',
                '--output', 'analysis_results/consumer']

    def test_dispatches_saved_inputs_without_legacy_inference(self):
        result={'status':'human_reviewed_native_input','pitch_id':'fixture'}
        with patch('sys.argv',self.arguments()), \
             patch('pitch_analysis.analysis.native_input.prepare_native_analysis_input',return_value=result) as prepare, \
             patch('pitch_analysis.cli.prepare_segment',side_effect=AssertionError('legacy processing invoked')), \
             patch('pitch_analysis.cli.extract_pose',side_effect=AssertionError('inference invoked')), \
             redirect_stdout(StringIO()) as output:
            main()
        self.assertEqual(prepare.call_args.args,(Path.cwd(),'native','pitch.json','track.jsonl','review.json','analysis_results/consumer'))
        self.assertEqual(json.loads(output.getvalue())['new_inference_calls'],0)

    def test_source_or_review_rejection_returns_nonzero(self):
        with patch('sys.argv',self.arguments()), \
             patch('pitch_analysis.analysis.native_input.prepare_native_analysis_input',side_effect=ValueError('review does not match source')), \
             redirect_stdout(StringIO()) as output:
            with self.assertRaises(SystemExit) as raised:main()
        self.assertEqual(raised.exception.code,1)
        self.assertEqual(json.loads(output.getvalue()),{'status':'failed','error':'review does not match source'})


if __name__=='__main__':unittest.main()
