"""Tests for core domain types."""

from datetime import date, datetime, timezone

from nba_props.utils.types import (
    BetDecision,
    BetResult,
    BetSide,
    FeatureLineage,
    GameInfo,
    InjurySnapshot,
    InjuryStatus,
    MakeRatePrediction,
    MinutesPrediction,
    OddsProp,
    PlayerArchetype,
    PlayerGameRow,
    SeasonType,
    ThreePAPrediction,
    TrackingEra,
    TrackingProvider,
    TrackingRow,
)


class TestEnums:
    def test_season_type_values(self):
        assert SeasonType.REGULAR == "Regular Season"
        assert SeasonType.PLAYOFFS == "Playoffs"

    def test_player_archetype_values(self):
        assert PlayerArchetype.MOVEMENT_WING_SHOOTER == "movement_wing_shooter"
        assert PlayerArchetype.PULL_UP_GUARD == "pull_up_guard"
        assert PlayerArchetype.STRETCH_BIG == "stretch_big"
        assert PlayerArchetype.STATIONARY_SPACER == "stationary_spacer"
        assert PlayerArchetype.BENCH_MICROWAVE == "bench_microwave"

    def test_injury_status_values(self):
        assert InjuryStatus.OUT == "Out"
        assert InjuryStatus.QUESTIONABLE == "Questionable"

    def test_bet_side_values(self):
        assert BetSide.OVER == "over"
        assert BetSide.UNDER == "under"
        assert BetSide.NO_BET == "no_bet"

    def test_bet_result_values(self):
        assert BetResult.WIN == "win"
        assert BetResult.LOSS == "loss"
        assert BetResult.PUSH == "push"

    def test_tracking_provider_values(self):
        assert TrackingProvider.SECOND_SPECTRUM == "second_spectrum"
        assert TrackingProvider.HAWKEYE_AWS == "hawkeye_aws"

    def test_tracking_era_values(self):
        assert TrackingEra.SECOND_SPECTRUM == "second_spectrum"
        assert TrackingEra.HAWKEYE == "hawkeye"


class TestGameInfo:
    def test_creation(self):
        game = GameInfo(
            nba_game_id="0022500123",
            season="2025-26",
            season_type=SeasonType.REGULAR,
            game_date=date(2026, 1, 15),
            tipoff_time_utc=datetime(2026, 1, 16, 0, 30, tzinfo=timezone.utc),
            home_team_abbr="BOS",
            away_team_abbr="LAL",
        )
        assert game.nba_game_id == "0022500123"
        assert game.home_team_abbr == "BOS"
        assert game.closing_spread_home is None

    def test_frozen(self):
        game = GameInfo(
            nba_game_id="0022500123",
            season="2025-26",
            season_type=SeasonType.REGULAR,
            game_date=date(2026, 1, 15),
            tipoff_time_utc=None,
            home_team_abbr="BOS",
            away_team_abbr="LAL",
        )
        try:
            game.nba_game_id = "changed"
            assert False, "Should not allow mutation"
        except AttributeError:
            pass


class TestPlayerGameRow:
    def test_creation(self):
        row = PlayerGameRow(
            nba_game_id="0022500123",
            nba_player_id="201566",
            team_abbr="BOS",
            opponent_abbr="LAL",
            is_home=True,
            started=True,
            minutes_played=34.5,
            three_pa=8,
            three_pm=3,
            fg3_pct=0.375,
            usage_rate=0.28,
            assist_rate=0.12,
        )
        assert row.three_pm == 3
        assert row.is_back_to_back is False


class TestTrackingRow:
    def test_creation_available(self):
        row = TrackingRow(
            nba_game_id="0022500123",
            nba_player_id="201566",
            tracking_available=True,
            tracking_provider=TrackingProvider.HAWKEYE_AWS,
            touches=55.0,
            catch_shoot_3pa=4,
            catch_shoot_3pm=2,
            pull_up_3pa=3,
            pull_up_3pm=1,
        )
        assert row.tracking_available is True

    def test_creation_unavailable(self):
        row = TrackingRow(
            nba_game_id="0022500123",
            nba_player_id="201566",
            tracking_available=False,
        )
        assert row.touches is None


class TestOddsProp:
    def test_creation(self):
        prop = OddsProp(
            odds_prop_id=1,
            snapshot_timestamp_utc=datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc),
            sportsbook="fanduel",
            market="player_3pt_made",
            nba_game_id="0022500123",
            nba_player_id="201566",
            line=2.5,
            over_price=-120,
            under_price=100,
        )
        assert prop.line == 2.5
        assert prop.is_closing_snapshot is False


class TestPredictionTypes:
    def test_minutes_prediction(self):
        pred = MinutesPrediction(p10=25.0, p50=32.0, p90=38.0)
        assert pred.p50 == 32.0

    def test_three_pa_prediction(self):
        pred = ThreePAPrediction(mean=7.2, dispersion=3.5)
        assert pred.mean == 7.2

    def test_make_rate_prediction(self):
        pred = MakeRatePrediction(mean=0.38, uncertainty=0.05)
        assert pred.mean == 0.38


class TestFeatureLineage:
    def test_tracking_feature(self):
        lineage = FeatureLineage(
            feature_name="catch_shoot_3pa_per_min",
            source_family="tracking",
            tracking_era=TrackingEra.HAWKEYE,
            provider=TrackingProvider.HAWKEYE_AWS,
        )
        assert lineage.is_imputed is False
        assert lineage.coverage_flag is True

    def test_fallback_feature(self):
        lineage = FeatureLineage(
            feature_name="3pa_per_36_l10",
            source_family="boxscore",
            is_imputed=False,
            coverage_flag=True,
        )
        assert lineage.tracking_era is None
