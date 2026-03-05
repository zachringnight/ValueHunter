#!/usr/bin/env python3
"""Run the betting model for today's games.

Fetches BBRef game logs, live odds, NBA.com advanced data,
and generates predictions with all advanced matchup features.
"""

import json
import logging
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from nba_props.validation.real_data_runner import (
    ODDS_API_KEY,
    ODDS_API_BASE,
    BBREF_HEADERS,
    _ODDS_API_TO_BBREF,
    fetch_odds_api_live_props,
    predict_live,
    scrape_bbref_game_logs,
    STAT_FG3M,
    STAT_ASSISTS,
)


# BBRef team roster page slugs
# Maps BBRef team abbr -> BBRef team page code
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


def get_tonight_teams():
    """Get list of team abbreviations playing tonight from the Odds API."""
    resp = requests.get(
        f"{ODDS_API_BASE}/sports/basketball_nba/events",
        params={"apiKey": ODDS_API_KEY}, timeout=15,
    )
    resp.raise_for_status()
    events = resp.json()
    teams = set()
    for ev in events:
        home = _ODDS_API_TO_BBREF.get(ev["home_team"], "")
        away = _ODDS_API_TO_BBREF.get(ev["away_team"], "")
        if home:
            teams.add(home)
        if away:
            teams.add(away)
    logger.info("Tonight's teams: %s", ", ".join(sorted(teams)))
    return sorted(teams)


def get_team_roster_slugs(team_abbr: str, season: int = 2026) -> dict[str, str]:
    """Scrape player name -> BBRef slug from a team's roster page."""
    code = _BBREF_TEAM_CODES.get(team_abbr, team_abbr)
    url = f"https://www.basketball-reference.com/teams/{code}/{season}.html"
    time.sleep(3.5)  # respect rate limit
    resp = requests.get(url, headers=BBREF_HEADERS, timeout=30)
    if resp.status_code != 200:
        logger.warning("Failed to get roster for %s: %d", team_abbr, resp.status_code)
        return {}

    soup = BeautifulSoup(resp.text, "html.parser")
    roster_table = soup.find("table", {"id": "roster"})
    if not roster_table:
        logger.warning("No roster table found for %s", team_abbr)
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
        # Extract slug: /players/c/curryst01.html -> c/curryst01
        parts = href.split("/players/")
        if len(parts) == 2:
            slug = parts[1].replace(".html", "")
            slugs[name] = slug

    logger.info("  %s: %d players", team_abbr, len(slugs))
    return slugs


def main():
    cache_path = Path("/tmp/nba_game_logs.json")

    # Step 1: Get tonight's teams
    logger.info("=" * 60)
    logger.info("NBA PROPS MODEL — %s", "Finding today's bets")
    logger.info("=" * 60)

    teams = get_tonight_teams()

    # Step 2: Scrape BBRef game logs for all players on tonight's teams
    if cache_path.exists():
        # Check age of cache
        import os
        from datetime import datetime
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        age_hours = (datetime.now() - mtime).total_seconds() / 3600
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

        logger.info("Scraping game logs for %d players...", len(all_slugs))
        all_logs = scrape_bbref_game_logs(all_slugs, season=2026)

        # Cache the results
        cache_data = {name: {"games": games} for name, games in all_logs.items()}
        with open(cache_path, "w") as f:
            json.dump(cache_data, f)
        logger.info("Cached %d player logs to %s", len(all_logs), cache_path)

    logger.info("Loaded game logs for %d players", len(all_logs))

    # Step 3: Fetch live props from Odds API
    logger.info("Fetching live props from Odds API...")
    stat_types = (STAT_FG3M, STAT_ASSISTS)
    try:
        live_props = fetch_odds_api_live_props(stat_types=stat_types)
    except Exception as e:
        logger.error("Failed to fetch live props: %s", e)
        return

    if not live_props:
        logger.error("No live props available")
        return

    logger.info("Got %d live props total", len(live_props))

    # Step 4: Run the model with all advanced features
    logger.info("Running model predictions with advanced matchup data...")
    predictions = predict_live(live_props, all_logs, min_ev_pct=0.02)

    # Step 5: Display results
    bets = [p for p in predictions if p["bet_side"]]
    no_bets = [p for p in predictions if not p["bet_side"]]

    print("\n" + "=" * 80)
    print("  NBA PLAYER PROPS — BETTING RECOMMENDATIONS FOR TODAY")
    print("  Model: Advanced matchup (synergy + tracking + scheme + game context)")
    print("=" * 80)

    if bets:
        # Sort by edge
        bets.sort(key=lambda p: abs(p["edge"]), reverse=True)

        # Separate by stat type
        for stat_type in stat_types:
            st_bets = [b for b in bets if b.get("stat_type", STAT_FG3M) == stat_type]
            if not st_bets:
                continue

            label = "THREE-POINTERS MADE (3PM)" if stat_type == STAT_FG3M else "ASSISTS"
            print(f"\n{'─' * 80}")
            print(f"  {label} — {len(st_bets)} bet(s) found")
            print(f"{'─' * 80}")

            for i, pred in enumerate(st_bets, 1):
                side = pred["bet_side"].upper()
                edge_pct = pred["edge"] * 100
                model_p = pred["model_p_over"] * 100
                book_p = pred["book_p_over"] * 100
                mean_stat = pred["model_mean_stat"]
                conf = pred.get("confidence", 0)

                # Game context details
                ctx = pred.get("game_context", {})
                spread = ctx.get("spread", 0)
                total = ctx.get("total", 0)
                opp = pred.get("opp", "")
                team = pred.get("team", "")

                # Find best book odds for this side
                books = pred.get("books", {})
                if side == "OVER":
                    best_odds = pred["odds_over"]
                    for bk, prices in books.items():
                        if prices.get("over", -999) > best_odds:
                            best_odds = prices["over"]
                else:
                    best_odds = pred["odds_under"]
                    for bk, prices in books.items():
                        if prices.get("under", -999) > best_odds:
                            best_odds = prices["under"]

                print(f"\n  #{i}  {pred['player']}")
                print(f"      {side} {pred['line']} ({'+' if best_odds > 0 else ''}{best_odds})")
                print(f"      Team: {team} vs {opp} | Spread: {spread:+.1f} | Total: {total:.0f}")
                print(f"      Model Proj: {mean_stat:.2f} | Edge: {edge_pct:+.1f}%")
                print(f"      Model P(over): {model_p:.1f}% vs Book: {book_p:.1f}%")
                print(f"      Pred Minutes: {pred['pred_minutes']:.1f} | Rate/36: {pred['pred_rate_per36']:.2f} | Make%: {pred['pred_make_pct']:.1%}")
                print(f"      Confidence: {conf}")

                # Show book comparison
                if len(books) > 1:
                    book_str = " | ".join(
                        f"{bk}: O{p.get('over','')}/U{p.get('under','')}"
                        for bk, p in sorted(books.items())
                    )
                    print(f"      Books: {book_str}")

        print(f"\n{'=' * 80}")
        print(f"  TOTAL: {len(bets)} bets from {len(predictions)} analyzed props")
        print(f"  Average edge: {sum(b['edge'] for b in bets)/len(bets)*100:+.1f}%")
        print(f"{'=' * 80}\n")
    else:
        print("\n  No bets found meeting minimum edge threshold.")
        print(f"  Analyzed {len(predictions)} props.\n")

    # Save predictions to file
    out_path = Path("validation_output/live_predictions_today.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(predictions, f, indent=2, default=str)
    logger.info("Saved %d predictions to %s", len(predictions), out_path)


if __name__ == "__main__":
    main()
