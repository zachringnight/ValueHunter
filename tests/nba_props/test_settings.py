"""Tests for configuration settings."""

from nba_props.config.settings import Settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.min_projected_minutes == 18.0
        assert s.min_ev_pct == 0.03
        assert s.min_edge_prob_pts == 0.025
        assert s.monte_carlo_draws == 25000
        assert s.flat_stake_pct == 0.005
        assert s.max_game_exposure_pct == 0.02
        assert s.max_correlated_positions == 3
        assert s.paper_trade_min_bets == 100
        assert s.api_port == 8000

    def test_from_env_defaults(self):
        s = Settings.from_env()
        assert isinstance(s, Settings)
        assert s.database_url == "postgresql://nba_props:nba_props@localhost:5432/nba_props"

    def test_tracking_providers(self):
        s = Settings()
        assert "second_spectrum" in s.tracking_providers
        assert "hawkeye_aws" in s.tracking_providers

    def test_odds_api_history_start(self):
        s = Settings()
        assert s.odds_api_history_start == "2023-05-03"

    def test_frozen(self):
        s = Settings()
        try:
            s.min_ev_pct = 0.10
            assert False, "Should be frozen"
        except AttributeError:
            pass
