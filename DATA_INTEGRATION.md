# Data Integration Guide

## Overview

This repository integrates **two complementary data sources** for college football analysis:

1. **User-Provided Stats Files** (Player-level data)
2. **CFBD API Data** (Team-level and game data)

## Current Architecture

### 1. User Stats Files (Player-Level)

**Location**: `data/external/`

**Files**:
- `defense_coverage_scheme 2.csv` - Defensive player stats by coverage type (man/zone)
- `receiving_concept 2.csv` - Receiver stats by route concept (screen, slot, etc.)
- `receiving_scheme 2.csv` - Receiver stats by scheme (man/zone)

**Characteristics**:
- Player-level granularity
- 3,530 defensive players, 2,072 receivers
- 136 FBS teams covered
- Detailed performance grades, efficiency metrics, situational splits

**Processing**:
```bash
# Analyze user stats files
cfb-mismatch analyze
```

This aggregates player-level data to team-level metrics and generates comparison reports.

### 2. CFBD API Data (Team-Level)

**Location**: `data/cfbd/` (created by Python script)

**Source**: CollegeFootballData API via direct HTTP requests

**Files Generated**:
- `{season}_{type}_games.csv` - Game results and scores
- `{season}_{type}_games.parquet` - Same data in Parquet format
- `team_info.csv` - Team reference information
- `team_info.parquet` - Team reference in Parquet format

**Characteristics**:
- Team-level and game-level data
- EPA, success rate, explosiveness, havoc metrics
- Play-by-play derived statistics
- Conference, division, and team metadata

**Fetching**:
```bash
# Set up your API key (see README.md "Setting Up Your API Key" section)
export CFBD_API_KEY="your-api-key-here"

# Fetch using the CLI command
cfb-mismatch fetch-cfbd --season 2024 --season-type regular

# OR use the standalone script
python scripts/fetch_cfb_data.py --season 2024 --season_type regular
```

Or via GitHub Actions workflow (requires API key set as repository secret).

## Integration Strategy

### How They Work Together

The two data sources are **complementary**:

- **User Stats Files**: Provide detailed player-level performance metrics, particularly for coverage schemes and receiving efficiency
- **CFBD API Data**: Provides team-level context, game results, and play-by-play derived metrics

### Combined Analysis Workflow

1. **Fetch CFBD data** for the season/games you want to analyze:
   ```bash
   export CFBD_API_KEY="your-key"
   cfb-mismatch fetch-cfbd --season 2024 --season-type regular
   
   # Or use the standalone script
   python scripts/fetch_cfb_data.py --season 2024 --season_type regular
   ```

2. **Analyze user stats** to generate team-level aggregations:
   ```bash
   cfb-mismatch analyze
   
   # Or analyze and fetch CFBD data in one step
   cfb-mismatch analyze --season 2024 --fetch-cfbd
   ```

3. **Combine outputs** for comprehensive analysis:
   - User stats provide player performance by coverage/scheme
   - CFBD data provides team success rates, EPA, and game context
   - Together: Identify mismatches by combining scheme tendencies with performance metrics

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Data Sources                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────┐      ┌─────────────────────────────┐  │
│  │  User Stats Files    │      │    CFBD API                 │  │
│  │  (data/external/)    │      │    (collegefootballdata.com)│  │
│  │                      │      │                             │  │
│  │ • Defense coverage   │      │ • Games & scores            │  │
│  │ • Receiving concepts │      │ • Team info                 │  │
│  │ • Receiving schemes  │      │ • EPA & success rates       │  │
│  │                      │      │ • Play-by-play metrics      │  │
│  └──────────┬───────────┘      └────────┬────────────────────┘  │
│             │                           │                        │
└─────────────┼───────────────────────────┼────────────────────────┘
              │                           │
              │                           │
              ▼                           ▼
   ┌──────────────────────┐    ┌─────────────────────┐
   │  Python Adapters     │    │  Python Script      │
   │  (cfb_mismatch/      │    │  (fetch_cfb_data.py)│
   │   adapters/)         │    │  + requests         │
   └──────────┬───────────┘    └─────────┬───────────┘
              │                           │
              │                           │
              ▼                           ▼
   ┌──────────────────────┐    ┌─────────────────────┐
   │  Team Aggregations   │    │  CFBD Data Files    │
   │  (data/out/)         │    │  (data/cfbd/)       │
   │                      │    │                     │
   │ • Team defense stats │    │ • Games CSV/Parquet │
   │ • Team receiving     │    │ • Team info         │
   │   stats              │    │                     │
   │ • Summary reports    │    │                     │
   └──────────────────────┘    └─────────────────────┘
```

## Configuration

### Settings (configs/settings.yaml)

```yaml
# CFBD API settings
cfbd_api_key: ${CFBD_API_KEY}  # From environment variable

# Enable/disable data sources
use_stats_files: true   # User-provided player stats
use_pff: false          # PFF data (when available)
use_fantasypoints: false # FantasyPoints data (when available)

# Paths to user stats files
stats_paths:
  defense_coverage_scheme: "data/external/defense_coverage_scheme 2.csv"
  receiving_concept: "data/external/receiving_concept 2.csv"
  receiving_scheme: "data/external/receiving_scheme 2.csv"

# CFBD data paths (created by R script)
cfbd_paths:
  data_dir: "data/cfbd"
  # Games files will be: {data_dir}/{season}_{season_type}_games.csv
  # Team info will be: {data_dir}/team_info.csv
```

## Use Cases

### 1. Team Performance Analysis
- Use user stats for player-level performance by position/coverage
- Use CFBD data for overall team efficiency and game results

### 2. Matchup Analysis
- User stats show how teams perform in specific schemes (man vs zone)
- CFBD data shows game-level success against specific opponents

### 3. Weekly Predictions
- Combine player performance trends from user stats
- With team-level EPA and success rates from CFBD
- Weight by recent game context

## Future Enhancements

### Planned Integrations

1. **Unified Team Analysis Command**
   - Automatically load both user stats and CFBD data
   - Generate combined reports with player AND team metrics
   - Command: `cfb-mismatch team-report --team "Alabama" --season 2024`

2. **Matchup Predictor**
   - Compare two teams using all available data sources
   - Generate mismatch scores for run/pass/coverage
   - Command: `cfb-mismatch matchup --team1 "Alabama" --team2 "Georgia"`

3. **CFBD Data Adapter**
   - ✅ Python adapter to load CFBD CSV/Parquet files
   - ✅ Direct API fetching using HTTP requests to api.collegefootballdata.com
   - ✅ Merge with user stats by team name
   - ✅ Expose via Python API and CLI commands

4. **Weekly Analysis Pipeline**
   - Fetch current week's games from CFBD
   - Load user stats for teams playing this week
   - Generate mismatch predictions

## API Keys and Security

**IMPORTANT**: Never commit API keys to the repository.

- Store `CFBD_API_KEY` as an environment variable
- Use GitHub repository secrets for Actions workflows
- Config file references `${CFBD_API_KEY}` which expands from environment

For detailed instructions on setting up your API key, see the [Setting Up Your API Key](README.md#setting-up-your-api-key) section in README.md.

## Questions?

For more details:
- See `README.md` for overall project documentation
- See `USAGE.md` for command-line examples
- See `scripts/fetch_cfb_data.R` for CFBD data fetching
- See `src/cfb_mismatch/main.py` for user stats processing
