"""Tests for Monte Carlo pricing engine."""

import pytest
from nba_props.pricing.monte_carlo import MonteCarloSimulator, SimulationResult


class TestMonteCarloSimulator:
    def setup_method(self):
        self.sim = MonteCarloSimulator(n_simulations=10000, seed=42)

    def test_simulate_returns_result(self):
        result = self.sim.simulate(
            minutes_p10=25.0,
            minutes_p50=32.0,
            minutes_p90=38.0,
            three_pa_mean=7.0,
            three_pa_dispersion=3.0,
            make_prob_mean=0.38,
            make_prob_uncertainty=0.05,
            line=2.5,
        )
        assert isinstance(result, SimulationResult)

    def test_probabilities_sum_to_one(self):
        result = self.sim.simulate(
            minutes_p10=25.0,
            minutes_p50=32.0,
            minutes_p90=38.0,
            three_pa_mean=7.0,
            three_pa_dispersion=3.0,
            make_prob_mean=0.38,
            make_prob_uncertainty=0.05,
            line=2.5,
        )
        assert result.p_over + result.p_under == pytest.approx(1.0, abs=0.001)

    def test_high_volume_shooter_over_likely(self):
        """A high-volume shooter with good accuracy should have p_over > 0.5 at 2.5."""
        result = self.sim.simulate(
            minutes_p10=30.0,
            minutes_p50=35.0,
            minutes_p90=40.0,
            three_pa_mean=9.0,
            three_pa_dispersion=4.0,
            make_prob_mean=0.40,
            make_prob_uncertainty=0.04,
            line=2.5,
        )
        assert result.p_over > 0.5

    def test_low_volume_under_likely(self):
        """A low-volume shooter should lean under at 2.5."""
        result = self.sim.simulate(
            minutes_p10=15.0,
            minutes_p50=22.0,
            minutes_p90=28.0,
            three_pa_mean=3.0,
            three_pa_dispersion=2.0,
            make_prob_mean=0.33,
            make_prob_uncertainty=0.06,
            line=2.5,
        )
        assert result.p_under > 0.5

    def test_alt_line_probs(self):
        result = self.sim.simulate(
            minutes_p10=25.0,
            minutes_p50=32.0,
            minutes_p90=38.0,
            three_pa_mean=7.0,
            three_pa_dispersion=3.0,
            make_prob_mean=0.38,
            make_prob_uncertainty=0.05,
            line=2.5,
        )
        assert 0.5 in result.alt_line_probs
        assert 1.5 in result.alt_line_probs
        assert 3.5 in result.alt_line_probs
        # P(over 0.5) should be highest
        assert result.alt_line_probs[0.5]["p_over"] > result.alt_line_probs[3.5]["p_over"]

    def test_fair_odds_reasonable(self):
        result = self.sim.simulate(
            minutes_p10=25.0,
            minutes_p50=32.0,
            minutes_p90=38.0,
            three_pa_mean=7.0,
            three_pa_dispersion=3.0,
            make_prob_mean=0.38,
            make_prob_uncertainty=0.05,
            line=2.5,
        )
        # Fair odds should be > 1.0 in decimal
        assert result.fair_odds_over_decimal > 1.0
        assert result.fair_odds_under_decimal > 1.0

    def test_mean_3pm_reasonable(self):
        result = self.sim.simulate(
            minutes_p10=25.0,
            minutes_p50=32.0,
            minutes_p90=38.0,
            three_pa_mean=7.0,
            three_pa_dispersion=3.0,
            make_prob_mean=0.38,
            make_prob_uncertainty=0.05,
            line=2.5,
        )
        # Mean 3PM should be roughly 3PA * make_rate
        assert 1.0 < result.mean_3pm < 5.0
        assert result.p10_3pm <= result.median_3pm <= result.p90_3pm

    def test_simulation_count(self):
        result = self.sim.simulate(
            minutes_p10=25.0,
            minutes_p50=32.0,
            minutes_p90=38.0,
            three_pa_mean=7.0,
            three_pa_dispersion=3.0,
            make_prob_mean=0.38,
            make_prob_uncertainty=0.05,
            line=2.5,
        )
        assert result.simulations == 10000

    def test_zero_minutes_edge_case(self):
        """Edge case: near-zero minutes should produce mostly zeros."""
        result = self.sim.simulate(
            minutes_p10=0.0,
            minutes_p50=1.0,
            minutes_p90=5.0,
            three_pa_mean=0.5,
            three_pa_dispersion=1.0,
            make_prob_mean=0.35,
            make_prob_uncertainty=0.10,
            line=0.5,
        )
        # With ~1 minute, should almost always go under 0.5
        assert result.p_under > 0.5

    def test_reproducible_with_seed(self):
        """Same seed should produce same results."""
        sim1 = MonteCarloSimulator(n_simulations=5000, seed=123)
        sim2 = MonteCarloSimulator(n_simulations=5000, seed=123)

        params = dict(
            minutes_p10=25.0, minutes_p50=32.0, minutes_p90=38.0,
            three_pa_mean=7.0, three_pa_dispersion=3.0,
            make_prob_mean=0.38, make_prob_uncertainty=0.05,
            line=2.5,
        )
        r1 = sim1.simulate(**params)
        r2 = sim2.simulate(**params)
        assert r1.p_over == pytest.approx(r2.p_over, abs=0.001)
