# ValueHunter Platform — Independent Technical Evaluation

**Evaluator:** Claude (AI Technical Advisor)
**Date:** March 7, 2026
**Commissioned by:** Prospective gambling syndicate buyer

---

## Executive Summary

ValueHunter is an **NBA player-prop pricing engine** focused primarily on **3-pointers made (3PM)** and **assists** markets. It uses a decomposition modeling approach (minutes → shot attempts → make rate) with Monte Carlo simulation to generate distributional forecasts, compares them against sportsbook lines, and outputs actionable betting recommendations with edge estimates and position sizing.

**Current state: Late-stage prototype / early production.** The core modeling pipeline is architecturally sound and demonstrates real domain expertise, but several critical gaps exist before a professional syndicate could deploy it at scale with confidence.

**Bottom-line current value: $15,000–$40,000** as intellectual property + working code.
**Potential post-improvement value: $150,000–$500,000+** annually in operational edge, depending on bankroll size and market access.

---

## 1. Current Functionality Assessment

### What Works Well

#### A. Modeling Architecture (Grade: A-)
The decomposition pipeline is the right approach. Rather than naively predicting 3PM directly, the system separates:

1. **Minutes model** — projects playing time distribution (p10/p50/p90) accounting for blowout risk, rest days, injury status, teammate availability
2. **3PA opportunity model** — projects shot attempts conditional on minutes, using opponent defensive scheme data (Synergy play types, zone shooting, tracking data)
3. **Make rate model** — projects shooting accuracy conditional on shot quality, opponent defense, and player archetype
4. **Monte Carlo simulation** (25,000 draws) — combines all three into a full 3PM distribution via Binomial(3PA, make_prob)

This is exactly how a sophisticated quant shop would structure this problem. The decomposition allows each sub-model to be validated independently, and the Monte Carlo produces calibrated probability distributions rather than point estimates.

**Key technical strengths:**
- Log-normal minutes distribution with quantile fitting (realistic tail behavior for blowouts)
- Negative binomial for 3PA (correctly handles count overdispersion)
- Beta distribution for make probability with uncertainty propagation
- Alt-line pricing across multiple lines (0.5 through 5.5) — exploitable for line shopping
- Leakage detection built into the feature pipeline (SHA-256 hashing of feature snapshots, temporal validation)

#### B. Feature Engineering (Grade: B+)
The feature set is rich and domain-appropriate:

- **Rolling averages** at multiple windows (L3/L5/L10/L20) — captures recent form vs. baseline
- **Opponent defensive data** — zone shooting, play-type defense (PnR, spot-up, transition), wide-open 3PA allowed
- **NBA tracking data** — catch-and-shoot vs. pull-up splits, touch data, shot clock distributions
- **Player archetypes** — classifies players into five types (movement_wing_shooter, pull_up_guard, stretch_big, stationary_spacer, bench_microwave) which inform model behavior
- **Game context** — spread, total, pace, home/away, rest days, back-to-back flags
- **Injury/teammate adjustments** — teammate out → usage redistribution

**26,080 lines of Python** across a well-organized package structure.

#### C. Decision Engine (Grade: B+)
The bet decision pipeline is professionally structured:

- **Power method vig removal** — superior to naive multiplicative devig; correctly distributes overround proportionally
- **Edge and EV thresholds** — minimum 3% EV, 2.5 probability-point edge required
- **Staleness checks** — odds older than 30 minutes are rejected
- **Hold monitoring** — rejects markets with >12% hold (thin/illiquid)
- **Kelly criterion staking** — quarter-Kelly option with caps
- **Correlation limits** — max 3 same-game positions, no same-team over stacking, max 2% game exposure
- **Line shopping** — compares across sportsbooks and selects best available price

#### D. Validation Framework (Grade: B)
Extensive validation infrastructure exists:

- **Walk-forward backtesting** with expanding windows and strict temporal ordering
- **Execution backtesting** — simulates realistic fill latency and multi-pass scoring
- **Three benchmark baselines** — rolling average, direct GBM, and bookmaker (market efficiency) baselines
- **Sliced analysis** — performance by line bucket, spread bucket, rest days, archetype, time bucket
- **Promotion gates** — automated pass/fail criteria before going live
- **Paper trading ledger** — minimum 100 bets in paper mode before live deployment
- **Real-data validation runner** — scrapes Basketball-Reference for actual verification

#### E. Infrastructure (Grade: B-)
- PostgreSQL database with migrations
- Docker Compose stack (db, API server, worker)
- FastAPI REST endpoint
- GitHub Actions CI (tests + linting)
- Persistent local caching for BBRef data
- Daily pipeline runner (`run_today.py`)

---

### What's Missing or Weak

#### F. Critical Gaps

| Gap | Severity | Impact |
|-----|----------|--------|
| **No proven P&L track record** | Critical | No historical bet-level P&L, no CLV tracking, no Sharpe ratio. Cannot verify if the model actually makes money. |
| **No live execution pipeline** | Critical | `run_today.py` generates recommendations but doesn't place bets. No sportsbook API integration for automated execution. |
| **Only 2 stat types** | High | Limited to 3PM and assists. Points, rebounds, steals, blocks, combos (PRA) are unsupported — massive missed market surface. |
| **NBA only** | High | No NFL, MLB, NHL, college sports, or international basketball. |
| **No closing line value (CLV) tracking** | High | The decision dict has CLV fields (`close_over_prob_novig`, `clv_prob_pts`) but they're always `None`. CLV is the single most important metric for validating a sports model. |
| **BBRef scraping fragility** | High | Relies on scraping Basketball-Reference HTML with BeautifulSoup. BBRef blocks aggressive scraping and changes page structure. |
| **No real-time odds streaming** | Medium | Polling The Odds API at intervals. Professional shops need WebSocket feeds from Pinnacle, Circa, etc. for sub-second execution. |
| **Flat staking only in production** | Medium | Quarter-Kelly is implemented but `_compute_stake` defaults to flat. A syndicate should use Kelly-based sizing. |
| **No market-making capability** | Medium | System only takes directional bets against books. No ability to lay both sides or act as a market maker. |
| **Single-threaded pipeline** | Medium | `run_today.py` is sequential. For a full slate this is slow. |

---

## 2. Roadmap for Improvement

### Phase 1: Prove the Edge (Weeks 1–4) — Priority: CRITICAL

Before investing further, the model's edge must be verified with hard data.

1. **Implement CLV tracking** — After each game, fetch closing lines and compute closing line value for every bet recommendation. This is the gold standard for model validation.
2. **Build P&L ledger** — Track every recommendation with entry price, closing price, actual outcome, and units won/lost. Compute ROI, Sharpe, max drawdown, and win rate by edge bucket.
3. **Run 60-day paper trade** — Generate recommendations daily but don't bet. After 60 days, analyze if the model beats the closing line (CLV > 0) consistently.
4. **Benchmark against closing line** — If the model's opening recommendations consistently beat closing lines by 1-3 cents, there's real edge. If not, the model is noise.

**Expected output:** A verified CLV of +1.5 to +3.0 probability points would confirm exploitable edge.

### Phase 2: Expand Market Coverage (Weeks 3–8)

5. **Add points, rebounds, steals, blocks props** — The decomposition framework generalizes well. Points = (2PA × 2P% × 2 + 3PA × 3P% × 3 + FTA × FT%). Rebounds need a separate opportunity model.
6. **Add combo props (PRA, PR, PA)** — Higher hold on combos = more exploitable.
7. **Add alternate lines** — The Monte Carlo already prices alt lines. Surface these as bettable opportunities since alt-line markets are often softer.
8. **Add first-basket / first-scorer props** — High-margin markets with weak lines.

### Phase 3: Execution Infrastructure (Weeks 4–10)

9. **Sportsbook API integrations** — Connect to DraftKings, FanDuel, BetMGM, Caesars APIs for automated bet placement. This is the single biggest operational unlock.
10. **Real-time odds ingestion** — Replace polling with WebSocket feeds. Build an odds database that stores every line movement for every prop.
11. **Execution latency optimization** — Pre-compute features, cache model outputs, execute bets within 2 seconds of edge detection.
12. **Multi-account / multi-book management** — Track limits, balances, and bet history across all books.

### Phase 4: Model Sophistication (Weeks 6–16)

13. **Bayesian minutes model** — Replace the current quantile-fitting approach with a hierarchical Bayesian model that learns per-player minute distributions with game-context adjustments.
14. **Dynamic make-rate adjustment** — Hot/cold streaks, altitude effects (Denver), schedule density fatigue.
15. **Lineup-conditional projections** — Integrate real-time lineup data (who's actually on the court) rather than just injury reports.
16. **Live/in-game adjustments** — Re-price props after tip-off based on first-quarter performance.
17. **Opponent team-level model** — Team defensive rating trends, not just static season averages.

### Phase 5: Scale and Diversify (Weeks 12–24)

18. **Add WNBA** — Smaller market, softer lines, same data sources.
19. **Add MLB (pitcher strikeouts, hits, HRs)** — Large prop market, decomposition approach transfers well.
20. **Add NFL (passing yards, rushing, receiving)** — Largest US betting market.
21. **Portfolio-level optimization** — Optimize across all bets on a slate using covariance-aware position sizing (not just per-bet Kelly).
22. **Stale-line detection** — Identify when specific books are slow to adjust and exploit the lag.

---

## 3. Value Assessment

### Current Value: $15,000–$40,000

| Component | Value |
|-----------|-------|
| Codebase (26K LOC, clean architecture) | $8,000–$15,000 |
| Domain knowledge embedded in features | $5,000–$10,000 |
| Validation framework | $2,000–$5,000 |
| Data pipeline and ingestion layer | $2,000–$5,000 |
| Historical data / cached game logs | $1,000–$3,000 |
| CI/CD, Docker, API infrastructure | $1,000–$2,000 |

**Why not higher:** No verified P&L. Without a proven track record of positive CLV, the model is a hypothesis, not an asset. The reports/todays_bets_2026_03_05.md shows 171 bets with +13.9% average edge — but this is model-claimed edge, not verified edge. Self-reported edge is meaningless until validated against outcomes.

### Post-Improvement Value: $150,000–$500,000+ annually

Assuming Phase 1 confirms genuine edge:

| Scenario | Annual Value |
|----------|-------------|
| 5-book operation, $500K bankroll, 3% ROI on turnover | ~$150,000/yr |
| 10-book operation, $2M bankroll, 3% ROI on turnover | ~$500,000/yr |
| Full-market expansion (NBA+WNBA+MLB+NFL), $5M bankroll | ~$1,000,000+/yr |

**Key assumption:** The model achieves 1.5–3.0 points of CLV consistently. Professional NBA prop models at sharp shops typically achieve 1–4% ROI on turnover with proper execution and book access.

### Risk Factors

1. **Model may not have real edge** — Most sports models don't beat the closing line. Phase 1 will determine this within 60 days.
2. **Book limits** — Sportsbooks limit winning accounts aggressively. A syndicate needs 10+ accounts across multiple books, beards, and account management infrastructure.
3. **Market efficiency is increasing** — NBA prop markets have gotten sharper over the last 3 years. The window for easy money is closing.
4. **Regulatory risk** — State-by-state regulations on automated betting, API access, and multi-accounting.
5. **Data source fragility** — BBRef scraping can break at any time. The Odds API has quota limits. NBA.com rate-limits aggressively.

---

## 4. Recommendation

**Do not buy at the current stage without a 60-day paper trading validation.**

The architecture is strong and demonstrates genuine quant-sports expertise. However, the gap between "well-architected model" and "profitable operation" is enormous. I recommend:

1. **Negotiate a pilot agreement** — Pay $5,000–$10,000 for a 90-day exclusive evaluation period with access to the code.
2. **Run Phase 1 (prove the edge)** immediately during the pilot.
3. **If CLV is consistently positive** (>1.0 probability points on 200+ bets), proceed with full acquisition at $30,000–$50,000 and invest $50,000–$100,000 in Phase 2–5 development.
4. **If CLV is flat or negative**, walk away. The architecture is good but the signal isn't there.

The platform's greatest asset is not its current predictions — it's the extensible framework that can be rapidly expanded to new markets and sports once edge is confirmed in the core NBA prop vertical.

---

*This evaluation is based on a complete code review of the ValueHunter repository as of commit c0003b6. All claims about model performance should be independently verified with out-of-sample testing on real betting outcomes.*
