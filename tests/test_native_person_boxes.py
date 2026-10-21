"""Deterministic person-box policy tests use no real models or GT."""
from copy import deepcopy
import unittest

import numpy as np

from pitch_analysis.native_person_boxes import prepare_detector_input, select_person_box


class PersonBoxTests(unittest.TestCase):
    def setUp(self):
        self.image = np.full((100, 160, 3), [10, 20, 30], np.uint8)
        self.tensor, self.geometry = prepare_detector_input(self.image, [20, 20, 140, 100])
        self.roi = [.2, .2, .7, .95]

    def outputs(self, boxes, labels=None):
        dets = np.array(boxes, np.float32).reshape(1, -1, 5)
        return dets, np.array(labels if labels is not None else [0]*len(boxes), np.int64).reshape(1, -1)

    def test_crop_only_bgr_padding_tensor_and_origin_are_preserved(self):
        self.assertEqual(self.tensor.shape, (1, 3, 640, 640))
        self.assertEqual(self.tensor.dtype, np.float32)
        np.testing.assert_array_equal(self.tensor[0, :, 0, 0], [10, 20, 30])
        np.testing.assert_array_equal(self.tensor[0, :, -1, -1], [114, 114, 114])
        changed = self.image.copy(); changed[:, :20] = 255
        other, _ = prepare_detector_input(changed, [20, 20, 140, 100])
        np.testing.assert_array_equal(self.tensor, other)
        self.assertEqual(self.geometry['crop_xyxy_px'], [20, 20, 140, 100])

    def test_unique_person_maps_original_box_without_score_ranking(self):
        result = select_person_box(self.outputs([[80, 80, 320, 400, .8], [300, 0, 600, 400, .99]], [0, 16]), self.geometry, self.roi)
        self.assertEqual(result['status'], 'selected')
        self.assertEqual(result['selected_output_index'], 0)
        np.testing.assert_allclose(result['selected_bbox_xyxy_px'], [35, 35, 80, 95])
        self.assertIn('not_person_class', result['candidates'][1]['rejection_reasons'])
        self.assertFalse(result['second_nms'])

    def test_ambiguity_does_not_pick_highest_or_reuse_previous(self):
        rows = [[80, 80, 320, 400, .8], [90, 90, 330, 390, .99]]
        result = select_person_box(self.outputs(rows), self.geometry, self.roi)
        self.assertEqual(result['status'], 'ambiguous_subject_boxes')
        self.assertEqual(result['eligible_count'], 2)
        self.assertIsNone(result['selected_bbox_xyxy_px'])
        empty = select_person_box(self.outputs([]), self.geometry, self.roi)
        self.assertEqual(empty['status'], 'no_subject_box')
        self.assertIsNone(empty['selected_output_index'])

    def test_every_emitted_candidate_and_local_rejection_is_kept(self):
        rows = [[0, 0, 100, 100, .6], [80, 80, 80, 400, .9], [500, 100, 600, 400, .9], [80, 80, 320, 400, float('nan')]]
        result = select_person_box(self.outputs(rows), self.geometry, self.roi)
        self.assertEqual(result['emitted_detection_count'], 4)
        self.assertEqual(result['status'], 'no_subject_box')
        self.assertIn('below_fixed_detector_score', result['candidates'][0]['rejection_reasons'])
        self.assertIn('nonpositive_box', result['candidates'][1]['rejection_reasons'])
        self.assertIn('box_center_outside_operator_roi', result['candidates'][2]['rejection_reasons'])
        self.assertIsNone(result['candidates'][3]['native_score'])
        __import__('json').dumps(result, allow_nan=False)

    def test_partial_canvas_box_is_not_clamped_or_claimed_complete(self):
        result = select_person_box(self.outputs([[-10, 30, 500, 600, .9]]), self.geometry, self.roi)
        self.assertEqual(result['status'], 'selected')
        self.assertLess(result['selected_bbox_xyxy_px'][0], 20)
        self.assertTrue(result['selected_bbox_extends_outside_operator_crop'])

    def test_wrong_output_type_and_roi_are_rejected(self):
        with self.assertRaises(ValueError):
            select_person_box((np.zeros((1, 2, 5),np.float32),np.zeros((1,1),np.int64)),self.geometry,self.roi)
        for roi in ([True, .1, .5, .9], [0,.1,2,.9], [.5,.2,.3,.9]):
            with self.subTest(roi=roi), self.assertRaises(ValueError):
                select_person_box(self.outputs([]),self.geometry,roi)


if __name__ == '__main__': unittest.main()
