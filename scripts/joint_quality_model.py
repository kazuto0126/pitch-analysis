"""Pure fixed NumPy preprocessing and logistic fitting for the frozen experiment.

No file IO or annotation access lives here. Probabilities are uncalibrated model
outputs, and an absent review hint must never be read as verified reliability.
"""
from __future__ import annotations

import math
from numbers import Real
from typing import Sequence

import numpy as np


CONTINUOUS_INDICES = (0, 1, 3, 4, 5, 6, 7, 8, 9)
BINARY_INDICES = (2, 11, 12)
INPUT_COLUMNS = 13
OUTPUT_COLUMNS = 22
C = 1.0
MAX_ITERATIONS = 100
GRADIENT_TOLERANCE = 1e-4
ARMIJO = 1e-4
MAX_BACKTRACKS = 25
HINT_THRESHOLD = 0.5


def _rows(rows: Sequence[Sequence[float | None]]) -> np.ndarray:
    """Validate original fixed features; only None denotes missingness."""
    values = list(rows)
    matrix = np.empty((len(values), INPUT_COLUMNS), dtype=np.float64)
    for i, row in enumerate(values):
        if len(row) != INPUT_COLUMNS:
            raise ValueError("feature rows must contain exactly 13 columns")
        for j, value in enumerate(row):
            if value is None and j in CONTINUOUS_INDICES:
                matrix[i, j] = np.nan
                continue
            if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
                raise ValueError(f"feature {j} must be a finite number or continuous None")
            number = float(value)
            if not math.isfinite(number):
                raise ValueError(f"feature {j} is nonfinite")
            if j in BINARY_INDICES and number not in (0.0, 1.0):
                raise ValueError(f"feature {j} must be 0 or 1")
            if j == 10 and (number < 0 or number > 6 or number != int(number)):
                raise ValueError("compatible candidate count must be an integer from 0 to 6")
            matrix[i, j] = number
    return matrix


def fit_preprocessor(rows: Sequence[Sequence[float | None]]) -> dict:
    """Fit nine median imputers and scales using training rows only."""
    matrix = _rows(rows)
    if not len(matrix):
        raise ValueError("preprocessing requires at least one training row")
    continuous = matrix[:, CONTINUOUS_INDICES].copy()
    missing = np.isnan(continuous)
    medians = np.array([
        float(np.median(continuous[~missing[:, j], j])) if (~missing[:, j]).any() else 0.0
        for j in range(len(CONTINUOUS_INDICES))
    ], dtype=np.float64)
    continuous = np.where(missing, medians, continuous)
    with np.errstate(over="ignore", invalid="ignore"):
        means = continuous.mean(axis=0)
        standard_deviations = continuous.std(axis=0, ddof=0)
    if not (np.isfinite(medians).all() and np.isfinite(means).all()
            and np.isfinite(standard_deviations).all()):
        raise ValueError("nonfinite fitted preprocessing statistics")
    scales = np.where(standard_deviations == 0.0, 1.0, standard_deviations)
    return {
        "schema": "fixed_joint_quality_preprocessor_v1",
        "input_columns": INPUT_COLUMNS,
        "output_columns": OUTPUT_COLUMNS,
        "continuous_indices": list(CONTINUOUS_INDICES),
        "training_rows": len(matrix),
        "medians": medians.tolist(),
        "means": means.tolist(),
        "scales": scales.tolist(),
        "all_missing": missing.all(axis=0).tolist(),
        "zero_standard_deviation": (standard_deviations == 0.0).tolist(),
        "missing_indicator_indices": list(CONTINUOUS_INDICES),
        "count_divisor": 6.0,
    }


def _preprocessing_arrays(preprocessor: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if (preprocessor.get("schema") != "fixed_joint_quality_preprocessor_v1"
            or preprocessor.get("input_columns") != INPUT_COLUMNS
            or preprocessor.get("output_columns") != OUTPUT_COLUMNS
            or preprocessor.get("continuous_indices") != list(CONTINUOUS_INDICES)
            or preprocessor.get("missing_indicator_indices") != list(CONTINUOUS_INDICES)
            or preprocessor.get("count_divisor") != 6.0):
        raise ValueError("preprocessor does not match frozen feature contract")
    arrays = tuple(np.asarray(preprocessor[k], dtype=np.float64) for k in ("medians", "means", "scales"))
    if any(a.shape != (9,) or not np.isfinite(a).all() for a in arrays):
        raise ValueError("invalid preprocessing statistics")
    if (arrays[2] <= 0.0).any():
        raise ValueError("preprocessing scales must be positive")
    return arrays


def transform(rows: Sequence[Sequence[float | None]], preprocessor: dict) -> np.ndarray:
    """Apply sealed training statistics without changing them or input rows."""
    matrix = _rows(rows)
    medians, means, scales = _preprocessing_arrays(preprocessor)
    continuous = matrix[:, CONTINUOUS_INDICES].copy()
    missing = np.isnan(continuous)
    with np.errstate(over="ignore", invalid="ignore"):
        matrix[:, CONTINUOUS_INDICES] = (np.where(missing, medians, continuous) - means) / scales
    matrix[:, 10] /= 6.0
    result = np.column_stack((matrix, missing.astype(np.float64)))
    if result.shape != (len(matrix), OUTPUT_COLUMNS) or not np.isfinite(result).all():
        raise ValueError("nonfinite transformed features")
    return result


def sigmoid(values: np.ndarray) -> np.ndarray:
    """Stable sigmoid; evaluates exponentials only on a nonpositive argument."""
    values = np.asarray(values, dtype=np.float64)
    result = np.empty_like(values)
    positive = values >= 0.0
    result[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
    negative_exp = np.exp(values[~positive])
    result[~positive] = negative_exp / (1.0 + negative_exp)
    return result


def objective_gradient_hessian(X: np.ndarray, y: np.ndarray, parameters: np.ndarray):
    """Frozen summed logistic objective with unpenalized final intercept."""
    weights = parameters[:-1]
    intercept = parameters[-1]
    design = np.column_stack((X, np.ones(len(X), dtype=np.float64)))
    z = X @ weights + intercept
    probability = sigmoid(z)
    objective = float(np.sum(np.logaddexp(0.0, z) - y * z) + np.dot(weights, weights) / (2.0 * C))
    regularization = np.r_[weights / C, 0.0]
    gradient = design.T @ (probability - y) + regularization
    curvature = probability * (1.0 - probability)
    hessian = design.T @ (curvature[:, None] * design)
    hessian.flat[::len(parameters) + 1] += np.r_[np.full(len(weights), 1.0 / C), 0.0]
    return objective, gradient, hessian


def _result(status, reason, parameters, iterations, objective=None, gradient=None):
    norm = float(np.max(np.abs(gradient))) if gradient is not None and np.isfinite(gradient).all() else None
    finite_parameters = parameters is not None and np.isfinite(parameters).all()
    return {
        "status": status,
        "failure_reason": reason,
        "weights": parameters[:-1].tolist() if finite_parameters else None,
        "intercept": float(parameters[-1]) if finite_parameters else None,
        "iterations": iterations,
        "objective": float(objective) if objective is not None and math.isfinite(objective) else None,
        "gradient_infinity_norm": norm,
        "C": C,
        "max_iterations": MAX_ITERATIONS,
        "gradient_tolerance": GRADIENT_TOLERANCE,
        "hint_threshold": HINT_THRESHOLD,
        "probability_calibrated": False,
    }


def fit_logistic(X: np.ndarray, y: Sequence[int]) -> dict:
    """Fit once with fixed settings, returning explicit failure without retries."""
    try:
        matrix = np.asarray(X, dtype=np.float64)
        labels = np.asarray(y, dtype=np.float64)
    except (TypeError, ValueError, OverflowError):
        return _result("failed", "invalid_numeric_input", None, 0)
    if matrix.ndim != 2 or matrix.shape[1] != OUTPUT_COLUMNS or labels.shape != (len(matrix),) or not len(matrix):
        return _result("failed", "invalid_training_shape", None, 0)
    if not np.isfinite(matrix).all() or not np.isfinite(labels).all():
        return _result("failed", "nonfinite_training_input", None, 0)
    if not np.isin(labels, [0.0, 1.0]).all():
        return _result("failed", "nonbinary_training_label", None, 0)
    if len(np.unique(labels)) != 2:
        return _result("failed", "single_training_class", None, 0)
    parameters = np.zeros(OUTPUT_COLUMNS + 1, dtype=np.float64)
    for iteration in range(MAX_ITERATIONS + 1):
        with np.errstate(over="ignore", invalid="ignore", under="ignore"):
            objective, gradient, hessian = objective_gradient_hessian(matrix, labels, parameters)
        if not (math.isfinite(objective) and np.isfinite(gradient).all() and np.isfinite(hessian).all()):
            return _result("failed", "nonfinite_solver_state", parameters, iteration, objective, gradient)
        if np.max(np.abs(gradient)) <= GRADIENT_TOLERANCE:
            return _result("converged", None, parameters, iteration, objective, gradient)
        if iteration == MAX_ITERATIONS:
            return _result("failed", "maximum_iterations_without_convergence", parameters, iteration, objective, gradient)
        try:
            step = np.linalg.solve(hessian, -gradient)
        except np.linalg.LinAlgError:
            return _result("failed", "singular_hessian", parameters, iteration, objective, gradient)
        directional_derivative = float(np.dot(gradient, step))
        if not np.isfinite(step).all() or not math.isfinite(directional_derivative) or directional_derivative >= 0.0:
            return _result("failed", "invalid_newton_direction", parameters, iteration, objective, gradient)
        alpha = 1.0
        accepted = False
        for _ in range(MAX_BACKTRACKS):
            candidate = parameters + alpha * step
            with np.errstate(over="ignore", invalid="ignore", under="ignore"):
                candidate_objective, _, _ = objective_gradient_hessian(matrix, labels, candidate)
            if math.isfinite(candidate_objective) and candidate_objective <= objective + ARMIJO * alpha * directional_derivative:
                parameters = candidate
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            return _result("failed", "armijo_backtracking_exhausted", parameters, iteration, objective, gradient)
    raise AssertionError("fixed solver loop must return")


def predict_probability(X: np.ndarray, model: dict) -> np.ndarray:
    """Apply sealed uncalibrated model only; failed fits cannot emit predictions."""
    if model.get("status") != "converged":
        raise ValueError("cannot predict with failed or unfinished model")
    matrix = np.asarray(X, dtype=np.float64)
    weights = np.asarray(model.get("weights"), dtype=np.float64)
    intercept = model.get("intercept")
    if (matrix.ndim != 2 or matrix.shape[1] != OUTPUT_COLUMNS or not np.isfinite(matrix).all()
            or weights.shape != (OUTPUT_COLUMNS,) or not np.isfinite(weights).all()
            or not isinstance(intercept, Real) or not math.isfinite(intercept)):
        raise ValueError("invalid prediction matrix or fitted coefficients")
    with np.errstate(over="ignore", invalid="ignore"):
        z = matrix @ weights + intercept
    if not np.isfinite(z).all():
        raise ValueError("nonfinite prediction logit")
    return sigmoid(z)
