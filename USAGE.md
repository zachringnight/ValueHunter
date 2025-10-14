# CFB Mismatch Model - Usage Examples

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/zachringnight/ValueHunter.git
cd ValueHunter

# Install dependencies
pip install -e .
```

### 2. Analyze Integrated Stats

The repository includes three stats files with player-level data:
- Defense coverage scheme (man vs zone coverage)
- Receiving concepts (screen, slot, etc.)
- Receiving schemes (man vs zone)

Run the analysis:

```bash
cfb-mismatch analyze
```

This will generate team-level aggregations in `data/out/`:
- `team_defense_coverage.csv` - Defensive coverage statistics by team
- `team_receiving_concept.csv` - Receiving concept metrics by team
- `team_receiving_scheme.csv` - Receiving scheme metrics by team
- `team_summary.csv` - Combined summary with key metrics

#### Integrate with CFBD API Data

If you have fetched CFBD data using the R script, you can integrate it with your analysis:

```bash
# First, fetch CFBD data (requires CFBD_API_KEY)
export CFBD_API_KEY="your-api-key"
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular

# Then analyze with integration
cfb-mismatch analyze --season 2024
```

This will:
- Load your player-level stats
- Load CFBD game data (wins, losses, points scored/allowed)
- Generate an integrated summary with both datasets
- Include win percentage, point differential, and game context

The integrated summary includes additional columns:
- `games_played` - Number of games played
- `wins` - Number of wins
- `win_pct` - Win percentage
- `avg_points_scored` - Average points scored per game
- `avg_points_allowed` - Average points allowed per game
- `point_differential` - Average point differential per game

### 3. View Results

The summary report shows top-performing teams across different metrics:

```
--- Top 5 Teams by Man Coverage Grade ---
 team_name  man_coverage_grade
  DOMINION           66.095238
N ILLINOIS           65.347059
    HAWAII           65.111111
 KANSAS ST           64.695652
      TROY           64.478571

--- Top 5 Teams by Zone Coverage Grade ---
 team_name  zone_coverage_grade
TEXAS TECH            67.020690
      UNLV            66.959091
   HOUSTON            66.604167
  BOISE ST            65.788889
     TULSA            65.629412
```

When CFBD data is integrated (using `--season`), you'll also see:

```
--- Top 5 Teams by Win Percentage ---
 team_name  win_pct  wins  games_played
   ALABAMA      1.0   1.0           1.0
   GEORGIA      1.0   1.0           1.0
     TEXAS      1.0   1.0           1.0
```

### 4. Custom Output Directory

Specify a custom output location:

```bash
cfb-mismatch analyze --output-dir my_reports/
```

## Python API

You can also use the package programmatically:

```python
from cfb_mismatch.main import (
    load_config,
    load_all_stats,
    compute_team_stats,
    save_team_stats,
    generate_summary_report
)

# Load configuration
config = load_config()

# Load stats files
defense_df, receiving_concept_df, receiving_scheme_df = load_all_stats(config)

# Compute team-level stats
team_stats = compute_team_stats(defense_df, receiving_concept_df, receiving_scheme_df)

# Generate summary
summary = generate_summary_report(team_stats)

# Save results
save_team_stats(team_stats, "data/out")
summary.to_csv("data/out/team_summary.csv", index=False)
```

## Configuration

### Settings (configs/settings.yaml)

- `use_stats_files`: Enable/disable stats file loading (default: true)
- `stats_paths`: Paths to the three CSV files
- `output_dir`: Default output directory

### Weights (configs/weights.yaml)

Customize feature importance for analysis:

```yaml
stats_weights:
  man_coverage_defense: 0.15
  zone_coverage_defense: 0.15
  man_qb_rating_against: 0.1
  zone_qb_rating_against: 0.1
  screen_efficiency: 0.1
  slot_efficiency: 0.1
  man_receiving_efficiency: 0.15
  zone_receiving_efficiency: 0.15
```

## Data Format

### Input Files

Each CSV file contains player-level statistics with:
- Player information (name, ID, position, team)
- Performance metrics (grades, yards, targets, etc.)
- Situational splits (man/zone for defense and receiving)

### Output Files

Team-level aggregations include:
- Averaged metrics across all players on each team
- Player counts per team
- Key performance indicators for comparison
