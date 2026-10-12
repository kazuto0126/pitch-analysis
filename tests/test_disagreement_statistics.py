"""Numerical semantics, label denominators, and missingness regressions."""
from __future__ import annotations

import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import disagreement_statistics as stats
finally:
    sys.path.pop(0)


def rows(negative=(), positive=()):
    return ([{"label": "reliable", "value": value} for value in negative]
            + [{"label": "unreliable", "value": value} for value in positive])


class DisagreementStatisticsTests(unittest.TestCase):
    def test_full_denominators_keep_missing_and_exclude_only_human_masks(self):
        source = rows([0, None, 2], [None, 5]) + [
            {"label": "uncertain", "value": 900},
            {"label": "not_observable", "value": None},
        ]
        result = stats.summarize_labeled(source)
        self.assertEqual(result["label_counts"], {
            "reliable": 3, "unreliable": 2, "uncertain": 1, "not_observable": 1})
        self.assertEqual(result["scorable_counts"], {"reliable": 3, "unreliable": 2, "total": 5})
        self.assertEqual(result["paired_counts"], {"reliable": 2, "unreliable": 1, "total": 3})
        self.assertEqual(result["unavailable_counts"], {"reliable": 1, "unreliable": 1, "total": 2})
        self.assertEqual(result["human_excluded_count"], 2)
        self.assertEqual(result["value_coverage"], {"reliable": 2 / 3, "unreliable": .5, "overall": .6})
        self.assertEqual(result["conditional_auroc"], 1.)

    def test_auroc_ties_receive_half_credit(self):
        result = stats.summarize_labeled(rows([1, 2], [2, 3]))
        self.assertEqual(result["conditional_auroc"], .875)
        self.assertEqual(stats.summarize_labeled(rows([0, 0], [0, 0]))["conditional_auroc"], .5)

    def test_reverse_ranking_is_not_automatically_flipped(self):
        result = stats.summarize_labeled(rows([4, 5], [1, 2]))
        self.assertEqual(result["conditional_auroc"], 0.)
        self.assertEqual(result["auroc_direction"], "larger_value_ranks_toward_unreliable")

    def test_single_class_and_unavailable_class_are_not_scorable_auc(self):
        for source in (rows([1, 2]), rows([], [1]), rows([1], [None]), rows([None], [2])):
            with self.subTest(source=source):
                self.assertIsNone(stats.summarize_labeled(source)["conditional_auroc"])

    def test_empty_and_all_unavailable_have_null_metrics_not_fake_zeros(self):
        empty = stats.summarize_labeled([])
        self.assertEqual(empty["scorable_counts"]["total"], 0)
        self.assertIsNone(empty["value_coverage"]["overall"])
        self.assertEqual(empty["descriptive"]["reliable"], {
            "count": 0, "mean": None, "median": None, "p90": None, "max": None})
        missing = stats.summarize_labeled(rows([None], [None]))
        self.assertEqual(missing["scorable_counts"]["total"], 2)
        self.assertEqual(missing["unavailable_counts"]["total"], 2)
        self.assertEqual(missing["value_coverage"]["overall"], 0.)
        self.assertIsNone(missing["conditional_auroc"])

    def test_descriptive_statistics_and_zero_are_real_values(self):
        result = stats.summarize_labeled(rows([0, 10, 20, 30], [0]))
        self.assertEqual(result["descriptive"]["reliable"], {
            "count": 4, "mean": 15., "median": 15., "p90": 27., "max": 30.})
        self.assertEqual(result["descriptive"]["unreliable"]["count"], 1)
        self.assertEqual(result["descriptive"]["unreliable"]["mean"], 0.)
        self.assertEqual(result["quantile_method"], "linear_type_7")

    def test_large_finite_distances_do_not_overflow_descriptions(self):
        result = stats.summarize_labeled(rows([1e308, 1e308], [1e308]))
        self.assertEqual(result["descriptive"]["reliable"]["mean"], 1e308)
        self.assertEqual(result["descriptive"]["reliable"]["median"], 1e308)
        self.assertEqual(result["conditional_auroc"], .5)
        tiny = stats.summarize_labeled(rows([5e-324, 5e-324], [0]))
        self.assertEqual(tiny["descriptive"]["reliable"]["mean"], 5e-324)

    def test_invalid_values_and_labels_rejected_even_for_excluded_human_rows(self):
        for label in stats.LABELS:
            for value in (float("nan"), float("inf"), -float("inf"), -1, True, False, "2"):
                with self.subTest(label=label, value=value):
                    with self.assertRaises(ValueError):
                        stats.summarize_labeled([{"label": label, "value": value}])
        for row in ({"label": "unknown", "value": 2}, {"label": [], "value": 1},
                    {"label": "reliable"}, {"value": 1}, None):
            with self.subTest(row=row):
                with self.assertRaises(ValueError):
                    stats.summarize_labeled([row])

    def test_rank_auc_matches_explicit_positive_negative_pairs(self):
        negative, positive = [0, 2, 2, 7], [1, 2, 8]
        expected = sum(1 if p > n else .5 if p == n else 0
                       for p in positive for n in negative) / 12
        result = stats.summarize_labeled(rows(negative, positive))
        self.assertEqual(result["conditional_auroc"], expected)

    def test_spearman_uses_average_tied_ranks_and_zero(self):
        self.assertEqual(stats.spearman([(0, 0), (1, 1), (1, 1), (3, 3)]), 1.)
        self.assertEqual(stats.spearman([(0, 3), (1, 1), (1, 1), (3, 0)]), -1.)
        # ranks(x)=(1,2.5,2.5,4), ranks(y)=(1,2,3,4)
        self.assertAlmostEqual(stats.spearman([(0, 0), (1, 1), (1, 2), (3, 3)]),
                               0.9486832980505138)

    def test_spearman_constant_or_less_than_two_pairs_is_null(self):
        for pairs in ([], [(0, 0)], [(1, 0), (1, 2)], [(0, 1), (2, 1)]):
            with self.subTest(pairs=pairs):
                self.assertIsNone(stats.spearman(pairs))

    def test_spearman_invalid_pairs_rejected_instead_of_silently_dropped(self):
        for pair in ((1,), (1, 2, 3), (None, 2), (True, 2), (1, float("inf")),
                     (float("nan"), 1), "12"):
            with self.subTest(pair=pair):
                with self.assertRaises(ValueError):
                    stats.spearman([(0, 0), pair])
        self.assertEqual(stats.spearman([(-2, 2), (0, 0), (2, -2)]), -1.)

    def test_functions_do_not_modify_input_and_accept_generators(self):
        source = rows([0, None, 2], [5, 1])
        pairs = [[0, 1], [2, 3], [2, 4]]
        original_source, original_pairs = copy.deepcopy(source), copy.deepcopy(pairs)
        expected = stats.summarize_labeled(source)
        self.assertEqual(stats.summarize_labeled(row for row in source), expected)
        self.assertEqual(stats.spearman(pair for pair in pairs), stats.spearman(pairs))
        self.assertEqual(source, original_source)
        self.assertEqual(pairs, original_pairs)


if __name__ == "__main__":
    unittest.main()
