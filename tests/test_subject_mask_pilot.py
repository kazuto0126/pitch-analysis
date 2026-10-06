"""Sampling and fail-closed checks for the isolated optional mask experiment."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

spec = importlib.util.spec_from_file_location(
    'subject_mask_pilot', Path(__file__).resolve().parents[1]/'scripts/measure_subject_mask_pilot.py')
measure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure)


class SubjectMaskPilotTests(unittest.TestCase):
    def test_fractional_probabilities_and_last_pixel_edges(self):
        mask = np.array([[0., .2], [.4, 1.]])
        self.assertAlmostEqual(measure.sample_mask(mask,.5,.5),.4)
        self.assertAlmostEqual(measure.sample_mask(mask,1.,.5),.6)
        self.assertAlmostEqual(measure.sample_mask(mask,1.9,1.9),1.)

    def test_queries_outside_source_image_are_not_clamped(self):
        for x,y in [(-.1,0),(2.,0),(0,2.),(float('nan'),0),(0,float('inf'))]:
            with self.subTest(x=x,y=y), self.assertRaises(ValueError):
                measure.sample_mask(np.zeros((2,2)),x,y)

    def test_known_native_float_reader_is_never_called(self):
        class FloatMask:
            image_format = 9
            def numpy_view(self):
                raise AssertionError('Would abort the real native process')
        array,reason = measure.read_mask(FloatMask())
        self.assertIsNone(array)
        self.assertEqual(reason,'sdk_float32_numpy_reader_native_failure')

    def test_other_formats_do_not_become_fake_probabilities(self):
        class OtherMask:
            image_format = 1
            def numpy_view(self):
                raise AssertionError('Do not reinterpret uint8 as probability')
        array,reason = measure.read_mask(OtherMask())
        self.assertIsNone(array)
        self.assertEqual(reason,'unexpected_pose_mask_format')
