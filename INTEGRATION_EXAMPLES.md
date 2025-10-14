# Integration Examples

This document provides detailed examples of how to use your stats files and CFBD API data separately and together.

## Example 1: Analyze User Stats Only

If you only have your player-level CSV files and want to analyze them:

```bash
# Basic analysis
cfb-mismatch analyze

# With custom output directory
cfb-mismatch analyze --output-dir reports/week12
```

**Output:**
- Team-level aggregations of your player data
- Defense coverage statistics by team
- Receiving concept and scheme metrics
- Summary report with key metrics

**Use case:** When you want to understand team-level performance trends from your detailed player data.

## Example 2: Fetch CFBD Data Only

If you want to fetch game data from the CFBD API:

```bash
# First, set up your API key (see README.md "Setting Up Your API Key" section)
# Then fetch data for 2024 regular season
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular

# Fetch postseason data
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type postseason

# Fetch data for a different season
Rscript scripts/fetch_cfb_data.R --season 2023 --season_type regular
```

**Output:**
- `data/cfbd/2024_regular_games.csv` - Game results and scores
- `data/cfbd/2024_regular_games.parquet` - Same in Parquet format
- `data/cfbd/team_info.csv` - Team reference information

**Use case:** When you want game-level context, team records, and scoring data from the CFBD API.

## Example 3: Integrated Analysis (Both Data Sources)

Combine your player-level stats with CFBD game data for comprehensive analysis:

```bash
# Step 1: Set up your API key (see README.md "Setting Up Your API Key" section)
# Then fetch CFBD data
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular

# Step 2: Run integrated analysis
cfb-mismatch analyze --season 2024

# Or specify season type if needed
cfb-mismatch analyze --season 2024 --season-type postseason
```

**Output:**
- All the user stats reports (defense, receiving concept, receiving scheme)
- **Enhanced summary** with CFBD metrics:
  - Win/loss records
  - Win percentage
  - Average points scored/allowed
  - Point differential per game

**Example integrated summary columns:**
```
team_name, man_coverage_grade, zone_coverage_grade, man_qb_rating_against,
zone_qb_rating_against, screen_yprr, slot_yprr, man_yprr, zone_yprr,
games_played, wins, win_pct, avg_points_scored, avg_points_allowed, point_differential
```

**Use case:** When you want to correlate player performance (coverage grades, receiving efficiency) with team outcomes (wins, scoring).

## Example 4: Multi-Season Analysis

Analyze multiple seasons to identify trends:

```bash
# Fetch multiple seasons
for year in 2021 2022 2023 2024; do
  Rscript scripts/fetch_cfb_data.R --season $year --season_type regular
done

# Analyze each season
cfb-mismatch analyze --season 2021 --output-dir reports/2021
cfb-mismatch analyze --season 2022 --output-dir reports/2022
cfb-mismatch analyze --season 2023 --output-dir reports/2023
cfb-mismatch analyze --season 2024 --output-dir reports/2024
```

## Example 5: Python API Usage

Use the package programmatically for custom analysis:

```python
from cfb_mismatch.main import (
    load_config,
    load_all_stats,
    load_cfbd_data,
    compute_team_stats,
    generate_integrated_report
)

# Load configuration
config = load_config()

# Load user stats
defense_df, receiving_concept_df, receiving_scheme_df = load_all_stats(config)

# Compute team-level stats
team_stats = compute_team_stats(defense_df, receiving_concept_df, receiving_scheme_df)

# Load CFBD data
games_df, team_info_df, cfbd_team_stats = load_cfbd_data(
    season=2024,
    season_type='regular',
    data_dir='data/cfbd'
)

# Generate integrated report
integrated_summary = generate_integrated_report(team_stats, cfbd_team_stats)

# Save or analyze further
integrated_summary.to_csv('my_custom_report.csv', index=False)

# Example: Find teams with high coverage grades and high win percentage
if cfbd_team_stats is not None:
    top_teams = integrated_summary[
        (integrated_summary['man_coverage_grade'] > 60) &
        (integrated_summary['win_pct'] > 0.7)
    ].sort_values('win_pct', ascending=False)
    
    print("Top teams with high coverage grades and win rate:")
    print(top_teams[['team_name', 'man_coverage_grade', 'win_pct', 'wins']])
```

## Example 6: Team-Specific Analysis

Focus on a specific team:

```python
import pandas as pd

# Load the integrated summary
summary = pd.read_csv('data/out/team_summary.csv')

# Analyze Alabama
alabama = summary[summary['team_name'] == 'ALABAMA']

print("Alabama Stats:")
print(f"Man Coverage Grade: {alabama['man_coverage_grade'].values[0]:.2f}")
print(f"Zone Coverage Grade: {alabama['zone_coverage_grade'].values[0]:.2f}")
print(f"Win Percentage: {alabama['win_pct'].values[0]:.2%}")
print(f"Point Differential: {alabama['point_differential'].values[0]:.2f}")
```

## Example 7: Compare Two Teams

Compare teams for matchup analysis:

```python
import pandas as pd

summary = pd.read_csv('data/out/team_summary.csv')

team1 = 'ALABAMA'
team2 = 'GEORGIA'

stats1 = summary[summary['team_name'] == team1].iloc[0]
stats2 = summary[summary['team_name'] == team2].iloc[0]

print(f"\nMatchup Analysis: {team1} vs {team2}\n")
print(f"{'Metric':<30} {team1:<15} {team2:<15}")
print("-" * 65)
print(f"{'Man Coverage Grade':<30} {stats1['man_coverage_grade']:<15.2f} {stats2['man_coverage_grade']:<15.2f}")
print(f"{'Zone Coverage Grade':<30} {stats1['zone_coverage_grade']:<15.2f} {stats2['zone_coverage_grade']:<15.2f}")
print(f"{'Man YPRR (Receiving)':<30} {stats1['man_yprr']:<15.2f} {stats2['man_yprr']:<15.2f}")
print(f"{'Zone YPRR (Receiving)':<30} {stats1['zone_yprr']:<15.2f} {stats2['zone_yprr']:<15.2f}")

if 'win_pct' in summary.columns:
    print(f"{'Win Percentage':<30} {stats1['win_pct']:<15.2%} {stats2['win_pct']:<15.2%}")
    print(f"{'Avg Points Scored':<30} {stats1['avg_points_scored']:<15.2f} {stats2['avg_points_scored']:<15.2f}")
    print(f"{'Avg Points Allowed':<30} {stats1['avg_points_allowed']:<15.2f} {stats2['avg_points_allowed']:<15.2f}")
```

## Data Flow Summary

```
┌─────────────────────┐         ┌──────────────────────┐
│  Your Player Stats  │         │    CFBD API          │
│  (CSV Files)        │         │    (R Script)        │
└──────────┬──────────┘         └───────────┬──────────┘
           │                                │
           │                                │
           ▼                                ▼
    ┌──────────────┐              ┌─────────────────┐
    │  Python      │              │  data/cfbd/     │
    │  Adapters    │              │  - games.csv    │
    └──────┬───────┘              │  - team_info    │
           │                      └────────┬────────┘
           │                               │
           ▼                               ▼
    ┌──────────────────────────────────────────────┐
    │  cfb-mismatch analyze --season 2024          │
    │                                               │
    │  Loads both sources, aggregates, and merges   │
    └──────────────────┬───────────────────────────┘
                       │
                       ▼
            ┌──────────────────────┐
            │  data/out/            │
            │  - team_summary.csv   │
            │  - defense stats      │
            │  - receiving stats    │
            └───────────────────────┘
```

## Troubleshooting

### "No CFBD data found"
Make sure you've run the R script to fetch data:
```bash
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular
```

### "Missing CFBD_API_KEY"
Your API key is not set as an environment variable. See the detailed [Setting Up Your API Key](README.md#setting-up-your-api-key) section in README.md for platform-specific instructions on:
- Getting your API key from https://collegefootballdata.com/key
- Setting it temporarily or permanently
- Verifying your setup

### Team names don't match
Team names are normalized (uppercase, trimmed) during merging. If some teams don't match, you may need to check the team name format in both data sources.

## Next Steps

- See `DATA_INTEGRATION.md` for architecture details
- See `README.md` for overall project documentation  
- See `USAGE.md` for command-line reference
