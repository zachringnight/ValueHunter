.PHONY: help install install-dev run clean test fetch-cfbd lint format analyze

# Default target - show help
help:
	@echo "CFB Mismatch Model - Available Make Tasks"
	@echo "=========================================="
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make install        Install the package and dependencies"
	@echo "  make install-dev    Install package with development dependencies"
	@echo ""
	@echo "Running the Model:"
	@echo "  make run           Run the model analysis (default: analyze existing stats)"
	@echo "  make analyze       Run the model analysis (alias for 'run')"
	@echo ""
	@echo "Data Management:"
	@echo "  make fetch-cfbd    Fetch CFBD data from API (requires CFBD_API_KEY)"
	@echo "  make clean         Remove output files and temporary data"
	@echo ""
	@echo "Development:"
	@echo "  make test          Run the test suite"
	@echo "  make lint          Run code linting checks"
	@echo "  make format        Format code (if formatters are available)"
	@echo ""
	@echo "Examples:"
	@echo "  make install && make run              # Install and run"
	@echo "  SEASON=2024 make fetch-cfbd           # Fetch 2024 data"
	@echo "  make fetch-cfbd && make run           # Fetch data and run"
	@echo ""

# Install the package
install:
	@echo "Installing CFB Mismatch package..."
	pip install -e .
	@echo ""
	@echo "✓ Installation complete!"
	@echo "You can now run: make run"

# Install with development dependencies
install-dev:
	@echo "Installing CFB Mismatch package with dev dependencies..."
	pip install -e .
	pip install -r requirements-dev.txt
	@echo ""
	@echo "✓ Installation complete!"
	@echo "You can now run: make run or make test"

# Run the model
run:
	@echo "Running CFB Mismatch Model..."
	@echo ""
	python run_model.py

# Alias for run
analyze: run

# Fetch CFBD data (requires CFBD_API_KEY environment variable)
fetch-cfbd:
	@if [ -z "$$CFBD_API_KEY" ]; then \
		echo "Error: CFBD_API_KEY environment variable not set"; \
		echo "Please set it first: export CFBD_API_KEY='your-key-here'"; \
		exit 1; \
	fi
	@echo "Fetching CFBD data..."
	@SEASON=$${SEASON:-2024}; \
	SEASON_TYPE=$${SEASON_TYPE:-regular}; \
	echo "Season: $$SEASON, Type: $$SEASON_TYPE"; \
	cfb-mismatch fetch-cfbd --season $$SEASON --season-type $$SEASON_TYPE

# Clean output files
clean:
	@echo "Cleaning output files..."
	rm -rf data/out/*.csv
	rm -rf data/cfbd/*.csv
	rm -rf data/cfbd/*.parquet
	@echo "✓ Output files cleaned"

# Run tests
test:
	@echo "Running tests..."
	pytest -v

# Run linting (if tools are available)
lint:
	@echo "Running linting checks..."
	@if command -v flake8 > /dev/null; then \
		echo "Running flake8..."; \
		flake8 src/ tests/ --max-line-length=120 --ignore=E501,W503; \
	else \
		echo "flake8 not installed. Install with: pip install flake8"; \
	fi
	@if command -v pylint > /dev/null; then \
		echo "Running pylint..."; \
		pylint src/cfb_mismatch/ --disable=C0111,C0103,R0913,R0914; \
	else \
		echo "pylint not installed. Install with: pip install pylint"; \
	fi

# Format code (if tools are available)
format:
	@echo "Formatting code..."
	@if command -v black > /dev/null; then \
		echo "Running black..."; \
		black src/ tests/; \
	else \
		echo "black not installed. Install with: pip install black"; \
	fi
	@if command -v isort > /dev/null; then \
		echo "Running isort..."; \
		isort src/ tests/; \
	else \
		echo "isort not installed. Install with: pip install isort"; \
	fi
