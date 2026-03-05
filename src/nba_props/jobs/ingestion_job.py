"""Data ingestion job - fetches and stores all raw data."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from ..config import Settings, get_settings
from ..ingestion.nba_stats import NBAStatsClient
from ..ingestion.injury_reports import InjuryReportIngester
from ..ingestion.sportradar import SportradarClient
from ..ingestion.odds_api import OddsAPIClient
from ..utils.db import Repository

logger = logging.getLogger(__name__)


class IngestionJob:
    """Orchestrates all data ingestion for a given date."""

    def __init__(
        self,
        repository: Repository,
        nba_client: Optional[NBAStatsClient] = None,
        injury_ingester: Optional[InjuryReportIngester] = None,
        sportradar_client: Optional[SportradarClient] = None,
        odds_client: Optional[OddsAPIClient] = None,
        settings: Optional[Settings] = None,
    ):
        self.repo = repository
        self.settings = settings or get_settings()
        self.nba_client = nba_client or NBAStatsClient()
        self.injury_ingester = injury_ingester or InjuryReportIngester()
        self.sportradar_client = sportradar_client
        self.odds_client = odds_client

    def run_full_ingestion(self, target_date: date, season: str) -> dict:
        """Run all ingestion steps for a target date."""
        results = {
            "date": str(target_date),
            "games": 0,
            "player_games": 0,
            "tracking_rows": 0,
            "opponent_shooting_rows": 0,
            "injury_snapshots": 0,
            "odds_snapshots": 0,
            "zone_shooting_rows": 0,
            "playtype_defense_rows": 0,
            "closest_def_rows": 0,
            "errors": [],
        }

        # Step 1: Ingest game schedule
        try:
            results["games"] = self._ingest_schedule(target_date, season)
        except Exception as e:
            logger.error("Schedule ingestion failed: %s", e)
            results["errors"].append(f"schedule: {e}")

        # Step 2: Ingest player game logs
        try:
            results["player_games"] = self._ingest_player_games(
                target_date, season
            )
        except Exception as e:
            logger.error("Player game ingestion failed: %s", e)
            results["errors"].append(f"player_games: {e}")

        # Step 3: Ingest tracking data
        try:
            results["tracking_rows"] = self._ingest_tracking(season)
        except Exception as e:
            logger.error("Tracking ingestion failed: %s", e)
            results["errors"].append(f"tracking: {e}")

        # Step 4: Ingest opponent shooting
        try:
            results["opponent_shooting_rows"] = self._ingest_opponent_shooting(
                season
            )
        except Exception as e:
            logger.error("Opponent shooting ingestion failed: %s", e)
            results["errors"].append(f"opponent_shooting: {e}")

        # Step 4b: Ingest opponent shooting by zone
        try:
            results["zone_shooting_rows"] = self._ingest_opponent_zone_shooting(
                season
            )
        except Exception as e:
            logger.error("Zone shooting ingestion failed: %s", e)
            results["errors"].append(f"zone_shooting: {e}")

        # Step 4c: Ingest play-type defense
        try:
            results["playtype_defense_rows"] = self._ingest_playtype_defense(
                season
            )
        except Exception as e:
            logger.error("Play-type defense ingestion failed: %s", e)
            results["errors"].append(f"playtype_defense: {e}")

        # Step 4d: Ingest closest-defender opponent shooting
        try:
            results["closest_def_rows"] = self._ingest_closest_defender(season)
        except Exception as e:
            logger.error("Closest-defender ingestion failed: %s", e)
            results["errors"].append(f"closest_defender: {e}")

        # Step 5: Ingest injury reports
        try:
            results["injury_snapshots"] = self._ingest_injuries()
        except Exception as e:
            logger.error("Injury ingestion failed: %s", e)
            results["errors"].append(f"injuries: {e}")

        # Step 6: Ingest odds
        try:
            if self.odds_client:
                results["odds_snapshots"] = self._ingest_odds(target_date)
        except Exception as e:
            logger.error("Odds ingestion failed: %s", e)
            results["errors"].append(f"odds: {e}")

        logger.info("Ingestion complete for %s: %s", target_date, results)
        return results

    def _ingest_schedule(self, target_date: date, season: str) -> int:
        """Ingest game schedule for the target date."""
        if self.sportradar_client:
            games = self.sportradar_client.get_daily_schedule(
                target_date.isoformat()
            )
        else:
            games = self.nba_client.get_team_game_logs(season)
            games = [
                g for g in games
                if g.get("GAME_DATE", "").startswith(str(target_date))
            ]

        count = 0
        for game in games:
            self.repo.upsert_game(self._normalize_game(game))
            count += 1
        return count

    def _ingest_player_games(self, target_date: date, season: str) -> int:
        """Ingest player box score data."""
        logs = self.nba_client.get_player_game_logs(
            season=season,
            season_type="Regular Season",
            date_from=target_date.strftime("%m/%d/%Y"),
            date_to=target_date.strftime("%m/%d/%Y"),
        )
        count = 0
        for log in logs:
            self.repo.upsert_player_game(self._normalize_player_game(log))
            count += 1
        return count

    def _ingest_tracking(self, season: str) -> int:
        """Ingest player tracking data (catch-and-shoot, pull-up, touches)."""
        count = 0
        try:
            cs_data = self.nba_client.get_tracking_catch_and_shoot(
                season, "Regular Season"
            )
            pu_data = self.nba_client.get_tracking_pull_up(
                season, "Regular Season"
            )
            touch_data = self.nba_client.get_tracking_touches(
                season, "Regular Season"
            )

            # Merge tracking data by player
            merged = self._merge_tracking_data(cs_data, pu_data, touch_data)
            for row in merged:
                self.repo.upsert_player_tracking(row)
                count += 1
        except Exception as e:
            logger.warning("Tracking data not available: %s", e)
        return count

    def _ingest_opponent_shooting(self, season: str) -> int:
        """Ingest team opponent shooting data."""
        opp_data = self.nba_client.get_opponent_shooting(
            season, "Regular Season"
        )
        count = 0
        for row in opp_data:
            self.repo.upsert_team_opponent_shooting(
                self._normalize_opponent_shooting(row)
            )
            count += 1
        return count

    def _ingest_injuries(self) -> int:
        """Fetch and store current injury report snapshot."""
        reports = self.injury_ingester.fetch_current_report()
        snapshots = self.injury_ingester.create_snapshot(reports)
        count = 0
        for snap in snapshots:
            try:
                self.repo.insert_injury_snapshot(snap)
                count += 1
            except Exception as e:
                logger.debug("Duplicate injury snapshot skipped: %s", e)
        return count

    def _ingest_odds(self, target_date: date) -> int:
        """Fetch and store odds snapshots for games on target date."""
        events = self.odds_client.get_upcoming_events()
        count = 0
        for event in events:
            commence = event.get("commence_time", "")
            if not commence.startswith(str(target_date)):
                continue
            try:
                snapshots = self.odds_client.get_player_prop_snapshots(
                    event["id"]
                )
                for snap in snapshots:
                    snap["nba_game_id"] = event.get("id", "")
                    self.repo.insert_odds_prop(snap)
                    count += 1
            except Exception as e:
                logger.warning("Odds fetch failed for event %s: %s", event.get("id"), e)
        return count

    @staticmethod
    def _normalize_game(raw: dict) -> dict:
        """Normalize raw game data to games table schema."""
        return {
            "nba_game_id": raw.get("GAME_ID", raw.get("id", "")),
            "season": raw.get("SEASON_ID", raw.get("season", "")),
            "season_type": raw.get("season_type", "Regular Season"),
            "game_date": raw.get("GAME_DATE", raw.get("scheduled", "")),
            "tipoff_time_utc": raw.get("tipoff_time_utc"),
            "arena_name": raw.get("arena", {}).get("name") if isinstance(raw.get("arena"), dict) else raw.get("arena_name"),
            "home_team_abbr": raw.get("home_team_abbr", raw.get("HOME_TEAM_ABBREVIATION", "")),
            "away_team_abbr": raw.get("away_team_abbr", raw.get("VISITOR_TEAM_ABBREVIATION", "")),
            "sr_game_id": raw.get("sr_game_id"),
        }

    @staticmethod
    def _normalize_player_game(raw: dict) -> dict:
        """Normalize raw player game log to player_game table schema."""
        fg3m = raw.get("FG3M", 0) or 0
        fg3a = raw.get("FG3A", 0) or 0
        return {
            "nba_game_id": raw.get("GAME_ID", ""),
            "nba_player_id": str(raw.get("PLAYER_ID", "")),
            "team_abbr": raw.get("TEAM_ABBREVIATION", ""),
            "opponent_abbr": raw.get("MATCHUP", "")[-3:] if raw.get("MATCHUP") else "",
            "is_home": "vs." in raw.get("MATCHUP", ""),
            "started": raw.get("START_POSITION", "") != "",
            "minutes_played": raw.get("MIN", 0) or 0,
            "three_pa": fg3a,
            "three_pm": fg3m,
            "fg3_pct": fg3m / fg3a if fg3a > 0 else None,
            "usage_rate": raw.get("USG_PCT"),
            "assist_rate": raw.get("AST_PCT"),
            "turnovers": raw.get("TOV", 0) or 0,
            "personal_fouls": raw.get("PF", 0) or 0,
        }

    def _ingest_opponent_zone_shooting(self, season: str) -> int:
        """Ingest opponent shooting broken down by zone."""
        zone_data = self.nba_client.get_opponent_shooting_by_zone(
            season, "Regular Season"
        )
        count = 0
        for row in zone_data:
            normalized = self._normalize_zone_shooting(row)
            if normalized:
                # Update existing opponent shooting record with zone data
                try:
                    self._update_zone_columns(normalized)
                    count += 1
                except Exception as e:
                    logger.debug("Zone update failed for %s: %s", normalized.get("team_abbr"), e)
        return count

    def _ingest_playtype_defense(self, season: str) -> int:
        """Ingest play-type defense stats."""
        pt_data = self.nba_client.get_opponent_play_type_defense(
            season, "Regular Season"
        )
        count = 0
        for row in pt_data:
            normalized = self._normalize_playtype_defense(row, season)
            if normalized:
                self.repo.upsert_team_playtype_defense(normalized)
                count += 1
        return count

    def _ingest_closest_defender(self, season: str) -> int:
        """Ingest opponent shooting by closest-defender distance."""
        def_data = self.nba_client.get_opponent_shooting_closest_defender(
            season, "Regular Season"
        )
        count = 0
        for row in def_data:
            logger.debug("Closest defender row: %s", row)
            count += 1
        return count

    def _update_zone_columns(self, zone: dict) -> None:
        """Update team_opponent_shooting with zone-level columns."""
        sql = """
            UPDATE team_opponent_shooting SET
                opp_paint_fga = %(opp_paint_fga)s,
                opp_paint_fg_pct = %(opp_paint_fg_pct)s,
                opp_midrange_fga = %(opp_midrange_fga)s,
                opp_midrange_fg_pct = %(opp_midrange_fg_pct)s,
                opp_corner_3pa = %(opp_corner_3pa)s,
                opp_corner_3p_pct = %(opp_corner_3p_pct)s,
                opp_above_break_3pa = %(opp_above_break_3pa)s,
                opp_above_break_3p_pct = %(opp_above_break_3p_pct)s
            WHERE team_abbr = %(team_abbr)s
        """
        self.repo._execute(sql, zone)
        self.repo.conn.commit()

    @staticmethod
    def _normalize_zone_shooting(raw: dict) -> dict | None:
        """Normalize zone shooting data."""
        team = raw.get("TEAM_ABBREVIATION", raw.get("team_abbr", ""))
        if not team:
            return None
        return {
            "team_abbr": team,
            "opp_paint_fga": raw.get("Restricted Area_FGA", raw.get("In The Paint (Non-RA)_FGA", 0)),
            "opp_paint_fg_pct": raw.get("Restricted Area_FG_PCT", raw.get("In The Paint (Non-RA)_FG_PCT", 0)),
            "opp_midrange_fga": raw.get("Mid-Range_FGA", 0),
            "opp_midrange_fg_pct": raw.get("Mid-Range_FG_PCT", 0),
            "opp_corner_3pa": raw.get("Left Corner 3_FGA", 0) + raw.get("Right Corner 3_FGA", 0) if raw.get("Left Corner 3_FGA") else raw.get("Corner 3_FGA", 0),
            "opp_corner_3p_pct": raw.get("Left Corner 3_FG_PCT", raw.get("Corner 3_FG_PCT", 0)),
            "opp_above_break_3pa": raw.get("Above the Break 3_FGA", 0),
            "opp_above_break_3p_pct": raw.get("Above the Break 3_FG_PCT", 0),
        }

    @staticmethod
    def _normalize_playtype_defense(raw: dict, season: str) -> dict | None:
        """Normalize play-type defense data."""
        team = raw.get("TEAM_ABBREVIATION", raw.get("team_abbreviation", ""))
        if not team:
            return None
        return {
            "team_abbr": team,
            "season": season,
            "play_type": raw.get("PLAY_TYPE", ""),
            "gp": raw.get("GP", 0),
            "poss_pct": raw.get("POSS_PCT", 0),
            "poss": raw.get("POSS", 0),
            "pts": raw.get("PTS", 0),
            "fga": raw.get("FGA", 0),
            "fgm": raw.get("FGM", 0),
            "fg_pct": raw.get("FG_PCT", 0),
            "efg_pct": raw.get("EFG_PCT", 0),
            "ft_freq": raw.get("FT_FREQ", 0),
            "tov_freq": raw.get("TOV_FREQ", 0),
            "score_freq": raw.get("SCORE_FREQ", 0),
            "percentile": raw.get("PERCENTILE", 0),
            "ppp": raw.get("PPP", 0),
        }

    @staticmethod
    def _normalize_opponent_shooting(raw: dict) -> dict:
        """Normalize opponent shooting data."""
        return {
            "nba_game_id": raw.get("GAME_ID", ""),
            "team_abbr": raw.get("TEAM_ABBREVIATION", ""),
            "opponent_abbr": raw.get("OPP_ABBREVIATION", ""),
            "opp_fga_allowed": raw.get("OPP_FGA", 0),
            "opp_fg_pct_allowed": raw.get("OPP_FG_PCT", 0),
            "opp_3pa_allowed": raw.get("OPP_FG3A", 0),
            "opp_3pm_allowed": raw.get("OPP_FG3M", 0),
            "opp_fg3_pct_allowed": raw.get("OPP_FG3_PCT", 0),
        }

    @staticmethod
    def _merge_tracking_data(
        catch_shoot: list, pull_up: list, touches: list
    ) -> list:
        """Merge catch-and-shoot, pull-up, and touch data by player."""
        by_player = {}

        for row in catch_shoot:
            pid = str(row.get("PLAYER_ID", ""))
            if pid not in by_player:
                by_player[pid] = {"nba_player_id": pid, "tracking_available": True}
            by_player[pid].update({
                "catch_shoot_fga": row.get("FGA", 0),
                "catch_shoot_fgm": row.get("FGM", 0),
                "catch_shoot_3pa": row.get("FG3A", 0),
                "catch_shoot_3pm": row.get("FG3M", 0),
            })

        for row in pull_up:
            pid = str(row.get("PLAYER_ID", ""))
            if pid not in by_player:
                by_player[pid] = {"nba_player_id": pid, "tracking_available": True}
            by_player[pid].update({
                "pull_up_fga": row.get("FGA", 0),
                "pull_up_fgm": row.get("FGM", 0),
                "pull_up_3pa": row.get("FG3A", 0),
                "pull_up_3pm": row.get("FG3M", 0),
            })

        for row in touches:
            pid = str(row.get("PLAYER_ID", ""))
            if pid not in by_player:
                by_player[pid] = {"nba_player_id": pid, "tracking_available": True}
            by_player[pid].update({
                "touches": row.get("TOUCHES", 0),
                "passes_made": row.get("PASSES_MADE", 0),
                "passes_received": row.get("PASSES_RECEIVED", 0),
                "time_of_possession_sec": row.get("TIME_OF_POSS", 0),
                "avg_seconds_per_touch": row.get("AVG_SEC_PER_TOUCH", 0),
                "avg_dribbles_per_touch": row.get("AVG_DRIB_PER_TOUCH", 0),
            })

        return list(by_player.values())
