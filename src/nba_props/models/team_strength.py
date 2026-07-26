"""Ridge-regression team-strength model.

Estimates a single target (for example: expected point differential or
team strength rating) from basketball box-score style features via
ridge-regularised linear regression.  Originally prototyped as the
standalone ValueSauce ``BasketballValueModel`` and merged into the NBA
3PM Props Engine as a general-purpose statistical building block.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_EPSILON = 1e-12


def _to_float_array(values: Sequence[float], name: str) -> np.ndarray:
    """Convert *values* to a validated, non-empty 1D float64 array."""
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        raise ValueError(f"{name} cannot be empty")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def _to_float_matrix(rows: Sequence[Sequence[float]]) -> np.ndarray:
    """Convert *rows* to a validated 2D float64 matrix."""
    matrix = np.asarray(rows, dtype=np.float64)
    if not np.all(np.isfinite(matrix)):
        raise ValueError("feature values must contain only finite values")
    return matrix


def _kfold_indices(sample_count: int, folds: int) -> List[np.ndarray]:
    """Split ``range(sample_count)`` into *folds* interleaved validation buckets."""
    if folds < 2:
        raise ValueError("folds must be at least 2")
    if folds > sample_count:
        raise ValueError("folds cannot exceed sample count")

    indices = np.arange(sample_count)
    return [indices[i::folds] for i in range(folds)]


class BasketballValueModel:
    """Ridge-regularised linear model for basketball value prediction.

    Features are standardised during training for numerical stability
    across basketball metrics with very different scales (pace, ratings,
    percentages, ...).
    """

    def __init__(
        self,
        ridge_alpha: float = 1e-3,
        feature_names: Optional[Sequence[str]] = None,
    ):
        self.name = "basketball_value_model"
        self.ridge_alpha = ridge_alpha
        self.feature_names = tuple(feature_names) if feature_names is not None else None

        self.weights: Optional[np.ndarray] = None
        self.bias: float = 0.0
        self.is_fitted: bool = False

        self._means: Optional[np.ndarray] = None
        self._scales: Optional[np.ndarray] = None
        self.logger = logging.getLogger(f"{__name__}.{self.name}")

    # ------------------------------------------------------------------ #
    # fit
    # ------------------------------------------------------------------ #

    def fit(
        self,
        features: Sequence[Sequence[float]],
        targets: Sequence[float],
        sample_weights: Optional[Sequence[float]] = None,
    ) -> "BasketballValueModel":
        """Fit the ridge regression via weighted least squares.

        Parameters
        ----------
        features : sequence of sequence of float
            Feature matrix ``(n_samples, n_features)``.
        targets : sequence of float
            Target values ``(n_samples,)``.
        sample_weights : sequence of float, optional
            Positive per-sample weights.  Defaults to uniform weighting.

        Returns
        -------
        BasketballValueModel
            ``self``, to allow method chaining.
        """
        if self.ridge_alpha < 0:
            raise ValueError("ridge_alpha must be non-negative")
        if len(features) == 0:
            raise ValueError("features cannot be empty")

        row_count = len(features)
        if row_count != len(targets):
            raise ValueError("feature and target counts must match")

        column_count = len(features[0])
        if column_count == 0:
            raise ValueError("features must include at least one column")
        if any(len(row) != column_count for row in features):
            raise ValueError("all feature rows must have the same number of columns")

        X = _to_float_matrix(features)
        y = _to_float_array(targets, "targets")

        if self.feature_names is not None and len(self.feature_names) != column_count:
            raise ValueError("feature_names length must match feature column count")

        if sample_weights is None:
            w = np.ones(row_count, dtype=np.float64)
        else:
            w = _to_float_array(sample_weights, "sample_weights")
            if w.shape[0] != row_count:
                raise ValueError("sample_weights length must match feature count")
            if np.any(w <= 0):
                raise ValueError("sample_weights must be positive")

        self._means = np.average(X, axis=0, weights=w)
        variance = np.average((X - self._means) ** 2, axis=0, weights=w)
        self._scales = np.where(variance <= _EPSILON, 1.0, np.sqrt(variance))

        X_std = (X - self._means) / self._scales
        y_mean = float(np.average(y, weights=w))
        y_centered = y - y_mean

        # Weighted ridge normal equations: (X'WX + alpha*I) beta = X'Wy
        xtx = X_std.T @ (X_std * w[:, None])
        xtx[np.diag_indices_from(xtx)] += self.ridge_alpha
        xty = X_std.T @ (w * y_centered)

        try:
            standardized_weights = np.linalg.solve(xtx, xty)
        except np.linalg.LinAlgError as exc:
            raise ValueError("unable to solve system; matrix is singular") from exc

        self.weights = standardized_weights / self._scales
        self.bias = float(y_mean - self.weights @ self._means)
        self.is_fitted = True
        self.logger.info(
            "BasketballValueModel fit complete (alpha=%.4g, n=%d, features=%d)",
            self.ridge_alpha,
            row_count,
            column_count,
        )
        return self

    def tune_ridge_alpha(
        self,
        features: Sequence[Sequence[float]],
        targets: Sequence[float],
        candidates: Sequence[float],
        folds: int = 5,
        sample_weights: Optional[Sequence[float]] = None,
    ) -> float:
        """Select ``ridge_alpha`` via k-fold cross-validated R^2.

        Parameters
        ----------
        features, targets : see :meth:`fit`.
        candidates : sequence of float
            Candidate ``ridge_alpha`` values to evaluate.
        folds : int
            Number of cross-validation folds (>= 2).
        sample_weights : sequence of float, optional
            Passed through to each fold's ``fit`` call.

        Returns
        -------
        float
            The selected ``ridge_alpha``.  The instance is refit on the
            full dataset using this value before returning.
        """
        alpha_candidates = _to_float_array(candidates, "candidates")
        if np.any(alpha_candidates < 0):
            raise ValueError("all ridge candidates must be non-negative")

        fold_groups = _kfold_indices(len(features), folds)

        best_alpha = float(alpha_candidates[0])
        best_score = float("-inf")

        for alpha in alpha_candidates:
            fold_scores: List[float] = []
            for val_idx in fold_groups:
                val_set = set(val_idx.tolist())
                train_idx = [i for i in range(len(features)) if i not in val_set]

                train_x = [features[i] for i in train_idx]
                train_y = [targets[i] for i in train_idx]
                val_x = [features[i] for i in val_idx]
                val_y = [targets[i] for i in val_idx]

                train_w = None
                if sample_weights is not None:
                    train_w = [sample_weights[i] for i in train_idx]

                candidate_model = BasketballValueModel(
                    ridge_alpha=float(alpha), feature_names=self.feature_names
                )
                try:
                    candidate_model.fit(train_x, train_y, sample_weights=train_w)
                except ValueError:
                    fold_scores.append(float("-inf"))
                    continue
                fold_scores.append(candidate_model.score_r2(val_x, val_y))

            mean_score = float(np.mean(fold_scores))
            if mean_score > best_score:
                best_score = mean_score
                best_alpha = float(alpha)

        self.ridge_alpha = best_alpha
        self.fit(features, targets, sample_weights=sample_weights)
        return best_alpha

    # ------------------------------------------------------------------ #
    # predict
    # ------------------------------------------------------------------ #

    def predict_one(self, feature_row: Sequence[float]) -> float:
        """Predict the target for a single feature row."""
        self._check_fitted()
        row = _to_float_array(feature_row, "feature_row")
        if row.shape[0] != self.weights.shape[0]:
            raise ValueError("feature row width does not match fitted model")
        return float(self.bias + self.weights @ row)

    def predict(self, features: Sequence[Sequence[float]]) -> List[float]:
        """Predict targets for a batch of feature rows."""
        if len(features) == 0:
            return []
        return [self.predict_one(row) for row in features]

    # ------------------------------------------------------------------ #
    # evaluate
    # ------------------------------------------------------------------ #

    def score_r2(self, features: Sequence[Sequence[float]], targets: Sequence[float]) -> float:
        """Return the coefficient of determination (R^2) on *features*/*targets*."""
        y_true = _to_float_array(targets, "targets")
        preds = np.asarray(self.predict(features), dtype=np.float64)
        if preds.shape[0] != y_true.shape[0]:
            raise ValueError("feature and target counts must match")

        y_mean = float(np.mean(y_true))
        ss_tot = float(np.sum((y_true - y_mean) ** 2))
        ss_res = float(np.sum((y_true - preds) ** 2))
        if ss_tot <= _EPSILON:
            # Target is constant across this fold/sample. Only report a
            # perfect score if predictions are (numerically) exact too --
            # otherwise a bad-but-nonzero-residual fold would silently be
            # scored as a perfect fit and skew fold-averaged selection in
            # tune_ridge_alpha.
            return 1.0 if ss_res <= _EPSILON else 0.0
        return 1 - (ss_res / ss_tot)

    def score_rmse(self, features: Sequence[Sequence[float]], targets: Sequence[float]) -> float:
        """Return the root-mean-squared error on *features*/*targets*."""
        y_true = _to_float_array(targets, "targets")
        preds = np.asarray(self.predict(features), dtype=np.float64)
        if preds.shape[0] != y_true.shape[0]:
            raise ValueError("feature and target counts must match")
        mse = float(np.mean((y_true - preds) ** 2))
        return mse**0.5

    def feature_importance(self) -> List[Tuple[str, float]]:
        """Return ``(name, weight)`` pairs sorted by absolute weight, descending."""
        self._check_fitted()
        names = self.feature_names or tuple(f"feature_{i}" for i in range(self.weights.shape[0]))
        pairs = list(zip(names, (float(w) for w in self.weights)))
        return sorted(pairs, key=lambda pair: abs(pair[1]), reverse=True)

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _check_fitted(self) -> None:
        if not self.is_fitted:
            raise RuntimeError(f"{self.name} has not been fitted yet. Call fit() first.")
