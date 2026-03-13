# ValueHunter — NBA Player Props Pricing Engine

A quantitative sports analytics engine that identifies mispriced NBA player prop bets using multi-stage statistical modeling, Monte Carlo simulation, and real-time odds comparison.

ValueHunter covers **3-pointers made**, **assists**, **points**, **rebounds**, **steals**, **blocks**, **turnovers**, and other standard fantasy categories — generating full box score projections with edge detection against live sportsbook lines.

## How It Works

```
Game Logs ─┐
            ├─► Feature Engineering ─► Minutes Model ─► Volume Model ─► Make-Rate Model
Live Odds ──┤                              │                │                  │
            │                              ▼                ▼                  ▼
Injuries ───┤                         Monte Carlo Simulation (25K draws)
            │                              │
Adv Stats ──┘                              ▼
                                    Edge Detection & Bet Sizing
                                           │
                                           ▼
                                    Bet Recommendations
```

**Pipeline stages:**

1. **Minutes model** — projects player minutes using lineup context, game spread, and blowout risk
2. **Volume model** — estimates stat attempts per 36 minutes (e.g., 3PA, FGA) using usage patterns and matchup data
3. **Make-rate model** — Bayesian shrinkage + opponent-adjusted conversion rates
4. **Monte Carlo simulation** — 25,000 draws produce full probability distributions for each stat
5. **Pricing engine** — compares model distributions against sportsbook lines to find edges

## Features

- **Multi-stat coverage** — 3PM, assists, points, rebounds, steals, blocks, turnovers, FGM, FTM
- **Advanced matchup modeling** — Synergy play-type defense, opponent zone shooting, tracking data (catch-and-shoot/pull-up splits)
- **Player archetypes** — classifies players by role to apply appropriate modeling adjustments
- **Real-time odds ingestion** — pulls live lines from The Odds API across multiple sportsbooks
- **Injury-aware** — scrapes the official NBA injury report and adjusts minutes projections
- **Walk-forward backtesting** — evaluate model performance without lookahead bias
- **Full fantasy projections** — DraftKings and FanDuel fantasy point projections
- **REST API** — FastAPI endpoints for programmatic access
- **Drift monitoring** — detects when model inputs shift beyond expected ranges

## Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 16+ (or use Docker)
- API keys for [The Odds API](https://the-odds-api.com/) and optionally [Sportradar](https://developer.sportradar.com/)

### Installation

```bash
git clone https://github.com/zachringnight/ValueHunter.git
cd ValueHunter

pip install -e .
pip install -r requirements-nba.txt

cp .env.example .env
# Edit .env with your API keys
```

### Using Docker

```bash
docker compose up -d

# Run the daily pipeline
docker compose run --rm worker
```

### Run Today's Bets

```bash
python run_today.py
```

This fetches live odds, scrapes current-season game logs, runs the full prediction pipeline, and outputs bet recommendations sorted by edge.

### Run Fantasy Projections

```bash
python run_fantasy_projections.py
```

Generates full box score projections for all players in today's games, with DraftKings and FanDuel fantasy point estimates.

## API

Start the API server:

```bash
uvicorn nba_props.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/health` | GET | Health check and version info |
| `/v1/models` | GET | List available models and metadata |
| `/v1/decisions?date=YYYY-MM-DD` | POST | Generate bet decisions for a date |
| `/v1/bets/{date}` | GET | Retrieve bet decisions for a date |
| `/v1/backtest/run` | POST | Run a walk-forward backtest |
| `/v1/feature_snapshot/{id}` | GET | Retrieve a frozen feature snapshot |

Interactive docs available at `http://localhost:8000/docs` when the server is running.

## Project Structure

```
src/nba_props/
├── api/             # FastAPI application and endpoints
├── backtest/        # Walk-forward backtesting framework
├── config/          # Engine configuration and settings
├── features/        # Feature engineering (minutes, opportunity, make-rate, archetypes)
├── ingestion/       # Data loaders (NBA Stats, Sportradar, Odds API, injury reports)
├── jobs/            # Pipeline orchestration and scheduling
├── models/          # Prediction models (minutes, 3PA, make-rate, baseline)
├── monitoring/      # Drift detection and alerting
├── pricing/         # Monte Carlo simulation and decision engine
├── utils/           # Odds math, types, database utilities
└── validation/      # Validation suite, paper trading, promotion gates
```

## Development

```bash
pip install -r requirements-nba.txt

make test           # Run tests
make lint           # Run linting
make validate       # Run real-data validation
```

### Database Setup

Apply migrations against a running PostgreSQL instance:

```bash
for f in sql/migrations/*.sql; do
  psql -h localhost -U nba_props -d nba_props -f "$f"
done
```

## Configuration

All configuration is managed through environment variables. See [`.env.example`](.env.example) for the full list.

Key settings:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://nba_props:nba_props@localhost:5432/nba_props` |
| `ODDS_API_KEY` | [The Odds API](https://the-odds-api.com/) key | Required |
| `SPORTRADAR_API_KEY` | Sportradar NBA API key | Optional |
| `MONTE_CARLO_DRAWS` | Number of MC simulation draws | `25000` |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[MIT](LICENSE)
