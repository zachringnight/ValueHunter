"""Tests for leakage detection."""

from datetime import datetime, timezone

from nba_props.backtest.leakage import LeakageDetector


class TestLeakageDetector:
    def setup_method(self):
        self.detector = LeakageDetector()
        self.freeze = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

    def test_clean_snapshot_passes(self):
        snapshot = {
            "injury_snapshot_timestamp_utc": datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc),
            "odds_snapshot_timestamp_utc": datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc),
            "tracking_available": True,
            "feature_json": {
                "rolling_minutes_l10": 32.5,
                "3pa_per_min_l5": 0.22,
            },
        }
        passed, violations = self.detector.run_all_checks(snapshot, self.freeze)
        assert passed is True
        assert len(violations) == 0

    def test_injury_timestamp_leak(self):
        snapshot = {
            "injury_snapshot_timestamp_utc": datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc),
            "odds_snapshot_timestamp_utc": datetime(2026, 1, 15, 23, 0, tzinfo=timezone.utc),
            "tracking_available": True,
            "feature_json": {},
        }
        violations = self.detector.check_feature_timestamps(snapshot, self.freeze)
        assert len(violations) == 1
        assert "Injury" in violations[0]

    def test_odds_timestamp_leak(self):
        snapshot = {
            "injury_snapshot_timestamp_utc": datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc),
            "odds_snapshot_timestamp_utc": datetime(2026, 1, 16, 2, 0, tzinfo=timezone.utc),
            "tracking_available": True,
            "feature_json": {},
        }
        violations = self.detector.check_feature_timestamps(snapshot, self.freeze)
        assert len(violations) == 1
        assert "Odds" in violations[0]

    def test_closing_line_leak(self):
        snapshot = {
            "feature_json": {
                "closing_line_spread": -3.5,
                "rolling_minutes_l10": 32.0,
            },
        }
        violations = self.detector.check_closing_line_leak(snapshot)
        assert len(violations) >= 1

    def test_tracking_imputation_leak(self):
        snapshot = {
            "tracking_available": False,
            "feature_json": {
                "catch_shoot_3pa_per_min": 0.15,
                "touches_per_min": 1.8,
            },
        }
        violations = self.detector.check_tracking_imputation(snapshot)
        assert len(violations) >= 1

    def test_tracking_ok_when_available(self):
        snapshot = {
            "tracking_available": True,
            "feature_json": {
                "catch_shoot_3pa_per_min": 0.15,
                "touches_per_min": 1.8,
            },
        }
        violations = self.detector.check_tracking_imputation(snapshot)
        assert len(violations) == 0

    def test_run_all_catches_multiple(self):
        snapshot = {
            "injury_snapshot_timestamp_utc": datetime(2026, 1, 16, 1, 0, tzinfo=timezone.utc),
            "odds_snapshot_timestamp_utc": datetime(2026, 1, 16, 2, 0, tzinfo=timezone.utc),
            "tracking_available": False,
            "feature_json": {
                "closing_line_value": 0.05,
                "catches_shoot_3pa_per_min": 0.15,
            },
        }
        passed, violations = self.detector.run_all_checks(snapshot, self.freeze)
        assert passed is False
        assert len(violations) >= 2
