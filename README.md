# NBA 3PM Props Engine v1.1

Pregame player props pricing system for NBA three-pointers made (3PM) markets.

## Overview

Multi-stage prediction pipeline:
1. **Minutes model** — predicts player minutes using lineup context
2. **3PA model** — estimates three-point attempts per 36 minutes
3. **Make-rate model** — Bayesian shrinkage + matchup adjustments for 3PT%
4. **Monte Carlo simulation** — 25K draws for full probability distribution
5. **Pricing** — converts simulated distributions to fair odds + edge detection

## Quick Start

```bash
pip install -e .
make test       # Run test suite
make validate   # Run real-data validation
```

## Validation

The validation pack evaluates engine accuracy against real data:
- Basketball-Reference game logs for model accuracy
- SportsGameOdds API for historical prop lines
- The Odds API for live prop lines

```bash
PYTHONPATH=src python -m nba_props.validation.real_data_runner
```

## Project Structure

```
src/nba_props/
├── models/          # Minutes, 3PA, make-rate, Monte Carlo models
├── features/        # Feature engineering pipeline
├── ingestion/       # Data loading and NBA API integration
├── pricing/         # Edge detection and bankroll management
├── backtesting/     # Walk-forward backtesting framework
├── validation/      # Release-candidate validation pack
├── api/             # FastAPI endpoints
├── monitoring/      # Drift detection and alerting
└── config/          # Engine configuration
```

## License

MIT License
