"""3PA opportunity feature builder (Sections H2 and H3).

Produces the feature vector consumed by the 3PA-opportunity sub-model.
Two code paths exist:

- **H2 (tracking available)** – full feature set including catch-and-shoot
  splits, touch data, defender-distance environment, etc.
- **H3 (tracking unavailable)** – reduced feature set derived from plain
  boxscore and opponent aggregate stats only.

Both paths are unified behind a single ``build`` method; the returned
dict always contains a ``tracking_available`` boolean so downstream
consumers know which path was used.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

logger = logging.getLogger(__name__)


class OpportunityFeatureBuilder:
    """Compute Section-H2 / H3 features for the 3PA opportunity model."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build(
        self,
        player_games: list[dict[str, Any]],
        tracking_games: list[dict[str, Any]] | None,
        opponent_shooting: list[dict[str, Any]] | None,
        game_context: dict[str, Any],
        archetype: str,
    ) -> dict[str, Any]:
        """Return the opportunity feature dict.

        Parameters
        ----------
        player_games:
            Boxscore-level game dicts, most-recent-first.
        tracking_games:
            Tracking-level game dicts (may be ``None`` or empty).
        opponent_shooting:
            Opponent-level defensive shooting stats – a list of
            per-game or aggregate dicts used to build the defensive
            environment.
        game_context:
            Pregame context with ``spread``, ``team_total``, ``is_home``,
            ``rest_days``, ``team_pace``, ``opponent_pace``, etc.
        archetype:
            The player's archetype label (from ``ArchetypeClassifier``).
        """
        if not player_games:
            logger.warning("No player games – returning empty opportunity features.")
            return {"tracking_available": False}

        has_tracking = bool(tracking_games)
        features: dict[str, Any] = {"tracking_available": has_tracking}

        if has_tracking:
            features.update(self._build_h2(player_games, tracking_games, game_context))  # type: ignore[arg-type]
        else:
            features.update(self._build_h3(player_games, game_context))

        # Opponent environment (available in both paths)
        opp_env = self._compute_opponent_env(opponent_shooting)
        features.update(opp_env)

        # Game-context features (shared)
        features["is_home"] = 1.0 if game_context.get("is_home") else 0.0
        features["rest_days"] = float(game_context.get("rest_days", 1))
        features["spread"] = float(game_context.get("spread", 0))
        features["team_total"] = float(game_context.get("team_total", 0))
        features["blowout_risk"] = self._compute_blowout_risk(
            float(game_context.get("spread", 0))
        )

        # Zone-level opponent shooting (from opponent_shooting records)
        features.update(self._compute_zone_features(opponent_shooting))

        # Play-type defense features (from game_context)
        features.update(self._compute_playtype_features(
            game_context.get("playtype_defense"), archetype
        ))

        # Archetype interaction features
        features.update(self._archetype_interactions(archetype, features))

        return features

    # ------------------------------------------------------------------
    # H2 path – tracking available
    # ------------------------------------------------------------------

    def _build_h2(
        self,
        player_games: list[dict[str, Any]],
        tracking_games: list[dict[str, Any]],
        game_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Full feature set when tracking data is present."""
        feats: dict[str, Any] = {}

        # --- Per-minute 3PA at various windows ---
        pm_l5 = self._rolling_per_minute(tracking_games, "fg3a", 5)
        pm_l10 = self._rolling_per_minute(tracking_games, "fg3a", 10)
        pm_l20 = self._rolling_per_minute(tracking_games, "fg3a", 20)
        feats["3pa_per_min_l5"] = pm_l5
        feats["3pa_per_min_l10"] = pm_l10
        feats["3pa_per_min_l20"] = pm_l20

        # --- Per-36 3PA ---
        feats["3pa_per_36_l10"] = pm_l10 * 36.0
        feats["3pa_per_36_l20"] = pm_l20 * 36.0

        # --- Share / rate features ---
        totals = self._aggregate_totals(tracking_games)
        feats["pct_3pa"] = self._safe_ratio(totals["fg3a"], totals["fga"])
        feats["pct_fga_3pt"] = feats["pct_3pa"]  # alias
        feats["pct_3pm"] = self._safe_ratio(totals["fg3m"], totals["fgm"])

        # --- Catch-shoot / pull-up splits ---
        feats["catch_shoot_3pa_per_min"] = self._per_minute_stat(
            totals["catch_shoot_3pa"], totals["minutes"]
        )
        feats["pull_up_3pa_per_min"] = self._per_minute_stat(
            totals["pull_up_3pa"], totals["minutes"]
        )
        feats["catch_shoot_share"] = self._safe_ratio(
            totals["catch_shoot_3pa"], totals["fg3a"]
        )
        feats["pull_up_share"] = self._safe_ratio(
            totals["pull_up_3pa"], totals["fg3a"]
        )

        # --- Assisted / unassisted ---
        feats["assisted_3pm_share"] = self._safe_ratio(
            totals["assisted_3pm"], totals["fg3m"]
        )
        feats["unassisted_3pm_share"] = 1.0 - feats["assisted_3pm_share"]

        # --- Touch / possession data ---
        feats["touches_per_min"] = self._per_minute_stat(
            totals["touches"], totals["minutes"]
        )
        feats["time_of_poss_per_min"] = self._per_minute_stat(
            totals["time_of_poss"], totals["minutes"]
        )

        # --- Passing metrics ---
        feats["passes_made_per_min"] = self._per_minute_stat(
            totals["passes_made"], totals["minutes"]
        )
        feats["passes_received_per_min"] = self._per_minute_stat(
            totals["passes_received"], totals["minutes"]
        )
        # Pass ratio: passes_made / passes_received indicates playmaking load
        feats["pass_ratio"] = self._safe_ratio(
            totals["passes_made"], totals["passes_received"]
        )

        # --- Seconds / dribbles per touch ---
        spt_vals = [
            float(g.get("avg_seconds_per_touch", 0) or 0) for g in tracking_games
        ]
        dpt_vals = [
            float(g.get("avg_dribbles_per_touch", 0) or 0) for g in tracking_games
        ]
        feats["avg_seconds_per_touch"] = (
            statistics.mean(spt_vals) if spt_vals else 0.0
        )
        feats["avg_dribbles_per_touch"] = (
            statistics.mean(dpt_vals) if dpt_vals else 0.0
        )

        # --- Assist rate (usage-weighted playmaking indicator) ---
        ast_pct_vals = [
            float(g.get("assist_rate", 0) or g.get("ast_pct", 0) or 0)
            for g in player_games[:10]
        ]
        feats["assist_rate_avg_l10"] = (
            statistics.mean(ast_pct_vals) if ast_pct_vals else 0.0
        )

        # --- Pace ---
        feats["team_pace"] = float(game_context.get("team_pace", 100.0))
        feats["opponent_pace"] = float(game_context.get("opponent_pace", 100.0))

        return feats

    # ------------------------------------------------------------------
    # H3 path – tracking unavailable (boxscore fallback)
    # ------------------------------------------------------------------

    def _build_h3(
        self,
        player_games: list[dict[str, Any]],
        game_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Reduced feature set from boxscore-only data."""
        feats: dict[str, Any] = {}

        # --- Per-minute 3PA ---
        feats["3pa_per_min_l5"] = self._rolling_per_minute(player_games, "fg3a", 5)
        feats["3pa_per_min_l10"] = self._rolling_per_minute(player_games, "fg3a", 10)
        feats["3pa_per_min_l20"] = self._rolling_per_minute(player_games, "fg3a", 20)

        # --- Per-36 3PA ---
        feats["3pa_per_36_l10"] = feats["3pa_per_min_l10"] * 36.0
        feats["3pa_per_36_l20"] = feats["3pa_per_min_l20"] * 36.0

        # --- Share / rate features ---
        total_fg3a = sum(float(g.get("fg3a", 0) or 0) for g in player_games)
        total_fga = sum(float(g.get("fga", 0) or 0) for g in player_games)
        total_fg3m = sum(float(g.get("fg3m", 0) or 0) for g in player_games)
        total_fgm = sum(float(g.get("fgm", 0) or 0) for g in player_games)

        feats["pct_3pa"] = self._safe_ratio(total_fg3a, total_fga)
        feats["pct_fga_3pt"] = feats["pct_3pa"]
        feats["pct_3pm"] = self._safe_ratio(total_fg3m, total_fgm)

        # Rolling raw 3PA means (useful as fallback signals)
        fg3a_vals = [float(g.get("fg3a", 0) or 0) for g in player_games]
        feats["3pa_avg_l5"] = self._mean_window(fg3a_vals, 5)
        feats["3pa_avg_l10"] = self._mean_window(fg3a_vals, 10)
        feats["3pa_avg_l20"] = self._mean_window(fg3a_vals, 20)

        # --- Assist rate ---
        ast_pct_vals = [
            float(g.get("assist_rate", 0) or g.get("ast_pct", 0) or 0)
            for g in player_games[:10]
        ]
        feats["assist_rate_avg_l10"] = (
            statistics.mean(ast_pct_vals) if ast_pct_vals else 0.0
        )

        # Pace (still available from game context)
        feats["team_pace"] = float(game_context.get("team_pace", 100.0))
        feats["opponent_pace"] = float(game_context.get("opponent_pace", 100.0))

        return feats

    # ------------------------------------------------------------------
    # Opponent environment
    # ------------------------------------------------------------------

    def _compute_opponent_env(
        self,
        opponent_shooting: list[dict[str, Any]] | None,
    ) -> dict[str, float]:
        """Aggregate opponent defensive stats into environment features.

        Input dicts may contain:
        - ``opp_3pa_allowed``
        - ``opp_3pm_allowed``
        - ``opp_fg3_pct_allowed``
        - ``opp_dribble_allowed`` (weighted)
        - ``opp_touch_allowed`` (weighted)
        - ``opp_closest_def_dist`` (weighted avg closest-defender distance)
        """
        defaults = {
            "opp_3pa_allowed": 0.0,
            "opp_3pm_allowed": 0.0,
            "opp_fg3_pct_allowed": 0.0,
            "opp_fga_allowed": 0.0,
            "opp_fg_pct_allowed": 0.0,
            "opp_dribble_env": 0.0,
            "opp_touch_env": 0.0,
            "opp_closest_def_env": 0.0,
        }
        if not opponent_shooting:
            return defaults

        # If multiple records, take weighted average or most-recent.
        # For simplicity we average across all records.
        n = len(opponent_shooting)
        acc: dict[str, float] = {k: 0.0 for k in defaults}
        field_map = {
            "opp_3pa_allowed": "opp_3pa_allowed",
            "opp_3pm_allowed": "opp_3pm_allowed",
            "opp_fg3_pct_allowed": "opp_fg3_pct_allowed",
            "opp_fga_allowed": "opp_fga_allowed",
            "opp_fg_pct_allowed": "opp_fg_pct_allowed",
            "opp_dribble_env": "opp_dribble_allowed",
            "opp_touch_env": "opp_touch_allowed",
            "opp_closest_def_env": "opp_closest_def_dist",
        }
        for rec in opponent_shooting:
            for out_key, src_key in field_map.items():
                acc[out_key] += float(rec.get(src_key, 0) or 0)

        return {k: v / n for k, v in acc.items()}

    # ------------------------------------------------------------------
    # Zone-level opponent shooting features
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_zone_features(
        opponent_shooting: list[dict[str, Any]] | None,
    ) -> dict[str, float]:
        """Extract zone-level opponent shooting into features.

        Zones: paint, mid-range, corner 3, above-the-break 3.
        """
        defaults = {
            "opp_paint_fga": 0.0,
            "opp_paint_fg_pct": 0.0,
            "opp_midrange_fga": 0.0,
            "opp_midrange_fg_pct": 0.0,
            "opp_corner_3pa": 0.0,
            "opp_corner_3p_pct": 0.0,
            "opp_above_break_3pa": 0.0,
            "opp_above_break_3p_pct": 0.0,
        }
        if not opponent_shooting:
            return defaults

        n = len(opponent_shooting)
        acc = {k: 0.0 for k in defaults}
        for rec in opponent_shooting:
            for key in defaults:
                acc[key] += float(rec.get(key, 0) or 0)

        return {k: v / n for k, v in acc.items()}

    # ------------------------------------------------------------------
    # Play-type defense features
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_playtype_features(
        playtype_defense: list[dict[str, Any]] | None,
        archetype: str,
    ) -> dict[str, float]:
        """Extract play-type defense features relevant to 3PA opportunity.

        Key play types for three-point shooting:
        - Spotup: spot-up defense (most 3PA come from spot-ups)
        - PRBallHandler: PnR ball-handler (pull-up 3s)
        - OffScreen: off-screen (movement shooters)
        - Handoff: hand-off plays
        - Transition: fast-break 3s
        """
        defaults = {
            "opp_spotup_ppp": 0.0,
            "opp_spotup_fg_pct": 0.0,
            "opp_spotup_freq": 0.0,
            "opp_pnr_handler_ppp": 0.0,
            "opp_pnr_handler_fg_pct": 0.0,
            "opp_offscreen_ppp": 0.0,
            "opp_offscreen_fg_pct": 0.0,
            "opp_handoff_ppp": 0.0,
            "opp_handoff_fg_pct": 0.0,
            "opp_transition_ppp": 0.0,
            "opp_transition_fg_pct": 0.0,
            "opp_isolation_ppp": 0.0,
            "opp_isolation_fg_pct": 0.0,
        }
        if not playtype_defense:
            return defaults

        # Build lookup by play_type
        by_type: dict[str, dict] = {}
        for rec in playtype_defense:
            pt = rec.get("play_type", "")
            by_type[pt] = rec

        field_map = {
            "Spotup": ("opp_spotup", ["ppp", "fg_pct", "poss_pct"]),
            "PRBallHandler": ("opp_pnr_handler", ["ppp", "fg_pct"]),
            "OffScreen": ("opp_offscreen", ["ppp", "fg_pct"]),
            "Handoff": ("opp_handoff", ["ppp", "fg_pct"]),
            "Transition": ("opp_transition", ["ppp", "fg_pct"]),
            "Isolation": ("opp_isolation", ["ppp", "fg_pct"]),
        }

        result = dict(defaults)
        for pt_name, (prefix, fields) in field_map.items():
            rec = by_type.get(pt_name, {})
            for f in fields:
                key = f"{prefix}_{f}"
                if key in result:
                    result[key] = float(rec.get(f, 0) or 0)

        # Special: spotup frequency
        spotup = by_type.get("Spotup", {})
        result["opp_spotup_freq"] = float(spotup.get("poss_pct", 0) or 0)

        # Archetype-specific play-type vulnerability
        # Movement shooters care about off-screen and spot-up defense
        # Pull-up guards care about PnR handler and isolation defense
        archetype_pt_map = {
            "movement_wing_shooter": ["opp_offscreen_ppp", "opp_spotup_ppp"],
            "pull_up_guard": ["opp_pnr_handler_ppp", "opp_isolation_ppp"],
            "stretch_big": ["opp_spotup_ppp", "opp_handoff_ppp"],
            "stationary_spacer": ["opp_spotup_ppp"],
            "bench_microwave": ["opp_spotup_ppp", "opp_transition_ppp"],
        }

        relevant_ppp = archetype_pt_map.get(archetype, ["opp_spotup_ppp"])
        result["opp_archetype_vulnerability"] = sum(
            result.get(k, 0) for k in relevant_ppp
        ) / len(relevant_ppp)

        return result

    # ------------------------------------------------------------------
    # Archetype interaction features
    # ------------------------------------------------------------------

    @staticmethod
    def _archetype_interactions(
        archetype: str,
        base_features: dict[str, Any],
    ) -> dict[str, float]:
        """Create interaction features between archetype and numeric
        base features that are informative for the opportunity model."""
        interactions: dict[str, float] = {}

        # One-hot archetype encoding
        all_archetypes = [
            "movement_wing_shooter",
            "pull_up_guard",
            "stretch_big",
            "stationary_spacer",
            "bench_microwave",
        ]
        for a in all_archetypes:
            interactions[f"arch_{a}"] = 1.0 if archetype == a else 0.0

        # Interaction: archetype x opp_3pa_allowed
        opp_3pa = float(base_features.get("opp_3pa_allowed", 0))
        interactions[f"arch_{archetype}_x_opp_3pa"] = opp_3pa

        # Interaction: archetype x spread
        spread = float(base_features.get("spread", 0))
        interactions[f"arch_{archetype}_x_spread"] = spread

        # Interaction: archetype x blowout_risk
        blowout = float(base_features.get("blowout_risk", 0))
        interactions[f"arch_{archetype}_x_blowout"] = blowout

        return interactions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _per_minute_stat(total: float, minutes: float) -> float:
        """Safe per-minute computation avoiding division by zero."""
        if minutes <= 0:
            return 0.0
        return total / minutes

    @staticmethod
    def _safe_ratio(numerator: float, denominator: float) -> float:
        """Return ``numerator / denominator`` or 0 when denominator is 0."""
        if denominator <= 0:
            return 0.0
        return numerator / denominator

    @staticmethod
    def _mean_window(values: list[float], window: int) -> float:
        """Mean of the first *window* items (most-recent-first)."""
        subset = values[:window]
        return statistics.mean(subset) if subset else 0.0

    def _rolling_per_minute(
        self,
        games: list[dict[str, Any]],
        stat_key: str,
        window: int,
    ) -> float:
        """Sum stat / sum minutes over a window of recent games."""
        subset = games[:window]
        total_stat = sum(float(g.get(stat_key, 0) or 0) for g in subset)
        total_min = sum(float(g.get("minutes", 0) or 0) for g in subset)
        return self._per_minute_stat(total_stat, total_min)

    def _aggregate_totals(
        self, tracking_games: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Sum up key columns across all tracking games."""
        keys = [
            "fg3a",
            "fg3m",
            "fga",
            "fgm",
            "catch_shoot_3pa",
            "pull_up_3pa",
            "assisted_3pm",
            "touches",
            "time_of_poss",
            "passes_made",
            "passes_received",
            "minutes",
        ]
        totals: dict[str, float] = {k: 0.0 for k in keys}
        for g in tracking_games:
            for k in keys:
                totals[k] += float(g.get(k, 0) or 0)
        return totals

    @staticmethod
    def _compute_blowout_risk(spread: float) -> float:
        """Simple blowout risk indicator (0-1 scale)."""
        import math

        abs_spread = abs(spread)
        return round(1.0 / (1.0 + math.exp(-0.25 * (abs_spread - 10.0))), 4)
