"""The shared skeleton commands dispatch without using the legacy33 pipeline."""
from contextlib import redirect_stdout
from io import StringIO
import unittest
from unittest.mock import patch

from pitch_analysis.cli import main


class SkeletonCliTests(unittest.TestCase):
    def test_prepare_dispatches_to_firstframe_only(self):
        value={'status':'awaiting_operator_seed','pitch_id':'fixture','display_choices':[],'pose_calls_during_preparation':0}
        with patch('sys.argv',['pitch-analysis','prepare-skeleton','a.mp4','a.json','--fps-fraction','30','--output','analysis_results/x']), \
             patch('pitch_analysis.native_skeleton_prepare.prepare_skeleton',return_value=value) as prepare,redirect_stdout(StringIO()) as output:
            main()
        self.assertEqual(prepare.call_args.kwargs['fps_fraction'],'30')
        self.assertIn('awaiting_operator_seed',output.getvalue())

    def test_extract_dispatches_to_seeded_native_flow(self):
        with patch('sys.argv',['pitch-analysis','extract-skeleton','prep.json','seed.json','--output','analysis_results/x']), \
             patch('pitch_analysis.seeded_skeleton.run_seeded_skeleton',return_value={'state':'completed'}) as run,redirect_stdout(StringIO()):
            main()
        self.assertEqual(run.call_args.args[1:],('prep.json','seed.json','analysis_results/x'))


if __name__=='__main__':unittest.main()
