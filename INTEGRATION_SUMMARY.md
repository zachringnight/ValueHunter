# Stats Integration Summary

## Overview

This repository now includes a complete Python package that integrates three college football stats files into a unified analysis framework.

## Files Integrated

### Input Data (in `data/external/`)
1. **defense_coverage_scheme 2.csv** - 3,530 defensive player records
   - Man vs zone coverage statistics
   - 65 columns including grades, QB rating against, yards allowed, etc.
   - Coverage data for 136 FBS teams

2. **receiving_concept 2.csv** - 2,072 receiver records  
   - Receiving stats by concept (screen, slot, etc.)
   - 65 columns including yards per route run, catch rates, efficiency metrics
   - Data for 136 FBS teams

3. **receiving_scheme 2.csv** - 2,072 receiver records
   - Receiving stats by scheme (man vs zone)
   - 64 columns including separation metrics, target data, success rates
   - Data for 136 FBS teams

## Implementation

### Package Structure
```
src/cfb_mismatch/
├── __init__.py              # Package initialization
├── cli.py                   # Command-line interface
├── main.py                  # Core logic for loading and aggregating stats
└── adapters/                # Data loaders for each file type
    ├── defense_coverage.py
    ├── receiving_concept.py
    └── receiving_scheme.py
```

### Key Features

1. **Data Loading**: Robust CSV parsers with error handling
2. **Team Aggregation**: Player-level stats aggregated to team averages
3. **CLI Tool**: Simple command-line interface for analysis
4. **Configuration**: YAML-based settings and feature weights
5. **Output Reports**: Four CSV files with team-level statistics

## Usage

### Installation
```bash
pip install -e .
```

### Run Analysis
```bash
cfb-mismatch analyze
```

### Output Files (in `data/out/`)
- `team_defense_coverage.csv` (122 KB, 62 columns)
- `team_receiving_concept.csv` (113 KB, 64 columns)  
- `team_receiving_scheme.csv` (121 KB, 64 columns)
- `team_summary.csv` (19 KB, 9 key metrics)

## Key Metrics Tracked

### Defense
- Man/zone coverage grades
- QB rating against (man vs zone)
- Coverage snaps per reception/target
- Yards allowed per coverage snap

### Receiving Concepts
- Yards per route run (YPRR) by concept
- Catch rates and drop rates
- Contested catch success
- First down conversion rates

### Receiving Schemes
- Efficiency vs man and zone coverage
- Route running grades
- Separation metrics
- Target distribution

## Top Performing Teams

Based on the integrated stats:

**Best Man Coverage Defenses:**
1. Dominion - 66.1 grade
2. Northern Illinois - 65.3 grade
3. Hawaii - 65.1 grade

**Best Zone Coverage Defenses:**
1. Texas Tech - 67.0 grade
2. UNLV - 67.0 grade
3. Houston - 66.6 grade

## Next Steps

The integration provides the foundation for:
- Team matchup analysis
- Player performance comparisons
- Coverage scheme optimization
- Recruiting and roster planning
- Game planning and strategy

## Technical Details

- **Python Version**: 3.9+
- **Dependencies**: pandas, pyyaml
- **Total Records**: 7,674 player records
- **Teams Covered**: 136 FBS teams
- **Data Points**: ~190 unique metrics across all files
