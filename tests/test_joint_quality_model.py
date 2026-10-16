"""Synthetic-only tests for fixed train-only preprocessing and Newton solver."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import joint_quality_model as model


def row(value=0.0):
    result = [value] * 13
    result[2] = 1
    result[10] = 3
    result[11] = result[12] = 0
    return result


class PreprocessorTests(unittest.TestCase):
    def test_train_only_statistics_missingness_and_columns(self):
        rows = [row(1.0), row(3.0), row(None)]
        rows[2][2] = 0
        rows[0][10] = 6
        saved = deepcopy(rows)
        fitted = model.fit_preprocessor(rows)
        self.assertEqual(fitted["medians"], [2.0] * 9)
        self.assertEqual(fitted["means"], [2.0] * 9)
        transformed = model.transform(rows, fitted)
        self.assertEqual(transformed.shape, (3, 22))
        np.testing.assert_allclose(transformed[2, model.CONTINUOUS_INDICES], 0.0)
        np.testing.assert_array_equal(transformed[:, 13:], [[0]*9, [0]*9, [1]*9])
        np.testing.assert_array_equal(transformed[:, 2], [1, 1, 0])
        np.testing.assert_array_equal(transformed[:, 10], [1, .5, .5])
        self.assertEqual(rows, saved)

    def test_query_mutation_does_not_change_training_statistics(self):
        fitted = model.fit_preprocessor([row(1.), row(2.), row(4.)])
        saved = deepcopy(fitted)
        query = [row(100.), row(-50.)]
        original = deepcopy(query)
        model.transform(query, fitted)
        self.assertEqual(query, original)
        query[0][0] = -1e8
        model.transform(query, fitted)
        self.assertEqual(fitted, saved)

    def test_all_missing_and_zero_variance_are_explicit(self):
        fitted = model.fit_preprocessor([row(None), row(None)])
        self.assertEqual(fitted["all_missing"], [True] * 9)
        self.assertEqual(fitted["medians"], [0.] * 9)
        self.assertEqual(fitted["scales"], [1.] * 9)
        values = model.transform([row(None)], fitted)
        np.testing.assert_array_equal(values[0, model.CONTINUOUS_INDICES], 0.)
        np.testing.assert_array_equal(values[0, 13:], 1.)
        fixed = model.fit_preprocessor([row(5.), row(5.)])
        self.assertEqual(fixed["zero_standard_deviation"], [True] * 9)

    def test_invalid_input_and_frozen_schema_rejected(self):
        for rows in ([], [[0.] * 12], [row(float("nan"))], [row(float("inf"))]):
            with self.assertRaises(ValueError): model.fit_preprocessor(rows)
        for column, value in ((2, None), (2, .4), (10, 7), (10, .5), (11, 3), (0, True)):
            bad = row(); bad[column] = value
            with self.assertRaises(ValueError): model.fit_preprocessor([bad])
        fitted = model.fit_preprocessor([row()])
        fitted["count_divisor"] = 5
        with self.assertRaises(ValueError): model.transform([row()], fitted)

    def test_empty_query_has_fixed_shape(self):
        fitted = model.fit_preprocessor([row()])
        self.assertEqual(model.transform([], fitted).shape, (0, 22))


class LogisticTests(unittest.TestCase):
    def test_gradient_and_hessian_match_finite_difference(self):
        rng = np.random.default_rng(33)
        X = rng.normal(size=(11, 22))
        y = np.array([0,1,0,1,0,1,0,1,0,1,1])
        parameters = rng.normal(scale=.2, size=23)
        objective, gradient, hessian = model.objective_gradient_hessian(X, y, parameters)
        finite_gradient = np.zeros(23); finite_hessian = np.zeros((23,23))
        epsilon = 1e-5
        for j in range(23):
            step = np.zeros(23); step[j] = epsilon
            plus = model.objective_gradient_hessian(X, y, parameters+step)
            minus = model.objective_gradient_hessian(X, y, parameters-step)
            finite_gradient[j] = (plus[0]-minus[0])/(2*epsilon)
            finite_hessian[:,j] = (plus[1]-minus[1])/(2*epsilon)
        np.testing.assert_allclose(gradient, finite_gradient, atol=1e-7, rtol=1e-7)
        np.testing.assert_allclose(hessian, finite_hessian, atol=1e-7, rtol=1e-7)
        np.testing.assert_allclose(hessian, hessian.T, atol=1e-12)
        self.assertGreater(np.linalg.eigvalsh(hessian).min(), 0.)
        self.assertTrue(np.isfinite(objective))

    def test_unpenalized_intercept_known_optimum(self):
        X = np.zeros((10,22)); y = [1]*7 + [0]*3
        saved = X.copy(); labels = y[:]
        fitted = model.fit_logistic(X, y)
        self.assertEqual(fitted["status"], "converged")
        self.assertLessEqual(fitted["gradient_infinity_norm"], 1e-4)
        self.assertAlmostEqual(fitted["intercept"], np.log(7/3), places=5)
        np.testing.assert_array_equal(fitted["weights"], np.zeros(22))
        np.testing.assert_allclose(model.predict_probability(X, fitted), .7, atol=1e-6)
        self.assertFalse(fitted["probability_calibrated"])
        np.testing.assert_array_equal(X, saved); self.assertEqual(y, labels)

    def test_symmetric_regularized_solution_and_repeatability(self):
        X = np.zeros((8,22)); X[:,0] = [-4,-3,-2,-1,1,2,3,4]
        y = [0]*4+[1]*4
        first = model.fit_logistic(X, y); second = model.fit_logistic(X, y)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "converged")
        self.assertAlmostEqual(first["intercept"], 0.)
        self.assertGreater(first["weights"][0], 0.)
        parameters = np.r_[first["weights"], first["intercept"]]
        _, gradient, _ = model.objective_gradient_hessian(X, np.asarray(y), parameters)
        self.assertLessEqual(np.max(np.abs(gradient)), 1e-4)
        np.testing.assert_array_equal(model.predict_probability(X, first) >= .5, np.asarray(y, dtype=bool))

    def test_sigmoid_does_not_overflow(self):
        with np.errstate(over="raise", invalid="raise"):
            probabilities = model.sigmoid(np.array([-1e300, -1000., 0., 1000., 1e300]))
        np.testing.assert_array_equal(probabilities, [0.,0.,.5,1.,1.])

    def test_input_failures_are_explicit(self):
        cases = [(np.zeros((2,22)), [1,1], "single_training_class"),
            (np.zeros((2,22)), [0,2], "nonbinary_training_label"),
            (np.zeros((2,22)), [0,"uncertain"], "invalid_numeric_input"),
            (np.full((2,22), np.nan), [0,1], "nonfinite_training_input"),
            (np.zeros((2,21)), [0,1], "invalid_training_shape")]
        for X, y, expected in cases:
            with self.subTest(expected=expected):
                result = model.fit_logistic(X,y)
                self.assertEqual((result["status"],result["failure_reason"]), ("failed",expected))
                with self.assertRaises(ValueError): model.predict_probability(np.zeros((1,22)), result)

    def test_singular_nonconvergence_and_backtrack_fail_without_retry(self):
        X = np.zeros((4,22)); X[:,0] = [-2,-1,1,2]; y = [0,0,1,1]
        with patch.object(np.linalg, "solve", side_effect=np.linalg.LinAlgError("synthetic singular")) as solve:
            result = model.fit_logistic(X,y)
        self.assertEqual(result["failure_reason"], "singular_hessian"); self.assertEqual(solve.call_count,1)
        with patch.object(model, "MAX_ITERATIONS", 0):
            result = model.fit_logistic(X,y)
        self.assertEqual(result["failure_reason"], "maximum_iterations_without_convergence")
        with patch.object(model, "MAX_BACKTRACKS", 0):
            result = model.fit_logistic(X,y)
        self.assertEqual(result["failure_reason"], "armijo_backtracking_exhausted")

    def test_nonfinite_solver_state_failed_and_prediction_validated(self):
        X = np.zeros((4,22)); X[:,0] = [-1e308,-1e308,1e308,1e308]
        fitted = model.fit_logistic(X,[0,0,1,1])
        self.assertEqual(fitted["failure_reason"], "nonfinite_solver_state")
        good = model.fit_logistic(np.zeros((2,22)), [0,1])
        with self.assertRaises(ValueError): model.predict_probability(np.zeros((1,21)),good)
        with self.assertRaises(ValueError): model.predict_probability(np.full((1,22),np.inf),good)


if __name__ == "__main__":
    unittest.main()
