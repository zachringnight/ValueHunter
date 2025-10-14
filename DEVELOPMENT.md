# Development Guide

## Quick Start for Development

### Installation

```bash
# Clone the repository
git clone https://github.com/zachringnight/ValueHunter.git
cd ValueHunter

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with development dependencies
pip install -e .
```

### Running Tests

```bash
# Run the integration test
python test_integration.py
```

### Using the CLI

```bash
# Set your CFBD API key
export CFBD_API_KEY=your_api_key_here

# Run for a specific week
cfb-mismatch week --year 2024 --week 10

# Specify custom output directory
cfb-mismatch week --year 2024 --week 10 --output-dir reports/week10
```

### Using Programmatically

```python
import os
os.environ['CFBD_API_KEY'] = 'your_api_key'

from cfb_mismatch.main import build_week

# Compute mismatches for week 10 of 2024
build_week(year=2024, week=10, output_dir='reports/week10')
```

## Project Structure

```
ValueHunter/
├── configs/              # Configuration files
│   ├── settings.yaml     # Global settings (API keys, feature toggles)
│   └── weights.yaml      # Feature weights for scoring
├── data/
│   ├── external/         # External data files (PFF, FantasyPoints)
│   └── out/             # Generated output files
├── src/cfb_mismatch/    # Main package
│   ├── __init__.py
│   ├── cli.py           # Command-line interface
│   ├── main.py          # Core logic and pipeline
│   ├── ext_features.py  # Extended features computation
│   └── adapters/        # Data loaders
│       ├── pff.py       # PFF data adapter
│       └── fantasypoints.py  # FantasyPoints adapter
├── setup.py             # Package setup
├── pyproject.toml       # Modern Python packaging
└── test_integration.py  # Integration tests
```

## Adding New Features

### Adding a New Metric

1. Add the metric to `configs/weights.yaml`
2. Update the computation logic in `main.py` or `ext_features.py`
3. Document the feature in the appropriate function docstring

### Adding a New Data Source

1. Create a new adapter in `src/cfb_mismatch/adapters/`
2. Add configuration to `configs/settings.yaml`
3. Update `ext_features.py` to use the new data

## Configuration

### settings.yaml

Controls which features are enabled and where data files are located:

```yaml
use_pff: false              # Enable PFF features
use_fantasypoints: false    # Enable FantasyPoints features
```

### weights.yaml

Controls the relative importance of each metric:

```yaml
base_weights:
  run_epa: 0.30           # Weight for run EPA
  pass_epa: 0.30          # Weight for pass EPA
  # ... more weights
```

## Common Tasks

### Updating Dependencies

```bash
pip install --upgrade -r requirements.txt
```

### Running on Historical Data

```python
from cfb_mismatch.main import build_week

# Backtest on multiple weeks
for week in range(1, 15):
    build_week(year=2024, week=week, output_dir=f'backtests/2024/week{week}')
```

### Calibrating Weights

1. Run the model on historical data
2. Compare results with actual game outcomes
3. Adjust weights in `configs/weights.yaml`
4. Iterate until satisfied with results

## Troubleshooting

### Import Errors

Make sure you installed the package:
```bash
pip install -e .
```

### API Key Issues

Ensure CFBD_API_KEY is set:
```bash
echo $CFBD_API_KEY  # Should print your API key
```

### Missing Data Files

The package gracefully handles missing PFF/FantasyPoints files. Set `use_pff: false` and `use_fantasypoints: false` in `configs/settings.yaml` if you don't have these files.
