"""Tests for odds conversion and math utilities."""

import pytest
from nba_props.utils.odds_math import (
    american_to_decimal,
    american_to_implied,
    compute_ev,
    compute_hold,
    decimal_to_american,
    half_kelly,
    implied_to_american,
    kelly_criterion,
    remove_vig_multiplicative,
    remove_vig_power,
)


class TestAmericanToDecimal:
    def test_positive_odds(self):
        assert american_to_decimal(150) == pytest.approx(2.5)

    def test_negative_odds(self):
        assert american_to_decimal(-200) == pytest.approx(1.5)

    def test_even_money(self):
        assert american_to_decimal(100) == pytest.approx(2.0)

    def test_large_underdog(self):
        assert american_to_decimal(500) == pytest.approx(6.0)

    def test_heavy_favorite(self):
        assert american_to_decimal(-500) == pytest.approx(1.2)


class TestDecimalToAmerican:
    def test_decimal_above_2(self):
        result = decimal_to_american(2.5)
        assert result == pytest.approx(150)

    def test_decimal_below_2(self):
        result = decimal_to_american(1.5)
        assert result == pytest.approx(-200)

    def test_even_money(self):
        result = decimal_to_american(2.0)
        assert result == pytest.approx(100)


class TestAmericanToImplied:
    def test_positive_odds(self):
        # +150 => 100/250 = 0.4
        assert american_to_implied(150) == pytest.approx(0.4, abs=0.001)

    def test_negative_odds(self):
        # -200 => 200/300 = 0.6667
        assert american_to_implied(-200) == pytest.approx(0.6667, abs=0.001)

    def test_even_money(self):
        assert american_to_implied(100) == pytest.approx(0.5)


class TestImpliedToAmerican:
    def test_coin_flip(self):
        # At 50% probability, the convention yields -100 (equivalent to +100)
        result = implied_to_american(0.5)
        assert abs(result) == pytest.approx(100, abs=1)

    def test_favorite(self):
        result = implied_to_american(0.7)
        assert result < 0  # Negative odds for favorites

    def test_underdog(self):
        result = implied_to_american(0.3)
        assert result > 0  # Positive odds for underdogs


class TestRemoveVig:
    def test_power_method_fair_market(self):
        # -110/-110 => ~50/50 after vig removal
        p_over, p_under = remove_vig_power(-110, -110)
        assert p_over == pytest.approx(0.5, abs=0.01)
        assert p_under == pytest.approx(0.5, abs=0.01)
        assert p_over + p_under == pytest.approx(1.0, abs=0.001)

    def test_power_method_skewed(self):
        # -150/+130 => overround removed
        p_over, p_under = remove_vig_power(-150, 130)
        assert p_over + p_under == pytest.approx(1.0, abs=0.001)
        assert p_over > p_under

    def test_multiplicative_fair_market(self):
        p_over, p_under = remove_vig_multiplicative(-110, -110)
        assert p_over == pytest.approx(0.5, abs=0.01)
        assert p_under == pytest.approx(0.5, abs=0.01)

    def test_multiplicative_sums_to_one(self):
        p_over, p_under = remove_vig_multiplicative(-200, 170)
        assert p_over + p_under == pytest.approx(1.0, abs=0.001)


class TestComputeHold:
    def test_standard_hold(self):
        # -110/-110 => ~4.5% hold
        hold = compute_hold(-110, -110)
        assert 0.04 < hold < 0.05

    def test_high_hold(self):
        # -120/-120 => higher hold
        hold = compute_hold(-120, -120)
        assert hold > compute_hold(-110, -110)


class TestComputeEV:
    def test_positive_ev(self):
        # 55% edge at even money
        ev = compute_ev(0.55, 2.0)
        assert ev > 0

    def test_negative_ev(self):
        # 45% edge at even money
        ev = compute_ev(0.45, 2.0)
        assert ev < 0

    def test_breakeven(self):
        # 50% at even money
        ev = compute_ev(0.5, 2.0)
        assert ev == pytest.approx(0.0, abs=0.001)


class TestKelly:
    def test_positive_edge(self):
        # 55% at even money
        k = kelly_criterion(0.55, 2.0)
        assert k > 0
        assert k == pytest.approx(0.1, abs=0.01)

    def test_no_edge(self):
        k = kelly_criterion(0.5, 2.0)
        assert k == pytest.approx(0.0, abs=0.001)

    def test_negative_edge_returns_zero(self):
        k = kelly_criterion(0.4, 2.0)
        assert k == 0.0

    def test_half_kelly_is_half(self):
        full = kelly_criterion(0.55, 2.0)
        half = half_kelly(0.55, 2.0)
        assert half == pytest.approx(full / 2, abs=0.001)
