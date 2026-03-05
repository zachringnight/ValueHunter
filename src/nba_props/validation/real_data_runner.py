"""Run the full validation pack against real NBA data only.

Data sources (all real, zero synthetic):
  1. Basketball-Reference: player game logs (minutes, 3PA, 3PM, assists, etc.)
  2. SportsGameOdds API:   historical props with multi-book odds & results
  3. The Odds API:         live props for current/upcoming games

Supported stat types:
  - fg3m: Three-pointers made (3PM)
  - assists: Player assists

No fake odds, no synthetic lines, no simulated results.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import requests

# Persistent cache directory — survives reboots unlike /tmp
_CACHE_DIR = Path(__file__).resolve().parents[3] / "data" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── API keys ─────────────────────────────────────────────────────────────────

SGO_API_KEY = os.environ.get("SGO_API_KEY", "17b9b40bdb521cbe9b81492d25bc922e")
SGO_BASE = "https://api.sportsgameodds.com/v2"

ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "6ae8c7a3c32758e91380e1a5c0f4241b")
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

BBREF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

LEAGUE_3PT_PCT = 0.363
LEAGUE_AST_PER_36 = 4.5  # League-average assists per 36 minutes
LEAGUE_AVG_3PA_PER_GAME = 35.0  # League-average team 3PA per game (2024-25)
LEAGUE_AVG_AST_PER_GAME = 26.0  # League-average team assists per game
LEAGUE_AVG_PACE = 100.0  # Possessions per 48 minutes baseline

# ── Odds API full team name → BBRef abbreviation ────────────────────────────

_ODDS_API_TO_BBREF = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BRK",
    "Charlotte Hornets": "CHO",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHO",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

# Stat type constants
STAT_FG3M = "fg3m"
STAT_ASSISTS = "assists"
STAT_POINTS = "points"
STAT_REBOUNDS = "rebounds"
STAT_STEALS = "steals"
STAT_BLOCKS = "blocks"
STAT_TURNOVERS = "turnovers"
STAT_FTM = "ftm"
STAT_FGM = "fgm"
SUPPORTED_STATS = (STAT_FG3M, STAT_ASSISTS)

# All stat types including fantasy-only (no odds required)
ALL_FANTASY_STATS = (
    STAT_FG3M, STAT_ASSISTS, STAT_POINTS, STAT_REBOUNDS,
    STAT_STEALS, STAT_BLOCKS, STAT_TURNOVERS, STAT_FTM, STAT_FGM,
)

# BBRef field name for each stat type
BBREF_STAT_FIELD_ALL = {
    STAT_FG3M: "fg3",
    STAT_ASSISTS: "ast",
    STAT_POINTS: "pts",
    STAT_REBOUNDS: "reb",
    STAT_STEALS: "stl",
    STAT_BLOCKS: "blk",
    STAT_TURNOVERS: "tov",
    STAT_FTM: "ft",
    STAT_FGM: "fg",
}

# League averages per 36 for each stat (2024-25 reference)
LEAGUE_AVG_PER_36 = {
    STAT_FG3M: 2.8,
    STAT_ASSISTS: 4.5,
    STAT_POINTS: 19.0,
    STAT_REBOUNDS: 7.5,
    STAT_STEALS: 1.2,
    STAT_BLOCKS: 0.8,
    STAT_TURNOVERS: 2.2,
    STAT_FTM: 3.0,
    STAT_FGM: 7.0,
}

# League averages per game for opponent allowed
LEAGUE_AVG_OPP_ALLOWED = {
    STAT_POINTS: 112.0,
    STAT_REBOUNDS: 43.0,
    STAT_STEALS: 8.0,
    STAT_BLOCKS: 5.0,
    STAT_TURNOVERS: 14.0,
    STAT_ASSISTS: 26.0,
    STAT_FGM: 41.0,
    STAT_FTM: 18.0,
}

# Mapping from stat type to SGO odds key prefix and market name suffix
SGO_STAT_CONFIG = {
    STAT_FG3M: {
        "key_prefix": "threePointersMade-",
        "key_suffix": "-game-ou-over",
        "market_name_strip": " Three Pointers Made Over/Under",
    },
    STAT_ASSISTS: {
        "key_prefix": "assists-",
        "key_suffix": "-game-ou-over",
        "market_name_strip": " Assists Over/Under",
    },
}

# Mapping from stat type to The Odds API market key
ODDS_API_MARKET_MAP = {
    STAT_FG3M: "player_threes",
    STAT_ASSISTS: "player_assists",
    STAT_POINTS: "player_points",
    STAT_REBOUNDS: "player_rebounds",
    STAT_STEALS: "player_steals",
    STAT_BLOCKS: "player_blocks",
    STAT_TURNOVERS: "player_turnovers",
}

# Mapping from stat type to BBRef game log field
BBREF_STAT_FIELD = {
    STAT_FG3M: "fg3",
    STAT_ASSISTS: "ast",
}


# ── Data classes ─────────────────────────────────────────────────────────────


@dataclass
class PropRecord:
    """A single over/under prop with actual result — all fields real."""

    source: str  # "sgo", "odds_api"
    event_id: str
    game_date: str
    player_name: str
    team: str
    opp: str
    home: bool
    line: float
    odds_over: int  # American
    odds_under: int
    closing_odds_over: int
    closing_odds_under: int
    actual_stat: int  # -1 if game hasn't happened
    stat_type: str = STAT_FG3M  # "fg3m" or "assists"
    books: dict = field(default_factory=dict)
    spread: float = 0.0
    total: float = 0.0
    _home_abbr: str = ""  # BBRef abbr of home team for this game
    _away_abbr: str = ""  # BBRef abbr of away team for this game

    @property
    def actual_3pm(self) -> int:
        """Backward compatibility alias."""
        return self.actual_stat


# ── Odds math ────────────────────────────────────────────────────────────────


def american_to_implied(odds: int) -> float:
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def american_to_decimal(odds: int) -> float:
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def remove_vig(odds_over: int, odds_under: int) -> tuple[float, float]:
    p_over = american_to_implied(odds_over)
    p_under = american_to_implied(odds_under)
    total = p_over + p_under
    return p_over / total, p_under / total


# ── SportsGameOdds fetcher ───────────────────────────────────────────────────


def _sgo_get(url: str, api_key: str, params: dict, max_retries: int = 4) -> dict:
    for attempt in range(max_retries):
        resp = requests.get(
            url, headers={"x-api-key": api_key}, params=params, timeout=30,
        )
        if resp.status_code == 429:
            wait = 2 ** (attempt + 1)
            logger.warning("SGO rate limited, waiting %ds...", wait)
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError("SGO API rate limit exceeded after retries")


def fetch_sgo_events(
    start_date: str, end_date: str, api_key: str = SGO_API_KEY,
) -> list[dict]:
    """Fetch NBA events with real odds from SportsGameOdds (cached)."""
    cache_path = Path(f"/tmp/sgo_events_{start_date}_{end_date}.json")
    if cache_path.exists():
        logger.info("Loading cached SGO events from %s", cache_path)
        with open(cache_path) as f:
            return json.load(f)

    all_events = []
    from datetime import date as dt_date

    s = dt_date.fromisoformat(start_date)
    e = dt_date.fromisoformat(end_date)
    chunk = s
    while chunk < e:
        chunk_end = min(chunk + timedelta(days=7), e)
        cursor = None
        while True:
            params: dict[str, Any] = {
                "leagueID": "NBA", "limit": 50,
                "startsAfter": f"{chunk.isoformat()}T00:00:00Z",
                "startsBefore": f"{chunk_end.isoformat()}T23:59:59Z",
            }
            if cursor:
                params["cursor"] = cursor
            data = _sgo_get(f"{SGO_BASE}/events", api_key, params)
            events = data.get("data", [])
            all_events.extend(events)
            cursor = data.get("nextCursor")
            if not cursor or not events:
                break
            time.sleep(1.0)
        logger.info("  %s→%s: %d events", chunk, chunk_end, len(all_events))
        chunk = chunk_end
        time.sleep(1.5)

    logger.info("Fetched %d SGO events", len(all_events))
    with open(cache_path, "w") as f:
        json.dump(all_events, f)
    return all_events


def extract_sgo_props(
    events: list[dict],
    stat_types: tuple[str, ...] = (STAT_FG3M,),
) -> list[PropRecord]:
    """Extract real props from SGO event data for specified stat types."""
    props = []
    for ev in events:
        odds = ev.get("odds", {})
        start_time = ev.get("startTimestamp", "")
        game_date = start_time[:10] if start_time else ""

        # Spread
        spread = 0.0
        sp_key = "points-home-game-sp-home"
        if sp_key in odds:
            try:
                spread = float(odds[sp_key].get("bookOverUnder", "0") or "0")
            except (ValueError, TypeError):
                pass

        for stat_type in stat_types:
            cfg = SGO_STAT_CONFIG.get(stat_type)
            if not cfg:
                continue

            for key in odds:
                if not (key.startswith(cfg["key_prefix"]) and key.endswith(cfg["key_suffix"])):
                    continue
                under_key = key.replace("-ou-over", "-ou-under")
                if under_key not in odds:
                    continue

                over_odd = odds[key]
                under_odd = odds[under_key]
                score = over_odd.get("score")
                if score is None:
                    continue

                player_name = over_odd.get("marketName", "").replace(
                    cfg["market_name_strip"], ""
                )
                try:
                    line = float(over_odd.get("bookOverUnder", "0") or "0")
                    odds_over = int(over_odd.get("bookOdds", "+100"))
                    odds_under = int(under_odd.get("bookOdds", "+100"))
                    close_over = int(over_odd.get("closeBookOdds", str(odds_over)))
                    close_under = int(under_odd.get("closeBookOdds", str(odds_under)))
                except (ValueError, TypeError):
                    continue

                books = {}
                for bk_name, bk_data in over_odd.get("byBookmaker", {}).items():
                    try:
                        books[bk_name] = {
                            "odds": int(bk_data.get("odds", "+100")),
                            "line": float(bk_data.get("overUnder", str(line))),
                        }
                    except (ValueError, TypeError):
                        pass

                props.append(PropRecord(
                    source="sgo",
                    event_id=ev["eventID"],
                    game_date=game_date,
                    player_name=player_name,
                    team="", opp="", home=False,
                    line=line,
                    odds_over=odds_over, odds_under=odds_under,
                    closing_odds_over=close_over, closing_odds_under=close_under,
                    actual_stat=int(score),
                    stat_type=stat_type,
                    books=books, spread=spread,
                ))

    for st in stat_types:
        count = sum(1 for p in props if p.stat_type == st)
        logger.info("Extracted %d real %s props from SGO", count, st)
    return props


# ── The Odds API fetcher ─────────────────────────────────────────────────────


def _fetch_game_spread_total(
    event_id: str, api_key: str,
) -> tuple[float, float]:
    """Fetch spread (home) and total for a single game from Odds API."""
    try:
        resp = requests.get(
            f"{ODDS_API_BASE}/sports/basketball_nba/events/{event_id}/odds",
            params={
                "apiKey": api_key, "regions": "us",
                "markets": "spreads,totals", "oddsFormat": "american",
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return 0.0, 0.0
        data = resp.json()
        spread, total = 0.0, 0.0
        for bk in data.get("bookmakers", [])[:1]:  # first book only
            for mkt in bk.get("markets", []):
                if mkt["key"] == "spreads":
                    for o in mkt["outcomes"]:
                        if o["name"] == data.get("home_team", ""):
                            spread = float(o.get("point", 0))
                            break
                elif mkt["key"] == "totals":
                    for o in mkt["outcomes"]:
                        if o["name"] == "Over":
                            total = float(o.get("point", 0))
                            break
        return spread, total
    except Exception:
        return 0.0, 0.0


def fetch_odds_api_live_props(
    api_key: str = ODDS_API_KEY,
    stat_types: tuple[str, ...] = (STAT_FG3M,),
) -> list[PropRecord]:
    """Fetch live props for upcoming games from The Odds API."""
    resp = requests.get(
        f"{ODDS_API_BASE}/sports/basketball_nba/events",
        params={"apiKey": api_key}, timeout=15,
    )
    resp.raise_for_status()
    events = resp.json()
    remaining = resp.headers.get("x-requests-remaining", "?")
    logger.info("Odds API: %d upcoming events (%s requests remaining)", len(events), remaining)

    # Build comma-separated markets string for all requested stat types
    markets = ",".join(
        ODDS_API_MARKET_MAP[st] for st in stat_types if st in ODDS_API_MARKET_MAP
    )
    if not markets:
        return []

    props = []
    for ev in events:
        eid = ev["id"]
        home_full = ev["home_team"]
        away_full = ev["away_team"]
        home_abbr = _ODDS_API_TO_BBREF.get(home_full, "")
        away_abbr = _ODDS_API_TO_BBREF.get(away_full, "")
        game_time = ev.get("commence_time", "")[:10]

        # Fetch spread and total for game context
        spread, total = _fetch_game_spread_total(eid, api_key)

        resp2 = requests.get(
            f"{ODDS_API_BASE}/sports/basketball_nba/events/{eid}/odds",
            params={
                "apiKey": api_key, "regions": "us",
                "markets": markets, "oddsFormat": "american",
            },
            timeout=15,
        )
        if resp2.status_code != 200:
            continue

        ev_data = resp2.json()

        # Aggregate across books — group by (market_key, player, line)
        player_lines: dict[tuple[str, str, float], dict] = {}
        for bk in ev_data.get("bookmakers", []):
            bk_key = bk["key"]
            for mkt in bk.get("markets", []):
                market_key = mkt.get("key", "")
                for outcome in mkt.get("outcomes", []):
                    player = outcome.get("description", "")
                    side = outcome.get("name", "").lower()
                    line = float(outcome.get("point", 0))
                    price = int(outcome.get("price", 100))

                    key = (market_key, player, line)
                    if key not in player_lines:
                        player_lines[key] = {
                            "market_key": market_key,
                            "player": player, "line": line,
                            "odds_over": 0, "odds_under": 0,
                            "books": {},
                        }

                    if side == "over":
                        player_lines[key]["odds_over"] = price
                        player_lines[key]["books"].setdefault(bk_key, {})["over"] = price
                    elif side == "under":
                        player_lines[key]["odds_under"] = price
                        player_lines[key]["books"].setdefault(bk_key, {})["under"] = price

        # Reverse lookup: Odds API market key -> stat type
        market_to_stat = {v: k for k, v in ODDS_API_MARKET_MAP.items()}

        for (market_key, player, line), data in player_lines.items():
            if data["odds_over"] and data["odds_under"]:
                stat_type = market_to_stat.get(market_key, STAT_FG3M)
                props.append(PropRecord(
                    source="odds_api",
                    event_id=eid,
                    game_date=game_time,
                    player_name=player,
                    team="", opp="",
                    home=False,
                    line=line,
                    odds_over=data["odds_over"],
                    odds_under=data["odds_under"],
                    closing_odds_over=data["odds_over"],  # live = current
                    closing_odds_under=data["odds_under"],
                    actual_stat=-1,  # game hasn't happened
                    stat_type=stat_type,
                    books=data["books"],
                    spread=spread,
                    total=total,
                    _home_abbr=home_abbr,
                    _away_abbr=away_abbr,
                ))

    for st in stat_types:
        count = sum(1 for p in props if p.stat_type == st)
        logger.info("Fetched %d live %s props from Odds API", count, st)
    return props


# ── BBRef game log scraper ───────────────────────────────────────────────────


def load_bbref_game_logs(cache_path: str = str(_CACHE_DIR / "nba_game_logs.json")) -> dict[str, list[dict]]:
    """Load real BBRef game logs from cache."""
    p = Path(cache_path)
    if not p.exists():
        logger.error("No BBRef cache at %s — run scraper first", cache_path)
        return {}
    with open(p) as f:
        raw = json.load(f)
    logs = {name: data["games"] for name, data in raw.items()}
    total = sum(len(v) for v in logs.values())
    logger.info("Loaded %d players, %d real game logs from BBRef", len(logs), total)
    return logs


def scrape_bbref_game_logs(
    player_slugs: dict[str, str], season: int = 2025,
) -> dict[str, list[dict]]:
    """Scrape real game logs from basketball-reference.com."""
    from bs4 import BeautifulSoup

    all_logs = {}
    for name, slug in player_slugs.items():
        url = f"https://www.basketball-reference.com/players/{slug}/gamelog/{season}"
        logger.info("Scraping %s...", name)
        time.sleep(3.5)
        resp = requests.get(url, headers=BBREF_HEADERS, timeout=30)
        if resp.status_code != 200:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", {"id": "player_game_log_reg"})
        if not table:
            continue

        games = []
        for row in table.find("tbody").find_all("tr"):
            if row.get("class") and "thead" in row.get("class", []):
                continue
            tds = row.find_all("td")
            th = row.find("th")
            if not tds:
                continue
            data = {}
            if th:
                data[th.get("data-stat")] = th.text
            for td in tds:
                data[td.get("data-stat")] = td.text

            mp_str = data.get("mp", "")
            if not mp_str:
                continue
            try:
                if ":" in mp_str:
                    parts = mp_str.split(":")
                    mp = float(parts[0]) + float(parts[1]) / 60
                else:
                    mp = float(mp_str)
                games.append({
                    "date": data.get("date", ""),
                    "team": data.get("team_name_abbr", ""),
                    "opp": data.get("opp_name_abbr", ""),
                    "home": data.get("game_location", "@") != "@",
                    "starter": data.get("is_starter", "") == "*",
                    "mp": mp,
                    "fg": int(data.get("fg", "0") or "0"),
                    "fga": int(data.get("fga", "0") or "0"),
                    "fg3": int(data.get("fg3", "0") or "0"),
                    "fg3a": int(data.get("fg3a", "0") or "0"),
                    "ft": int(data.get("ft", "0") or "0"),
                    "fta": int(data.get("fta", "0") or "0"),
                    "orb": int(data.get("orb", "0") or "0"),
                    "drb": int(data.get("drb", "0") or "0"),
                    "reb": int(data.get("trb", "0") or "0"),
                    "ast": int(data.get("ast", "0") or "0"),
                    "stl": int(data.get("stl", "0") or "0"),
                    "blk": int(data.get("blk", "0") or "0"),
                    "tov": int(data.get("tov", "0") or "0"),
                    "pf": int(data.get("pf", "0") or "0"),
                    "pts": int(data.get("pts", "0") or "0"),
                    "plus_minus": float(data.get("plus_minus", "0") or "0"),
                    "result": data.get("game_result", ""),
                })
            except (ValueError, TypeError):
                continue

        all_logs[name] = games
        logger.info("  %s: %d games", name, len(games))

    return all_logs


# ── Opponent defensive context from NBA.com stats API ────────────────────────

# NBA API team ID → BBRef abbreviation (handles mismatches)
_NBA_ID_TO_BBREF = {
    1610612737: "ATL", 1610612738: "BOS", 1610612751: "BRK",
    1610612766: "CHO", 1610612741: "CHI", 1610612739: "CLE",
    1610612742: "DAL", 1610612743: "DEN", 1610612765: "DET",
    1610612744: "GSW", 1610612745: "HOU", 1610612754: "IND",
    1610612746: "LAC", 1610612747: "LAL", 1610612763: "MEM",
    1610612748: "MIA", 1610612749: "MIL", 1610612750: "MIN",
    1610612740: "NOP", 1610612752: "NYK", 1610612760: "OKC",
    1610612753: "ORL", 1610612755: "PHI", 1610612756: "PHO",
    1610612757: "POR", 1610612758: "SAC", 1610612759: "SAS",
    1610612761: "TOR", 1610612762: "UTA", 1610612764: "WAS",
}


def fetch_nba_opponent_shooting(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch opponent shooting by zone from NBA.com stats API.

    Uses the LeagueDashTeamShotLocations endpoint with MeasureType=Opponent
    and DistanceRange=By Zone to get real opponent 3PA/3PM by zone
    (Left Corner 3, Right Corner 3, Above the Break 3).

    Returns dict keyed by BBRef team abbr:
        {
            "BOS": {
                "opp_3pa_per_game": 38.8,
                "opp_3pm_per_game": 14.0,
                "opp_fg3_pct_allowed": 0.361,
                "opp_corner3_fga": 8.5,
                "opp_corner3_pct": 0.375,
                "opp_atb3_fga": 30.3,
                "opp_atb3_pct": 0.357,
            },
            ...
        }
    """
    cache_path = _CACHE_DIR / f"nba_opp_shooting_{season}.json"

    # Use cached data if fresh enough
    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached NBA opponent shooting (%d teams, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import leaguedashteamshotlocations
        import time as _time

        _time.sleep(0.6)  # rate-limit courtesy
        result = leaguedashteamshotlocations.LeagueDashTeamShotLocations(
            measure_type_simple="Opponent",
            distance_range="By Zone",
            per_mode_detailed="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df = result.get_data_frames()[0]
    except Exception as exc:
        logger.warning("NBA API opponent shooting fetch failed: %s", exc)
        # Fall back to cache even if stale
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    opp_data: dict[str, dict] = {}
    for _, row in df.iterrows():
        team_id = int(row[("", "TEAM_ID")])
        bbref = _NBA_ID_TO_BBREF.get(team_id, "")
        if not bbref:
            continue

        lc3_fga = float(row[("Left Corner 3", "OPP_FGA")])
        lc3_fgm = float(row[("Left Corner 3", "OPP_FGM")])
        lc3_pct = float(row[("Left Corner 3", "OPP_FG_PCT")])
        rc3_fga = float(row[("Right Corner 3", "OPP_FGA")])
        rc3_fgm = float(row[("Right Corner 3", "OPP_FGM")])
        rc3_pct = float(row[("Right Corner 3", "OPP_FG_PCT")])
        ab3_fga = float(row[("Above the Break 3", "OPP_FGA")])
        ab3_fgm = float(row[("Above the Break 3", "OPP_FGM")])
        ab3_pct = float(row[("Above the Break 3", "OPP_FG_PCT")])
        c3_fga = float(row[("Corner 3", "OPP_FGA")])
        c3_pct = float(row[("Corner 3", "OPP_FG_PCT")])

        total_3pa = lc3_fga + rc3_fga + ab3_fga
        total_3pm = lc3_fgm + rc3_fgm + ab3_fgm
        total_pct = total_3pm / total_3pa if total_3pa > 0 else 0.0

        opp_data[bbref] = {
            "opp_3pa_per_game": round(total_3pa, 1),
            "opp_3pm_per_game": round(total_3pm, 1),
            "opp_fg3_pct_allowed": round(total_pct, 4),
            "opp_corner3_fga": round(c3_fga, 1),
            "opp_corner3_pct": round(c3_pct, 4),
            "opp_atb3_fga": round(ab3_fga, 1),
            "opp_atb3_pct": round(ab3_pct, 4),
        }

    # Cache the result
    with open(cache_path, "w") as f:
        json.dump(opp_data, f, indent=2)
    logger.info("Fetched NBA opponent shooting for %d teams from NBA.com", len(opp_data))

    return opp_data


def fetch_nba_opponent_general(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch general opponent stats (assists, pace) from NBA.com stats API.

    Returns dict keyed by BBRef team abbr with opp_ast_per_game and pace.
    """
    cache_path = _CACHE_DIR / f"nba_opp_general_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                return json.load(f)

    try:
        from nba_api.stats.endpoints import leaguedashteamstats
        import time as _time

        _time.sleep(0.6)
        # Opponent stats
        result = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense="Opponent",
            per_mode_detailed="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df = result.get_data_frames()[0]
    except Exception as exc:
        logger.warning("NBA API opponent general fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    opp_data: dict[str, dict] = {}
    for _, row in df.iterrows():
        team_id = int(row["TEAM_ID"])
        bbref = _NBA_ID_TO_BBREF.get(team_id, "")
        if not bbref:
            continue
        opp_data[bbref] = {
            # Core per-game stats allowed
            "opp_pts_per_game": round(float(row.get("OPP_PTS", 0)), 1),
            "opp_reb_per_game": round(float(row.get("OPP_REB", 0)), 1),
            "opp_oreb_per_game": round(float(row.get("OPP_OREB", 0)), 1),
            "opp_dreb_per_game": round(float(row.get("OPP_DREB", 0)), 1),
            "opp_ast_per_game": round(float(row.get("OPP_AST", 0)), 1),
            "opp_stl_per_game": round(float(row.get("OPP_STL", 0)), 1),
            "opp_blk_per_game": round(float(row.get("OPP_BLK", 0)), 1),
            "opp_tov_per_game": round(float(row.get("OPP_TOV", 0)), 1),
            "opp_pf_per_game": round(float(row.get("OPP_PF", 0)), 1),
            # Shooting allowed
            "opp_fgm_per_game": round(float(row.get("OPP_FGM", 0)), 1),
            "opp_fga_per_game": round(float(row.get("OPP_FGA", 0)), 1),
            "opp_fg_pct": round(float(row.get("OPP_FG_PCT", 0)), 4),
            "opp_fg3m_per_game": round(float(row.get("OPP_FG3M", 0)), 1),
            "opp_fg3a_per_game": round(float(row.get("OPP_FG3A", 0)), 1),
            "opp_fg3_pct": round(float(row.get("OPP_FG3_PCT", 0)), 4),
            "opp_ftm_per_game": round(float(row.get("OPP_FTM", 0)), 1),
            "opp_fta_per_game": round(float(row.get("OPP_FTA", 0)), 1),
            "opp_ft_pct": round(float(row.get("OPP_FT_PCT", 0)), 4),
            # Pace
            "pace": round(float(row.get("OPP_PACE", 0) if "OPP_PACE" in row else 0), 1),
        }

    with open(cache_path, "w") as f:
        json.dump(opp_data, f, indent=2)
    logger.info("Fetched NBA opponent general stats for %d teams", len(opp_data))
    return opp_data


def fetch_nba_team_advanced(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch team advanced stats (pace, def rating) from NBA.com."""
    cache_path = _CACHE_DIR / f"nba_team_advanced_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                return json.load(f)

    try:
        from nba_api.stats.endpoints import leaguedashteamstats
        import time as _time

        _time.sleep(0.6)
        result = leaguedashteamstats.LeagueDashTeamStats(
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df = result.get_data_frames()[0]
    except Exception as exc:
        logger.warning("NBA API team advanced fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    data: dict[str, dict] = {}
    for _, row in df.iterrows():
        team_id = int(row["TEAM_ID"])
        bbref = _NBA_ID_TO_BBREF.get(team_id, "")
        if not bbref:
            continue
        data[bbref] = {
            "pace": round(float(row.get("PACE", 100)), 2),
            "def_rating": round(float(row.get("DEF_RATING", 110)), 1),
            "off_rating": round(float(row.get("OFF_RATING", 110)), 1),
            "net_rating": round(float(row.get("NET_RATING", 0)), 1),
        }

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched NBA team advanced stats for %d teams", len(data))
    return data


def fetch_nba_opp_tracking_shooting(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch opponent tracking shot data by defender distance from NBA.com.

    Returns per-team dict with wide-open (6+ft), open (4-6ft), tight (2-4ft),
    and catch-and-shoot 3PA/3PM allowed per game.
    """
    cache_path = _CACHE_DIR / f"nba_opp_tracking_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached NBA opponent tracking (%d teams, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import leaguedashoppptshot
        import time as _time

        data: dict[str, dict] = {}

        # Wide open (6+ feet)
        _time.sleep(0.6)
        r1 = leaguedashoppptshot.LeagueDashOppPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            close_def_dist_range_nullable="6+ Feet - Wide Open",
        )
        df1 = r1.get_data_frames()[0]
        for _, row in df1.iterrows():
            team_id = int(row["TEAM_ID"])
            bbref = _NBA_ID_TO_BBREF.get(team_id, "")
            if not bbref:
                continue
            data.setdefault(bbref, {})
            data[bbref]["opp_wide_open_3pa"] = round(float(row["FG3A"]), 2)
            data[bbref]["opp_wide_open_3pm"] = round(float(row["FG3M"]), 2)
            data[bbref]["opp_wide_open_3pct"] = round(float(row["FG3_PCT"]), 4)

        # Open (4-6 feet)
        _time.sleep(0.6)
        r2 = leaguedashoppptshot.LeagueDashOppPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            close_def_dist_range_nullable="4-6 Feet - Open",
        )
        df2 = r2.get_data_frames()[0]
        for _, row in df2.iterrows():
            team_id = int(row["TEAM_ID"])
            bbref = _NBA_ID_TO_BBREF.get(team_id, "")
            if not bbref:
                continue
            data.setdefault(bbref, {})
            data[bbref]["opp_open_3pa"] = round(float(row["FG3A"]), 2)
            data[bbref]["opp_open_3pm"] = round(float(row["FG3M"]), 2)
            data[bbref]["opp_open_3pct"] = round(float(row["FG3_PCT"]), 4)

        # Tight (2-4 feet)
        _time.sleep(0.6)
        r3 = leaguedashoppptshot.LeagueDashOppPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            close_def_dist_range_nullable="2-4 Feet - Tight",
        )
        df3 = r3.get_data_frames()[0]
        for _, row in df3.iterrows():
            team_id = int(row["TEAM_ID"])
            bbref = _NBA_ID_TO_BBREF.get(team_id, "")
            if not bbref:
                continue
            data.setdefault(bbref, {})
            data[bbref]["opp_tight_3pa"] = round(float(row["FG3A"]), 2)
            data[bbref]["opp_tight_3pm"] = round(float(row["FG3M"]), 2)
            data[bbref]["opp_tight_3pct"] = round(float(row["FG3_PCT"]), 4)

        # Catch-and-shoot (0 dribbles)
        _time.sleep(0.6)
        r4 = leaguedashoppptshot.LeagueDashOppPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            dribble_range_nullable="0 Dribbles",
        )
        df4 = r4.get_data_frames()[0]
        for _, row in df4.iterrows():
            team_id = int(row["TEAM_ID"])
            bbref = _NBA_ID_TO_BBREF.get(team_id, "")
            if not bbref:
                continue
            data.setdefault(bbref, {})
            data[bbref]["opp_catch_shoot_3pa"] = round(float(row["FG3A"]), 2)
            data[bbref]["opp_catch_shoot_3pm"] = round(float(row["FG3M"]), 2)
            data[bbref]["opp_catch_shoot_3pct"] = round(float(row["FG3_PCT"]), 4)

        # Pull-up (3-6 dribbles)
        _time.sleep(0.6)
        r5 = leaguedashoppptshot.LeagueDashOppPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            dribble_range_nullable="3-6 Dribbles",
        )
        df5 = r5.get_data_frames()[0]
        for _, row in df5.iterrows():
            team_id = int(row["TEAM_ID"])
            bbref = _NBA_ID_TO_BBREF.get(team_id, "")
            if not bbref:
                continue
            data.setdefault(bbref, {})
            data[bbref]["opp_pullup_3pa"] = round(float(row["FG3A"]), 2)
            data[bbref]["opp_pullup_3pm"] = round(float(row["FG3M"]), 2)
            data[bbref]["opp_pullup_3pct"] = round(float(row["FG3_PCT"]), 4)

    except Exception as exc:
        logger.warning("NBA API opponent tracking fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched NBA opponent tracking for %d teams", len(data))
    return data


def fetch_nba_synergy_defense(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch team defensive synergy play type data from NBA.com.

    Returns how each team defends specific play types: spot-up, isolation,
    P&R ball handler, off-screen, transition, handoff — with PPP, FG%,
    EFG%, possessions, and percentile.
    """
    cache_path = _CACHE_DIR / f"nba_synergy_defense_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached synergy defense (%d teams, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import synergyplaytypes
        import time as _time

        data: dict[str, dict] = {}
        play_types = [
            "Spotup", "Isolation", "PRBallHandler", "PRRollman",
            "OffScreen", "Transition", "Handoff", "Cut",
        ]

        for pt in play_types:
            _time.sleep(0.6)
            r = synergyplaytypes.SynergyPlayTypes(
                per_mode_simple="PerGame",
                play_type_nullable=pt,
                type_grouping_nullable="defensive",
                season=season,
                season_type_all_star="Regular Season",
                player_or_team_abbreviation="T",
            )
            df = r.get_data_frames()[0]
            pt_key = pt.lower()

            for _, row in df.iterrows():
                team_id = int(row["TEAM_ID"])
                bbref = _NBA_ID_TO_BBREF.get(team_id, "")
                if not bbref:
                    continue
                data.setdefault(bbref, {})
                data[bbref][f"def_{pt_key}_ppp"] = round(float(row.get("PPP", 0)), 3)
                data[bbref][f"def_{pt_key}_fg_pct"] = round(float(row.get("FG_PCT", 0)), 4)
                data[bbref][f"def_{pt_key}_efg"] = round(float(row.get("EFG_PCT", 0)), 4)
                data[bbref][f"def_{pt_key}_poss"] = round(float(row.get("POSS", 0)), 1)
                data[bbref][f"def_{pt_key}_percentile"] = round(float(row.get("PERCENTILE", 0)), 3)
                data[bbref][f"def_{pt_key}_freq"] = round(float(row.get("POSS_PCT", 0)), 4)
                data[bbref][f"def_{pt_key}_tov_pct"] = round(float(row.get("TOV_POSS_PCT", 0)), 4)

    except Exception as exc:
        logger.warning("NBA API synergy defense fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched synergy defense for %d teams", len(data))
    return data


def fetch_nba_synergy_player(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch player offensive synergy play type data from NBA.com.

    Returns how each player generates offense by play type: spot-up,
    isolation, P&R ball handler, off-screen, transition — with PPP, FG%,
    possessions share, and efficiency.
    """
    cache_path = _CACHE_DIR / f"nba_synergy_player_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached synergy player (%d players, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import synergyplaytypes
        import time as _time

        data: dict[str, dict] = {}
        play_types = [
            "Spotup", "Isolation", "PRBallHandler", "PRRollman",
            "OffScreen", "Transition", "Handoff", "Cut",
        ]

        for pt in play_types:
            _time.sleep(0.6)
            r = synergyplaytypes.SynergyPlayTypes(
                per_mode_simple="PerGame",
                play_type_nullable=pt,
                type_grouping_nullable="offensive",
                season=season,
                season_type_all_star="Regular Season",
                player_or_team_abbreviation="P",
            )
            df = r.get_data_frames()[0]
            pt_key = pt.lower()

            for _, row in df.iterrows():
                name = str(row.get("PLAYER_NAME", ""))
                key = name.lower()
                if not key:
                    continue
                data.setdefault(key, {"name": name})
                data[key][f"off_{pt_key}_ppp"] = round(float(row.get("PPP", 0)), 3)
                data[key][f"off_{pt_key}_fg_pct"] = round(float(row.get("FG_PCT", 0)), 4)
                data[key][f"off_{pt_key}_efg"] = round(float(row.get("EFG_PCT", 0)), 4)
                data[key][f"off_{pt_key}_poss"] = round(float(row.get("POSS", 0)), 1)
                data[key][f"off_{pt_key}_freq"] = round(float(row.get("POSS_PCT", 0)), 4)
                data[key][f"off_{pt_key}_score_pct"] = round(float(row.get("SCORE_POSS_PCT", 0)), 4)

    except Exception as exc:
        logger.warning("NBA API synergy player fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched synergy player data for %d players", len(data))
    return data


def fetch_nba_team_hustle(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch team hustle stats (contested shots, deflections, etc.)."""
    cache_path = _CACHE_DIR / f"nba_team_hustle_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                return json.load(f)

    try:
        from nba_api.stats.endpoints import leaguehustlestatsteam
        import time as _time

        _time.sleep(0.6)
        r = leaguehustlestatsteam.LeagueHustleStatsTeam(
            per_mode_time="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df = r.get_data_frames()[0]
    except Exception as exc:
        logger.warning("NBA API team hustle fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    data: dict[str, dict] = {}
    for _, row in df.iterrows():
        team_id = int(row["TEAM_ID"])
        bbref = _NBA_ID_TO_BBREF.get(team_id, "")
        if not bbref:
            continue
        data[bbref] = {
            "contested_shots": round(float(row.get("CONTESTED_SHOTS", 0)), 1),
            "contested_shots_3pt": round(float(row.get("CONTESTED_SHOTS_3PT", 0)), 1),
            "contested_shots_2pt": round(float(row.get("CONTESTED_SHOTS_2PT", 0)), 1),
            "deflections": round(float(row.get("DEFLECTIONS", 0)), 1),
            "charges_drawn": round(float(row.get("CHARGES_DRAWN", 0)), 2),
            "loose_balls_recovered": round(float(row.get("LOOSE_BALLS_RECOVERED", 0)), 1),
            "screen_assists": round(float(row.get("SCREEN_ASSISTS", 0)), 1),
            "screen_ast_pts": round(float(row.get("SCREEN_AST_PTS", 0)), 1),
        }

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched team hustle stats for %d teams", len(data))
    return data


def fetch_nba_opp_shot_clock(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch opponent shooting by shot clock range from NBA.com.

    Returns how many 3PA and at what FG3% each team allows by shot clock:
    early (22-18), normal (18-15, 15-7), and late (7-4, 4-0).
    """
    cache_path = _CACHE_DIR / f"nba_opp_shot_clock_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached opp shot clock (%d teams, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import leaguedashoppptshot
        import time as _time

        data: dict[str, dict] = {}
        sc_ranges = {
            "early": "22-18 Very Early",
            "normal_early": "18-15 Early",
            "normal": "15-7 Average",
            "late": "4-0 Very Late",
        }

        for key, sc_range in sc_ranges.items():
            _time.sleep(0.6)
            r = leaguedashoppptshot.LeagueDashOppPtShot(
                per_mode_simple="PerGame", season=season,
                season_type_all_star="Regular Season",
                shot_clock_range_nullable=sc_range,
            )
            df = r.get_data_frames()[0]
            for _, row in df.iterrows():
                team_id = int(row["TEAM_ID"])
                bbref = _NBA_ID_TO_BBREF.get(team_id, "")
                if not bbref:
                    continue
                data.setdefault(bbref, {})
                data[bbref][f"sc_{key}_3pa"] = round(float(row["FG3A"]), 2)
                data[bbref][f"sc_{key}_3pm"] = round(float(row["FG3M"]), 2)
                fg3_pct = row["FG3_PCT"]
                data[bbref][f"sc_{key}_3pct"] = round(
                    float(fg3_pct if fg3_pct and fg3_pct == fg3_pct else 0), 4
                )

    except Exception as exc:
        logger.warning("NBA API opp shot clock fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched opp shot clock data for %d teams", len(data))
    return data


def fetch_nba_player_shot_clock(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch player shooting by shot clock range from NBA.com.

    Returns per-player 3PA and FG3% broken down by shot clock:
    early (22-18), normal (15-7), late (4-0).
    """
    cache_path = _CACHE_DIR / f"nba_player_shot_clock_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached player shot clock (%d players, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import leaguedashplayerptshot
        import time as _time

        data: dict[str, dict] = {}
        sc_ranges = {
            "early": "22-18 Very Early",
            "normal": "15-7 Average",
            "late": "4-0 Very Late",
        }

        for key, sc_range in sc_ranges.items():
            _time.sleep(0.6)
            r = leaguedashplayerptshot.LeagueDashPlayerPtShot(
                per_mode_simple="PerGame", season=season,
                season_type_all_star="Regular Season",
                shot_clock_range_nullable=sc_range,
            )
            df = r.get_data_frames()[0]
            for _, row in df.iterrows():
                name = str(row.get("PLAYER_NAME_LAST_FIRST", ""))
                # Convert "Last, First" to "first last"
                parts = name.split(", ")
                if len(parts) == 2:
                    pkey = f"{parts[1]} {parts[0]}".lower()
                else:
                    pkey = name.lower()
                if not pkey:
                    continue
                data.setdefault(pkey, {})
                data[pkey][f"sc_{key}_3pa"] = round(float(row.get("FG3A", 0)), 2)
                data[pkey][f"sc_{key}_3pm"] = round(float(row.get("FG3M", 0)), 2)
                fg3_pct = row.get("FG3_PCT", 0)
                data[pkey][f"sc_{key}_3pct"] = round(
                    float(fg3_pct if fg3_pct and fg3_pct == fg3_pct else 0), 4
                )

    except Exception as exc:
        logger.warning("NBA API player shot clock fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched player shot clock data for %d players", len(data))
    return data


def fetch_nba_player_advanced(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch player advanced stats from NBA.com.

    Returns per-player: NET_RATING, USG_PCT, AST_PCT, OFF_RATING, DEF_RATING,
    TS_PCT, EFG_PCT, PACE, PIE — key context for usage and on-court impact.
    """
    cache_path = _CACHE_DIR / f"nba_player_advanced_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached player advanced (%d players, %.1fh old)",
                len(data), age_hours,
            )
            return data

    try:
        from nba_api.stats.endpoints import leaguedashplayerstats
        import time as _time

        _time.sleep(0.6)
        r = leaguedashplayerstats.LeagueDashPlayerStats(
            measure_type_detailed_defense="Advanced",
            per_mode_detailed="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df = r.get_data_frames()[0]
    except Exception as exc:
        logger.warning("NBA API player advanced fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    data: dict[str, dict] = {}
    for _, row in df.iterrows():
        name = str(row.get("PLAYER_NAME", ""))
        pkey = name.lower()
        if not pkey:
            continue
        data[pkey] = {
            "net_rating": round(float(row.get("NET_RATING", 0)), 1),
            "off_rating": round(float(row.get("OFF_RATING", 0)), 1),
            "def_rating": round(float(row.get("DEF_RATING", 0)), 1),
            "usg_pct": round(float(row.get("USG_PCT", 0)), 3),
            "ast_pct": round(float(row.get("AST_PCT", 0)), 3),
            "ast_ratio": round(float(row.get("AST_RATIO", 0)), 1),
            "ast_to": round(float(row.get("AST_TO", 0)), 2),
            "ts_pct": round(float(row.get("TS_PCT", 0)), 3),
            "efg_pct": round(float(row.get("EFG_PCT", 0)), 3),
            "pace": round(float(row.get("PACE", 0)), 1),
            "pie": round(float(row.get("PIE", 0)), 3),
            "poss": round(float(row.get("POSS", 0)), 0),
        }

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched player advanced stats for %d players", len(data))
    return data


def fetch_nba_player_shooting(
    season: str = "2025-26",
    cache_ttl_hours: int = 12,
) -> dict[str, dict]:
    """Fetch player shooting profiles from NBA.com.

    Returns per-player dict with:
    - Shooting by zone (corner 3, above-the-break 3)
    - Catch-and-shoot vs pull-up splits
    - Wide-open vs contested splits
    """
    cache_path = _CACHE_DIR / f"nba_player_shooting_{season}.json"

    if cache_path.exists():
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
        if age_hours < cache_ttl_hours:
            with open(cache_path) as f:
                data = json.load(f)
            logger.info(
                "Loaded cached NBA player shooting (%d players, %.1fh old)",
                len(data), age_hours,
            )
            return data

    data: dict[str, dict] = {}

    try:
        from nba_api.stats.endpoints import (
            leaguedashplayershotlocations,
            leaguedashplayerptshot,
            leaguedashptstats,
        )
        import time as _time

        # 1. Player shooting by zone
        _time.sleep(0.6)
        r_zone = leaguedashplayershotlocations.LeagueDashPlayerShotLocations(
            measure_type_simple="Base",
            distance_range="By Zone",
            per_mode_detailed="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_zone = r_zone.get_data_frames()[0]

        for _, row in df_zone.iterrows():
            name = str(row[("", "PLAYER_NAME")])
            key = name.lower()

            lc3_fga = float(row[("Left Corner 3", "FGA")])
            lc3_fgm = float(row[("Left Corner 3", "FGM")])
            rc3_fga = float(row[("Right Corner 3", "FGA")])
            rc3_fgm = float(row[("Right Corner 3", "FGM")])
            ab3_fga = float(row[("Above the Break 3", "FGA")])
            ab3_fgm = float(row[("Above the Break 3", "FGM")])
            c3_fga = float(row[("Corner 3", "FGA")])
            c3_fgm = float(row[("Corner 3", "FGM")])

            total_3pa = lc3_fga + rc3_fga + ab3_fga
            total_3pm = lc3_fgm + rc3_fgm + ab3_fgm

            data[key] = {
                "name": name,
                "total_3pa_pg": round(total_3pa, 2),
                "total_3pm_pg": round(total_3pm, 2),
                "total_3pct": round(total_3pm / total_3pa, 4) if total_3pa > 0 else 0.0,
                "corner3_fga": round(c3_fga, 2),
                "corner3_fgm": round(c3_fgm, 2),
                "corner3_pct": round(c3_fgm / c3_fga, 4) if c3_fga > 0 else 0.0,
                "atb3_fga": round(ab3_fga, 2),
                "atb3_fgm": round(ab3_fgm, 2),
                "atb3_pct": round(ab3_fgm / ab3_fga, 4) if ab3_fga > 0 else 0.0,
                # Fraction of 3PA that come from corners vs above-the-break
                "corner3_share": round(c3_fga / total_3pa, 3) if total_3pa > 0 else 0.0,
                "atb3_share": round(ab3_fga / total_3pa, 3) if total_3pa > 0 else 0.0,
            }

        # 2. Catch-and-shoot (0 dribbles)
        _time.sleep(0.6)
        r_cs = leaguedashplayerptshot.LeagueDashPlayerPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            dribble_range_nullable="0 Dribbles",
        )
        df_cs = r_cs.get_data_frames()[0]
        for _, row in df_cs.iterrows():
            key = row["PLAYER_NAME"].lower()
            if key not in data:
                data[key] = {"name": row["PLAYER_NAME"]}
            data[key]["catch_shoot_3pa"] = round(float(row["FG3A"]), 2)
            data[key]["catch_shoot_3pm"] = round(float(row["FG3M"]), 2)
            data[key]["catch_shoot_3pct"] = round(float(row["FG3_PCT"]), 4)

        # 3. Pull-up (1-2 dribbles — common pull-up range)
        _time.sleep(0.6)
        r_pu = leaguedashplayerptshot.LeagueDashPlayerPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            dribble_range_nullable="1 Dribble",
        )
        df_pu = r_pu.get_data_frames()[0]
        for _, row in df_pu.iterrows():
            key = row["PLAYER_NAME"].lower()
            if key not in data:
                data[key] = {"name": row["PLAYER_NAME"]}
            data[key]["pullup_1d_3pa"] = round(float(row["FG3A"]), 2)
            data[key]["pullup_1d_3pm"] = round(float(row["FG3M"]), 2)
            data[key]["pullup_1d_3pct"] = round(float(row["FG3_PCT"]), 4)

        # 4. Self-created (7+ dribbles)
        _time.sleep(0.6)
        r_sc = leaguedashplayerptshot.LeagueDashPlayerPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            dribble_range_nullable="7+ Dribbles",
        )
        df_sc = r_sc.get_data_frames()[0]
        for _, row in df_sc.iterrows():
            key = row["PLAYER_NAME"].lower()
            if key not in data:
                data[key] = {"name": row["PLAYER_NAME"]}
            data[key]["self_created_3pa"] = round(float(row["FG3A"]), 2)
            data[key]["self_created_3pm"] = round(float(row["FG3M"]), 2)
            data[key]["self_created_3pct"] = round(float(row["FG3_PCT"]), 4)

        # 5. Wide open (6+ feet)
        _time.sleep(0.6)
        r_wo = leaguedashplayerptshot.LeagueDashPlayerPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            close_def_dist_range_nullable="6+ Feet - Wide Open",
        )
        df_wo = r_wo.get_data_frames()[0]
        for _, row in df_wo.iterrows():
            key = row["PLAYER_NAME"].lower()
            if key not in data:
                data[key] = {"name": row["PLAYER_NAME"]}
            data[key]["wide_open_3pa"] = round(float(row["FG3A"]), 2)
            data[key]["wide_open_3pm"] = round(float(row["FG3M"]), 2)
            data[key]["wide_open_3pct"] = round(float(row["FG3_PCT"]), 4)

        # 6. Tight (2-4 feet)
        _time.sleep(0.6)
        r_tight = leaguedashplayerptshot.LeagueDashPlayerPtShot(
            per_mode_simple="PerGame", season=season,
            season_type_all_star="Regular Season",
            close_def_dist_range_nullable="2-4 Feet - Tight",
        )
        df_tight = r_tight.get_data_frames()[0]
        for _, row in df_tight.iterrows():
            key = row["PLAYER_NAME"].lower()
            if key not in data:
                data[key] = {"name": row["PLAYER_NAME"]}
            data[key]["tight_3pa"] = round(float(row["FG3A"]), 2)
            data[key]["tight_3pm"] = round(float(row["FG3M"]), 2)
            data[key]["tight_3pct"] = round(float(row["FG3_PCT"]), 4)

        # 7. Catch-and-shoot tracking (dedicated endpoint — more detailed)
        _time.sleep(0.6)
        r_cs2 = leaguedashptstats.LeagueDashPtStats(
            player_or_team="Player",
            pt_measure_type="CatchShoot",
            per_mode_simple="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_cs2 = r_cs2.get_data_frames()[0]
        for _, row in df_cs2.iterrows():
            key = row["PLAYER_NAME"].lower()
            data.setdefault(key, {"name": row["PLAYER_NAME"]})
            data[key]["cs_fgm"] = round(float(row.get("CATCH_SHOOT_FGM", 0)), 2)
            data[key]["cs_fga"] = round(float(row.get("CATCH_SHOOT_FGA", 0)), 2)
            cs_pct = row.get("CATCH_SHOOT_FG_PCT", 0)
            data[key]["cs_fg_pct"] = round(float(cs_pct if cs_pct and cs_pct == cs_pct else 0), 4)
            data[key]["cs_fg3m"] = round(float(row.get("CATCH_SHOOT_FG3M", 0)), 2)
            data[key]["cs_fg3a"] = round(float(row.get("CATCH_SHOOT_FG3A", 0)), 2)
            cs3_pct = row.get("CATCH_SHOOT_FG3_PCT", 0)
            data[key]["cs_fg3_pct"] = round(float(cs3_pct if cs3_pct and cs3_pct == cs3_pct else 0), 4)
            data[key]["cs_pts"] = round(float(row.get("CATCH_SHOOT_PTS", 0)), 2)

        # 8. Pull-up shooting tracking
        _time.sleep(0.6)
        r_pu2 = leaguedashptstats.LeagueDashPtStats(
            player_or_team="Player",
            pt_measure_type="PullUpShot",
            per_mode_simple="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_pu2 = r_pu2.get_data_frames()[0]
        for _, row in df_pu2.iterrows():
            key = row["PLAYER_NAME"].lower()
            data.setdefault(key, {"name": row["PLAYER_NAME"]})
            data[key]["pullup_fgm"] = round(float(row.get("PULL_UP_FGM", 0)), 2)
            data[key]["pullup_fga"] = round(float(row.get("PULL_UP_FGA", 0)), 2)
            pu_pct = row.get("PULL_UP_FG_PCT", 0)
            data[key]["pullup_fg_pct"] = round(float(pu_pct if pu_pct and pu_pct == pu_pct else 0), 4)
            data[key]["pullup_fg3m"] = round(float(row.get("PULL_UP_FG3M", 0)), 2)
            data[key]["pullup_fg3a"] = round(float(row.get("PULL_UP_FG3A", 0)), 2)
            pu3_pct = row.get("PULL_UP_FG3_PCT", 0)
            data[key]["pullup_fg3_pct"] = round(float(pu3_pct if pu3_pct and pu3_pct == pu3_pct else 0), 4)
            data[key]["pullup_pts"] = round(float(row.get("PULL_UP_PTS", 0)), 2)

        # 9. Passing tracking
        _time.sleep(0.6)
        r_pass = leaguedashptstats.LeagueDashPtStats(
            player_or_team="Player",
            pt_measure_type="Passing",
            per_mode_simple="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_pass = r_pass.get_data_frames()[0]
        for _, row in df_pass.iterrows():
            key = row["PLAYER_NAME"].lower()
            data.setdefault(key, {"name": row["PLAYER_NAME"]})
            data[key]["passes_made"] = round(float(row.get("PASSES_MADE", 0)), 1)
            data[key]["passes_received"] = round(float(row.get("PASSES_RECEIVED", 0)), 1)
            data[key]["potential_ast"] = round(float(row.get("POTENTIAL_AST", 0)), 2)
            data[key]["ast_points_created"] = round(float(row.get("AST_POINTS_CREATED", 0)), 1)
            data[key]["secondary_ast"] = round(float(row.get("SECONDARY_AST", 0)), 2)
            data[key]["ft_ast"] = round(float(row.get("FT_AST", 0)), 2)
            pct = row.get("AST_TO_PASS_PCT", 0)
            data[key]["ast_to_pass_pct"] = round(float(pct if pct and pct == pct else 0), 4)
            adj = row.get("AST_TO_PASS_PCT_ADJ", 0)
            data[key]["ast_to_pass_pct_adj"] = round(float(adj if adj and adj == adj else 0), 4)

        # 10. Possessions / touches tracking
        _time.sleep(0.6)
        r_poss = leaguedashptstats.LeagueDashPtStats(
            player_or_team="Player",
            pt_measure_type="Possessions",
            per_mode_simple="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_poss = r_poss.get_data_frames()[0]
        for _, row in df_poss.iterrows():
            key = row["PLAYER_NAME"].lower()
            data.setdefault(key, {"name": row["PLAYER_NAME"]})
            data[key]["touches"] = round(float(row.get("TOUCHES", 0)), 1)
            data[key]["front_ct_touches"] = round(float(row.get("FRONT_CT_TOUCHES", 0)), 1)
            data[key]["time_of_poss"] = round(float(row.get("TIME_OF_POSS", 0)), 2)
            data[key]["avg_sec_per_touch"] = round(float(row.get("AVG_SEC_PER_TOUCH", 0)), 2)
            data[key]["avg_drib_per_touch"] = round(float(row.get("AVG_DRIB_PER_TOUCH", 0)), 2)
            data[key]["elbow_touches"] = round(float(row.get("ELBOW_TOUCHES", 0)), 1)
            data[key]["post_touches"] = round(float(row.get("POST_TOUCHES", 0)), 1)
            data[key]["paint_touches"] = round(float(row.get("PAINT_TOUCHES", 0)), 1)

        # 11. Drives tracking
        _time.sleep(0.6)
        r_drv = leaguedashptstats.LeagueDashPtStats(
            player_or_team="Player",
            pt_measure_type="Drives",
            per_mode_simple="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_drv = r_drv.get_data_frames()[0]
        for _, row in df_drv.iterrows():
            key = row["PLAYER_NAME"].lower()
            data.setdefault(key, {"name": row["PLAYER_NAME"]})
            data[key]["drives"] = round(float(row.get("DRIVES", 0)), 1)
            data[key]["drive_fgm"] = round(float(row.get("DRIVE_FGM", 0)), 2)
            data[key]["drive_fga"] = round(float(row.get("DRIVE_FGA", 0)), 2)
            data[key]["drive_pts"] = round(float(row.get("DRIVE_PTS", 0)), 1)
            data[key]["drive_ast"] = round(float(row.get("DRIVE_AST", 0)), 2)
            data[key]["drive_passes"] = round(float(row.get("DRIVE_PASSES", 0)), 1)
            data[key]["drive_tov"] = round(float(row.get("DRIVE_TOV", 0)), 2)

        # 12. Speed & distance tracking
        _time.sleep(0.6)
        r_spd = leaguedashptstats.LeagueDashPtStats(
            player_or_team="Player",
            pt_measure_type="SpeedDistance",
            per_mode_simple="PerGame",
            season=season,
            season_type_all_star="Regular Season",
        )
        df_spd = r_spd.get_data_frames()[0]
        for _, row in df_spd.iterrows():
            key = row["PLAYER_NAME"].lower()
            data.setdefault(key, {"name": row["PLAYER_NAME"]})
            data[key]["dist_miles"] = round(float(row.get("DIST_MILES", 0)), 2)
            data[key]["dist_miles_off"] = round(float(row.get("DIST_MILES_OFF", 0)), 2)
            data[key]["dist_miles_def"] = round(float(row.get("DIST_MILES_DEF", 0)), 2)
            data[key]["avg_speed"] = round(float(row.get("AVG_SPEED", 0)), 2)
            data[key]["avg_speed_off"] = round(float(row.get("AVG_SPEED_OFF", 0)), 2)

    except Exception as exc:
        logger.warning("NBA API player shooting fetch failed: %s", exc)
        if cache_path.exists():
            with open(cache_path) as f:
                return json.load(f)
        return {}

    # Compute derived fields: catch-and-shoot share of total 3PA
    for key, p in data.items():
        total = p.get("total_3pa_pg", 0)
        if total > 0:
            p["catch_shoot_share"] = round(
                p.get("catch_shoot_3pa", 0) / total, 3
            )
            p["self_created_share"] = round(
                p.get("self_created_3pa", 0) / total, 3
            )
            p["wide_open_share"] = round(
                p.get("wide_open_3pa", 0) / total, 3
            )
            p["pullup_share"] = round(
                p.get("pullup_fg3a", 0) / total, 3
            )

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Fetched NBA player shooting for %d players", len(data))
    return data


# ── Model: Empirical Bayes 3PM predictor ─────────────────────────────────────


class ThreePMPredictor:
    """Monte Carlo 3PM predictor with empirical Bayes shrinkage.

    Uses only real historical stats to predict. No synthetic data.
    """

    def __init__(self, window: int = 15, prior_strength: int = 20):
        self.window = window
        self.prior_strength = prior_strength

    def predict(
        self,
        recent_games: list[dict],
        line: float,
        n_sims: int = 25000,
        game_context: dict | None = None,
    ) -> dict:
        """Predict 3PM distribution with scheme-matchup-aware adjustments.

        Uses player shooting profile × opponent defensive profile to compute
        weighted attempt-rate and make-rate adjustments by shot type:
        - Corner 3 vs ATB 3 (zone matchup)
        - Catch-and-shoot vs pull-up (creation matchup)
        - Wide-open vs contested (closeout matchup)
        """
        if len(recent_games) < 5:
            return {"p_over": 0.5, "mean_stat": line, "confidence": "low",
                    "pred_minutes": 0, "pred_rate_per36": 0, "pred_make_pct": 0}

        ctx = game_context or {}
        games = recent_games[-self.window:]
        minutes = np.array([g["mp"] for g in games])
        fg3a = np.array([g["fg3a"] for g in games], dtype=float)
        fg3m = np.array([g["fg3"] for g in games], dtype=float)

        # ── Minutes projection with blowout adjustment ───────────────
        min_mean = float(np.mean(minutes))
        min_std = max(float(np.std(minutes)), 1.0)

        spread = ctx.get("spread", 0.0)
        if abs(spread) > 8 and min_mean > 20:
            blowout_excess = abs(spread) - 8
            minutes_adj = 1.0 - min(blowout_excess * 0.02, 0.12)
            min_mean *= minutes_adj

        # ── 3PA rate: base with shrinkage ────────────────────────────
        total_min = np.sum(minutes)
        total_3pa = np.sum(fg3a)
        raw_rate = total_3pa / max(total_min, 1) * 36.0
        league_rate = 7.5
        n_eff = total_min / 36.0
        adaptive_prior = self.prior_strength * max(0.2, 1.0 - n_eff / 25.0)
        shrunk_rate = (
            (raw_rate * n_eff + league_rate * adaptive_prior)
            / (n_eff + adaptive_prior)
        )

        # ── Scheme matchup: attempt rate adjustment ──────────────────
        # Instead of a single blanket ratio, weight the opponent's
        # defensive profile by HOW this player takes their 3s.
        opp_3pa = ctx.get("opp_3pa_per_game", 0.0)
        sample_avg_3pa = ctx.get("sample_avg_3pa", 0.0)

        # Player's shot creation profile
        cs_share = ctx.get("player_catch_shoot_share", 0.0)
        sc_share = ctx.get("player_self_created_share", 0.0)

        if opp_3pa > 0 and sample_avg_3pa > 0 and (cs_share > 0 or sc_share > 0):
            # Catch-and-shoot weighted by how many open looks opp gives up
            opp_cs_3pa = ctx.get("opp_catch_shoot_3pa", 0.0)
            avg_cs_3pa = ctx.get("sample_avg_catch_shoot_3pa", 20.0)
            cs_ratio = opp_cs_3pa / avg_cs_3pa if avg_cs_3pa > 0 and opp_cs_3pa > 0 else 1.0

            # Wide-open weighted by how many uncontested looks opp gives up
            opp_wo_3pa = ctx.get("opp_wide_open_3pa", 0.0)
            avg_wo_3pa = ctx.get("sample_avg_wide_open_3pa", 15.0)
            wo_ratio = opp_wo_3pa / avg_wo_3pa if avg_wo_3pa > 0 and opp_wo_3pa > 0 else 1.0

            # Overall opponent ratio (fallback)
            overall_ratio = opp_3pa / sample_avg_3pa

            # Weighted blend: catch-and-shoot players are more affected
            # by the opponent's ability to close out; self-creators less so
            remaining_share = max(1.0 - cs_share - sc_share, 0.0)
            matchup_ratio = (
                cs_share * (0.5 * cs_ratio + 0.5 * wo_ratio)
                + sc_share * 1.0  # self-creators are opponent-independent
                + remaining_share * overall_ratio
            )
            matchup_ratio = np.clip(matchup_ratio, 0.85, 1.15)
            shrunk_rate *= matchup_ratio

        elif opp_3pa > 0 and sample_avg_3pa > 0:
            # Fallback: simple overall ratio
            opp_3pa_ratio = np.clip(opp_3pa / sample_avg_3pa, 0.85, 1.15)
            shrunk_rate *= opp_3pa_ratio

        # Pace adjustment from real team pace data
        team_pace = ctx.get("team_pace", 0.0)
        opp_pace = ctx.get("opp_pace", 0.0)
        if team_pace > 0 and opp_pace > 0:
            # Expected game pace is average of both teams
            expected_pace = (team_pace + opp_pace) / 2.0
            pace_ratio = np.clip(expected_pace / 100.0, 0.90, 1.10)
            shrunk_rate *= pace_ratio
        else:
            # Fall back to game total if no pace data
            game_total = ctx.get("total", 0.0)
            if game_total > 0:
                pace_ratio = np.clip(game_total / 228.0, 0.90, 1.10)
                shrunk_rate *= pace_ratio

        # ── Make rate: zone-weighted opponent FG3% adjustment ────────
        total_3pm = np.sum(fg3m)
        shrunk_pct = (
            (total_3pm + LEAGUE_3PT_PCT * self.prior_strength)
            / (total_3pa + self.prior_strength)
        )

        # Zone-weighted FG3% adjustment: weight opponent's corner vs ATB
        # defense by how this player distributes their shots
        corner_share = ctx.get("player_corner3_share", 0.0)
        atb_share = ctx.get("player_atb3_share", 0.0)
        opp_corner3_pct = ctx.get("opp_corner3_pct", 0.0)
        opp_atb3_pct = ctx.get("opp_atb3_pct", 0.0)

        if corner_share > 0 and atb_share > 0 and opp_corner3_pct > 0:
            # Weighted opponent FG3% based on player's zone distribution
            weighted_opp_pct = (
                corner_share * opp_corner3_pct
                + atb_share * opp_atb3_pct
            )
            fg3_diff = weighted_opp_pct - LEAGUE_3PT_PCT
            shrunk_pct += fg3_diff * 0.5
        else:
            # Fallback: overall opponent FG3%
            opp_fg3_pct = ctx.get("opp_fg3_pct_allowed", 0.0)
            if opp_fg3_pct > 0:
                fg3_diff = opp_fg3_pct - LEAGUE_3PT_PCT
                shrunk_pct += fg3_diff * 0.5

        shrunk_pct = float(np.clip(shrunk_pct, 0.15, 0.55))

        # ── Synergy matchup quality: player play type × opp defense ──
        # Compute a weighted matchup quality score across play types.
        # For 3PM-relevant play types (spotup, offscreen, P&R, handoff),
        # cross the player's frequency with the opponent's defensive PPP.
        # Higher opp PPP allowed = weaker defense = boost for player.
        _LEAGUE_AVG_PPP = {
            "spotup": 1.03, "isolation": 0.89, "prballhandler": 0.87,
            "offscreen": 1.01, "transition": 1.12, "handoff": 0.95,
        }
        # Play types most relevant to 3PM (with weight)
        _3PM_PLAY_TYPE_WEIGHTS = {
            "spotup": 0.40, "offscreen": 0.25, "prballhandler": 0.15,
            "handoff": 0.10, "transition": 0.10,
        }
        synergy_adj = 0.0
        synergy_weight_sum = 0.0
        for pt, pt_weight in _3PM_PLAY_TYPE_WEIGHTS.items():
            player_freq = ctx.get(f"player_off_{pt}_freq", 0.0)
            opp_def_ppp = ctx.get(f"opp_def_{pt}_ppp", 0.0)
            avg_ppp = _LEAGUE_AVG_PPP.get(pt, 1.0)
            if player_freq > 0 and opp_def_ppp > 0:
                # How much better/worse is this opp vs average at defending this play type
                ppp_ratio = opp_def_ppp / avg_ppp
                # Weight by both the play type importance and the player's usage of it
                w = pt_weight * player_freq
                synergy_adj += w * (ppp_ratio - 1.0)
                synergy_weight_sum += w

        if synergy_weight_sum > 0:
            # Normalize and apply as a multiplicative adjustment
            synergy_adj /= synergy_weight_sum
            # Clip to +/- 5% — synergy is a secondary signal
            synergy_adj = np.clip(synergy_adj, -0.05, 0.05)
            shrunk_rate *= (1.0 + synergy_adj)

        # ── Hustle/contest adjustment: opponent 3PT contest rate ─────
        # Teams that contest more 3s tend to lower FG3% against
        opp_contested_3pt = ctx.get("opp_contested_shots_3pt", 0.0)
        if opp_contested_3pt > 0:
            # League average is roughly 7-8 contested 3s per game
            contest_ratio = opp_contested_3pt / 7.5
            # More contests = lower make rate (up to -3%)
            contest_adj = np.clip((contest_ratio - 1.0) * -0.03, -0.03, 0.03)
            shrunk_pct += contest_adj
            shrunk_pct = float(np.clip(shrunk_pct, 0.15, 0.55))

        # ── Shot clock matchup: player tempo × opp shot clock defense ─
        # Players who shoot early in the clock face different defense than
        # late-clock shooters. Cross player's shot clock distribution with
        # opponent's shot clock FG3% allowed.
        p_sc_early = ctx.get("player_sc_early_3pa", 0.0)
        p_sc_normal = ctx.get("player_sc_normal_3pa", 0.0)
        p_sc_late = ctx.get("player_sc_late_3pa", 0.0)
        total_sc = p_sc_early + p_sc_normal + p_sc_late
        if total_sc > 0:
            early_share = p_sc_early / total_sc
            normal_share = p_sc_normal / total_sc
            late_share = p_sc_late / total_sc
            opp_sc_early = ctx.get("opp_sc_early_3pct", 0.0)
            opp_sc_normal_3pct = ctx.get("opp_sc_normal_3pa", 0.0)  # use 3pa as proxy
            opp_sc_late = ctx.get("opp_sc_late_3pct", 0.0)
            # If opponent allows high late-clock FG3% and player shoots late,
            # that's a boost. Weight by player's shot clock distribution.
            if opp_sc_early > 0 and opp_sc_late > 0:
                weighted_opp_sc_pct = (
                    early_share * opp_sc_early
                    + normal_share * LEAGUE_3PT_PCT
                    + late_share * opp_sc_late
                )
                sc_diff = weighted_opp_sc_pct - LEAGUE_3PT_PCT
                sc_adj = np.clip(sc_diff * 0.3, -0.02, 0.02)
                shrunk_pct += sc_adj
                shrunk_pct = float(np.clip(shrunk_pct, 0.15, 0.55))

        # ── Monte Carlo ──────────────────────────────────────────────
        rng = np.random.default_rng()
        log_mu = np.log(max(min_mean, 1)) - 0.5 * (min_std / max(min_mean, 1)) ** 2
        log_sig = np.sqrt(np.log(1 + (min_std / max(min_mean, 1)) ** 2))
        sim_min = np.clip(rng.lognormal(log_mu, log_sig, n_sims), 0, 48)
        sim_3pa = rng.poisson(np.maximum(shrunk_rate * sim_min / 36.0, 0.01))

        alpha = total_3pm + LEAGUE_3PT_PCT * self.prior_strength
        beta_p = (total_3pa - total_3pm) + (1 - LEAGUE_3PT_PCT) * self.prior_strength
        sim_pct = rng.beta(max(alpha, 0.5), max(beta_p, 0.5), n_sims)
        sim_3pm = rng.binomial(sim_3pa, np.clip(sim_pct, 0.01, 0.99))

        return {
            "p_over": float(np.mean(sim_3pm > line)),
            "p_under": float(np.mean(sim_3pm <= line)),
            "mean_stat": float(np.mean(sim_3pm)),
            "mean_3pm": float(np.mean(sim_3pm)),
            "std_stat": float(np.std(sim_3pm)),
            "pred_minutes": float(min_mean),
            "pred_rate_per36": float(shrunk_rate),
            "pred_3pa_per36": float(shrunk_rate),
            "pred_make_pct": float(shrunk_pct),
            "pred_fg3_pct": float(shrunk_pct),
            "n_games_used": len(games),
            "confidence": "high" if len(games) >= 10 else "medium",
        }


# ── Model: Empirical Bayes Assists predictor ──────────────────────────────────


class AssistsPredictor:
    """Monte Carlo assists predictor with empirical Bayes shrinkage.

    Models assists as a Poisson-like count scaled by minutes, with
    Bayesian shrinkage toward the league-average rate.
    """

    def __init__(self, window: int = 15, prior_strength: int = 20):
        self.window = window
        self.prior_strength = prior_strength

    def predict(
        self,
        recent_games: list[dict],
        line: float,
        n_sims: int = 25000,
        game_context: dict | None = None,
    ) -> dict:
        """Predict assists distribution with optional game-context adjustments.

        game_context keys (all optional):
            spread: float           — home spread
            total: float            — game total (O/U)
            opp_ast_per_game: float — opponent assists allowed per game
            is_home: bool
        """
        if len(recent_games) < 5:
            return {"p_over": 0.5, "mean_stat": line, "confidence": "low",
                    "pred_minutes": 0, "pred_rate_per36": 0, "pred_make_pct": 0}

        ctx = game_context or {}
        games = recent_games[-self.window:]
        minutes = np.array([g["mp"] for g in games])
        assists = np.array([g["ast"] for g in games], dtype=float)

        # ── Minutes projection with blowout adjustment ───────────────
        min_mean = float(np.mean(minutes))
        min_std = max(float(np.std(minutes)), 1.0)

        spread = ctx.get("spread", 0.0)
        if abs(spread) > 8 and min_mean > 20:
            blowout_excess = abs(spread) - 8
            minutes_adj = 1.0 - min(blowout_excess * 0.02, 0.12)
            min_mean *= minutes_adj

        # ── Assists rate per 36 with shrinkage ───────────────────────
        total_min = np.sum(minutes)
        total_ast = np.sum(assists)
        raw_rate = total_ast / max(total_min, 1) * 36.0
        n_eff = total_min / 36.0
        adaptive_prior = self.prior_strength * max(0.2, 1.0 - n_eff / 25.0)
        shrunk_rate = (raw_rate * n_eff + LEAGUE_AST_PER_36 * adaptive_prior) / (n_eff + adaptive_prior)

        # Opponent assists-allowed adjustment
        opp_ast = ctx.get("opp_ast_per_game", 0.0)
        sample_avg_ast = ctx.get("sample_avg_ast", 0.0)
        if opp_ast > 0 and sample_avg_ast > 0:
            opp_ast_ratio = np.clip(opp_ast / sample_avg_ast, 0.85, 1.15)
            shrunk_rate *= opp_ast_ratio

        # Pace adjustment from real team pace data
        team_pace = ctx.get("team_pace", 0.0)
        opp_pace = ctx.get("opp_pace", 0.0)
        if team_pace > 0 and opp_pace > 0:
            expected_pace = (team_pace + opp_pace) / 2.0
            pace_ratio = np.clip(expected_pace / 100.0, 0.90, 1.10)
            shrunk_rate *= pace_ratio
        else:
            game_total = ctx.get("total", 0.0)
            if game_total > 0:
                pace_ratio = np.clip(game_total / 228.0, 0.90, 1.10)
                shrunk_rate *= pace_ratio

        # ── Synergy matchup: assists-relevant play types ─────────────
        # P&R ball handlers and isolation players generate assists differently
        # vs opponents who are weak/strong at defending those play types.
        # Weak P&R defense → more drive-and-kick assists for ball handlers.
        _AST_LEAGUE_AVG_PPP = {
            "prballhandler": 0.87, "isolation": 0.89, "transition": 1.12,
            "handoff": 0.95, "cut": 1.10,
        }
        _AST_PLAY_TYPE_WEIGHTS = {
            "prballhandler": 0.35, "isolation": 0.20, "transition": 0.20,
            "handoff": 0.15, "cut": 0.10,
        }
        ast_synergy_adj = 0.0
        ast_syn_weight_sum = 0.0
        for pt, pt_w in _AST_PLAY_TYPE_WEIGHTS.items():
            p_freq = ctx.get(f"player_off_{pt}_freq", 0.0)
            opp_ppp = ctx.get(f"opp_def_{pt}_ppp", 0.0)
            avg_ppp = _AST_LEAGUE_AVG_PPP.get(pt, 1.0)
            if p_freq > 0 and opp_ppp > 0:
                ratio = opp_ppp / avg_ppp
                w = pt_w * p_freq
                ast_synergy_adj += w * (ratio - 1.0)
                ast_syn_weight_sum += w

        if ast_syn_weight_sum > 0:
            ast_synergy_adj /= ast_syn_weight_sum
            ast_synergy_adj = np.clip(ast_synergy_adj, -0.05, 0.05)
            shrunk_rate *= (1.0 + ast_synergy_adj)

        # ── Deflections adjustment: high-deflection teams disrupt passing ─
        opp_deflections = ctx.get("opp_deflections", 0.0)
        if opp_deflections > 0:
            # League average ~15 deflections per game
            defl_ratio = opp_deflections / 15.0
            # More deflections = slightly fewer assists (up to -3%)
            defl_adj = np.clip((defl_ratio - 1.0) * -0.03, -0.03, 0.03)
            shrunk_rate *= (1.0 + defl_adj)

        # ── Overdispersion estimate ──────────────────────────────────
        if len(games) >= 5 and np.mean(assists) > 0:
            var = np.var(assists)
            mean = np.mean(assists)
            if var > mean:
                dispersion = mean ** 2 / (var - mean)
                dispersion = max(dispersion, 1.0)
            else:
                dispersion = 50.0
        else:
            dispersion = 10.0

        # ── Monte Carlo ──────────────────────────────────────────────
        rng = np.random.default_rng()
        log_mu = np.log(max(min_mean, 1)) - 0.5 * (min_std / max(min_mean, 1)) ** 2
        log_sig = np.sqrt(np.log(1 + (min_std / max(min_mean, 1)) ** 2))
        sim_min = np.clip(rng.lognormal(log_mu, log_sig, n_sims), 0, 48)

        sim_rate = np.maximum(shrunk_rate * sim_min / 36.0, 0.01)

        nb_n = dispersion
        nb_p = dispersion / (dispersion + sim_rate)
        nb_p = np.clip(nb_p, 0.001, 0.999)
        sim_ast = rng.negative_binomial(
            n=np.full(n_sims, nb_n),
            p=nb_p,
        )

        return {
            "p_over": float(np.mean(sim_ast > line)),
            "p_under": float(np.mean(sim_ast <= line)),
            "mean_stat": float(np.mean(sim_ast)),
            "mean_3pm": float(np.mean(sim_ast)),  # backward compat key
            "std_stat": float(np.std(sim_ast)),
            "pred_minutes": float(min_mean),
            "pred_rate_per36": float(shrunk_rate),
            "pred_3pa_per36": float(shrunk_rate),  # backward compat key
            "pred_make_pct": 0.0,  # not applicable for assists
            "pred_fg3_pct": 0.0,  # backward compat key
            "n_games_used": len(games),
            "confidence": "high" if len(games) >= 10 else "medium",
        }


class BoxScorePredictor:
    """Advanced Monte Carlo predictor for any counting stat.

    Each stat category has its own scheme-matchup logic using opponent
    defensive data, synergy play types, tracking stats, and hustle metrics
    — paralleling the depth of ThreePMPredictor and AssistsPredictor.

    Stat-specific adjustment layers:
      POINTS:    Opp def rating, FG% allowed by zone, synergy scoring PPP,
                 contested shot rate, usage-weighted matchup quality
      REBOUNDS:  Opp OREB/DREB splits, opp FG% (misses = more DREBs),
                 opp paint FGA (drives = more OREB chances), pace
      STEALS:    Opp TOV rate, opp ball-handling quality (synergy TOV%),
                 deflection environment, transition frequency
      BLOCKS:    Opp paint FGA, opp FG% at rim, opp isolation/PnR drives,
                 contested shot rate
      TURNOVERS: Opp deflections, opp steal rate, synergy TOV% by play type,
                 player usage rate interaction
      FGM:       Opp FG% allowed, opp contested shot rate, zone matchup
                 (paint vs mid vs 3), player TS%/EFG% context
      FTM:       Opp personal fouls, opp FTA allowed, player usage (drives),
                 synergy isolation/PnR frequency (foul-drawing play types)
    """

    # League-average reference points for synergy play types
    _LEAGUE_AVG_PPP = {
        "spotup": 1.03, "isolation": 0.89, "prballhandler": 0.87,
        "prrollman": 0.96, "offscreen": 1.01, "transition": 1.12,
        "handoff": 0.95, "cut": 1.10,
    }

    def __init__(
        self,
        stat_type: str,
        window: int = 15,
        prior_strength: int = 20,
    ):
        self.stat_type = stat_type
        self.window = window
        self.prior_strength = prior_strength
        self.bbref_field = BBREF_STAT_FIELD_ALL.get(stat_type, stat_type)
        self.league_rate = LEAGUE_AVG_PER_36.get(stat_type, 5.0)

    def predict(
        self,
        recent_games: list[dict],
        line: float = 0.0,
        n_sims: int = 25000,
        game_context: dict | None = None,
    ) -> dict:
        """Predict stat distribution with full advanced-stats adjustments."""
        if len(recent_games) < 5:
            return {
                "p_over": 0.5, "mean_stat": line, "confidence": "low",
                "pred_minutes": 0, "pred_rate_per36": 0,
            }

        ctx = game_context or {}
        games = recent_games[-self.window:]
        minutes = np.array([g["mp"] for g in games])
        stat_vals = np.array(
            [g.get(self.bbref_field, 0) for g in games], dtype=float
        )

        # ── Minutes projection with blowout adjustment ───────────────
        min_mean = float(np.mean(minutes))
        min_std = max(float(np.std(minutes)), 1.0)

        spread = ctx.get("spread", 0.0)
        if abs(spread) > 8 and min_mean > 20:
            blowout_excess = abs(spread) - 8
            minutes_adj = 1.0 - min(blowout_excess * 0.02, 0.12)
            min_mean *= minutes_adj

        # ── Rate per 36 with adaptive shrinkage ──────────────────
        # Prior fades as sample grows — stars with large samples
        # keep their actual rates, while low-sample players get
        # pulled toward the league average.
        total_min = np.sum(minutes)
        total_stat = np.sum(stat_vals)
        raw_rate = total_stat / max(total_min, 1) * 36.0
        n_eff = total_min / 36.0
        # Scale prior strength: full strength at n_eff=5, half at n_eff=15
        adaptive_prior = self.prior_strength * max(0.2, 1.0 - n_eff / 25.0)
        shrunk_rate = (
            (raw_rate * n_eff + self.league_rate * adaptive_prior)
            / (n_eff + adaptive_prior)
        )

        # ── Opponent allowed adjustment (baseline for all stats) ──
        opp_key = self._opp_context_key()
        opp_val = ctx.get(opp_key, 0.0)
        league_opp_avg = LEAGUE_AVG_OPP_ALLOWED.get(self.stat_type, 0.0)
        if opp_val > 0 and league_opp_avg > 0:
            opp_ratio = np.clip(opp_val / league_opp_avg, 0.85, 1.15)
            shrunk_rate *= opp_ratio

        # ── Pace adjustment ──────────────────────────────────────
        team_pace = ctx.get("team_pace", 0.0)
        opp_pace = ctx.get("opp_pace", 0.0)
        if team_pace > 0 and opp_pace > 0:
            expected_pace = (team_pace + opp_pace) / 2.0
            pace_ratio = np.clip(expected_pace / 100.0, 0.90, 1.10)
            shrunk_rate *= pace_ratio
        else:
            game_total = ctx.get("total", 0.0)
            if game_total > 0:
                pace_ratio = np.clip(game_total / 228.0, 0.90, 1.10)
                shrunk_rate *= pace_ratio

        # ── Stat-specific advanced adjustments ───────────────────
        shrunk_rate = self._apply_stat_adjustments(
            shrunk_rate, ctx, games, stat_vals, minutes
        )

        # ── Overdispersion ─────────────────────────────────────────
        if len(games) >= 5 and np.mean(stat_vals) > 0:
            var = np.var(stat_vals)
            mean = np.mean(stat_vals)
            if var > mean:
                dispersion = mean ** 2 / (var - mean)
                dispersion = max(dispersion, 1.0)
            else:
                dispersion = 50.0
        else:
            dispersion = 10.0

        # ── Monte Carlo ────────────────────────────────────────────
        rng = np.random.default_rng()
        log_mu = np.log(max(min_mean, 1)) - 0.5 * (min_std / max(min_mean, 1)) ** 2
        log_sig = np.sqrt(np.log(1 + (min_std / max(min_mean, 1)) ** 2))
        sim_min = np.clip(rng.lognormal(log_mu, log_sig, n_sims), 0, 48)

        sim_rate = np.maximum(shrunk_rate * sim_min / 36.0, 0.01)
        nb_n = dispersion
        nb_p = dispersion / (dispersion + sim_rate)
        nb_p = np.clip(nb_p, 0.001, 0.999)
        sim_stat = rng.negative_binomial(
            n=np.full(n_sims, nb_n), p=nb_p,
        )

        return {
            "p_over": float(np.mean(sim_stat > line)) if line > 0 else 0.5,
            "mean_stat": float(np.mean(sim_stat)),
            "std_stat": float(np.std(sim_stat)),
            "median_stat": float(np.median(sim_stat)),
            "p10": float(np.percentile(sim_stat, 10)),
            "p90": float(np.percentile(sim_stat, 90)),
            "pred_minutes": float(min_mean),
            "pred_rate_per36": float(shrunk_rate),
            "n_games_used": len(games),
            "confidence": "high" if len(games) >= 10 else "medium",
        }

    # ── Stat-specific adjustment dispatch ─────────────────────────────

    def _apply_stat_adjustments(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """Route to the right stat-specific adjustment method."""
        dispatch = {
            STAT_POINTS: self._adjust_points,
            STAT_REBOUNDS: self._adjust_rebounds,
            STAT_STEALS: self._adjust_steals,
            STAT_BLOCKS: self._adjust_blocks,
            STAT_TURNOVERS: self._adjust_turnovers,
            STAT_FGM: self._adjust_fgm,
            STAT_FTM: self._adjust_ftm,
        }
        fn = dispatch.get(self.stat_type)
        if fn:
            rate = fn(rate, ctx, games, stat_vals, minutes)
        return rate

    # ── POINTS ────────────────────────────────────────────────────────

    def _adjust_points(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """Points adjustments: def rating, usage, synergy scoring, contests.

        Logic:
        - Opp defensive rating → overall scoring environment
        - Player USG% × opp contested shot rate → shot difficulty
        - Synergy play-type matchup → scoring efficiency by play type
          weighted by player's offensive frequency
        - Opp FG% allowed → field goal conversion environment
        """
        # Defensive rating: higher = worse defense = more scoring
        opp_def_rating = ctx.get("opp_def_rating", 0.0)
        if opp_def_rating > 0:
            def_adj = np.clip(opp_def_rating / 112.0, 0.93, 1.07)
            rate *= def_adj

        # Contested shot pressure: more contests = lower FG% = fewer pts
        opp_contested = ctx.get("opp_contested_shots", 0.0)
        if opp_contested > 0:
            contest_ratio = opp_contested / 50.0  # ~50 avg
            contest_adj = np.clip(1.0 - (contest_ratio - 1.0) * 0.03, 0.95, 1.05)
            rate *= contest_adj

        # Synergy scoring matchup — weight by player's play-type freq
        _PTS_PLAY_TYPE_WEIGHTS = {
            "isolation": 0.25, "prballhandler": 0.25, "spotup": 0.20,
            "transition": 0.15, "cut": 0.10, "prrollman": 0.05,
        }
        syn_adj = self._synergy_matchup_adj(ctx, _PTS_PLAY_TYPE_WEIGHTS)
        if syn_adj != 0:
            rate *= (1.0 + syn_adj)

        # Usage-weighted: high-usage players are more matchup-sensitive
        player_usg = ctx.get("player_usg_pct", 0.0)
        if player_usg > 0.25:
            # Above-average usage amplifies the matchup effects
            usg_multiplier = np.clip(player_usg / 0.20, 1.0, 1.08)
            rate *= usg_multiplier
        elif player_usg > 0 and player_usg < 0.15:
            # Low-usage players are less affected by matchup
            rate *= 0.98

        return rate

    # ── REBOUNDS ───────────────────────────────────────────────────────

    def _adjust_rebounds(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """Rebounds adjustments: OREB/DREB splits, opp FG%, paint FGA, pace.

        Logic:
        - Opp FG% allowed → more misses = more DREB opportunities
        - Opp OREB allowed → how well opponent crashes glass (limits DREBs)
        - Opp paint FGA → more drives = more long rebound chances
        - Opp pace × game total → faster pace = more possessions = more boards
        - Player's OREB vs DREB split × opponent's specific weakness
        """
        # Opponent FG% → misses create rebounds
        opp_fg_pct = ctx.get("opp_fg_pct", 0.0)
        if opp_fg_pct > 0:
            # Lower FG% = more misses = more rebound opportunities
            # League avg ~46.5%
            miss_adj = np.clip((0.465 - opp_fg_pct) * 2.0 + 1.0, 0.95, 1.05)
            rate *= miss_adj

        # Opponent OREB rate — teams that crash the glass reduce your DREBs
        opp_oreb = ctx.get("opp_oreb_per_game", 0.0)
        if opp_oreb > 0:
            # League avg ~10.5 OREBs/game — more opponent OREBs = fewer DREBs
            oreb_adj = np.clip(1.0 - (opp_oreb / 10.5 - 1.0) * 0.04, 0.95, 1.05)
            rate *= oreb_adj

        # Player's rebound type split (from recent games)
        total_orb = sum(g.get("orb", 0) for g in games)
        total_drb = sum(g.get("drb", 0) for g in games)
        total_reb = total_orb + total_drb
        if total_reb > 0:
            orb_share = total_orb / total_reb
            # OREB-heavy rebounders are sensitive to paint/rim FGA
            opp_paint_fga = ctx.get("opp_fga_per_game", 0.0)
            if orb_share > 0.30 and opp_paint_fga > 0:
                # More opponent FGA (especially paint) = more OREB chances
                fga_adj = np.clip(opp_paint_fga / 85.0, 0.97, 1.03)
                rate *= fga_adj

        # Opponent PnR roll man defense — weak roll defense = more
        # rim activity = more rebound opportunities for bigs
        rollman_ppp = ctx.get("def_prrollman_ppp", 0.0)
        if rollman_ppp > 0:
            roll_adj = np.clip(rollman_ppp / 0.96, 0.97, 1.03)
            rate *= roll_adj

        return rate

    # ── STEALS ────────────────────────────────────────────────────────

    def _adjust_steals(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """Steals adjustments: opp TOV rate, synergy TOV%, deflections, transition.

        Logic:
        - Opp turnover rate → sloppy teams give up more steal opportunities
        - Synergy play-type TOV% → specific play types opponent is turnover-prone in
        - Opp pace → more possessions = more steal chances
        - Player's steal profile × opponent's ball security by play type
        - Transition frequency → fast breaks create loose-ball steal chances
        """
        # Opponent turnover tendency
        opp_tov = ctx.get("opp_tov_per_game", 0.0)
        if opp_tov > 0:
            tov_adj = np.clip(opp_tov / 14.0, 0.93, 1.07)
            rate *= tov_adj

        # Deflections environment — more deflections from player's team
        # means more loose-ball chances
        opp_deflections = ctx.get("opp_deflections", 0.0)
        if opp_deflections > 0:
            defl_adj = np.clip(opp_deflections / 15.0, 0.97, 1.03)
            rate *= defl_adj

        # Opponent's ball-handling weakness by play type
        # PnR ball handlers and iso players are most steal-prone
        _STL_PLAY_TYPES = {
            "prballhandler": 0.35, "isolation": 0.30,
            "transition": 0.20, "handoff": 0.15,
        }
        for pt, weight in _STL_PLAY_TYPES.items():
            opp_tov_pct = ctx.get(f"def_{pt}_tov_pct", 0.0)
            if opp_tov_pct > 0:
                # Higher TOV% on this play type = more steal chances
                # League avg TOV% varies by play type but ~10-15%
                tov_pct_adj = np.clip(opp_tov_pct / 0.12, 0.95, 1.05)
                rate *= (1.0 + (tov_pct_adj - 1.0) * weight)

        # Loose balls recovered → proxy for opponent's ball security
        opp_loose = ctx.get("opp_loose_balls_recovered", 0.0)
        if opp_loose > 0:
            loose_adj = np.clip(opp_loose / 5.5, 0.97, 1.03)
            rate *= loose_adj

        return rate

    # ── BLOCKS ────────────────────────────────────────────────────────

    def _adjust_blocks(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """Blocks adjustments: opp paint FGA, rim contests, PnR/iso drives.

        Logic:
        - Opp FGA → more shots = more block chances (especially paint)
        - Opp paint/rim FG% → opponents who attack the rim face more blocks
        - Opp isolation/PnR ball handler frequency → these create rim attacks
        - Contested shot rate → player on a team that contests more = more blocks
        - Player's block rate × opponent's rim attack frequency
        """
        # More opponent FGA = more block chances
        opp_fga = ctx.get("opp_fga_per_game", 0.0)
        if opp_fga > 0:
            fga_adj = np.clip(opp_fga / 85.0, 0.95, 1.05)
            rate *= fga_adj

        # Opponent rim attack frequency (isolation + PnR drives)
        iso_poss = ctx.get("def_isolation_ppp", 0.0)
        pnr_poss = ctx.get("def_prballhandler_ppp", 0.0)
        if iso_poss > 0 and pnr_poss > 0:
            # Weak rim protection on these play types = opponents attack more
            # but that also means more block opportunities for shot blockers
            rim_attack = (iso_poss + pnr_poss) / 2.0
            rim_avg = (0.89 + 0.87) / 2.0
            rim_adj = np.clip(rim_attack / rim_avg, 0.95, 1.05)
            rate *= rim_adj

        # Opponent 2-point contested shot profile
        opp_contested_2pt = ctx.get("opp_contested_shots_2pt", 0.0)
        if opp_contested_2pt > 0:
            # More 2-point contests = more rim action = more blocks
            c2_adj = np.clip(opp_contested_2pt / 30.0, 0.97, 1.03)
            rate *= c2_adj

        # Opponent paint FG% — low FG% at rim suggests they face more
        # rim protection, but we want opponents that ATTACK the rim,
        # so use cut PPP as proxy for rim attack volume
        cut_ppp = ctx.get("def_cut_ppp", 0.0)
        if cut_ppp > 0:
            cut_adj = np.clip(cut_ppp / 1.10, 0.97, 1.03)
            rate *= cut_adj

        return rate

    # ── TURNOVERS ─────────────────────────────────────────────────────

    def _adjust_turnovers(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """Turnovers adjustments: opp deflections, steal rate, usage, synergy.

        Logic:
        - Opp deflections → disruptive defense forces more turnovers
        - Opp steal rate → ball-hawking opponents create more live-ball TOs
        - Player USG% interaction → high-usage players in tough matchups turn
          it over more
        - Synergy play-type TOV% → opponent forces TOs on specific plays
        - Opp PnR defense quality → good PnR defense creates traps → TOs
        """
        # Opponent deflections → direct TO pressure
        defl = ctx.get("opp_deflections", 0.0)
        if defl > 0:
            defl_adj = np.clip(defl / 15.0, 0.95, 1.05)
            rate *= defl_adj

        # Opponent steal rate
        opp_stl = ctx.get("opp_stl_per_game", 0.0)
        if opp_stl > 0:
            stl_adj = np.clip(opp_stl / 8.0, 0.95, 1.05)
            rate *= stl_adj

        # Usage interaction — high-usage players are more affected
        player_usg = ctx.get("player_usg_pct", 0.0)
        if player_usg > 0.25:
            # High-usage players have more chance to turn it over
            usg_tov = np.clip(player_usg / 0.20, 1.0, 1.05)
            rate *= usg_tov

        # Synergy: opponent forces TOs on specific play types
        _TOV_PLAY_TYPES = {
            "prballhandler": 0.35, "isolation": 0.30,
            "transition": 0.20, "handoff": 0.15,
        }
        for pt, weight in _TOV_PLAY_TYPES.items():
            player_freq = ctx.get(f"player_{pt}_freq", 0.0)
            if player_freq == 0:
                player_freq = ctx.get(f"player_off_{pt}_freq", 0.0)
            opp_tov_pct = ctx.get(f"def_{pt}_tov_pct", 0.0)
            if player_freq > 0 and opp_tov_pct > 0:
                # Cross player's play-type usage with opponent's TO-forcing rate
                tov_signal = opp_tov_pct / 0.12  # ~12% avg
                rate *= (1.0 + (tov_signal - 1.0) * weight * player_freq)

        # Opponent PnR defense quality — good PnR defense creates traps
        pnr_def_ppp = ctx.get("def_prballhandler_ppp", 0.0)
        player_pnr_freq = ctx.get("player_pnr_freq", 0.0)
        if pnr_def_ppp > 0 and player_pnr_freq > 0.15:
            # Low PPP = good defense = more traps = more TOs for ball handlers
            pnr_adj = np.clip(1.0 - (pnr_def_ppp / 0.87 - 1.0) * 0.04, 0.96, 1.04)
            rate *= pnr_adj

        return rate

    # ── FGM ───────────────────────────────────────────────────────────

    def _adjust_fgm(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """FGM adjustments: opp FG% allowed, zone matchup, contests, synergy.

        Logic:
        - Opp FG% allowed → overall shooting environment
        - Opp def rating → offensive efficiency environment
        - Opp contested shot rate → shot difficulty
        - Player TS%/EFG% → high-efficiency shooters sustain FGM better
        - Synergy matchup → play-type efficiency × opponent defense
        """
        # Defensive rating environment
        opp_def_rating = ctx.get("opp_def_rating", 0.0)
        if opp_def_rating > 0:
            def_adj = np.clip(opp_def_rating / 112.0, 0.95, 1.05)
            rate *= def_adj

        # Opponent contested shot rate
        opp_contested = ctx.get("opp_contested_shots", 0.0)
        if opp_contested > 0:
            contest_adj = np.clip(1.0 - (opp_contested / 50.0 - 1.0) * 0.03, 0.96, 1.04)
            rate *= contest_adj

        # Opponent FG% allowed directly
        opp_fg_pct = ctx.get("opp_fg_pct", 0.0)
        if opp_fg_pct > 0:
            fg_env = np.clip(opp_fg_pct / 0.465, 0.96, 1.04)
            rate *= fg_env

        # Player efficiency context
        player_ts = ctx.get("player_ts_pct", 0.0)
        if player_ts > 0.60:
            # Highly efficient scorers are more matchup-resistant
            rate *= 1.02
        elif player_ts > 0 and player_ts < 0.50:
            rate *= 0.98

        # Synergy scoring matchup
        _FGM_PLAY_TYPES = {
            "isolation": 0.25, "prballhandler": 0.25,
            "spotup": 0.20, "cut": 0.15, "transition": 0.15,
        }
        syn_adj = self._synergy_matchup_adj(ctx, _FGM_PLAY_TYPES)
        if syn_adj != 0:
            rate *= (1.0 + syn_adj)

        return rate

    # ── FTM ───────────────────────────────────────────────────────────

    def _adjust_ftm(
        self, rate: float, ctx: dict, games: list, stat_vals, minutes,
    ) -> float:
        """FTM adjustments: opp PF rate, FTA allowed, isolation/PnR freq, drives.

        Logic:
        - Opp personal fouls per game → foul-prone teams send players to line
        - Opp FTA allowed per game → how many FTs opponent gives up
        - Player's iso/PnR frequency → drive-heavy players draw more fouls
        - Player USG% → high-usage players get to the line more
        - Synergy isolation defense → weak iso defense = more drives = more FTs
        """
        # Opponent personal fouls
        opp_pf = ctx.get("opp_pf_per_game", 0.0)
        if opp_pf > 0:
            foul_adj = np.clip(opp_pf / 20.0, 0.93, 1.07)
            rate *= foul_adj

        # Opponent FTA allowed
        opp_fta = ctx.get("opp_fta_per_game", 0.0)
        if opp_fta > 0:
            fta_adj = np.clip(opp_fta / 22.0, 0.95, 1.05)
            rate *= fta_adj

        # Player drive frequency (iso + PnR are foul-drawing play types)
        player_iso_freq = ctx.get("player_iso_freq", 0.0)
        player_pnr_freq = ctx.get("player_pnr_freq", 0.0)
        drive_freq = player_iso_freq + player_pnr_freq
        if drive_freq > 0.30:
            # Drive-heavy players draw more fouls vs weak isolation defense
            iso_def_ppp = ctx.get("def_isolation_ppp", 0.0)
            if iso_def_ppp > 0:
                # Higher PPP = weaker defense = more drives reaching the basket
                drive_adj = np.clip(iso_def_ppp / 0.89, 0.97, 1.05)
                rate *= drive_adj

        # High-usage players get to the line more
        player_usg = ctx.get("player_usg_pct", 0.0)
        if player_usg > 0.25:
            usg_ft_adj = np.clip(player_usg / 0.20, 1.0, 1.04)
            rate *= usg_ft_adj

        return rate

    # ── Helpers ───────────────────────────────────────────────────────

    def _synergy_matchup_adj(
        self, ctx: dict, play_type_weights: dict,
    ) -> float:
        """Compute weighted synergy matchup adjustment across play types.

        Crosses player's offensive play-type frequency with opponent's
        defensive PPP for each play type. Returns a multiplier delta
        (e.g., +0.03 means 3% boost).
        """
        adj_sum = 0.0
        weight_sum = 0.0
        for pt, pt_weight in play_type_weights.items():
            player_freq = ctx.get(f"player_{pt}_freq", 0.0)
            if player_freq == 0:
                player_freq = ctx.get(f"player_off_{pt}_freq", 0.0)
            opp_def_ppp = ctx.get(f"def_{pt}_ppp", 0.0)
            avg_ppp = self._LEAGUE_AVG_PPP.get(pt, 1.0)
            if player_freq > 0 and opp_def_ppp > 0:
                ppp_ratio = opp_def_ppp / avg_ppp
                w = pt_weight * player_freq
                adj_sum += w * (ppp_ratio - 1.0)
                weight_sum += w

        if weight_sum > 0:
            return float(np.clip(adj_sum / weight_sum, -0.05, 0.05))
        return 0.0

    def _opp_context_key(self) -> str:
        """Return the game_context key for opponent allowed stat."""
        return {
            STAT_POINTS: "opp_pts_per_game",
            STAT_REBOUNDS: "opp_reb_per_game",
            STAT_STEALS: "opp_stl_per_game",
            STAT_BLOCKS: "opp_blk_per_game",
            STAT_TURNOVERS: "opp_tov_per_game",
            STAT_ASSISTS: "opp_ast_per_game",
            STAT_FGM: "opp_fgm_per_game",
            STAT_FTM: "opp_ftm_per_game",
        }.get(self.stat_type, "")


def get_predictor(stat_type: str):
    """Factory to return the appropriate predictor for a stat type."""
    if stat_type == STAT_ASSISTS:
        return AssistsPredictor()
    if stat_type == STAT_FG3M:
        return ThreePMPredictor()
    return BoxScorePredictor(stat_type)


# ── Name matching ────────────────────────────────────────────────────────────


def _names_match(a: str, b: str) -> bool:
    a, b = a.strip().lower(), b.strip().lower()
    if a == b:
        return True
    a_parts, b_parts = a.split(), b.split()
    if a_parts and b_parts and a_parts[-1] == b_parts[-1]:
        if len(a_parts) > 1 and len(b_parts) > 1 and a_parts[0][0] == b_parts[0][0]:
            return True
    return False


def _find_player_logs(
    player_name: str, game_log_index: dict[str, dict[str, dict]],
) -> str | None:
    pname = player_name.lower()
    for log_name in game_log_index:
        if _names_match(pname, log_name):
            return log_name
    return None


# ── Evaluation ───────────────────────────────────────────────────────────────


@dataclass
class EvalRecord:
    """One prediction against a real prop — all fields from real data."""

    source: str  # where the odds came from
    game_date: str
    player_name: str
    line: float
    actual_stat: int
    went_over: bool

    model_p_over: float
    model_mean_stat: float
    model_pred_minutes: float
    model_pred_rate_per36: float
    model_pred_make_pct: float

    rolling_avg_p_over: float
    book_p_over: float

    odds_over: int
    odds_under: int
    closing_odds_over: int
    closing_odds_under: int

    stat_type: str = STAT_FG3M

    actual_minutes: float = 0.0
    actual_attempts: int = 0
    starter: bool = True

    edge: float = 0.0
    bet_side: str = ""
    bet_odds: int = 0
    bet_decimal: float = 0.0
    won: bool = False
    clv: float = 0.0
    spread: float = 0.0

    # Backward compatibility aliases
    @property
    def actual_3pm(self) -> int:
        return self.actual_stat

    @property
    def actual_3pa(self) -> int:
        return self.actual_attempts

    @property
    def model_mean_3pm(self) -> float:
        return self.model_mean_stat

    @property
    def model_pred_3pa_per36(self) -> float:
        return self.model_pred_rate_per36

    @property
    def model_pred_fg3_pct(self) -> float:
        return self.model_pred_make_pct


def evaluate_historical(
    props: list[PropRecord],
    player_logs: dict[str, list[dict]],
    min_ev_pct: float = 0.03,
) -> list[EvalRecord]:
    """Walk-forward evaluation against real historical props."""
    predictors: dict[str, ThreePMPredictor | AssistsPredictor] = {}
    records: list[EvalRecord] = []

    # Index logs by (name_lower, date)
    log_index: dict[str, dict[str, dict]] = {}
    for pname, logs in player_logs.items():
        log_index[pname.lower()] = {g["date"]: g for g in logs}

    for prop in sorted(props, key=lambda p: p.game_date):
        if prop.actual_stat < 0:
            continue  # skip unsettled

        matched = _find_player_logs(prop.player_name, log_index)
        if not matched:
            continue

        all_games = sorted(log_index[matched].values(), key=lambda g: g["date"])
        train = [g for g in all_games if g["date"] < prop.game_date]
        test_game = log_index[matched].get(prop.game_date)

        if len(train) < 5:
            continue

        # Get the right predictor for this stat type
        if prop.stat_type not in predictors:
            predictors[prop.stat_type] = get_predictor(prop.stat_type)
        predictor = predictors[prop.stat_type]

        pred = predictor.predict(train, prop.line)
        stat_field = BBREF_STAT_FIELD.get(prop.stat_type, "fg3")

        # Rolling average baseline (real data)
        recent = train[-15:]
        ra_over = sum(1 for g in recent if g[stat_field] > prop.line) / len(recent) if recent else 0.5

        # Bookmaker baseline (real odds, no-vig)
        bk_over, _ = remove_vig(prop.odds_over, prop.odds_under)

        went_over = prop.actual_stat > prop.line

        # Betting decision using real odds
        edge_over = pred["p_over"] - american_to_implied(prop.odds_over)
        edge_under = pred["p_under"] - american_to_implied(prop.odds_under)

        bet_side, edge, bet_odds = "", 0.0, 0
        if edge_over > min_ev_pct and edge_over > edge_under:
            bet_side, edge, bet_odds = "over", edge_over, prop.odds_over
        elif edge_under > min_ev_pct:
            bet_side, edge, bet_odds = "under", edge_under, prop.odds_under

        won = (bet_side == "over" and went_over) or (bet_side == "under" and not went_over)

        # CLV from real closing odds
        clv = 0.0
        if bet_side == "over":
            clv = american_to_implied(prop.odds_over) - american_to_implied(prop.closing_odds_over)
        elif bet_side == "under":
            clv = american_to_implied(prop.odds_under) - american_to_implied(prop.closing_odds_under)

        # Determine actual attempts field based on stat type
        if prop.stat_type == STAT_FG3M:
            actual_attempts = test_game["fg3a"] if test_game else 0
        else:
            actual_attempts = 0  # assists don't have an "attempts" analog

        records.append(EvalRecord(
            source=prop.source,
            game_date=prop.game_date,
            player_name=prop.player_name,
            line=prop.line,
            actual_stat=prop.actual_stat,
            went_over=went_over,
            model_p_over=pred["p_over"],
            model_mean_stat=pred["mean_stat"],
            model_pred_minutes=pred["pred_minutes"],
            model_pred_rate_per36=pred["pred_rate_per36"],
            model_pred_make_pct=pred["pred_make_pct"],
            rolling_avg_p_over=ra_over,
            book_p_over=bk_over,
            odds_over=prop.odds_over,
            odds_under=prop.odds_under,
            closing_odds_over=prop.closing_odds_over,
            closing_odds_under=prop.closing_odds_under,
            stat_type=prop.stat_type,
            actual_minutes=test_game["mp"] if test_game else 0,
            actual_attempts=actual_attempts,
            starter=test_game["starter"] if test_game else True,
            edge=edge,
            bet_side=bet_side,
            bet_odds=bet_odds,
            bet_decimal=american_to_decimal(bet_odds) if bet_odds else 0,
            won=won,
            clv=clv,
            spread=prop.spread,
        ))

    logger.info("Walk-forward: %d evaluation records", len(records))
    return records


def _resolve_player_team(
    player_games: list[dict], home_abbr: str, away_abbr: str,
) -> tuple[str, str, bool]:
    """Determine player's team, opponent, and home status from game logs + event."""
    if not player_games:
        return "", "", False
    # Use the most recent game log to identify the player's team
    last_team = player_games[-1].get("team", "")
    if last_team == home_abbr:
        return home_abbr, away_abbr, True
    elif last_team == away_abbr:
        return away_abbr, home_abbr, False
    # Fuzzy: team may have changed or abbreviation mismatch
    return last_team, "", False


def predict_live(
    props: list[PropRecord],
    player_logs: dict[str, list[dict]],
    min_ev_pct: float = 0.03,
) -> list[dict]:
    """Generate predictions for live/upcoming props using real odds.

    Now incorporates game context: spread, total, opponent defensive stats.
    """
    predictors: dict[str, ThreePMPredictor | AssistsPredictor] = {}
    predictions = []

    log_index: dict[str, dict[str, dict]] = {}
    for pname, logs in player_logs.items():
        log_index[pname.lower()] = {g["date"]: g for g in logs}

    # Fetch real opponent defensive stats from NBA.com
    opp_shooting = fetch_nba_opponent_shooting()
    opp_general = fetch_nba_opponent_general()
    team_advanced = fetch_nba_team_advanced()
    opp_tracking = fetch_nba_opp_tracking_shooting()
    synergy_defense = fetch_nba_synergy_defense()
    team_hustle = fetch_nba_team_hustle()
    opp_shot_clock = fetch_nba_opp_shot_clock()
    player_shooting = fetch_nba_player_shooting()
    synergy_player = fetch_nba_synergy_player()
    player_shot_clock = fetch_nba_player_shot_clock()
    player_advanced = fetch_nba_player_advanced()

    # Compute league averages from the real data for ratio normalization
    if opp_shooting:
        all_3pa = [v["opp_3pa_per_game"] for v in opp_shooting.values()]
        league_avg_3pa = sum(all_3pa) / len(all_3pa)
    else:
        league_avg_3pa = LEAGUE_AVG_3PA_PER_GAME
    if opp_general:
        all_ast = [v.get("opp_ast_per_game", 0) for v in opp_general.values()]
        league_avg_ast = sum(all_ast) / len(all_ast) if all_ast else LEAGUE_AVG_AST_PER_GAME
    else:
        league_avg_ast = LEAGUE_AVG_AST_PER_GAME
    # Tracking averages for ratio calculations
    if opp_tracking:
        all_wo = [v.get("opp_wide_open_3pa", 0) for v in opp_tracking.values()]
        all_cs = [v.get("opp_catch_shoot_3pa", 0) for v in opp_tracking.values()]
        avg_wide_open_3pa = sum(all_wo) / len(all_wo) if all_wo else 15.0
        avg_catch_shoot_3pa = sum(all_cs) / len(all_cs) if all_cs else 20.0
    else:
        avg_wide_open_3pa, avg_catch_shoot_3pa = 15.0, 20.0

    for prop in props:
        matched = _find_player_logs(prop.player_name, log_index)
        if not matched:
            continue

        all_games = sorted(log_index[matched].values(), key=lambda g: g["date"])
        if len(all_games) < 5:
            continue

        # Resolve player's team, opponent, and home status
        player_team, opp_team, is_home = _resolve_player_team(
            all_games, prop._home_abbr, prop._away_abbr,
        )

        # Build game context dict from real NBA.com data
        opp_shot = opp_shooting.get(opp_team, {})
        opp_gen = opp_general.get(opp_team, {})
        opp_adv = team_advanced.get(opp_team, {})
        opp_trk = opp_tracking.get(opp_team, {})
        player_team_adv = team_advanced.get(player_team, {})

        # Player shooting profile (try exact match then fuzzy)
        player_key = prop.player_name.lower()
        player_prof = player_shooting.get(player_key, {})
        if not player_prof:
            for ps_key in player_shooting:
                if _names_match(player_key, ps_key):
                    player_prof = player_shooting[ps_key]
                    break

        # Player synergy profile (try exact match then fuzzy)
        player_syn = synergy_player.get(player_key, {})
        if not player_syn:
            for sp_key in synergy_player:
                if _names_match(player_key, sp_key):
                    player_syn = synergy_player[sp_key]
                    break

        # Player shot clock profile
        player_sc = player_shot_clock.get(player_key, {})
        if not player_sc:
            for psc_key in player_shot_clock:
                if _names_match(player_key, psc_key):
                    player_sc = player_shot_clock[psc_key]
                    break

        # Player advanced stats (net rating, usage, etc.)
        player_adv = player_advanced.get(player_key, {})
        if not player_adv:
            for pa_key in player_advanced:
                if _names_match(player_key, pa_key):
                    player_adv = player_advanced[pa_key]
                    break

        # Opponent synergy defense & hustle & shot clock
        opp_syn = synergy_defense.get(opp_team, {})
        opp_hustle = team_hustle.get(opp_team, {})
        opp_sc = opp_shot_clock.get(opp_team, {})

        game_context = {
            # Game-level
            "spread": prop.spread if is_home else -prop.spread,
            "total": prop.total,
            "is_home": is_home,

            # Opponent shooting by zone (NBA.com)
            "opp_3pa_per_game": opp_shot.get("opp_3pa_per_game", 0.0),
            "opp_3pm_per_game": opp_shot.get("opp_3pm_per_game", 0.0),
            "opp_fg3_pct_allowed": opp_shot.get("opp_fg3_pct_allowed", 0.0),
            "opp_corner3_fga": opp_shot.get("opp_corner3_fga", 0.0),
            "opp_corner3_pct": opp_shot.get("opp_corner3_pct", 0.0),
            "opp_atb3_fga": opp_shot.get("opp_atb3_fga", 0.0),
            "opp_atb3_pct": opp_shot.get("opp_atb3_pct", 0.0),

            # Opponent tracking defense (NBA.com)
            "opp_wide_open_3pa": opp_trk.get("opp_wide_open_3pa", 0.0),
            "opp_wide_open_3pct": opp_trk.get("opp_wide_open_3pct", 0.0),
            "opp_open_3pa": opp_trk.get("opp_open_3pa", 0.0),
            "opp_open_3pct": opp_trk.get("opp_open_3pct", 0.0),
            "opp_tight_3pa": opp_trk.get("opp_tight_3pa", 0.0),
            "opp_tight_3pct": opp_trk.get("opp_tight_3pct", 0.0),
            "opp_catch_shoot_3pa": opp_trk.get("opp_catch_shoot_3pa", 0.0),
            "opp_catch_shoot_3pct": opp_trk.get("opp_catch_shoot_3pct", 0.0),
            "opp_pullup_3pa": opp_trk.get("opp_pullup_3pa", 0.0),
            "opp_pullup_3pct": opp_trk.get("opp_pullup_3pct", 0.0),

            # Opponent general stats
            "opp_ast_per_game": opp_gen.get("opp_ast_per_game", 0.0),
            "opp_tov_per_game": opp_gen.get("opp_tov_per_game", 0.0),
            "opp_pts_per_game": opp_gen.get("opp_pts_per_game", 0.0),

            # Team advanced (pace, ratings)
            "opp_pace": opp_adv.get("pace", 100.0),
            "opp_def_rating": opp_adv.get("def_rating", 110.0),
            "team_pace": player_team_adv.get("pace", 100.0),

            # Player shooting profile (NBA.com)
            "player_corner3_share": player_prof.get("corner3_share", 0.0),
            "player_atb3_share": player_prof.get("atb3_share", 0.0),
            "player_catch_shoot_share": player_prof.get("catch_shoot_share", 0.0),
            "player_catch_shoot_3pa": player_prof.get("catch_shoot_3pa", 0.0),
            "player_catch_shoot_3pct": player_prof.get("catch_shoot_3pct", 0.0),
            "player_self_created_share": player_prof.get("self_created_share", 0.0),
            "player_self_created_3pa": player_prof.get("self_created_3pa", 0.0),
            "player_wide_open_3pa": player_prof.get("wide_open_3pa", 0.0),
            "player_wide_open_3pct": player_prof.get("wide_open_3pct", 0.0),
            "player_tight_3pa": player_prof.get("tight_3pa", 0.0),
            "player_tight_3pct": player_prof.get("tight_3pct", 0.0),
            "player_corner3_pct": player_prof.get("corner3_pct", 0.0),
            "player_atb3_pct": player_prof.get("atb3_pct", 0.0),
            "player_total_3pa_pg": player_prof.get("total_3pa_pg", 0.0),

            # League averages for ratio calculations
            "sample_avg_3pa": league_avg_3pa,
            "sample_avg_ast": league_avg_ast,
            "sample_avg_wide_open_3pa": avg_wide_open_3pa,
            "sample_avg_catch_shoot_3pa": avg_catch_shoot_3pa,

            # Opponent synergy defense (PPP allowed by play type)
            "opp_def_spotup_ppp": opp_syn.get("def_spotup_ppp", 0.0),
            "opp_def_spotup_efg": opp_syn.get("def_spotup_efg", 0.0),
            "opp_def_spotup_freq": opp_syn.get("def_spotup_freq", 0.0),
            "opp_def_isolation_ppp": opp_syn.get("def_isolation_ppp", 0.0),
            "opp_def_isolation_efg": opp_syn.get("def_isolation_efg", 0.0),
            "opp_def_prballhandler_ppp": opp_syn.get("def_prballhandler_ppp", 0.0),
            "opp_def_prballhandler_efg": opp_syn.get("def_prballhandler_efg", 0.0),
            "opp_def_prrollman_ppp": opp_syn.get("def_prrollman_ppp", 0.0),
            "opp_def_offscreen_ppp": opp_syn.get("def_offscreen_ppp", 0.0),
            "opp_def_offscreen_efg": opp_syn.get("def_offscreen_efg", 0.0),
            "opp_def_transition_ppp": opp_syn.get("def_transition_ppp", 0.0),
            "opp_def_handoff_ppp": opp_syn.get("def_handoff_ppp", 0.0),
            "opp_def_cut_ppp": opp_syn.get("def_cut_ppp", 0.0),

            # Player offensive synergy (play type distribution & efficiency)
            "player_off_spotup_freq": player_syn.get("off_spotup_freq", 0.0),
            "player_off_spotup_ppp": player_syn.get("off_spotup_ppp", 0.0),
            "player_off_spotup_poss": player_syn.get("off_spotup_poss", 0.0),
            "player_off_isolation_freq": player_syn.get("off_isolation_freq", 0.0),
            "player_off_isolation_ppp": player_syn.get("off_isolation_ppp", 0.0),
            "player_off_prballhandler_freq": player_syn.get("off_prballhandler_freq", 0.0),
            "player_off_prballhandler_ppp": player_syn.get("off_prballhandler_ppp", 0.0),
            "player_off_prrollman_freq": player_syn.get("off_prrollman_freq", 0.0),
            "player_off_offscreen_freq": player_syn.get("off_offscreen_freq", 0.0),
            "player_off_offscreen_ppp": player_syn.get("off_offscreen_ppp", 0.0),
            "player_off_transition_freq": player_syn.get("off_transition_freq", 0.0),
            "player_off_handoff_freq": player_syn.get("off_handoff_freq", 0.0),
            "player_off_cut_freq": player_syn.get("off_cut_freq", 0.0),

            # Opponent hustle stats (defensive intensity)
            "opp_contested_shots_3pt": opp_hustle.get("contested_shots_3pt", 0.0),
            "opp_contested_shots": opp_hustle.get("contested_shots", 0.0),
            "opp_deflections": opp_hustle.get("deflections", 0.0),

            # Opponent shot clock defense (3PA allowed by clock phase)
            "opp_sc_early_3pa": opp_sc.get("sc_early_3pa", 0.0),
            "opp_sc_early_3pct": opp_sc.get("sc_early_3pct", 0.0),
            "opp_sc_normal_early_3pa": opp_sc.get("sc_normal_early_3pa", 0.0),
            "opp_sc_normal_3pa": opp_sc.get("sc_normal_3pa", 0.0),
            "opp_sc_late_3pa": opp_sc.get("sc_late_3pa", 0.0),
            "opp_sc_late_3pct": opp_sc.get("sc_late_3pct", 0.0),

            # Player passing/playmaking profile (for assists model)
            "player_passes_made": player_prof.get("passes_made", 0.0),
            "player_potential_ast": player_prof.get("potential_ast", 0.0),
            "player_ast_pts_created": player_prof.get("ast_pts_created", 0.0),
            "player_secondary_ast": player_prof.get("secondary_ast", 0.0),
            "player_touches": player_prof.get("touches", 0.0),
            "player_time_of_poss": player_prof.get("time_of_poss", 0.0),
            "player_drives": player_prof.get("drives", 0.0),
            "player_drive_ast": player_prof.get("drive_ast", 0.0),
            "player_drive_passes": player_prof.get("drive_passes", 0.0),

            # Player shot clock splits (3PA/3P% by clock phase)
            "player_sc_early_3pa": player_sc.get("sc_early_3pa", 0.0),
            "player_sc_early_3pct": player_sc.get("sc_early_3pct", 0.0),
            "player_sc_normal_3pa": player_sc.get("sc_normal_3pa", 0.0),
            "player_sc_normal_3pct": player_sc.get("sc_normal_3pct", 0.0),
            "player_sc_late_3pa": player_sc.get("sc_late_3pa", 0.0),
            "player_sc_late_3pct": player_sc.get("sc_late_3pct", 0.0),

            # Player advanced (on-court impact, usage context)
            "player_net_rating": player_adv.get("net_rating", 0.0),
            "player_off_rating": player_adv.get("off_rating", 0.0),
            "player_usg_pct": player_adv.get("usg_pct", 0.0),
            "player_ast_pct": player_adv.get("ast_pct", 0.0),
            "player_ast_ratio": player_adv.get("ast_ratio", 0.0),
            "player_ts_pct": player_adv.get("ts_pct", 0.0),
            "player_efg_pct": player_adv.get("efg_pct", 0.0),
            "player_pie": player_adv.get("pie", 0.0),
        }

        # Get the right predictor for this stat type
        if prop.stat_type not in predictors:
            predictors[prop.stat_type] = get_predictor(prop.stat_type)
        predictor = predictors[prop.stat_type]

        pred = predictor.predict(all_games, prop.line, game_context=game_context)
        bk_over, _ = remove_vig(prop.odds_over, prop.odds_under)

        edge_over = pred["p_over"] - american_to_implied(prop.odds_over)
        edge_under = pred["p_under"] - american_to_implied(prop.odds_under)

        bet_side, edge = "", 0.0
        if edge_over > min_ev_pct and edge_over > edge_under:
            bet_side, edge = "over", edge_over
        elif edge_under > min_ev_pct:
            bet_side, edge = "under", edge_under

        predictions.append({
            "player": prop.player_name,
            "stat_type": prop.stat_type,
            "line": prop.line,
            "odds_over": prop.odds_over,
            "odds_under": prop.odds_under,
            "model_p_over": pred["p_over"],
            "model_mean_stat": pred["mean_stat"],
            "model_mean_3pm": pred["mean_stat"],  # backward compat
            "book_p_over": bk_over,
            "pred_minutes": pred["pred_minutes"],
            "pred_rate_per36": pred["pred_rate_per36"],
            "pred_3pa_per36": pred["pred_rate_per36"],  # backward compat
            "pred_make_pct": pred["pred_make_pct"],
            "pred_fg3_pct": pred["pred_make_pct"],  # backward compat
            "edge_over": edge_over,
            "edge_under": edge_under,
            "bet_side": bet_side,
            "edge": edge,
            "confidence": pred["confidence"],
            "books": prop.books,
            "team": player_team,
            "opp": opp_team,
            "is_home": is_home,
            "game_context": game_context,
        })

    predictions.sort(key=lambda p: abs(p["edge"]), reverse=True)
    return predictions


# ── Metrics ──────────────────────────────────────────────────────────────────


def compute_metrics(records: list[EvalRecord], stat_type: str | None = None) -> dict:
    if stat_type:
        records = [r for r in records if r.stat_type == stat_type]
    if not records:
        return {}

    bets = [r for r in records if r.bet_side]
    n_total = len(records)
    n_bets = len(bets)

    # Determine the stat label
    label = stat_type or "all"

    model_probs = np.array([r.model_p_over for r in records])
    actuals = np.array([1.0 if r.went_over else 0.0 for r in records])
    eps = 1e-7

    # Log loss
    pc = np.clip(model_probs, eps, 1 - eps)
    log_loss = float(-np.mean(actuals * np.log(pc) + (1 - actuals) * np.log(1 - pc)))

    # Brier
    brier = float(np.mean((model_probs - actuals) ** 2))

    # Calibration
    cal = {}
    for lo, hi, label_cal in [(0, .3, "0-30%"), (.3, .4, "30-40%"), (.4, .5, "40-50%"),
                           (.5, .6, "50-60%"), (.6, .7, "60-70%"), (.7, 1, "70-100%")]:
        mask = (model_probs >= lo) & (model_probs < hi)
        if np.sum(mask) > 0:
            cal[label_cal] = {
                "n": int(np.sum(mask)),
                "pred": float(np.mean(model_probs[mask])),
                "actual": float(np.mean(actuals[mask])),
                "gap": float(abs(np.mean(model_probs[mask]) - np.mean(actuals[mask]))),
            }
    max_gap = max((b["gap"] for b in cal.values()), default=0)

    # Baselines
    bk = np.array([r.book_p_over for r in records])
    bk_ll = float(-np.mean(actuals * np.log(np.clip(bk, eps, 1-eps)) + (1-actuals) * np.log(np.clip(1-bk, eps, 1-eps))))
    bk_brier = float(np.mean((bk - actuals) ** 2))

    ra = np.clip(np.array([r.rolling_avg_p_over for r in records]), eps, 1-eps)
    ra_ll = float(-np.mean(actuals * np.log(ra) + (1-actuals) * np.log(1-ra)))
    ra_brier = float(np.mean((ra - actuals) ** 2))

    # Betting
    if bets:
        wins = [r for r in bets if r.won]
        hit_rate = len(wins) / len(bets)
        pnl = sum((r.bet_decimal - 1) if r.won else -1 for r in bets)
        roi = pnl / len(bets)
        avg_clv = float(np.mean([r.clv for r in bets]))
        avg_edge = float(np.mean([r.edge for r in bets]))

        cumsum = np.cumsum([(r.bet_decimal - 1) if r.won else -1 for r in bets])
        peak = np.maximum.accumulate(cumsum)
        max_dd = float(np.max(peak - cumsum))
    else:
        hit_rate = roi = avg_clv = avg_edge = max_dd = 0.0
        pnl = 0.0

    # Minutes MAE
    with_min = [r for r in records if r.actual_minutes > 0]
    if with_min:
        min_mae = float(np.mean(np.abs(
            np.array([r.model_pred_minutes for r in with_min]) -
            np.array([r.actual_minutes for r in with_min])
        )))
        starters = [r for r in with_min if r.starter]
        bench = [r for r in with_min if not r.starter]
        min_mae_s = float(np.mean(np.abs(
            np.array([r.model_pred_minutes for r in starters]) -
            np.array([r.actual_minutes for r in starters])
        ))) if starters else 0
        min_mae_b = float(np.mean(np.abs(
            np.array([r.model_pred_minutes for r in bench]) -
            np.array([r.actual_minutes for r in bench])
        ))) if bench else 0
    else:
        min_mae = min_mae_s = min_mae_b = 0

    # Attempts MAE (only for fg3m)
    with_att = [r for r in records if r.actual_attempts > 0]
    tpa_mae = float(np.mean(np.abs(
        np.array([r.model_pred_rate_per36 * r.actual_minutes / 36 for r in with_att]) -
        np.array([r.actual_attempts for r in with_att])
    ))) if with_att else 0

    # Stat MAE
    stat_mae = float(np.mean(np.abs(
        np.array([r.model_mean_stat for r in records]) -
        np.array([r.actual_stat for r in records])
    )))

    # By line
    line_bkts = {}
    # Determine buckets based on stat type
    if stat_type == STAT_ASSISTS:
        buckets = [("1.5", 1.4, 1.6), ("2.5", 2.4, 2.6), ("3.5", 3.4, 3.6),
                   ("4.5", 4.4, 4.6), ("5.5", 5.4, 5.6), ("6.5+", 6.4, 99)]
    else:
        buckets = [("0.5", .4, .6), ("1.5", 1.4, 1.6), ("2.5", 2.4, 2.6), ("3.5+", 3.4, 99)]

    for b_label, lo, hi in buckets:
        b_recs = [r for r in records if lo <= r.line <= hi]
        if b_recs:
            b_bets = [r for r in b_recs if r.bet_side]
            b_wins = [r for r in b_bets if r.won]
            line_bkts[b_label] = {
                "n": len(b_recs), "n_bets": len(b_bets),
                "hit": len(b_wins) / len(b_bets) if b_bets else 0,
                "roi": sum((r.bet_decimal-1) if r.won else -1 for r in b_bets) / len(b_bets) if b_bets else 0,
            }

    return {
        "stat_type": stat_type or "all",
        "n_predictions": n_total, "n_bets": n_bets,
        "log_loss": log_loss, "brier": brier,
        "calibration": cal, "max_cal_gap": max_gap,
        "book_log_loss": bk_ll, "book_brier": bk_brier,
        "ra_log_loss": ra_ll, "ra_brier": ra_brier,
        "hit_rate": hit_rate, "roi": roi, "pnl": pnl,
        "avg_clv": avg_clv, "avg_edge": avg_edge, "max_drawdown": max_dd,
        "min_mae": min_mae, "min_mae_starters": min_mae_s, "min_mae_bench": min_mae_b,
        "tpa_mae": tpa_mae, "stat_mae": stat_mae,
        "tpm_mae": stat_mae,  # backward compat
        "line_buckets": line_bkts,
    }


# ── Report ───────────────────────────────────────────────────────────────────

STAT_DISPLAY_NAMES = {
    STAT_FG3M: "3PM (FG3M)",
    STAT_ASSISTS: "Assists",
}


def format_report(
    metrics: dict,
    records: list[EvalRecord],
    live_preds: list[dict] | None = None,
    stat_type: str | None = None,
    all_metrics: dict[str, dict] | None = None,
) -> str:
    L = []
    sep = "=" * 78
    dash = "-" * 78

    stat_label = STAT_DISPLAY_NAMES.get(stat_type, "All Stats") if stat_type else "All Stats"
    stat_types_in_data = sorted(set(r.stat_type for r in records))

    L.append(sep)
    L.append(f"  NBA PLAYER PROPS ENGINE v2.0 — RC VALIDATION (REAL DATA ONLY)")
    L.append(f"  Stat Type: {stat_label}")
    L.append(f"  Generated: {datetime.utcnow().isoformat()[:19]}Z")
    L.append(f"  Data: basketball-reference.com game logs + sportsbook odds")
    L.append(sep)
    L.append("")

    # If we have multiple stat types and all_metrics, show combined summary first
    if all_metrics and len(all_metrics) > 1:
        L.append("  0. MULTI-STAT OVERVIEW")
        L.append(dash)
        L.append(f"  {'Stat Type':<16} {'N':>6} {'Bets':>6} {'LogLoss':>9} {'Brier':>8} {'Hit%':>7} {'ROI':>8} {'CLV':>8}")
        for st, m in sorted(all_metrics.items()):
            st_name = STAT_DISPLAY_NAMES.get(st, st)
            L.append(
                f"  {st_name:<16} {m['n_predictions']:>6} {m['n_bets']:>6} "
                f"{m['log_loss']:>9.4f} {m['brier']:>8.4f} "
                f"{m['hit_rate']:>6.1%} {m['roi']:>+7.1%} {m['avg_clv']:>+7.4f}"
            )
        L.append("")

    # 1. Summary
    n = metrics["n_predictions"]
    nb = metrics["n_bets"]
    L.append("  1. EVALUATION SUMMARY")
    L.append(dash)
    L.append(f"  Predictions:  {n:,}")
    L.append(f"  Bets placed:  {nb:,}  ({nb/n*100:.1f}% bet rate)" if n else "")
    L.append("")

    # 2. Model accuracy
    stat_col = "Stat" if stat_type != STAT_FG3M else "3PM"
    L.append("  2. MODEL ACCURACY")
    L.append(dash)
    L.append(f"  Minutes MAE (starters):  {metrics['min_mae_starters']:.2f}    (target <= 2.8)")
    L.append(f"  Minutes MAE (bench):     {metrics['min_mae_bench']:.2f}    (target <= 3.5)")
    if metrics.get("tpa_mae", 0) > 0:
        L.append(f"  Attempts MAE:            {metrics['tpa_mae']:.2f}")
    L.append(f"  {stat_col} MAE:                 {metrics['stat_mae']:.2f}")
    L.append("")

    # 3. Calibration
    L.append("  3. CALIBRATION")
    L.append(dash)
    L.append(f"  {'Source':<14} {'Log Loss':>10} {'Brier':>10}")
    L.append(f"  {'Model':<14} {metrics['log_loss']:>10.4f} {metrics['brier']:>10.4f}")
    L.append(f"  {'Bookmaker':<14} {metrics['book_log_loss']:>10.4f} {metrics['book_brier']:>10.4f}")
    L.append(f"  {'Rolling Avg':<14} {metrics['ra_log_loss']:>10.4f} {metrics['ra_brier']:>10.4f}")
    L.append("")
    cal = metrics.get("calibration", {})
    if cal:
        L.append(f"  {'Bucket':<12} {'N':>6} {'Pred':>8} {'Actual':>8} {'Gap':>8}")
        for label, b in sorted(cal.items()):
            L.append(f"  {label:<12} {b['n']:>6} {b['pred']:>8.3f} {b['actual']:>8.3f} {b['gap']:>8.3f}")
    L.append("")

    # 4. Betting
    L.append("  4. BETTING (real odds, 1u flat stakes)")
    L.append(dash)
    L.append(f"  Hit rate:     {metrics['hit_rate']:.1%}")
    L.append(f"  ROI:          {metrics['roi']:+.1%}")
    L.append(f"  P&L:          {metrics['pnl']:+.2f} units")
    L.append(f"  Avg CLV:      {metrics['avg_clv']:+.4f}")
    L.append(f"  Avg edge:     {metrics['avg_edge']:+.4f}")
    L.append(f"  Max drawdown: {metrics['max_drawdown']:.2f} units")
    L.append("")

    # 5. By line
    lb = metrics.get("line_buckets", {})
    if lb:
        L.append("  5. BY LINE")
        L.append(dash)
        L.append(f"  {'Line':<8} {'N':>6} {'Bets':>6} {'Hit%':>8} {'ROI':>9}")
        for b_label in sorted(lb.keys(), key=lambda x: float(x.replace("+", ""))):
            b = lb[b_label]
            L.append(f"  {b_label:<8} {b['n']:>6} {b['n_bets']:>6} {b['hit']:>7.1%} {b['roi']:>8.1%}")
        L.append("")

    # 6. Paper ledger (last 25)
    bets = [r for r in records if r.bet_side]
    if stat_type:
        bets = [r for r in bets if r.stat_type == stat_type]
    if bets:
        L.append("  6. PAPER BET LEDGER (last 25)")
        L.append(dash)
        L.append(f"  {'Date':<12} {'Player':<22} {'Stat':<6} {'Side':<6} {'Ln':>4} {'Odds':>6} {'Act':>4} {'W/L':>4} {'Edge':>6} {'CLV':>7}")
        for r in bets[-25:]:
            st_short = "3PM" if r.stat_type == STAT_FG3M else "AST"
            L.append(
                f"  {r.game_date:<12} {r.player_name[:21]:<22} {st_short:<6} {r.bet_side:<6} "
                f"{r.line:>4.1f} {r.bet_odds:>+6} {r.actual_stat:>4} "
                f"{'W' if r.won else 'L':>4} {r.edge:>5.3f} {r.clv:>+6.3f}"
            )
        L.append("")

    # 7. Promotion gates
    L.append("  7. PROMOTION GATES")
    L.append(dash)
    gates = [
        ("Positive OOS CLV", metrics["avg_clv"] > 0,
         f"CLV = {metrics['avg_clv']:+.4f}"),
        ("Calibration gap < 0.05", metrics["max_cal_gap"] < 0.05,
         f"Max gap = {metrics['max_cal_gap']:.4f}"),
        ("Minutes MAE starters <= 2.8", metrics["min_mae_starters"] <= 2.8,
         f"MAE = {metrics['min_mae_starters']:.2f}"),
        ("Minutes MAE bench <= 3.5", metrics["min_mae_bench"] <= 3.5,
         f"MAE = {metrics['min_mae_bench']:.2f}"),
        ("Beats book (log loss)", metrics["log_loss"] < metrics["book_log_loss"],
         f"{metrics['log_loss']:.4f} vs {metrics['book_log_loss']:.4f}"),
        ("Beats rolling avg (log loss)", metrics["log_loss"] < metrics["ra_log_loss"],
         f"{metrics['log_loss']:.4f} vs {metrics['ra_log_loss']:.4f}"),
        (">=100 paper bets", nb >= 100, f"{nb} bets"),
        ("Positive ROI", metrics["roi"] > 0, f"ROI = {metrics['roi']:+.1%}"),
    ]
    for name, passed, detail in gates:
        s = "PASS" if passed else "FAIL"
        m = "  " if passed else "**"
        L.append(f"  {m}[{s}] {name:<32} {detail}")

    n_pass = sum(1 for _, p, _ in gates if p)
    L.append("")
    L.append(f"  VERDICT: {'PROMOTED' if n_pass == len(gates) else 'BLOCKED'} ({n_pass}/{len(gates)} gates)")
    L.append(sep)

    # 8. Live predictions
    if live_preds:
        filtered_preds = live_preds
        if stat_type:
            filtered_preds = [p for p in live_preds if p.get("stat_type") == stat_type]

        if filtered_preds:
            L.append("")
            L.append(f"  8. LIVE PREDICTIONS (real odds from The Odds API)")
            L.append(dash)
            L.append(f"  {'Player':<22} {'Stat':<5} {'Ln':>4} {'Odds':>12} {'Model':>7} {'Book':>6} {'Edge':>7} {'Bet':>6}")
            for p in filtered_preds[:30]:
                odds_str = f"{p['odds_over']:+d}/{p['odds_under']:+d}"
                bet_str = p["bet_side"].upper() if p["bet_side"] else "—"
                st_short = "3PM" if p.get("stat_type") == STAT_FG3M else "AST"
                L.append(
                    f"  {p['player'][:21]:<22} {st_short:<5} {p['line']:>4.1f} {odds_str:>12} "
                    f"{p['model_p_over']:>6.1%} {p['book_p_over']:>5.1%} "
                    f"{p['edge']:>+6.3f} {bet_str:>6}"
                )
            L.append(sep)

    return "\n".join(L)


# ── Main ─────────────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="NBA Player Props Engine v2.0 — Real Data Only Validation (fg3m + assists)",
    )
    parser.add_argument("--start-date", default="2025-01-01")
    parser.add_argument("--end-date", default="2025-03-03")
    parser.add_argument("--output-dir", default="validation_output")
    parser.add_argument("--skip-live", action="store_true", help="Skip live Odds API fetch")
    parser.add_argument("--sgo-start", default=None, help="SGO fetch start date (if quota available)")
    parser.add_argument("--sgo-end", default=None, help="SGO fetch end date")
    parser.add_argument(
        "--stat-types",
        default="fg3m,assists",
        help="Comma-separated stat types to run (default: fg3m,assists)",
    )
    args = parser.parse_args()

    # Parse stat types
    requested_stats = tuple(s.strip() for s in args.stat_types.split(","))
    for st in requested_stats:
        if st not in SUPPORTED_STATS:
            logger.error("Unsupported stat type: %s (supported: %s)", st, ", ".join(SUPPORTED_STATS))
            return

    logger.info("=" * 60)
    logger.info("NBA Player Props Engine v2.0 — REAL DATA VALIDATION")
    logger.info("Stat types: %s", ", ".join(requested_stats))
    logger.info("=" * 60)

    # ── Load real BBRef game logs ──
    player_logs = load_bbref_game_logs()
    if not player_logs:
        return

    # ── Get real props ──
    props: list[PropRecord] = []

    # Try SGO historical if requested and quota allows
    if args.sgo_start and args.sgo_end:
        try:
            events = fetch_sgo_events(args.sgo_start, args.sgo_end)
            props.extend(extract_sgo_props(events, stat_types=requested_stats))
        except Exception as e:
            logger.warning("SGO fetch failed: %s", e)

    # ── Get live props from Odds API ──
    live_preds = None
    if not args.skip_live:
        try:
            live_props = fetch_odds_api_live_props(stat_types=requested_stats)
            if live_props:
                live_preds = predict_live(live_props, player_logs)
                logger.info("Generated %d live predictions", len(live_preds))
        except Exception as e:
            logger.warning("Odds API fetch failed: %s", e)

    # ── Historical evaluation ──
    records: list[EvalRecord] = []
    if props:
        logger.info("Running historical evaluation on %d real props...", len(props))
        records = evaluate_historical(props, player_logs)
    else:
        logger.info("No historical props with real odds available.")
        logger.info("Run with --sgo-start/--sgo-end when SGO quota resets,")
        logger.info("or results below use model accuracy metrics only.")

    # If no SGO props, run model accuracy evaluation using BBRef data alone
    if not records:
        logger.info("Computing model accuracy from BBRef game logs only...")
        records = _evaluate_model_accuracy_only(
            player_logs, args.start_date, args.end_date,
            stat_types=requested_stats,
        )

    if not records:
        logger.error("No records produced.")
        return

    # Compute metrics per stat type and combined
    all_metrics: dict[str, dict] = {}
    for st in requested_stats:
        st_records = [r for r in records if r.stat_type == st]
        if st_records:
            all_metrics[st] = compute_metrics(st_records, stat_type=st)

    # Generate reports per stat type
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    for st in requested_stats:
        st_metrics = all_metrics.get(st)
        if not st_metrics:
            logger.warning("No records for stat type %s, skipping report", st)
            continue

        st_records = [r for r in records if r.stat_type == st]
        report = format_report(
            st_metrics, st_records, live_preds,
            stat_type=st, all_metrics=all_metrics,
        )
        print(report)
        print()

        (out_dir / f"validation_report_{st}_{ts}.txt").write_text(report)
        (out_dir / f"validation_metrics_{st}_{ts}.json").write_text(
            json.dumps(st_metrics, indent=2, default=str)
        )

    # Save combined metrics
    (out_dir / f"validation_metrics_combined_{ts}.json").write_text(
        json.dumps(all_metrics, indent=2, default=str)
    )

    logger.info("Saved reports to %s", out_dir)


def _evaluate_model_accuracy_only(
    player_logs: dict[str, list[dict]],
    start_date: str,
    end_date: str,
    stat_types: tuple[str, ...] = (STAT_FG3M,),
) -> list[EvalRecord]:
    """Evaluate model prediction accuracy using ONLY real BBRef stats.

    Since we have no real odds here, betting metrics (ROI, CLV) are not
    computed — those require real sportsbook lines.
    """
    predictors: dict[str, ThreePMPredictor | AssistsPredictor] = {}
    records = []

    for pname, games in player_logs.items():
        games_sorted = sorted(games, key=lambda g: g["date"])
        for i, game in enumerate(games_sorted):
            if game["date"] < start_date or game["date"] > end_date:
                continue
            if i < 10:
                continue

            train = games_sorted[:i]

            for stat_type in stat_types:
                stat_field = BBREF_STAT_FIELD.get(stat_type, "fg3")

                # Get predictor
                if stat_type not in predictors:
                    predictors[stat_type] = get_predictor(stat_type)
                predictor = predictors[stat_type]

                # Evaluate at standard lines this player would see
                recent_vals = [g[stat_field] for g in train[-15:]]
                avg_val = np.mean(recent_vals)

                if stat_type == STAT_FG3M:
                    if avg_val < 1.3:
                        line = 0.5
                    elif avg_val < 2.3:
                        line = 1.5
                    elif avg_val < 3.3:
                        line = 2.5
                    else:
                        line = 3.5
                elif stat_type == STAT_ASSISTS:
                    if avg_val < 2.3:
                        line = 1.5
                    elif avg_val < 3.3:
                        line = 2.5
                    elif avg_val < 4.3:
                        line = 3.5
                    elif avg_val < 5.3:
                        line = 4.5
                    elif avg_val < 6.3:
                        line = 5.5
                    elif avg_val < 8.0:
                        line = 6.5
                    else:
                        line = 8.5
                else:
                    line = 2.5

                pred = predictor.predict(train, line)
                actual_val = game[stat_field]
                went_over = actual_val > line

                # Determine actual attempts
                if stat_type == STAT_FG3M:
                    actual_attempts = game["fg3a"]
                else:
                    actual_attempts = 0

                records.append(EvalRecord(
                    source="bbref_accuracy",
                    game_date=game["date"],
                    player_name=pname,
                    line=line,
                    actual_stat=actual_val,
                    went_over=went_over,
                    model_p_over=pred["p_over"],
                    model_mean_stat=pred["mean_stat"],
                    model_pred_minutes=pred["pred_minutes"],
                    model_pred_rate_per36=pred["pred_rate_per36"],
                    model_pred_make_pct=pred["pred_make_pct"],
                    rolling_avg_p_over=sum(1 for g in train[-15:] if g[stat_field] > line) / min(len(train), 15),
                    book_p_over=0.5,  # no real odds — bookmaker baseline N/A
                    odds_over=0, odds_under=0,
                    closing_odds_over=0, closing_odds_under=0,
                    stat_type=stat_type,
                    actual_minutes=game["mp"],
                    actual_attempts=actual_attempts,
                    starter=game.get("starter", True),
                    # No betting — no real odds to bet against
                ))

    for st in stat_types:
        count = sum(1 for r in records if r.stat_type == st)
        logger.info("Model accuracy (%s): %d records from real BBRef stats", st, count)
    return records


if __name__ == "__main__":
    main()
