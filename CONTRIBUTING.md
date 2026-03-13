# Contributing to ValueHunter

Thanks for your interest in contributing to ValueHunter.

## Getting Started

1. Fork the repository
2. Clone your fork and create a feature branch:
   ```bash
   git clone https://github.com/<your-username>/ValueHunter.git
   cd ValueHunter
   git checkout -b my-feature
   ```
3. Install dependencies:
   ```bash
   pip install -e .
   pip install -r requirements-nba.txt
   ```
4. Set up the database (requires PostgreSQL 16+):
   ```bash
   docker compose up -d db
   for f in sql/migrations/*.sql; do
     psql -h localhost -U nba_props -d nba_props -f "$f"
   done
   ```

## Development Workflow

- Run tests before submitting: `make test`
- Run linting: `make lint`
- Run validation against real data: `make validate`

## Pull Requests

- Keep PRs focused on a single change
- Include tests for new functionality
- Update documentation if you change public interfaces
- Ensure CI passes before requesting review

## Code Style

- Follow PEP 8 conventions
- Maximum line length: 120 characters
- Use type hints for function signatures in public APIs

## Reporting Issues

Open an issue with:
- A clear description of the problem
- Steps to reproduce
- Expected vs. actual behavior
- Python version and OS

## Areas Where Help Is Welcome

- Additional stat category models (e.g., double-doubles, player combos)
- Improved backtesting visualizations
- Support for additional sportsbook APIs
- Documentation and examples
