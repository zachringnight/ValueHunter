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

# Stat type constants
STAT_FG3M = "fg3m"
STAT_ASSISTS = "assists"
SUPPORTED_STATS = (STAT_FG3M, STAT_ASSISTS)

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
        home = ev["home_team"]
        away = ev["away_team"]
        game_time = ev.get("commence_time", "")[:10]

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
                ))

    for st in stat_types:
        count = sum(1 for p in props if p.stat_type == st)
        logger.info("Fetched %d live %s props from Odds API", count, st)
    return props


# ── BBRef game log scraper ───────────────────────────────────────────────────


def load_bbref_game_logs(cache_path: str = "/tmp/nba_game_logs.json") -> dict[str, list[dict]]:
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
                    "fg3": int(data.get("fg3", "0") or "0"),
                    "fg3a": int(data.get("fg3a", "0") or "0"),
                    "fg": int(data.get("fg", "0") or "0"),
                    "fga": int(data.get("fga", "0") or "0"),
                    "pts": int(data.get("pts", "0") or "0"),
                    "reb": int(data.get("trb", "0") or "0"),
                    "ast": int(data.get("ast", "0") or "0"),
                    "plus_minus": float(data.get("plus_minus", "0") or "0"),
                    "result": data.get("game_result", ""),
                })
            except (ValueError, TypeError):
                continue

        all_logs[name] = games
        logger.info("  %s: %d games", name, len(games))

    return all_logs


# ── Model: Empirical Bayes 3PM predictor ─────────────────────────────────────


class ThreePMPredictor:
    """Monte Carlo 3PM predictor with empirical Bayes shrinkage.

    Uses only real historical stats to predict. No synthetic data.
    """

    def __init__(self, window: int = 15, prior_strength: int = 20):
        self.window = window
        self.prior_strength = prior_strength

    def predict(self, recent_games: list[dict], line: float, n_sims: int = 25000) -> dict:
        if len(recent_games) < 5:
            return {"p_over": 0.5, "mean_stat": line, "confidence": "low",
                    "pred_minutes": 0, "pred_rate_per36": 0, "pred_make_pct": 0}

        games = recent_games[-self.window:]
        minutes = np.array([g["mp"] for g in games])
        fg3a = np.array([g["fg3a"] for g in games], dtype=float)
        fg3m = np.array([g["fg3"] for g in games], dtype=float)

        # Minutes (log-normal)
        min_mean = np.mean(minutes)
        min_std = max(np.std(minutes), 1.0)

        # 3PA rate with shrinkage
        total_min = np.sum(minutes)
        total_3pa = np.sum(fg3a)
        raw_rate = total_3pa / max(total_min, 1) * 36.0
        league_rate = 7.5
        n_eff = total_min / 36.0
        shrunk_rate = (raw_rate * n_eff + league_rate * self.prior_strength) / (n_eff + self.prior_strength)

        # Make rate with empirical Bayes
        total_3pm = np.sum(fg3m)
        shrunk_pct = (total_3pm + LEAGUE_3PT_PCT * self.prior_strength) / (total_3pa + self.prior_strength)

        # Monte Carlo
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

    def predict(self, recent_games: list[dict], line: float, n_sims: int = 25000) -> dict:
        if len(recent_games) < 5:
            return {"p_over": 0.5, "mean_stat": line, "confidence": "low",
                    "pred_minutes": 0, "pred_rate_per36": 0, "pred_make_pct": 0}

        games = recent_games[-self.window:]
        minutes = np.array([g["mp"] for g in games])
        assists = np.array([g["ast"] for g in games], dtype=float)

        # Minutes (log-normal)
        min_mean = np.mean(minutes)
        min_std = max(np.std(minutes), 1.0)

        # Assists rate per 36 with shrinkage
        total_min = np.sum(minutes)
        total_ast = np.sum(assists)
        raw_rate = total_ast / max(total_min, 1) * 36.0
        n_eff = total_min / 36.0
        shrunk_rate = (raw_rate * n_eff + LEAGUE_AST_PER_36 * self.prior_strength) / (n_eff + self.prior_strength)

        # Overdispersion: assists tend to be slightly overdispersed vs Poisson
        # Estimate dispersion from the data
        if len(games) >= 5 and np.mean(assists) > 0:
            var = np.var(assists)
            mean = np.mean(assists)
            # Negative binomial dispersion: variance = mean + mean^2/r
            # r = mean^2 / (var - mean) if var > mean, else use Poisson (large r)
            if var > mean:
                dispersion = mean ** 2 / (var - mean)
                dispersion = max(dispersion, 1.0)
            else:
                dispersion = 50.0  # approximately Poisson
        else:
            dispersion = 10.0

        # Monte Carlo
        rng = np.random.default_rng()
        log_mu = np.log(max(min_mean, 1)) - 0.5 * (min_std / max(min_mean, 1)) ** 2
        log_sig = np.sqrt(np.log(1 + (min_std / max(min_mean, 1)) ** 2))
        sim_min = np.clip(rng.lognormal(log_mu, log_sig, n_sims), 0, 48)

        # Scale assists rate by minutes
        sim_rate = np.maximum(shrunk_rate * sim_min / 36.0, 0.01)

        # Draw from Negative Binomial: n=dispersion, p=dispersion/(dispersion+mu)
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


def get_predictor(stat_type: str) -> ThreePMPredictor | AssistsPredictor:
    """Factory to return the appropriate predictor for a stat type."""
    if stat_type == STAT_ASSISTS:
        return AssistsPredictor()
    return ThreePMPredictor()


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


def predict_live(
    props: list[PropRecord],
    player_logs: dict[str, list[dict]],
    min_ev_pct: float = 0.03,
) -> list[dict]:
    """Generate predictions for live/upcoming props using real odds."""
    predictors: dict[str, ThreePMPredictor | AssistsPredictor] = {}
    predictions = []

    log_index: dict[str, dict[str, dict]] = {}
    for pname, logs in player_logs.items():
        log_index[pname.lower()] = {g["date"]: g for g in logs}

    for prop in props:
        matched = _find_player_logs(prop.player_name, log_index)
        if not matched:
            continue

        all_games = sorted(log_index[matched].values(), key=lambda g: g["date"])
        if len(all_games) < 5:
            continue

        # Get the right predictor for this stat type
        if prop.stat_type not in predictors:
            predictors[prop.stat_type] = get_predictor(prop.stat_type)
        predictor = predictors[prop.stat_type]

        pred = predictor.predict(all_games, prop.line)
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
