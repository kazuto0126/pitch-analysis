from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'), str(Path(__file__).resolve().parents[1] / 'src')]
import evaluate_chain_reliability as evaluate


class ChainEvaluationTests(unittest.TestCase):
    def row(self, label='reliable', state='within_reference_range', warning=False):
        return {'target': label, 'state': state, 'old_jump_chain': False,
            'previous_joint_cues_as_chain': False, 'new_chain_geometry': warning,
            'additive_chain_cues': warning, 'anchor_labels': 'shoulder=reliable|hip=not_observable',
            'member_states': 'observed|observed|missing'}

    def test_known_member_error_retained_with_unknown_members(self):
        for unknown in ('uncertain', 'not_observable'):
            self.assertEqual(evaluate.chain_target(['reliable', unknown, 'unreliable']), 'unreliable')

    def test_negative_requires_all_members_reliable(self):
        self.assertEqual(evaluate.chain_target(['reliable'] * 3), 'reliable')
        self.assertEqual(evaluate.chain_target(['reliable', 'not_observable', 'reliable']), 'not_observable')
        self.assertEqual(evaluate.chain_target(['uncertain', 'not_observable', 'reliable']), 'uncertain')

    def test_wrong_or_incomplete_member_labels_rejected(self):
        for labels in ([], ['reliable'] * 2, ['reliable'] * 4, ['reliable', None, 'unreliable']):
            with self.assertRaises(ValueError): evaluate.chain_target(labels)

    def test_missing_positive_stays_fn_and_unknown_warning_is_burden(self):
        rows = [self.row('unreliable', 'insufficient_evidence'), self.row('not_observable', 'warning', True), self.row()]
        score = evaluate.score(rows, 'new_chain_geometry')
        self.assertEqual((score['non_seed_chain_rows'], score['fn'], score['tn'], score['human_excluded']), (3, 1, 1, 1))
        self.assertEqual(score['warning_on_excluded'], {'uncertain': 0, 'not_observable': 1})
        self.assertEqual(score['new_geometry_insufficient_by_target']['unreliable'], 1)

    def test_query_anchor_unknown_does_not_remove_primary_fp(self):
        summary = evaluate.summarize([self.row(state='warning', warning=True)])
        self.assertEqual(summary['screens']['new_chain_geometry']['fp'], 1)
        self.assertEqual(summary['anchor_label_context']['shoulder=reliable|hip=not_observable']['rows'], 1)

    def test_empty_positive_recall_is_null(self):
        self.assertIsNone(evaluate.score([self.row()], 'new_chain_geometry')['recall'])

    def test_screens_keep_the_same_target_and_original_warnings(self):
        row = self.row('unreliable')
        row.update(old_jump_chain=True, additive_chain_cues=True)
        summary = evaluate.summarize([row])
        self.assertEqual(summary['screens']['new_chain_geometry']['fn'], 1)
        self.assertEqual(summary['screens']['additive_chain_cues']['tp'], 1)
        self.assertEqual({v['non_seed_chain_rows'] for v in summary['screens'].values()}, {1})

    def test_boolean_and_state_contract_rejected(self):
        row = self.row()
        row['new_chain_geometry'] = 1
        with self.assertRaises(ValueError): evaluate.score([row], 'new_chain_geometry')
        row = self.row(state='seed_excluded')
        with self.assertRaises(ValueError): evaluate.score([row], 'new_chain_geometry')

    def test_receipt_rejects_joint_attribution_or_production_adoption(self):
        application = {'policy': {}, 'code': {'producer_code': {'sha256': 'code'}}, 'calibration_artifact': {'sha256': 'artifact'}}
        data = {'status': 'sealed_chain_warning_sidecar', 'policy': {}, 'plan_sha256': 'plan', 'producer_sha256': 'code',
            'calibration_artifact': {'sha256': 'artifact'}, 'human_training_inputs': ['other_clip'],
            'supervised_calibration_used': True, 'application_human_annotation_inputs': [],
            'production_adoption': False, 'major_warning_generated': False, 'joint_warning_generated': False,
            'pose_inference_calls': 0, 'tracker_inference_calls': 0}
        evaluate.verify_receipt(data, application, 'plan', ['other_clip'], sidecar=True)
        for flag in ('production_adoption', 'major_warning_generated', 'joint_warning_generated'):
            changed = deepcopy(data); changed[flag] = True
            with self.assertRaises(ValueError): evaluate.verify_receipt(changed, application, 'plan', ['other_clip'], sidecar=True)
        changed = deepcopy(data); changed['application_human_annotation_inputs'] = ['query_gt']
        with self.assertRaises(ValueError): evaluate.verify_receipt(changed, application, 'plan', ['other_clip'], sidecar=True)


if __name__ == '__main__': unittest.main()
