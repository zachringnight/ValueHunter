#!/usr/bin/env python3
"""Generate full box score fantasy projections for today's NBA games.

Produces per-player projections for all standard fantasy categories:
  PTS, REB, AST, STL, BLK, TOV, FGM, FGA, FTM, FTA, 3PM, 3PA, MIN

Uses the same data pipeline as the betting model (BBRef game logs + NBA.com
advanced stats) but generates projections for ALL stat categories instead of
just the ones with prop lines.
"""

import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent / "src"))

from nba_props.validation.real_data_runner import (
    ODDS_API_KEY,
    ODDS_API_BASE,
    BBREF_HEADERS,
    _ODDS_API_TO_BBREF,
    ODDS_API_MARKET_MAP,
    scrape_bbref_game_logs,
    ThreePMPredictor,
    AssistsPredictor,
    BoxScorePredictor,
    STAT_FG3M, STAT_ASSISTS, STAT_POINTS, STAT_REBOUNDS,
    STAT_STEALS, STAT_BLOCKS, STAT_TURNOVERS, STAT_FTM, STAT_FGM,
    ALL_FANTASY_STATS,
    BBREF_STAT_FIELD_ALL,
    fetch_nba_opponent_shooting,
    _CACHE_DIR,
)

# Import advanced context fetchers
try:
    from nba_props.validation.real_data_runner import (
        fetch_nba_opponent_general,
        fetch_nba_team_advanced,
        fetch_nba_opp_tracking_shooting,
        fetch_nba_synergy_defense,
        fetch_nba_synergy_player,
        fetch_nba_team_hustle,
        fetch_nba_player_advanced,
        fetch_nba_opp_shot_clock,
    )
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False


_BBREF_TEAM_CODES = {
    "ATL": "ATL", "BOS": "BOS", "BRK": "NJN", "CHO": "CHA",
    "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN",
    "DET": "DET", "GSW": "GSW", "HOU": "HOU", "IND": "IND",
    "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA",
    "MIL": "MIL", "MIN": "MIN", "NOP": "NOP", "NYK": "NYK",
    "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHO": "PHO",
    "POR": "POR", "SAC": "SAC", "SAS": "SAS", "TOR": "TOR",
    "UTA": "UTA", "WAS": "WAS",
}

# Minimum games and minutes to generate a projection
MIN_GAMES = 5
MIN_AVG_MINUTES = 12.0

# Prop-line market weight — how much to blend market-implied line into projection
# 0.0 = ignore market, 1.0 = use market as-is.  0.20 = 20% weight to market consensus.
MARKET_BLEND_WEIGHT = 0.20

# Total available minutes per team per game (48 minutes × 5 on-court spots)
TEAM_MINUTES_PER_GAME = 240.0


# ── Per-player minutes projection model ──────────────────────────────────────


def _strip_injury_exits(games: list[dict]) -> list[dict]:
    """Remove games where a player likely exited early due to injury.

    If a player has a stable minutes baseline (median of recent games) and
    one game is <40% of that baseline, that game is likely an injury exit
    and should be excluded entirely from projection inputs.

    This must be called BEFORE any analysis — these games are noise.
    """
    if len(games) < 5:
        return games

    minutes = [g["mp"] for g in games]
    med = float(np.median(minutes))
    if med < 8:
        return games  # Deep bench player — low games are normal

    # Check each game: if minutes < 40% of median AND the surrounding
    # games are at normal levels, this is an injury exit
    cleaned = []
    for i, g in enumerate(games):
        m = g["mp"]
        if m < med * 0.35 and m < 12:
            # Check if games before and after are at normal levels
            before = minutes[max(0, i-2):i]
            after = minutes[i+1:min(len(minutes), i+3)]
            context = before + after
            if context and np.mean(context) > med * 0.6:
                # Surrounding games are normal → this was an injury exit
                continue
        cleaned.append(g)

    # Never strip so many games that we have fewer than 4
    if len(cleaned) < 4:
        return games
    return cleaned


def _detect_teammate_absences(
    team_players: dict[str, list[dict]],
) -> dict[str, dict]:
    """Detect teammates who appear to be out for the upcoming game.

    A player is flagged as "likely out" if their last game had <40% of
    their usual minutes (injury exit) or if they've been absent recently.

    Returns {player_name: {"normal_minutes": float, "likely_out": bool,
                           "freed_minutes": float}}
    """
    absence_info = {}
    for name, games in team_players.items():
        if len(games) < 4:
            continue
        recent = games[-8:]  # Last 8 games
        minutes = [g["mp"] for g in recent]
        med = float(np.median(minutes))

        if med < 5:
            continue  # Deep bench — doesn't matter

        last_mp = games[-1]["mp"]
        # Player is "likely out" if last game was an injury exit
        likely_out = last_mp < med * 0.35 and last_mp < 12 and med >= 15

        absence_info[name] = {
            "normal_minutes": med,
            "likely_out": likely_out,
            "freed_minutes": med - last_mp if likely_out else 0.0,
        }

    return absence_info


def _detect_outlier_games(minutes: list[float]) -> list[bool]:
    """Flag remaining anomalous games after injury exits are stripped.

    This catches subtler anomalies like blowout garbage time or unusual
    coach decisions.  Only flags games drastically below the norm and
    only if they're isolated (not part of a sustained change).

    Returns a boolean mask (True = outlier to exclude from weighting).
    """
    n = len(minutes)
    if n < 5:
        return [False] * n

    med = float(np.median(minutes))
    mad = float(np.median([abs(m - med) for m in minutes]))
    if mad < 2.0:
        mad = 2.0

    mask = [False] * n
    for i, m in enumerate(minutes):
        deviation = (med - m) / mad
        # Only flag extreme low outliers, never high-minute games
        if deviation > 2.5 and m < med * 0.5:
            # Don't flag if it's part of a recent sustained change
            if i >= n - 3:
                recent_avg = float(np.mean(minutes[max(0, n-3):]))
                if recent_avg < med * 0.6:
                    continue  # Role change, not outlier
            mask[i] = True

    return mask


def _detect_role_change(minutes: list[float], starters: list[bool]) -> dict:
    """Detect if a player's role has recently changed.

    Looks for structural breaks in minutes patterns:
    - Sustained shift: recent 3-game avg differs from earlier by 5+ min
    - Monotonic trend: minutes consistently increasing/decreasing
    - Starter status change: moved from bench to starting lineup or vice versa

    Returns {"shift": float, "recent_avg": float, "is_trending": bool,
             "trend_strength": float, "starter_change": float}
    """
    n = len(minutes)
    if n < 4:
        return {
            "shift": 0.0, "recent_avg": float(np.mean(minutes)),
            "is_trending": False, "trend_strength": 0.0, "starter_change": 0.0,
        }

    # Split into recent (last 3 games) vs earlier
    split = 3
    recent = minutes[-split:]
    earlier = minutes[:-split]

    recent_avg = float(np.mean(recent))
    earlier_avg = float(np.mean(earlier))
    shift = recent_avg - earlier_avg

    # Monotonic trend: compute linear regression slope over last 6 games
    trend_window = minutes[-min(6, n):]
    x = np.arange(len(trend_window))
    if len(trend_window) >= 3:
        slope = float(np.polyfit(x, trend_window, 1)[0])
    else:
        slope = 0.0

    # Starter status change
    recent_starter_pct = sum(starters[-split:]) / split
    earlier_starter_pct = sum(starters[:-split]) / len(starters[:-split])
    starter_change = recent_starter_pct - earlier_starter_pct

    # Determine if trending: multiple signals
    # 1. Minutes shift of 5+ is a role change
    # 2. Slope of 2+ min/game is a strong trend
    # 3. Starter status flipped
    trend_strength = 0.0
    if abs(shift) > 5.0:
        trend_strength += min(abs(shift) / 10.0, 1.0)
    if abs(slope) > 2.0:
        trend_strength += min(abs(slope) / 4.0, 1.0)
    if abs(starter_change) > 0.5:
        trend_strength += 0.5

    is_trending = trend_strength >= 0.5

    return {
        "shift": shift,
        "recent_avg": recent_avg,
        "is_trending": is_trending,
        "trend_strength": min(trend_strength, 1.0),
        "slope": slope,
        "starter_change": starter_change,
    }


def _compute_weighted_minutes(
    minutes: list[float],
    starters: list[bool],
    role_info: dict,
) -> float:
    """Compute the predicted minutes for a player.

    Uses adaptive exponential recency weighting:
    - Stable roles: decay=0.75 over last 10 games with winsorization
    - Role changes: decay=0.65 over last 4 games (short window, high recency)

    Winsorization clips at 10th/90th percentile to reduce outlier impact
    without completely removing data points.
    """
    mins = list(minutes)
    k = len(mins)
    decay = 0.75

    # Check for role change → use shorter, more aggressive window
    if k >= 5 and role_info["is_trending"]:
        mins = mins[-4:]
        k = len(mins)
        decay = 0.65

    # Winsorize: clip at 10th/90th percentile to reduce outlier impact
    if k >= 5:
        lo, hi = float(np.percentile(mins, 10)), float(np.percentile(mins, 90))
        mins = [float(np.clip(m, lo, hi)) for m in mins]

    # Exponential recency-weighted average
    weights = [decay ** (k - 1 - i) for i in range(k)]
    total_w = sum(weights)
    pred = sum(m * w for m, w in zip(mins, weights)) / total_w

    return max(pred, 0.0)


def _apply_context_adjustment(
    base_minutes: float,
    role: str,
    spread: float,
    total: float,
) -> float:
    """Apply small game-context adjustments to base minutes prediction.

    These are micro-adjustments (±1-3 min max), not normalization.
    Based on empirical NBA patterns.
    """
    adj = base_minutes
    abs_spread = abs(spread)

    # Blowout factor: games with large spreads tend to have starters play
    # 1-3 fewer minutes and bench plays 1-2 more
    if abs_spread > 10:
        excess = abs_spread - 10
        if role == "starter":
            # Starters lose ~0.3 min per point of spread beyond 10
            adj -= min(excess * 0.3, 3.0)
        else:
            # Bench gains ~0.15 min per point of spread beyond 10
            adj += min(excess * 0.15, 2.0)

    # Pace/total: high-total games are competitive → starters play more
    # Average NBA total is ~228. Each point above/below nudges ±0.05 min
    if total > 0:
        pace_delta = (total - 228.0) * 0.05
        if role == "starter":
            adj += np.clip(pace_delta, -1.5, 1.5)
        else:
            adj -= np.clip(pace_delta * 0.3, -0.5, 0.5)

    # Tight game (spread < 3) → starters get ~1 extra minute on average
    if abs_spread < 3 and role == "starter":
        adj += 0.5

    return max(adj, 0.0)


class TeamMinutesModel:
    """Project minutes for every player on every team — no normalization.

    Philosophy: predict each player's minutes independently based on their
    own recent history, role changes, and game context. The predictions
    should naturally sum close to 240 because that's what the input data
    sums to. If they don't, that's a useful signal (e.g. missing players,
    roster changes).

    After independent prediction, we apply a soft reconciliation step that
    only acts when the team total is unrealistically far from 240 (>255 or
    <225), redistributing small amounts proportionally. This is NOT
    normalization — it's a sanity guardrail.
    """

    def __init__(self, window: int = 10):
        self.window = window

    def predict_player_minutes(
        self,
        games: list[dict],
        spread: float = 0.0,
        total: float = 228.0,
        teammate_boost: float = 0.0,
    ) -> dict:
        """Predict minutes for a single player from their game logs.

        Args:
            games: Player's game logs (already filtered to current team)
            spread: Game spread (absolute value)
            total: Game total (O/U line)
            teammate_boost: Extra minutes expected due to absent teammates

        Returns dict with 'minutes', 'role', 'confidence', etc.
        """
        # Step 0: Strip injury-exit games (noise removal)
        clean_games = _strip_injury_exits(games)
        recent = clean_games[-self.window:]
        if not recent:
            return {"minutes": 0.0, "role": "dnp", "confidence": 0.0}

        minutes = [g["mp"] for g in recent]
        starters = [g.get("starter", False) for g in recent]

        # Skip players with no meaningful minutes
        if max(minutes) < 1.0:
            return {"minutes": 0.0, "role": "dnp", "confidence": 0.0}

        # Detect remaining outliers after injury exits are stripped
        outlier_mask = _detect_outlier_games(minutes)
        n_outliers = sum(outlier_mask)

        # Detect role changes (promotion, demotion, trade adjustment)
        role_info = _detect_role_change(minutes, starters)

        # Core prediction: adaptive exponential decay with winsorization
        pred_minutes = _compute_weighted_minutes(minutes, starters, role_info)

        # Determine role
        starter_pct = sum(starters) / len(starters)
        # Use recent starter pct more heavily if role is changing
        recent_starter_pct = sum(starters[-3:]) / min(3, len(starters))
        effective_starter_pct = (
            0.7 * recent_starter_pct + 0.3 * starter_pct
            if role_info["is_trending"]
            else 0.4 * recent_starter_pct + 0.6 * starter_pct
        )

        if effective_starter_pct >= 0.5 and pred_minutes >= 20:
            role = "starter"
        elif pred_minutes >= 10:
            role = "bench"
        else:
            role = "deep_bench"

        # Apply game-context micro-adjustments
        pred_minutes = _apply_context_adjustment(pred_minutes, role, spread, total)

        # Apply teammate absence boost (minutes freed by injured/resting teammates)
        if teammate_boost > 0 and pred_minutes >= 10:
            pred_minutes += teammate_boost

        # Confidence based on sample size and consistency
        clean_minutes = [m for m, out in zip(minutes, outlier_mask) if not out]
        std = float(np.std(clean_minutes)) if len(clean_minutes) > 1 else 10.0
        cv = std / max(pred_minutes, 1.0)
        games_factor = min(len(recent) / 10, 1.0)
        confidence = round(games_factor * (1.0 - min(cv, 1.0)), 2)

        return {
            "minutes": round(pred_minutes, 1),
            "role": role,
            "confidence": confidence,
            "starter_pct": round(effective_starter_pct, 2),
            "raw_avg": round(float(np.mean(minutes)), 1),
            "recent_avg": round(role_info["recent_avg"], 1),
            "std": round(std, 1),
            "n_outliers": n_outliers,
            "n_injury_exits_stripped": len(games) - len(recent) + (self.window - len(recent)) if len(games) > len(recent) else 0,
            "is_trending": role_info["is_trending"],
            "trend_shift": round(role_info["shift"], 1),
            "games_played": len(recent),
        }

    def project_team(
        self,
        team_abbr: str,
        team_players: dict[str, list[dict]],
        game_context: dict | None = None,
    ) -> dict[str, dict]:
        """Project minutes for all players on a team.

        Each player is predicted independently. Teammate absences are
        detected and their freed minutes are redistributed to remaining
        rotation players proportionally.
        """
        ctx = game_context or {}
        spread = abs(ctx.get("spread", 0.0))
        total_line = ctx.get("total", 228.0)

        # Detect teammate absences (injury exits in last game)
        absences = _detect_teammate_absences(team_players)
        absent_players = {
            name for name, info in absences.items() if info["likely_out"]
        }
        freed_minutes = sum(
            absences[name]["freed_minutes"]
            for name in absent_players
        )

        if absent_players:
            logger.info(
                "  %s: detected %d likely absent player(s): %s (%.1f freed min)",
                team_abbr, len(absent_players),
                ", ".join(sorted(absent_players)), freed_minutes,
            )

        # Count active rotation players (for distributing freed minutes)
        active_count = sum(
            1 for name, games in team_players.items()
            if name not in absent_players
            and len(games) >= 4
            and np.mean([g["mp"] for g in games[-5:]]) >= 10
        )
        per_player_boost = (
            freed_minutes / max(active_count, 1) if freed_minutes > 0 else 0.0
        )

        # Predict each player independently
        projections = {}
        for name, games in team_players.items():
            if name in absent_players:
                # Mark as likely out — project reduced minutes
                projections[name] = {
                    "minutes": 0.0,
                    "role": "out",
                    "confidence": 0.0,
                    "likely_out": True,
                    "normal_minutes": absences[name]["normal_minutes"],
                    "starter_pct": 0.0,
                    "raw_avg": 0.0,
                    "recent_avg": 0.0,
                    "std": 0.0,
                    "n_outliers": 0,
                    "n_injury_exits_stripped": 0,
                    "is_trending": False,
                    "trend_shift": 0.0,
                    "games_played": 0,
                }
                continue

            boost = per_player_boost if freed_minutes > 0 else 0.0
            pred = self.predict_player_minutes(
                games, spread, total_line, teammate_boost=boost,
            )
            pred["likely_out"] = False
            if pred["minutes"] > 0:
                projections[name] = pred

        # Compute team total (for logging/sanity, no normalization)
        team_total = sum(p["minutes"] for p in projections.values())

        # Determine active rotation: top N players by projected minutes
        # who collectively cover ~240 min. Everyone else is DNP-caliber.
        sorted_by_min = sorted(
            [(n, i) for n, i in projections.items() if not i.get("likely_out")],
            key=lambda x: -x[1]["minutes"],
        )
        cumulative = 0.0
        active_set = set()
        for name, info in sorted_by_min:
            if cumulative < TEAM_MINUTES_PER_GAME and info["minutes"] >= 3:
                active_set.add(name)
                cumulative += info["minutes"]

        # Enforce the 240-minute physical constraint on the active rotation.
        # This is not statistical normalization — it's a real constraint:
        # only 5 players are on the court at any time × 48 minutes = 240.
        active_total = sum(
            projections[n]["minutes"] for n in active_set
        )
        if active_total > TEAM_MINUTES_PER_GAME:
            scale = TEAM_MINUTES_PER_GAME / active_total
            for name in active_set:
                projections[name]["minutes"] = round(
                    projections[name]["minutes"] * scale, 1
                )
            logger.debug(
                "  %s: scaled active rotation %.1f → 240.0 (%.2fx)",
                team_abbr, active_total, scale,
            )

        for name, info in projections.items():
            info["active_rotation"] = name in active_set
            info["team"] = team_abbr

        # Recompute final active total and shares
        final_active = sum(
            i["minutes"] for i in projections.values() if i["active_rotation"]
        )
        for info in projections.values():
            info["share"] = round(
                info["minutes"] / final_active if final_active > 0 else 0, 3
            )

        return projections

    def project_all_teams(
        self,
        all_player_logs: dict[str, list[dict]],
        game_lookup: dict[str, dict],
    ) -> dict[str, dict]:
        """Project minutes for every player across all games.

        Args:
            all_player_logs: {player_name: [game_logs]}
            game_lookup: {team_abbr: {"opp": str, "is_home": bool, ...}}

        Returns:
            {player_name: {"minutes": float, "role": str, "team": str, ...}}
        """
        # Group players by team (using ONLY games for their current team)
        teams: dict[str, dict[str, list[dict]]] = {}
        for name, games in all_player_logs.items():
            if not games:
                continue
            current_team = games[-1].get("team", "")
            if current_team and current_team in game_lookup:
                # Filter to only games with current team (handles trades)
                team_games = [g for g in games if g.get("team") == current_team]
                if team_games:
                    teams.setdefault(current_team, {})[name] = team_games

        all_projections = {}
        for team_abbr, players in sorted(teams.items()):
            game_info = game_lookup.get(team_abbr, {})
            ctx = {
                "spread": game_info.get("spread", 0.0),
                "total": game_info.get("total", 228.0),
                "is_home": game_info.get("is_home", True),
            }

            team_result = self.project_team(team_abbr, players, ctx)
            for name, info in team_result.items():
                all_projections[name] = info

        return all_projections


def fetch_all_fantasy_props() -> dict[str, dict[str, float]]:
    """Fetch prop lines for all fantasy stat types from Odds API.

    Returns dict keyed by (lowercase player name) -> {stat_type: line}.
    Uses persistent cache with 4-hour TTL.
    """
    cache_path = _CACHE_DIR / "fantasy_prop_lines.json"
    if cache_path.exists():
        from datetime import datetime as dt
        mtime = dt.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (dt.now() - mtime).total_seconds() / 3600
        if age_hours < 4:
            logger.info("Using cached prop lines (%.1fh old)", age_hours)
            with open(cache_path) as f:
                return json.load(f)

    logger.info("Fetching prop lines for all fantasy stat types...")
    # Get events
    try:
        resp = requests.get(
            f"{ODDS_API_BASE}/sports/basketball_nba/events",
            params={"apiKey": ODDS_API_KEY}, timeout=15,
        )
        resp.raise_for_status()
        events = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch events for props: %s", e)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    # Markets to request
    all_markets = ",".join(ODDS_API_MARKET_MAP.values())
    reverse_map = {v: k for k, v in ODDS_API_MARKET_MAP.items()}

    props: dict[str, dict[str, float]] = {}

    for ev in events:
        eid = ev["id"]
        try:
            time.sleep(0.3)
            resp2 = requests.get(
                f"{ODDS_API_BASE}/sports/basketball_nba/events/{eid}/odds",
                params={
                    "apiKey": ODDS_API_KEY, "regions": "us",
                    "markets": all_markets, "oddsFormat": "american",
                },
                timeout=15,
            )
            if resp2.status_code != 200:
                continue
            ev_data = resp2.json()
        except Exception:
            continue

        for bk in ev_data.get("bookmakers", []):
            for mkt in bk.get("markets", []):
                market_key = mkt.get("key", "")
                stat_type = reverse_map.get(market_key, "")
                if not stat_type:
                    continue
                for outcome in mkt.get("outcomes", []):
                    player = outcome.get("description", "").lower()
                    line = float(outcome.get("point", 0))
                    if player and line > 0:
                        props.setdefault(player, {})
                        # Use the line — multiple books will give similar lines,
                        # just take the latest (consensus is tight)
                        props[player][stat_type] = line

    remaining = resp.headers.get("x-requests-remaining", "?")
    logger.info(
        "Fetched prop lines for %d players across %d events (%s API calls left)",
        len(props), len(events), remaining,
    )

    with open(cache_path, "w") as f:
        json.dump(props, f, indent=2)
    return props


def get_tonight_games():
    """Get tonight's games with team abbreviations, spread, and total."""
    from nba_props.validation.real_data_runner import _fetch_game_spread_total

    resp = requests.get(
        f"{ODDS_API_BASE}/sports/basketball_nba/events",
        params={"apiKey": ODDS_API_KEY},
        timeout=15,
    )
    resp.raise_for_status()
    events = resp.json()
    games = []
    teams = set()
    for ev in events:
        home = _ODDS_API_TO_BBREF.get(ev["home_team"], "")
        away = _ODDS_API_TO_BBREF.get(ev["away_team"], "")
        if home and away:
            spread, total = _fetch_game_spread_total(ev["id"], ODDS_API_KEY)
            games.append({
                "home": home,
                "away": away,
                "event_id": ev["id"],
                "commence_time": ev.get("commence_time", ""),
                "spread": spread,
                "total": total if total > 0 else 228.0,
            })
            teams.add(home)
            teams.add(away)
    return games, sorted(teams)


def get_team_roster_slugs(team_abbr: str, season: int = 2026) -> dict[str, str]:
    """Scrape player name -> BBRef slug from a team's roster page."""
    from bs4 import BeautifulSoup
    code = _BBREF_TEAM_CODES.get(team_abbr, team_abbr)
    url = f"https://www.basketball-reference.com/teams/{code}/{season}.html"
    time.sleep(3.5)
    resp = requests.get(url, headers=BBREF_HEADERS, timeout=30)
    if resp.status_code != 200:
        return {}
    soup = BeautifulSoup(resp.text, "html.parser")
    roster_table = soup.find("table", {"id": "roster"})
    if not roster_table:
        return {}
    slugs = {}
    for row in roster_table.find("tbody").find_all("tr"):
        player_cell = row.find("td", {"data-stat": "player"})
        if not player_cell:
            continue
        link = player_cell.find("a")
        if not link:
            continue
        href = link.get("href", "")
        name = link.text.strip()
        parts = href.split("/players/")
        if len(parts) == 2:
            slug = parts[1].replace(".html", "")
            slugs[name] = slug
    return slugs


def build_fantasy_context(
    player_name: str,
    games: list[dict],
    opp_abbr: str,
    player_team_abbr: str,
    is_home: bool,
    spread: float = 0.0,
    total: float = 228.0,
    absent_teammates: list[dict] | None = None,
    *,
    _cache: dict = {},
) -> dict:
    """Build game context dict for a player's fantasy projection.

    Pulls from multiple NBA.com data sources:
    - Opponent shooting zones (3PA/3P% allowed)
    - Opponent general stats (all box score stats allowed per game)
    - Team advanced (pace, def/off rating)
    - Opponent tracking (wide-open/tight 3PA, catch-and-shoot)
    - Synergy defense (play-type PPP/FG%)
    - Team hustle (deflections, contested shots)
    - Player advanced (USG%, AST%, TS%, pace)
    - Player synergy (offensive play-type breakdown)
    - Absent teammate data (for usage/role redistribution)
    """
    ctx = {
        "spread": spread,
        "total": total,
        "is_home": is_home,
    }

    # Teammate absence context: how many minutes/usage freed up
    if absent_teammates:
        total_freed = sum(t.get("normal_minutes", 0) for t in absent_teammates)
        ctx["absent_teammate_minutes"] = total_freed
        ctx["absent_teammate_count"] = len(absent_teammates)
        ctx["absent_teammates"] = absent_teammates
    else:
        ctx["absent_teammate_minutes"] = 0.0
        ctx["absent_teammate_count"] = 0
        ctx["absent_teammates"] = []

    # --- Opponent 3P shooting zone data ---
    try:
        opp_data = fetch_nba_opponent_shooting()
        opp_info = opp_data.get(opp_abbr, {})
        ctx.update({
            "opp_3pa_per_game": opp_info.get("opp_3pa_per_game", 0),
            "opp_fg3_pct_allowed": opp_info.get("opp_fg3_pct_allowed", 0),
            "opp_corner3_pct": opp_info.get("opp_corner3_pct", 0),
            "opp_atb3_pct": opp_info.get("opp_atb3_pct", 0),
        })
    except Exception:
        pass

    if not HAS_ADVANCED:
        return ctx

    # --- Opponent general stats (all box score categories) ---
    try:
        if "opp_general" not in _cache:
            _cache["opp_general"] = fetch_nba_opponent_general()
        opp_gen = _cache["opp_general"].get(opp_abbr, {})
        ctx.update(opp_gen)  # All opp_* keys directly
    except Exception:
        pass

    # --- Team advanced stats (pace, ratings) ---
    try:
        if "team_advanced" not in _cache:
            _cache["team_advanced"] = fetch_nba_team_advanced()
        adv = _cache["team_advanced"]
        opp_adv = adv.get(opp_abbr, {})
        team_adv = adv.get(player_team_abbr, {})
        ctx["opp_def_rating"] = opp_adv.get("def_rating", 110.0)
        ctx["opp_off_rating"] = opp_adv.get("off_rating", 110.0)
        ctx["opp_pace"] = opp_adv.get("pace", 100.0)
        ctx["team_pace"] = team_adv.get("pace", 100.0)
        ctx["team_off_rating"] = team_adv.get("off_rating", 110.0)
        ctx["team_net_rating"] = team_adv.get("net_rating", 0.0)
    except Exception:
        pass

    # --- Opponent tracking shooting (defender distance, catch-and-shoot) ---
    try:
        if "opp_tracking" not in _cache:
            _cache["opp_tracking"] = fetch_nba_opp_tracking_shooting()
        opp_trk = _cache["opp_tracking"].get(opp_abbr, {})
        ctx.update({
            "opp_wide_open_3pa": opp_trk.get("opp_wide_open_3pa", 0),
            "opp_wide_open_3pct": opp_trk.get("opp_wide_open_3pct", 0),
            "opp_open_3pa": opp_trk.get("opp_open_3pa", 0),
            "opp_open_3pct": opp_trk.get("opp_open_3pct", 0),
            "opp_tight_3pa": opp_trk.get("opp_tight_3pa", 0),
            "opp_tight_3pct": opp_trk.get("opp_tight_3pct", 0),
            "opp_catch_shoot_3pa": opp_trk.get("opp_catch_shoot_3pa", 0),
            "opp_catch_shoot_3pct": opp_trk.get("opp_catch_shoot_3pct", 0),
            "opp_pullup_3pa": opp_trk.get("opp_pullup_3pa", 0),
            "opp_pullup_3pct": opp_trk.get("opp_pullup_3pct", 0),
        })
    except Exception:
        pass

    # --- Synergy play-type defense ---
    try:
        if "synergy_def" not in _cache:
            _cache["synergy_def"] = fetch_nba_synergy_defense()
        syn = _cache["synergy_def"].get(opp_abbr, {})
        ctx.update({
            "def_spotup_ppp": syn.get("def_spotup_ppp", 0),
            "def_isolation_ppp": syn.get("def_isolation_ppp", 0),
            "def_prballhandler_ppp": syn.get("def_prballhandler_ppp", 0),
            "def_prrollman_ppp": syn.get("def_prrollman_ppp", 0),
            "def_transition_ppp": syn.get("def_transition_ppp", 0),
            "def_offscreen_ppp": syn.get("def_offscreen_ppp", 0),
            "def_handoff_ppp": syn.get("def_handoff_ppp", 0),
            "def_cut_ppp": syn.get("def_cut_ppp", 0),
            "def_spotup_efg": syn.get("def_spotup_efg", 0),
            "def_isolation_efg": syn.get("def_isolation_efg", 0),
            "def_prballhandler_efg": syn.get("def_prballhandler_efg", 0),
            "def_transition_efg": syn.get("def_transition_efg", 0),
        })
    except Exception:
        pass

    # --- Team hustle stats ---
    try:
        if "hustle" not in _cache:
            _cache["hustle"] = fetch_nba_team_hustle()
        hustle = _cache["hustle"].get(opp_abbr, {})
        ctx.update({
            "opp_deflections": hustle.get("deflections", 0),
            "opp_contested_shots": hustle.get("contested_shots", 0),
            "opp_contested_shots_3pt": hustle.get("contested_shots_3pt", 0),
            "opp_loose_balls_recovered": hustle.get("loose_balls_recovered", 0),
        })
    except Exception:
        pass

    # --- Player advanced stats ---
    try:
        if "player_advanced" not in _cache:
            _cache["player_advanced"] = fetch_nba_player_advanced()
        pkey = player_name.lower()
        padv = _cache["player_advanced"].get(pkey, {})
        if padv:
            ctx.update({
                "player_usg_pct": padv.get("usg_pct", 0),
                "player_ast_pct": padv.get("ast_pct", 0),
                "player_ast_ratio": padv.get("ast_ratio", 0),
                "player_ts_pct": padv.get("ts_pct", 0),
                "player_efg_pct": padv.get("efg_pct", 0),
                "player_pace": padv.get("pace", 0),
                "player_off_rating": padv.get("off_rating", 0),
                "player_pie": padv.get("pie", 0),
            })
    except Exception:
        pass

    # --- Player synergy offensive play types ---
    try:
        if "synergy_player" not in _cache:
            _cache["synergy_player"] = fetch_nba_synergy_player()
        pkey = player_name.lower()
        psyn = _cache["synergy_player"].get(pkey, {})
        if psyn:
            ctx.update({
                "player_spotup_freq": psyn.get("off_spotup_freq", 0),
                "player_spotup_ppp": psyn.get("off_spotup_ppp", 0),
                "player_iso_freq": psyn.get("off_isolation_freq", 0),
                "player_iso_ppp": psyn.get("off_isolation_ppp", 0),
                "player_pnr_freq": psyn.get("off_prballhandler_freq", 0),
                "player_pnr_ppp": psyn.get("off_prballhandler_ppp", 0),
                "player_transition_freq": psyn.get("off_transition_freq", 0),
                "player_transition_ppp": psyn.get("off_transition_ppp", 0),
                "player_offscreen_freq": psyn.get("off_offscreen_freq", 0),
            })
    except Exception:
        pass

    # --- Opponent shot clock data ---
    try:
        if "opp_shot_clock" not in _cache:
            _cache["opp_shot_clock"] = fetch_nba_opp_shot_clock()
        sc = _cache["opp_shot_clock"].get(opp_abbr, {})
        ctx.update({
            "opp_sc_early_3pa": sc.get("sc_early_3pa", 0),
            "opp_sc_late_3pa": sc.get("sc_late_3pa", 0),
            "opp_sc_late_3pct": sc.get("sc_late_3pct", 0),
        })
    except Exception:
        pass

    return ctx


def _blend_with_market(model_proj: float, market_line: float, weight: float) -> float:
    """Blend model projection with market-implied line.

    The market line represents the consensus of sharp and recreational money.
    A weighted blend anchors the model to market reality while still allowing
    the model's edge to show through.
    """
    if market_line <= 0:
        return model_proj
    return model_proj * (1.0 - weight) + market_line * weight


def project_player(
    player_name: str,
    games: list[dict],
    game_context: dict,
    prop_lines: dict[str, float] | None = None,
    team_minutes: float | None = None,
) -> dict | None:
    """Generate full box score projection for one player.

    If prop_lines is provided (stat_type -> line), the model projection is
    blended with the market line using MARKET_BLEND_WEIGHT.
    If team_minutes is provided (from TeamMinutesModel), it overrides the
    per-predictor minutes estimate to ensure team totals sum to 240.
    """
    if len(games) < MIN_GAMES:
        return None

    avg_min = np.mean([g["mp"] for g in games[-15:]])
    if avg_min < MIN_AVG_MINUTES:
        return None

    props = prop_lines or {}
    w = MARKET_BLEND_WEIGHT

    projection = {
        "player": player_name,
        "team": games[-1].get("team", ""),
        "opp": games[-1].get("opp", ""),
        "games_used": min(len(games), 15),
    }

    # Use specialized predictors for 3PM and assists
    fg3_pred = ThreePMPredictor()
    ast_pred = AssistsPredictor()

    # 3PM projection
    fg3_result = fg3_pred.predict(games, line=0, game_context=game_context)
    fg3m_raw = fg3_result["mean_stat"]
    fg3m_market = props.get(STAT_FG3M, 0)
    fg3m_final = _blend_with_market(fg3m_raw, fg3m_market, w)
    projection["fg3m"] = round(fg3m_final, 1)
    projection["fg3m_model"] = round(fg3m_raw, 1)
    projection["fg3m_market"] = fg3m_market
    projection["fg3m_floor"] = round(fg3m_final - fg3_result.get("std_stat", 0), 1)
    projection["fg3m_ceiling"] = round(fg3m_final + fg3_result.get("std_stat", 0), 1)

    # Assists projection
    ast_result = ast_pred.predict(games, line=0, game_context=game_context)
    ast_raw = ast_result["mean_stat"]
    ast_market = props.get(STAT_ASSISTS, 0)
    projection["ast"] = round(_blend_with_market(ast_raw, ast_market, w), 1)
    projection["ast_model"] = round(ast_raw, 1)
    projection["ast_market"] = ast_market

    # Minutes: use team-constrained model if available, else predictor estimate
    if team_minutes is not None:
        projection["min"] = round(team_minutes, 1)
    else:
        projection["min"] = round(fg3_result["pred_minutes"], 1)

    # All other stats via generic predictor
    stat_short = {
        STAT_POINTS: "pts", STAT_REBOUNDS: "reb", STAT_STEALS: "stl",
        STAT_BLOCKS: "blk", STAT_TURNOVERS: "tov", STAT_FTM: "ftm",
        STAT_FGM: "fgm",
    }
    for stat_type, short_name in stat_short.items():
        pred = BoxScorePredictor(stat_type)
        result = pred.predict(games, line=0, game_context=game_context)
        raw = result["mean_stat"]
        market = props.get(stat_type, 0)
        projection[short_name] = round(_blend_with_market(raw, market, w), 1)
        projection[f"{short_name}_model"] = round(raw, 1)
        projection[f"{short_name}_market"] = market

    # Derived stats
    recent = games[-15:]
    total_fga = sum(g.get("fga", 0) for g in recent)
    total_fg = sum(g.get("fg", 0) for g in recent)
    total_fta = sum(g.get("fta", 0) for g in recent)
    total_ft = sum(g.get("ft", 0) for g in recent)
    total_fg3a = sum(g.get("fg3a", 0) for g in recent)
    total_min = sum(g["mp"] for g in recent)

    # FGA projection (from FGM and FG%)
    fg_pct = total_fg / max(total_fga, 1)
    projection["fga"] = round(projection["fgm"] / max(fg_pct, 0.35), 1)

    # FTA projection (from FTM and FT%)
    ft_pct = total_ft / max(total_fta, 1)
    projection["fta"] = round(projection["ftm"] / max(ft_pct, 0.60), 1)

    # 3PA projection (from rate)
    fg3a_per_min = total_fg3a / max(total_min, 1)
    projection["fg3a"] = round(fg3a_per_min * projection["min"], 1)

    # Fantasy points (DraftKings scoring)
    dk_pts = (
        projection["pts"] * 1.0
        + projection["fg3m"] * 0.5
        + projection["reb"] * 1.25
        + projection["ast"] * 1.5
        + projection["stl"] * 2.0
        + projection["blk"] * 2.0
        - projection["tov"] * 0.5
    )
    projection["dk_fantasy_pts"] = round(dk_pts, 1)

    # FanDuel scoring
    fd_pts = (
        projection["pts"] * 1.0
        + projection["reb"] * 1.2
        + projection["ast"] * 1.5
        + projection["stl"] * 3.0
        + projection["blk"] * 3.0
        - projection["tov"] * 1.0
    )
    projection["fd_fantasy_pts"] = round(fd_pts, 1)

    # PRA (Points + Rebounds + Assists)
    projection["pra"] = round(
        projection["pts"] + projection["reb"] + projection["ast"], 1
    )

    # PA (Points + Assists)
    projection["pa"] = round(projection["pts"] + projection["ast"], 1)

    # PR (Points + Rebounds)
    projection["pr"] = round(projection["pts"] + projection["reb"], 1)

    # RA (Rebounds + Assists)
    projection["ra"] = round(projection["reb"] + projection["ast"], 1)

    # Stocks (Steals + Blocks)
    projection["stocks"] = round(projection["stl"] + projection["blk"], 1)

    projection["confidence"] = fg3_result.get("confidence", "medium")

    return projection


def main():
    # Use persistent project cache directory for game logs
    cache_dir = Path(__file__).resolve().parent / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "nba_game_logs.json"

    logger.info("=" * 60)
    logger.info("FANTASY BOX SCORE PROJECTIONS — %s", datetime.now().strftime("%Y-%m-%d"))
    logger.info("=" * 60)

    # Step 1: Get tonight's games
    games_tonight, teams = get_tonight_games()
    logger.info("Found %d games tonight with %d teams", len(games_tonight), len(teams))

    # Step 2: Load or scrape BBRef game logs
    if cache_path.exists():
        from datetime import datetime as dt
        mtime = dt.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (dt.now() - mtime).total_seconds() / 3600
        if age_hours < 12:
            logger.info("Using cached BBRef game logs (%.1fh old)", age_hours)
            with open(cache_path) as f:
                raw = json.load(f)
            all_logs = {name: data["games"] for name, data in raw.items()}
        else:
            all_logs = None
    else:
        all_logs = None

    if all_logs is None:
        logger.info("Scraping BBRef game logs for tonight's players...")
        all_slugs = {}
        for team in teams:
            try:
                roster = get_team_roster_slugs(team)
                all_slugs.update(roster)
            except Exception as e:
                logger.warning("Failed roster for %s: %s", team, e)

        all_logs = scrape_bbref_game_logs(all_slugs, season=2026)
        cache_data = {name: {"games": games} for name, games in all_logs.items()}
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)

    logger.info("Loaded game logs for %d players", len(all_logs))

    # Build game lookup: team -> game info (with spread/total)
    game_lookup = {}
    for g in games_tonight:
        game_lookup[g["home"]] = {
            "opp": g["away"], "is_home": True,
            "spread": g.get("spread", 0.0),
            "total": g.get("total", 228.0),
        }
        game_lookup[g["away"]] = {
            "opp": g["home"], "is_home": False,
            "spread": -g.get("spread", 0.0),  # Away team gets opposite spread
            "total": g.get("total", 228.0),
        }

    # Step 3: Project team-constrained minutes (sum to 240 per team)
    logger.info("Projecting team-constrained minutes...")
    minutes_model = TeamMinutesModel(window=10)
    all_minutes = minutes_model.project_all_teams(all_logs, game_lookup)
    logger.info(
        "Projected minutes for %d players across %d teams",
        len(all_minutes), len(set(v["team"] for v in all_minutes.values())),
    )

    # Validate: check team totals (active rotation only)
    team_totals: dict[str, float] = {}
    team_active: dict[str, int] = {}
    for info in all_minutes.values():
        t = info["team"]
        if info.get("active_rotation"):
            team_totals.setdefault(t, 0.0)
            team_totals[t] += info["minutes"]
            team_active.setdefault(t, 0)
            team_active[t] += 1
    for team, total in sorted(team_totals.items()):
        logger.info("  %s: %.1f active rotation minutes (%d players)",
                     team, total, team_active.get(team, 0))

    # Step 4: Fetch prop lines (market consensus) for all stat types
    all_prop_lines = {}
    try:
        all_prop_lines = fetch_all_fantasy_props()
        logger.info("Loaded prop lines for %d players", len(all_prop_lines))
    except Exception as e:
        logger.warning("Could not fetch prop lines: %s — proceeding without market data", e)

    # Collect absent teammate info per team for stat adjustments
    team_absences: dict[str, list[dict]] = {}
    for name, info in all_minutes.items():
        if info.get("likely_out"):
            t = info.get("team", "")
            team_absences.setdefault(t, []).append({
                "name": name,
                "normal_minutes": info.get("normal_minutes", 0),
                "role": "starter" if info.get("starter_pct", 0) >= 0.5 else "bench",
            })

    # Step 5: Generate projections
    projections = []
    props_used = 0
    for player_name, games in all_logs.items():
        if not games:
            continue

        team = games[-1].get("team", "")
        game_info = game_lookup.get(team)
        if not game_info:
            continue

        # Get absent teammates for this player's team
        absent = team_absences.get(team, [])
        # Exclude self from absent list
        absent_others = [a for a in absent if a["name"] != player_name]

        ctx = build_fantasy_context(
            player_name, games,
            opp_abbr=game_info["opp"],
            player_team_abbr=team,
            is_home=game_info["is_home"],
            spread=game_info.get("spread", 0.0),
            total=game_info.get("total", 228.0),
            absent_teammates=absent_others,
        )

        # Look up prop lines for this player (case-insensitive match)
        player_props = all_prop_lines.get(player_name.lower(), {})
        if player_props:
            props_used += 1

        # Get minutes model info for this player
        player_min_info = all_minutes.get(player_name, {})

        # Skip players who are likely OUT
        if player_min_info.get("likely_out"):
            continue

        # Skip players not in the active rotation
        if player_min_info and not player_min_info.get("active_rotation"):
            continue

        team_min = player_min_info.get("minutes") if player_min_info else None

        proj = project_player(
            player_name, games, ctx,
            prop_lines=player_props,
            team_minutes=team_min,
        )
        if proj:
            proj["opp"] = game_info["opp"]
            proj["is_home"] = game_info["is_home"]
            proj["has_prop_lines"] = bool(player_props)
            proj["role"] = player_min_info.get("role", "unknown")
            proj["min_share"] = player_min_info.get("share", 0.0)
            proj["active_rotation"] = True
            projections.append(proj)

    logger.info(
        "Generated %d projections (%d with market prop anchoring)",
        len(projections), props_used,
    )

    # ── Team-level stat reconciliation ────────────────────────────────────
    # Players share possessions: the sum of individual projections must be
    # consistent with the implied team total from the game line.
    # Implied team score = (total / 2) + (spread / 2) for home, etc.
    # We scale scoring stats proportionally when team totals are unrealistic.
    from collections import defaultdict

    # Group projections by team
    team_projs: dict[str, list[dict]] = defaultdict(list)
    for p in projections:
        team_projs[p.get("team", "")].append(p)

    for team_abbr, team_ps in team_projs.items():
        game_info = game_lookup.get(team_abbr, {})
        game_total = game_info.get("total", 228.0)
        game_spread = game_info.get("spread", 0.0)

        # Implied team score: total/2 adjusted by spread
        # Home team: (total + spread) / 2 ... but spread sign varies
        # Use absolute: implied = total/2 + abs(spread)/2 for favorite
        if game_info.get("is_home"):
            implied_pts = (game_total - game_spread) / 2
        else:
            implied_pts = (game_total + game_spread) / 2

        # Sanity bound: NBA teams score 95-135 typically
        implied_pts = max(95, min(implied_pts, 135))

        # Sum projected PTS for this team
        total_proj_pts = sum(p.get("pts", 0) for p in team_ps)

        if total_proj_pts > implied_pts * 1.15:  # >15% over implied
            scale = implied_pts / total_proj_pts
            logger.info(
                "  %s: scaling scoring stats %.1f → %.1f (implied=%.1f)",
                team_abbr, total_proj_pts, total_proj_pts * scale, implied_pts,
            )
            # Scale scoring-related stats proportionally
            scoring_stats = ["pts", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta"]
            combo_stats = ["pra", "pa", "pr", "dk_fantasy_pts", "fd_fantasy_pts"]
            for p in team_ps:
                for stat in scoring_stats:
                    if stat in p:
                        p[stat] = round(p[stat] * scale, 1)
                # Recompute combo stats
                p["pra"] = round(p["pts"] + p["reb"] + p["ast"], 1)
                p["pa"] = round(p["pts"] + p["ast"], 1)
                p["pr"] = round(p["pts"] + p["reb"], 1)
                # Recompute fantasy points
                p["dk_fantasy_pts"] = round(
                    p["pts"] * 1.0 + p.get("fg3m", 0) * 0.5
                    + p["reb"] * 1.25 + p["ast"] * 1.5
                    + p.get("stl", 0) * 2.0 + p.get("blk", 0) * 2.0
                    - p.get("tov", 0) * 0.5, 1
                )
                p["fd_fantasy_pts"] = round(
                    p["pts"] * 1.0 + p["reb"] * 1.2 + p["ast"] * 1.5
                    + p.get("stl", 0) * 3.0 + p.get("blk", 0) * 3.0
                    - p.get("tov", 0) * 1.0, 1
                )

    # Sort by DK fantasy points
    projections.sort(key=lambda p: p.get("dk_fantasy_pts", 0), reverse=True)

    # ── Team-by-team minutes rotation report ──────────────────────────────
    print(f"\n{'=' * 90}")
    print(f"  MINUTES ROTATION REPORT — {datetime.now().strftime('%B %d, %Y')}")
    print(f"{'=' * 90}")

    for game in games_tonight:
        home, away = game["home"], game["away"]
        spread = game.get("spread", 0.0)
        total_line = game.get("total", 228.0)
        print(f"\n  {away} @ {home}  (spread: {spread:+.1f}  total: {total_line})")
        print(f"  {'-' * 84}")

        for team_abbr in [away, home]:
            team_players = sorted(
                [(n, i) for n, i in all_minutes.items() if i.get("team") == team_abbr],
                key=lambda x: -x[1]["minutes"],
            )
            team_total = sum(i["minutes"] for _, i in team_players)
            absent = [n for n, i in team_players if i.get("likely_out")]

            active_players = [
                (n, i) for n, i in team_players if i.get("active_rotation")
            ]
            active_total = sum(i["minutes"] for _, i in active_players)
            inactive = [
                (n, i) for n, i in team_players
                if not i.get("active_rotation") and not i.get("likely_out")
            ]
            absent_list = [(n, i) for n, i in team_players if i.get("likely_out")]

            label = f"{team_abbr} ({active_total:.0f} active min, {len(active_players)} rotation"
            if absent_list:
                label += f", {len(absent_list)} OUT"
            label += ")"
            print(f"\n    {label}")
            print(f"    {'Player':<24} {'Proj':>5} {'Role':<8} {'Avg':>5} {'Rec':>5} "
                  f"{'Conf':>5} {'Trend':<8}")

            for name, info in team_players:
                if info.get("likely_out"):
                    print(f"    {name:<24} {'OUT':>5} {'out':<8} "
                          f"{info.get('normal_minutes',0):5.1f}   -     -  LIKELY OUT")
                    continue
                if not info.get("active_rotation"):
                    continue  # Skip inactive in report
                trend = ""
                if info.get("is_trending"):
                    shift = info.get("trend_shift", 0)
                    trend = f"{'↑' if shift > 0 else '↓'}{abs(shift):.0f}min"
                print(f"    {name:<24} {info['minutes']:5.1f} {info['role']:<8} "
                      f"{info.get('raw_avg', 0):5.1f} {info.get('recent_avg', 0):5.1f} "
                      f"{info.get('confidence', 0):5.2f} {trend:<8}")
            if inactive:
                inactive_names = ", ".join(n for n, _ in inactive[:5])
                if len(inactive) > 5:
                    inactive_names += f" +{len(inactive)-5}"
                print(f"    (Inactive: {inactive_names})")

    # ── Full box score projections ────────────────────────────────────────
    print(f"\n{'=' * 130}")
    print(f"  FULL BOX SCORE PROJECTIONS — {datetime.now().strftime('%B %d, %Y')}")
    print(f"  {len(projections)} players projected across {len(games_tonight)} games")
    print(f"{'=' * 130}")

    print(f"\n{'Player':<22} {'Team':<5} {'Opp':<5} {'MIN':<5} {'PTS':<5} {'REB':<5} "
          f"{'AST':<5} {'STL':<5} {'BLK':<5} {'TOV':<5} {'3PM':<5} {'FGM':<5} "
          f"{'FGA':<5} {'FTM':<5} {'FTA':<5} {'PRA':<6} {'DK':<7} {'FD':<7}")
    print("-" * 130)

    for p in projections:
        print(f"{p['player']:<22} {p.get('team',''):<5} {p['opp']:<5} "
              f"{p['min']:<5} {p['pts']:<5} {p['reb']:<5} "
              f"{p['ast']:<5} {p['stl']:<5} {p['blk']:<5} {p['tov']:<5} "
              f"{p['fg3m']:<5} {p['fgm']:<5} {p['fga']:<5} "
              f"{p['ftm']:<5} {p['fta']:<5} {p['pra']:<6} "
              f"{p['dk_fantasy_pts']:<7} {p['fd_fantasy_pts']:<7}")

    # Save projections to file
    out_path = Path("validation_output/fantasy_projections_today.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(projections, f, indent=2, default=str)
    logger.info("Saved %d projections to %s", len(projections), out_path)

    # Save minutes model output
    min_path = Path("validation_output/minutes_projections_today.json")
    with open(min_path, "w") as f:
        json.dump(all_minutes, f, indent=2, default=str)
    logger.info("Saved minutes projections to %s", min_path)

    # Also save CSV for easy import
    csv_path = Path("validation_output/fantasy_projections_today.csv")
    cols = ["player", "team", "opp", "min", "pts", "reb", "ast", "stl", "blk",
            "tov", "fg3m", "fg3a", "fgm", "fga", "ftm", "fta",
            "pra", "pa", "pr", "ra", "stocks", "dk_fantasy_pts", "fd_fantasy_pts"]
    with open(csv_path, "w") as f:
        f.write(",".join(cols) + "\n")
        for p in projections:
            f.write(",".join(str(p.get(c, "")) for c in cols) + "\n")
    logger.info("Saved CSV to %s", csv_path)


if __name__ == "__main__":
    main()
