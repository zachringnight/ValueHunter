.PHONY: help install install-dev test lint validate clean

help:
	@echo "NBA 3PM Props Engine v1.1 - Available Tasks"
	@echo "============================================"
	@echo ""
	@echo "  make install        Install the package"
	@echo "  make install-dev    Install with dev dependencies"
	@echo "  make test           Run the test suite"
	@echo "  make validate       Run real-data validation"
	@echo "  make lint           Run linting checks"
	@echo "  make clean          Remove output files"

install:
	pip install -e .

install-dev:
	pip install -e .
	pip install pytest

test:
	PYTHONPATH=src pytest tests/nba_props/ -v

validate:
	PYTHONPATH=src python -m nba_props.validation.real_data_runner

lint:
	@if command -v flake8 > /dev/null; then \
		flake8 src/nba_props/ tests/nba_props/ --max-line-length=120; \
	else \
		echo "flake8 not installed"; \
	fi

clean:
	rm -rf validation_output/*.json validation_output/*.txt
