"""Tests for backtest metrics computation."""

import numpy as np
import pytest

from nba_props.backtest.metrics import BacktestMetrics


class TestMinutesMetrics:
    def test_perfect_prediction(self):
        actual = np.array([30.0, 32.0, 28.0, 35.0])
        predicted = actual.copy()
        p10 = actual - 5
        p90 = actual + 5

        metrics = BacktestMetrics.compute_minutes_metrics(
            actual, predicted, p10, p90
        )
        assert metrics.mae_overall == pytest.approx(0.0)
        assert metrics.interval_coverage_80 == pytest.approx(1.0)

    def test_imperfect_prediction(self):
        actual = np.array([30.0, 32.0, 28.0, 35.0])
        predicted = np.array([28.0, 34.0, 26.0, 33.0])
        p10 = predicted - 5
        p90 = predicted + 5

        metrics = BacktestMetrics.compute_minutes_metrics(
            actual, predicted, p10, p90
        )
        assert metrics.mae_overall == pytest.approx(2.0)
        assert metrics.interval_coverage_80 == pytest.approx(1.0)

    def test_role_buckets(self):
        actual = np.array([30.0, 32.0, 20.0, 22.0])
        predicted = np.array([28.0, 34.0, 18.0, 24.0])
        p10 = predicted - 5
        p90 = predicted + 5
        minutes_avg = np.array([30.0, 32.0, 20.0, 22.0])

        metrics = BacktestMetrics.compute_minutes_metrics(
            actual, predicted, p10, p90, minutes_avg
        )
        assert metrics.mae_starters >= 0
        assert metrics.mae_rotation >= 0


class TestThreePAMetrics:
    def test_basic(self):
        actual = np.array([5, 7, 3, 8, 6])
        predicted = np.array([5.5, 6.5, 3.5, 7.5, 5.5])

        metrics = BacktestMetrics.compute_3pa_metrics(actual, predicted)
        assert metrics.mae >= 0
        assert metrics.rmse >= metrics.mae  # RMSE >= MAE always


class TestThreePMMetrics:
    def test_perfect_calibration(self):
        actual = np.array([1, 0, 1, 0, 1, 0, 1, 0, 1, 0])
        p_over = np.array([0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1, 0.9, 0.1])

        metrics = BacktestMetrics.compute_3pm_metrics(actual, p_over)
        assert metrics.log_loss < 0.5
        assert metrics.brier_score < 0.1
        assert metrics.sharpness > 0.3

    def test_random_predictions(self):
        actual = np.array([1, 0, 1, 0, 1])
        p_over = np.array([0.5, 0.5, 0.5, 0.5, 0.5])

        metrics = BacktestMetrics.compute_3pm_metrics(actual, p_over)
        assert metrics.sharpness == pytest.approx(0.0, abs=0.001)


class TestBettingMetrics:
    def test_all_wins(self):
        metrics = BacktestMetrics.compute_betting_metrics(
            edges=np.array([0.05, 0.04, 0.06]),
            results=np.array([1, 1, 1]),
            stakes=np.array([0.005, 0.005, 0.005]),
            odds_decimal=np.array([2.0, 1.9, 2.1]),
        )
        assert metrics.roi > 0
        assert metrics.hit_rate == 1.0
        assert metrics.n_bets == 3

    def test_all_losses(self):
        metrics = BacktestMetrics.compute_betting_metrics(
            edges=np.array([0.03, 0.03]),
            results=np.array([-1, -1]),
            stakes=np.array([0.005, 0.005]),
            odds_decimal=np.array([2.0, 2.0]),
        )
        assert metrics.roi < 0
        assert metrics.hit_rate == 0.0

    def test_empty(self):
        metrics = BacktestMetrics.compute_betting_metrics(
            edges=np.array([]),
            results=np.array([]),
            stakes=np.array([]),
            odds_decimal=np.array([]),
        )
        assert metrics.n_bets == 0

    def test_drawdown(self):
        metrics = BacktestMetrics.compute_betting_metrics(
            edges=np.array([0.05, 0.05, 0.05, 0.05]),
            results=np.array([1, -1, -1, 1]),
            stakes=np.array([0.005, 0.005, 0.005, 0.005]),
            odds_decimal=np.array([2.0, 2.0, 2.0, 2.0]),
        )
        assert metrics.max_drawdown >= 0


class TestReliabilityCurve:
    def test_bins_present(self):
        actual = np.array([1, 0, 1, 0, 1, 0, 1, 1, 0, 0] * 10)
        p_over = np.array([0.8, 0.2, 0.7, 0.3, 0.9, 0.1, 0.6, 0.8, 0.4, 0.2] * 10)

        curve = BacktestMetrics.compute_reliability_curve(actual, p_over, n_bins=5)
        assert isinstance(curve, list)
        assert len(curve) > 0
        for point in curve:
            assert "bin_lower" in point
            assert "mean_predicted" in point
            assert "mean_actual" in point
            assert "count" in point
