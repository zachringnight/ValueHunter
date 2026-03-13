.PHONY: help install install-dev test lint validate clean docker-up docker-down run-today run-projections

help:
	@echo "ValueHunter — NBA Player Props Pricing Engine"
	@echo "=============================================="
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install the package"
	@echo "  make install-dev      Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test             Run the test suite"
	@echo "  make lint             Run linting checks"
	@echo "  make validate         Run real-data validation"
	@echo "  make clean            Remove generated output files"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-up        Start database and API containers"
	@echo "  make docker-down      Stop all containers"
	@echo ""
	@echo "Run:"
	@echo "  make run-today        Generate today's bet recommendations"
	@echo "  make run-projections  Generate full fantasy projections"

install:
	pip install -e .

install-dev:
	pip install -e .
	pip install -r requirements-nba.txt

test:
	PYTHONPATH=src pytest tests/nba_props/ -v

lint:
	ruff check src/nba_props/ tests/nba_props/

validate:
	PYTHONPATH=src python -m nba_props.validation.real_data_runner

clean:
	rm -rf validation_output/*.json validation_output/*.txt validation_output/*.csv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

docker-up:
	docker compose up -d

docker-down:
	docker compose down

run-today:
	python run_today.py

run-projections:
	python run_fantasy_projections.py
