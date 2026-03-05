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
    scrape_bbref_game_logs,
    ThreePMPredictor,
    AssistsPredictor,
    BoxScorePredictor,
    STAT_FG3M, STAT_ASSISTS, STAT_POINTS, STAT_REBOUNDS,
    STAT_STEALS, STAT_BLOCKS, STAT_TURNOVERS, STAT_FTM, STAT_FGM,
    ALL_FANTASY_STATS,
    BBREF_STAT_FIELD_ALL,
    fetch_nba_opponent_shooting,
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


def get_tonight_games():
    """Get tonight's games with team abbreviations from Odds API."""
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
            games.append({
                "home": home,
                "away": away,
                "event_id": ev["id"],
                "commence_time": ev.get("commence_time", ""),
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
    """
    ctx = {
        "spread": spread,
        "total": total,
        "is_home": is_home,
    }

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


def project_player(
    player_name: str,
    games: list[dict],
    game_context: dict,
) -> dict | None:
    """Generate full box score projection for one player."""
    if len(games) < MIN_GAMES:
        return None

    avg_min = np.mean([g["mp"] for g in games[-15:]])
    if avg_min < MIN_AVG_MINUTES:
        return None

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
    projection["fg3m"] = round(fg3_result["mean_stat"], 1)
    projection["fg3m_floor"] = round(fg3_result.get("mean_stat", 0) - fg3_result.get("std_stat", 0), 1)
    projection["fg3m_ceiling"] = round(fg3_result.get("mean_stat", 0) + fg3_result.get("std_stat", 0), 1)

    # Assists projection
    ast_result = ast_pred.predict(games, line=0, game_context=game_context)
    projection["ast"] = round(ast_result["mean_stat"], 1)

    # Minutes
    projection["min"] = round(fg3_result["pred_minutes"], 1)

    # All other stats via generic predictor
    for stat_type in [STAT_POINTS, STAT_REBOUNDS, STAT_STEALS,
                      STAT_BLOCKS, STAT_TURNOVERS, STAT_FTM, STAT_FGM]:
        pred = BoxScorePredictor(stat_type)
        result = pred.predict(games, line=0, game_context=game_context)
        short_name = {
            STAT_POINTS: "pts", STAT_REBOUNDS: "reb", STAT_STEALS: "stl",
            STAT_BLOCKS: "blk", STAT_TURNOVERS: "tov", STAT_FTM: "ftm",
            STAT_FGM: "fgm",
        }[stat_type]
        projection[short_name] = round(result["mean_stat"], 1)

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

    # Build game lookup: team -> game info
    game_lookup = {}
    for g in games_tonight:
        game_lookup[g["home"]] = {"opp": g["away"], "is_home": True}
        game_lookup[g["away"]] = {"opp": g["home"], "is_home": False}

    # Step 3: Generate projections
    projections = []
    for player_name, games in all_logs.items():
        if not games:
            continue

        team = games[-1].get("team", "")
        game_info = game_lookup.get(team)
        if not game_info:
            continue

        ctx = build_fantasy_context(
            player_name, games,
            opp_abbr=game_info["opp"],
            player_team_abbr=team,
            is_home=game_info["is_home"],
        )

        proj = project_player(player_name, games, ctx)
        if proj:
            proj["opp"] = game_info["opp"]
            proj["is_home"] = game_info["is_home"]
            projections.append(proj)

    # Sort by DK fantasy points
    projections.sort(key=lambda p: p.get("dk_fantasy_pts", 0), reverse=True)

    # Display results
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

    # Save to file
    out_path = Path("validation_output/fantasy_projections_today.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(projections, f, indent=2, default=str)
    logger.info("Saved %d projections to %s", len(projections), out_path)

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
