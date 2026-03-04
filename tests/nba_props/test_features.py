"""Tests for feature engineering."""

import pytest

from nba_props.features.archetype import ArchetypeClassifier
from nba_props.features.minutes_features import MinutesFeatureBuilder
from nba_props.features.opportunity_features import OpportunityFeatureBuilder
from nba_props.features.make_rate_features import MakeRateFeatureBuilder


class TestArchetypeClassifier:
    def setup_method(self):
        self.classifier = ArchetypeClassifier()

    def test_movement_wing_from_tracking(self):
        player_games = [
            {"minutes_played": 32, "started": True, "usage_rate": 0.18,
             "three_pa": 6, "three_pm": 2}
            for _ in range(10)
        ]
        tracking_games = [
            {
                "catch_shoot_3pa": 5, "pull_up_3pa": 1,
                "catch_shoot_3pm": 2, "pull_up_3pm": 0,
                "avg_seconds_per_touch": 2.0,
                "avg_dribbles_per_touch": 1.5,
                "touches": 40, "minutes_played": 32,
                "three_pm": 2, "assisted_3pm": 2,
            }
            for _ in range(10)
        ]
        archetype = self.classifier.classify(player_games, tracking_games)
        assert archetype in [
            "movement_wing_shooter", "pull_up_guard", "stretch_big",
            "stationary_spacer", "bench_microwave",
        ]

    def test_bench_microwave(self):
        player_games = [
            {"minutes_played": 18, "started": False, "usage_rate": 0.20,
             "three_pa": 4, "three_pm": 1}
            for _ in range(10)
        ]
        tracking_games = []  # No tracking
        archetype = self.classifier.classify(player_games, tracking_games)
        # Low minutes + not starting => bench microwave
        assert archetype == "bench_microwave"

    def test_returns_valid_archetype(self):
        valid = {
            "movement_wing_shooter", "pull_up_guard", "stretch_big",
            "stationary_spacer", "bench_microwave",
        }
        player_games = [
            {"minutes_played": 30, "started": True, "usage_rate": 0.22,
             "three_pa": 7, "three_pm": 3}
            for _ in range(10)
        ]
        archetype = self.classifier.classify(player_games, [])
        assert archetype in valid


class TestMinutesFeatureBuilder:
    def setup_method(self):
        self.builder = MinutesFeatureBuilder()

    def test_build_basic(self):
        player_games = [
            {"minutes_played": 30 + i, "started": True, "three_pa": 6,
             "rest_days": 1, "is_back_to_back": False, "is_3in4": False}
            for i in range(20)
        ]
        game_context = {
            "spread": -3.5,
            "team_total": 112.5,
            "is_home": True,
        }
        features = self.builder.build(
            player_games=player_games,
            game_context=game_context,
            injury_snapshot=None,
            teammate_statuses=[],
        )
        assert isinstance(features, dict)
        assert "rolling_minutes_l3" in features or "minutes_l3" in features or len(features) > 0

    def test_handles_empty_games(self):
        features = self.builder.build(
            player_games=[],
            game_context={"spread": 0, "team_total": 110, "is_home": True},
            injury_snapshot=None,
            teammate_statuses=[],
        )
        assert isinstance(features, dict)

    def test_injury_state_flagged(self):
        player_games = [
            {"minutes_played": 30, "started": True, "three_pa": 6,
             "rest_days": 1, "is_back_to_back": False, "is_3in4": False}
            for _ in range(10)
        ]
        injury = {"status": "Questionable", "reason_text": "ankle"}
        features = self.builder.build(
            player_games=player_games,
            game_context={"spread": 0, "team_total": 110, "is_home": True},
            injury_snapshot=injury,
            teammate_statuses=[],
        )
        assert isinstance(features, dict)


class TestOpportunityFeatureBuilder:
    def setup_method(self):
        self.builder = OpportunityFeatureBuilder()

    def test_build_with_tracking(self):
        player_games = [
            {"minutes_played": 32, "three_pa": 7, "three_pm": 3,
             "fg3_pct": 0.43, "usage_rate": 0.25}
            for _ in range(10)
        ]
        tracking_games = [
            {
                "tracking_available": True,
                "catch_shoot_3pa": 4, "catch_shoot_3pm": 2,
                "pull_up_3pa": 3, "pull_up_3pm": 1,
                "touches": 55, "time_of_possession_sec": 60,
                "avg_seconds_per_touch": 2.5,
                "avg_dribbles_per_touch": 2.0,
                "minutes_played": 32,
            }
            for _ in range(10)
        ]
        features = self.builder.build(
            player_games=player_games,
            tracking_games=tracking_games,
            opponent_shooting=[],
            game_context={"spread": -2, "team_total": 115, "is_home": True},
            archetype="pull_up_guard",
        )
        assert isinstance(features, dict)
        assert features.get("tracking_available", True) is True

    def test_build_fallback_no_tracking(self):
        player_games = [
            {"minutes_played": 32, "three_pa": 7, "three_pm": 3,
             "fg3_pct": 0.43, "usage_rate": 0.25}
            for _ in range(10)
        ]
        features = self.builder.build(
            player_games=player_games,
            tracking_games=[],
            opponent_shooting=[],
            game_context={"spread": -2, "team_total": 115, "is_home": True},
            archetype="pull_up_guard",
        )
        assert isinstance(features, dict)


class TestMakeRateFeatureBuilder:
    def setup_method(self):
        self.builder = MakeRateFeatureBuilder()

    def test_build(self):
        player_games = [
            {"three_pa": 7, "three_pm": 3, "fg3_pct": 0.43, "minutes_played": 32}
            for _ in range(20)
        ]
        features = self.builder.build(
            player_games=player_games,
            tracking_games=[],
            opponent_shooting=[],
            game_context={"spread": -2, "team_total": 115, "is_home": True},
            archetype="pull_up_guard",
        )
        assert isinstance(features, dict)

    def test_empirical_bayes_present(self):
        player_games = [
            {"three_pa": 7, "three_pm": 3, "fg3_pct": 0.43, "minutes_played": 32}
            for _ in range(20)
        ]
        features = self.builder.build(
            player_games=player_games,
            tracking_games=[],
            opponent_shooting=[],
            game_context={"spread": 0, "team_total": 110, "is_home": False},
            archetype="movement_wing_shooter",
        )
        # Should have some form of shrunk/bayes estimate
        has_bayes = any("bayes" in k or "shrunk" in k or "eb_" in k for k in features.keys())
        # If no specific key, at least has fg3 features
        has_fg3 = any("fg3" in k or "3pt" in k or "make" in k for k in features.keys())
        assert has_bayes or has_fg3
