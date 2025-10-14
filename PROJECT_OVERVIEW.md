# CFB Mismatch Model - Project Overview

## Project Status: ✅ COMPLETE

This repository contains a fully functional Python package for computing weekly position-group mismatch scores for college football games.

## Quick Reference

### Installation
\`\`\`bash
pip install -e .
\`\`\`

### Usage
\`\`\`bash
export CFBD_API_KEY=your_api_key
cfb-mismatch week --year 2025 --week 7
\`\`\`

## Project Structure

\`\`\`
ValueHunter/
├── configs/                      # Configuration files
│   ├── settings.yaml            # Feature toggles, paths, output settings
│   └── weights.yaml             # Metric weights for scoring
│
├── data/                        # Data directories
│   ├── external/                # Place PFF & FantasyPoints CSV files here
│   │   └── README.md           # Expected file formats
│   └── out/                    # Generated output CSV files
│       └── README.md
│
├── src/cfb_mismatch/           # Main package
│   ├── __init__.py             # Package initialization
│   ├── cli.py                  # Command-line interface
│   ├── main.py                 # Core pipeline logic
│   ├── ext_features.py         # Extended features computation
│   └── adapters/               # Data source adapters
│       ├── __init__.py
│       ├── pff.py              # PFF data loader
│       └── fantasypoints.py    # FantasyPoints data loader
│
├── examples/                    # Example scripts and data
│   ├── README.md               # Examples guide
│   ├── basic_usage.py          # Usage examples
│   ├── sample_pff_*.csv        # Sample PFF data files
│   └── sample_fp_*.csv         # Sample FantasyPoints data
│
├── setup.py                     # Package setup (setuptools)
├── pyproject.toml              # Modern Python packaging
├── LICENSE                      # MIT License
├── README.md                   # Original project description
├── DEVELOPMENT.md              # Developer guide
├── BUILD_SUMMARY.md            # Detailed build information
├── PROJECT_OVERVIEW.md         # This file
└── test_integration.py         # Integration tests
\`\`\`

## Key Components

### 1. CLI (cli.py)
- Main entry point: \`cfb-mismatch\` command
- Subcommands: \`week\`
- Parameters: \`--year\`, \`--week\`, \`--output-dir\`

### 2. Core Pipeline (main.py)
- \`build_week()\`: Main pipeline function
- \`fetch_team_stats()\`: Gets data from CFBD
- \`compute_base_mismatches()\`: Calculates base scores
- Configuration loading and validation

### 3. Extended Features (ext_features.py)
- \`compute_extended_features()\`: Enhances with PFF/FP data
- \`enhance_with_pff_features()\`: Adds PFF metrics
- \`enhance_with_fp_features()\`: Adds FantasyPoints metrics

### 4. Data Adapters
- **PFF Adapter** (adapters/pff.py):
  - OL/DL win rates
  - Defensive fronts and coverage
  - Run concept efficiency
  
- **FantasyPoints Adapter** (adapters/fantasypoints.py):
  - Receiver splits vs man/zone
  - Team-level aggregation

## Configuration

### settings.yaml
Controls feature toggles and paths:
\`\`\`yaml
use_pff: false                 # Enable PFF features
use_fantasypoints: false       # Enable FantasyPoints features
output:
  default_dir: "data/out"
  top_n_mismatches: 20
\`\`\`

### weights.yaml
Controls scoring weights:
\`\`\`yaml
base_weights:
  run_epa: 0.30
  pass_epa: 0.30
  # ... more weights

pff_weights:
  ol_pass_block_wr: 0.40
  # ... more weights

fp_weights:
  receiver_yprr_vs_man: 0.35
  # ... more weights
\`\`\`

## Output Files

When you run \`cfb-mismatch week --year 2025 --week 7\`, it generates:

- \`cfb_unit_mismatches_week7.csv\` - Complete data for all matchups
- \`top_run_mismatches.csv\` - Top 20 run game mismatches
- \`top_pass_mismatches.csv\` - Top 20 passing game mismatches
- \`top_passpro_mismatches.csv\` - Top 20 pass protection mismatches

## Usage Examples

### CLI Usage
\`\`\`bash
# Basic usage
cfb-mismatch week --year 2024 --week 10

# Custom output directory
cfb-mismatch week --year 2024 --week 10 --output-dir reports/week10

# Use current week (from CFBD)
cfb-mismatch week --year 2025
\`\`\`

### Programmatic Usage
\`\`\`python
from cfb_mismatch.main import build_week

# Compute mismatches
build_week(year=2024, week=10, output_dir='reports/week10')

# Load configurations
from cfb_mismatch.main import load_config, load_weights
settings = load_config('settings')
weights = load_weights()
\`\`\`

## Testing

Run tests to verify installation:
\`\`\`bash
# Integration tests
python test_integration.py

# Example usage
python examples/basic_usage.py

# Test with sample data
cp examples/sample_*.csv data/external/
python examples/basic_usage.py
\`\`\`

## Dependencies

- **Python 3.9+** (tested with 3.12)
- **cfbd** - College Football Data API client
- **pandas** - Data manipulation
- **pyyaml** - YAML configuration
- **requests** - HTTP requests

All install automatically with \`pip install -e .\`

## Key Features

✅ **CFBD Integration** - Fetches EPA, success rate, explosiveness metrics  
✅ **PFF Support** - Optional OL/DL, defensive fronts, run concepts  
✅ **FantasyPoints Support** - Optional receiver splits vs coverage  
✅ **Configurable Weights** - Tune via YAML without code changes  
✅ **Multiple Outputs** - Run, pass, pass protection, and overall scores  
✅ **CLI + API** - Use via command-line or Python code  
✅ **Graceful Fallbacks** - Works without optional data sources  

## Documentation

- **README.md** - Original project specification
- **DEVELOPMENT.md** - Setup, development workflow, troubleshooting
- **BUILD_SUMMARY.md** - Comprehensive build details
- **PROJECT_OVERVIEW.md** - This file (quick reference)
- **examples/README.md** - Examples and sample data guide

## Next Steps

1. Get a CFBD API key from https://collegefootballdata.com/
2. Set the environment variable: \`export CFBD_API_KEY=your_key\`
3. Run: \`cfb-mismatch week --year 2025 --week 7\`
4. Check output in \`data/out/\`

Optional:
- Add PFF data to \`data/external/\` and set \`use_pff: true\`
- Add FantasyPoints data and set \`use_fantasypoints: true\`
- Adjust weights in \`configs/weights.yaml\`

## Support

For issues or questions:
1. Check the documentation files
2. Review example scripts in \`examples/\`
3. Run integration tests to verify setup
4. See adapter docstrings for data format requirements

---

Built for the ValueHunter repository by GitHub Copilot
