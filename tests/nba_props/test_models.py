"""Tests for prediction models."""

import numpy as np
import pytest

from nba_props.models.minutes_model import MinutesModel
from nba_props.models.three_pa_model import ThreePAModel
from nba_props.models.make_rate_model import MakeRateModel
from nba_props.models.baseline import (
    BookmakerBaseline,
    DirectThreePMBaseline,
    RollingAverageBaseline,
)


class TestMinutesModel:
    def test_init(self):
        model = MinutesModel(version="1.0")
        assert model.name == "minutes_model"
        assert model.is_fitted is False

    def test_fit_and_predict(self):
        model = MinutesModel(version="1.0")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((100, 5))
        y = 28 + 3 * X[:, 0] + rng.standard_normal(100) * 2

        model.fit(X, y)
        assert model.is_fitted is True

        preds = model.predict(X)
        assert preds.shape == (100,)
        assert np.mean(np.abs(preds - y)) < 5.0  # Reasonable MAE

    def test_predict_quantiles(self):
        model = MinutesModel(version="1.0")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((100, 5))
        y = 28 + 3 * X[:, 0] + rng.standard_normal(100) * 2

        model.fit(X, y)
        quantiles = model.predict_quantiles(X)

        assert "p10" in quantiles
        assert "p50" in quantiles
        assert "p90" in quantiles
        assert quantiles["p10"].shape == (100,)
        # p10 <= p50 <= p90 on average
        assert np.mean(quantiles["p10"]) <= np.mean(quantiles["p50"])
        assert np.mean(quantiles["p50"]) <= np.mean(quantiles["p90"])

    def test_evaluate(self):
        model = MinutesModel(version="1.0")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((100, 5))
        y = 28 + 3 * X[:, 0] + rng.standard_normal(100) * 2

        model.fit(X, y)
        metrics = model.evaluate(X, y)
        assert "mae_overall" in metrics
        assert metrics["mae_overall"] >= 0


class TestThreePAModel:
    def test_init(self):
        model = ThreePAModel(version="1.0")
        assert model.name == "three_pa_model"

    def test_fit_and_predict(self):
        model = ThreePAModel(version="1.0", distribution="gbm_count")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((200, 5))
        y = np.maximum(0, np.round(3 + X[:, 0] + rng.standard_normal(200))).astype(int)
        minutes = 30 + rng.standard_normal(200) * 3

        model.fit(X, y, minutes_exposure=minutes)
        assert model.is_fitted is True

        preds = model.predict(X, minutes_exposure=minutes)
        assert preds.shape == (200,)
        assert np.all(preds >= 0)

    def test_predict_distribution_params(self):
        model = ThreePAModel(version="1.0", distribution="gbm_count")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((200, 5))
        y = np.maximum(0, np.round(3 + X[:, 0] + rng.standard_normal(200))).astype(int)
        minutes = 30 + rng.standard_normal(200) * 3

        model.fit(X, y, minutes_exposure=minutes)
        params = model.predict_distribution_params(X, minutes_exposure=minutes)

        assert "mean" in params
        assert "dispersion" in params



    def test_poisson_rejects_negative_targets(self):
        model = ThreePAModel(version="1.0", distribution="poisson")
        X = np.zeros((5, 2))
        y = np.array([1.0, 0.0, -0.5, 2.0, 1.0])
        minutes = np.full(5, 30.0)

        with pytest.raises(ValueError, match="non-negative"):
            model.fit(X, y, minutes_exposure=minutes)

    def test_predict_rejects_non_finite_features(self):
        model = ThreePAModel(version="1.0", distribution="poisson")
        X = np.zeros((20, 3))
        y = np.ones(20)
        minutes = np.full(20, 24.0)
        model.fit(X, y, minutes_exposure=minutes)

        X_bad = np.zeros((2, 3))
        X_bad[0, 1] = np.nan
        with pytest.raises(ValueError, match="finite"):
            model.predict(X_bad, minutes_exposure=np.array([20.0, 20.0]))

    def test_poisson_rejects_invalid_minutes_inputs(self):
        model = ThreePAModel(version="1.0", distribution="poisson")
        X = np.zeros((6, 3))
        y = np.ones(6)

        with pytest.raises(ValueError, match="negative"):
            model.fit(X, y, minutes_exposure=np.array([30, 28, -1, 25, 26, 27]))

        with pytest.raises(ValueError, match="length"):
            model.fit(X, y, minutes_exposure=np.array([30, 28, 25]))

    def test_poisson_handles_zero_minutes_without_nan(self):
        model = ThreePAModel(version="1.0", distribution="poisson")
        rng = np.random.default_rng(123)
        X = rng.standard_normal((120, 3))
        minutes = rng.uniform(0, 35, size=120)
        y = rng.poisson(0.12 * minutes)

        model.fit(X, y, minutes_exposure=minutes)
        preds = model.predict(X[:20], minutes_exposure=np.zeros(20))

        assert np.all(np.isfinite(preds))
        assert np.all(preds >= 0)
        assert np.max(preds) < 0.5

    def test_poisson_minutes_exposure_scales_predictions(self):
        model = ThreePAModel(version="1.0", distribution="poisson")
        rng = np.random.default_rng(7)
        X = rng.standard_normal((300, 4))
        minutes = rng.uniform(12, 38, size=300)

        # Constant per-minute shot rate with Poisson noise.
        true_rate = 0.18
        y = rng.poisson(true_rate * minutes)

        model.fit(X, y, minutes_exposure=minutes)

        X_eval = np.zeros((32, 4))
        short_minutes = np.full(32, 18.0)
        long_minutes = np.full(32, 36.0)

        pred_short = model.predict(X_eval, minutes_exposure=short_minutes)
        pred_long = model.predict(X_eval, minutes_exposure=long_minutes)

        # Doubling minutes should approximately double predicted count.
        ratio = np.mean(pred_long) / np.mean(pred_short)
        assert ratio == pytest.approx(2.0, rel=0.25)


class TestMakeRateModel:
    def test_init(self):
        model = MakeRateModel(version="1.0")
        assert model.name == "make_rate_model"

    def test_shrink_to_prior(self):
        # Player with 100 3PA and 40 3PM (40%)
        shrunk = MakeRateModel._shrink_to_prior(40, 100, 0.363, 100)
        # Should be between 36.3% and 40%
        assert 0.363 < shrunk < 0.40

    def test_shrink_small_sample(self):
        # Player with only 10 3PA and 5 3PM (50%) - should shrink heavily
        shrunk = MakeRateModel._shrink_to_prior(5, 10, 0.363, 100)
        # Should be close to prior with small sample
        assert shrunk < 0.45
        assert shrunk > 0.363

    def test_fit_and_predict(self):
        model = MakeRateModel(version="1.0", method="logit_gbm")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((200, 5))
        attempts = rng.integers(3, 12, size=200)
        makes = rng.binomial(attempts, 0.36)

        model.fit(X, makes, attempts)
        assert model.is_fitted is True

        preds = model.predict(X)
        assert preds.shape == (200,)
        assert np.all(preds > 0)
        assert np.all(preds < 1)

    def test_predict_with_uncertainty(self):
        model = MakeRateModel(version="1.0", method="logit_gbm")
        rng = np.random.default_rng(42)
        X = rng.standard_normal((200, 5))
        attempts = rng.integers(3, 12, size=200)
        makes = rng.binomial(attempts, 0.36)

        model.fit(X, makes, attempts)
        result = model.predict_with_uncertainty(X)

        assert "mean" in result
        assert "uncertainty" in result
        assert np.all(result["uncertainty"] > 0)


class TestRollingAverageBaseline:
    def test_predict_3pm(self):
        baseline = RollingAverageBaseline()
        games = [3, 2, 4, 1, 3]
        avg = baseline.predict_3pm(games, window=5)
        assert avg == pytest.approx(2.6)

    def test_predict_p_over(self):
        baseline = RollingAverageBaseline()
        games = [3, 2, 4, 1, 3, 0, 5, 2, 1, 3]
        p_over = baseline.predict_p_over(games, line=2.5, window=10)
        # 3, 4, 3, 5, 3 are over 2.5 => 5/10 = 0.5
        assert p_over == pytest.approx(0.5)


class TestBookmakerBaseline:
    def test_predict(self):
        baseline = BookmakerBaseline()
        prob = baseline.predict_p_over(0.55)
        assert prob == 0.55
