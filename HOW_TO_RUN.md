# How to Run the CFB Mismatch Model

This guide provides step-by-step instructions for running the CFB Mismatch Model to analyze college football team statistics and generate mismatch scores.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Advanced Usage](#advanced-usage)
- [Understanding the Output](#understanding-the-output)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### 1. Python Installation
- Python 3.9 or higher is required
- Check your Python version:
  ```bash
  python --version
  ```
  or
  ```bash
  python3 --version
  ```

### 2. Git (for cloning the repository)
- Verify Git is installed:
  ```bash
  git --version
  ```

## Installation

### Step 1: Clone the Repository
```bash
git clone https://github.com/zachringnight/ValueHunter.git
cd ValueHunter
```

### Step 2: Install the Package
```bash
pip install -e .
```

This will install the `cfb-mismatch` command-line tool and all required dependencies:
- pandas (for data processing)
- pyyaml (for configuration)
- requests (for API calls)
- numpy (for numerical operations)

### Step 3: Verify Installation
```bash
cfb-mismatch --help
```

You should see the help menu with available commands.

## Basic Usage

### Running the Model with Existing Data

The repository comes with three stats files already loaded in `data/external/`:
- `defense_coverage_scheme 2.csv` - Defensive coverage statistics (man vs zone)
- `receiving_concept 2.csv` - Receiving concept metrics (screen, slot, etc.)
- `receiving_scheme 2.csv` - Receiving scheme statistics (man vs zone)

To analyze these files and generate team-level reports, use any of these methods:

```bash
# Method 1: Simple Python script
python run_model.py

# Method 2: Simple bash script
./run_model.sh

# Method 3: CLI command
cfb-mismatch analyze
```

**That's it!** Any of these commands will:
1. Load all three stats files
2. Aggregate player-level stats to team-level metrics
3. Calculate mismatch scores based on configured weights
4. Generate output files in `data/out/`

### What Gets Generated

After running the analyze command, you'll find these files in `data/out/`:

1. **team_defense_coverage.csv** - Team-level defensive coverage statistics
2. **team_receiving_concept.csv** - Team-level receiving concept metrics
3. **team_receiving_scheme.csv** - Team-level receiving scheme metrics
4. **team_summary.csv** - Combined summary with overall mismatch scores and tiers

## Advanced Usage

### Option 1: Custom Output Directory

Save results to a specific location:

```bash
cfb-mismatch analyze --output-dir reports/my_analysis
```

### Option 2: Custom Configuration

Use different configuration or weight files:

```bash
cfb-mismatch analyze --config my_config.yaml --weights my_weights.yaml
```

### Option 3: Integration with CFBD API Data

For enhanced analysis with game data from CollegeFootballData.com:

#### Step 1: Set up your CFBD API Key

1. Get your API key from https://collegefootballdata.com/key
2. Set it as an environment variable:

**On Linux/Mac:**
```bash
export CFBD_API_KEY="your-api-key-here"
```

**On Windows (Command Prompt):**
```cmd
set CFBD_API_KEY=your-api-key-here
```

**On Windows (PowerShell):**
```powershell
$env:CFBD_API_KEY="your-api-key-here"
```

#### Step 2: Fetch CFBD Data

```bash
cfb-mismatch fetch-cfbd --season 2024 --season-type regular
```

This downloads game data and saves it to `data/cfbd/`.

#### Step 3: Run Integrated Analysis

```bash
cfb-mismatch analyze --season 2024
```

Or fetch and analyze in one step:

```bash
cfb-mismatch analyze --season 2024 --fetch-cfbd
```

The integrated analysis adds:
- Win/loss records
- Points scored and allowed
- Win percentage
- Point differential

## Understanding the Output

### Terminal Output

When you run `cfb-mismatch analyze`, you'll see a summary like this:

```
=== CFB Mismatch Model - Stats Analysis ===

Loading configuration...

Loading stats files...
✓ Loaded 3530 defensive player records
✓ Loaded 2072 receiving concept records
✓ Loaded 2072 receiving scheme records

Computing team-level statistics...
✓ Aggregated defense stats for 136 teams
✓ Aggregated receiving concept stats for 136 teams
✓ Aggregated receiving scheme stats for 136 teams

Saving team statistics to data/out...
✓ Saved data/out/team_defense_coverage.csv
✓ Saved data/out/team_receiving_concept.csv
✓ Saved data/out/team_receiving_scheme.csv

Generating summary report...
✓ Generated summary report (user stats only)
✓ Saved data/out/team_summary.csv

=== Analysis Complete ===

Total teams analyzed: 136
Output directory: data/out

--- Top 5 Teams by Overall Mismatch Score ---
 team_name  mismatch_score mismatch_tier
   INDIANA        0.705147         Elite
   ARIZONA        0.645588         Elite
  MO STATE        0.616176         Elite
     TEXAS        0.608088         Elite
NOTRE DAME        0.599265         Elite

--- Top 5 Teams by Man Coverage Grade ---
 team_name  man_coverage_grade
  DOMINION           67.311000
    HAWAII           66.108654
N ILLINOIS           65.909524
    OREGON           65.787500
 KANSAS ST           65.012214

--- Top 5 Teams by Zone Coverage Grade ---
 team_name  zone_coverage_grade
   N TEXAS            69.944681
TEXAS TECH            68.336207
   HOUSTON            67.943750
      UNLV            67.296970
   INDIANA            66.118681
```

### Output Files Explained

#### 1. team_summary.csv
This is your main file with overall mismatch scores. Key columns:
- `team_name` - Team name
- `mismatch_score` - Overall mismatch score (0-1, higher is better)
- `mismatch_tier` - Elite, Strong, Average, Below Average, Poor
- Individual feature scores for all metrics

#### 2. team_defense_coverage.csv
Detailed defensive coverage metrics:
- `man_coverage_grade` - Average PFF grade in man coverage
- `zone_coverage_grade` - Average PFF grade in zone coverage
- `man_qb_rating_against` - QB rating allowed in man coverage
- `zone_qb_rating_against` - QB rating allowed in zone coverage
- Player counts and games tracked

#### 3. team_receiving_concept.csv
Receiving concept efficiency:
- `screen_yprr` - Yards per route run on screens
- `slot_yprr` - Yards per route run from slot
- Other receiving concept metrics

#### 4. team_receiving_scheme.csv
Receiving scheme metrics:
- `man_yprr` - Yards per route run vs man coverage
- `zone_yprr` - Yards per route run vs zone coverage
- Player counts and games tracked

### Mismatch Tiers

Teams are categorized into tiers based on their overall mismatch score:
- **Elite** (≥0.6): Top-tier teams with significant advantages
- **Strong** (0.4-0.6): Above-average teams with notable strengths
- **Average** (0.2-0.4): Middle-tier teams
- **Below Average** (0.1-0.2): Teams with some weaknesses
- **Poor** (<0.1): Teams with significant disadvantages

## Examples

### Example 1: Quick Analysis

```bash
# Navigate to the repository
cd ValueHunter

# Run the analysis
cfb-mismatch analyze

# View the summary
cat data/out/team_summary.csv
```

### Example 2: Weekly Reports

```bash
# Create a dated output directory
cfb-mismatch analyze --output-dir reports/week_7_2024

# Archive the results
mkdir -p archive/
cp -r reports/week_7_2024 archive/
```

### Example 3: Compare With CFBD Data

```bash
# Set your API key
export CFBD_API_KEY="your-key"

# Fetch and analyze
cfb-mismatch analyze --season 2024 --fetch-cfbd --output-dir reports/2024_integrated

# Results now include win percentages and point differentials
```

### Example 4: Programmatic Use

You can also use the package in your own Python scripts:

```python
from cfb_mismatch.main import (
    load_config,
    load_weights,
    load_all_stats,
    compute_team_stats,
    generate_summary_report
)

# Load configuration
config = load_config()
weights = load_weights()

# Load and process data
defense_df, receiving_concept_df, receiving_scheme_df = load_all_stats(config)
team_stats = compute_team_stats(defense_df, receiving_concept_df, receiving_scheme_df)

# Generate summary
summary = generate_summary_report(team_stats, weights=weights)

# Work with the data
top_teams = summary.nlargest(10, 'mismatch_score')
print(top_teams[['team_name', 'mismatch_score', 'mismatch_tier']])

# Save custom output
summary.to_csv('my_custom_report.csv', index=False)
```

## Troubleshooting

### Issue: "command not found: cfb-mismatch"

**Solution**: The package wasn't installed correctly. Try:
```bash
pip install -e . --force-reinstall
```

Or use the Python module directly:
```bash
python -m cfb_mismatch.cli analyze
```

### Issue: "File not found" errors

**Solution**: Make sure you're in the ValueHunter directory when running commands:
```bash
cd /path/to/ValueHunter
cfb-mismatch analyze
```

### Issue: Empty or missing output files

**Solution**: Check that the input files exist in `data/external/`:
```bash
ls -l data/external/
```

You should see:
- `defense_coverage_scheme 2.csv`
- `receiving_concept 2.csv`
- `receiving_scheme 2.csv`

### Issue: CFBD API errors

**Solution**: 
1. Verify your API key is set:
   ```bash
   echo $CFBD_API_KEY
   ```
2. Check you have a valid key from https://collegefootballdata.com/key
3. Try running without CFBD integration first:
   ```bash
   cfb-mismatch analyze
   ```

### Issue: Permission denied when saving files

**Solution**: Ensure you have write permissions:
```bash
chmod -R u+w data/
```

Or specify a different output directory:
```bash
cfb-mismatch analyze --output-dir ~/my_reports
```

## Configuration

### Adjusting Feature Weights

The model's weights are configured in `configs/weights.yaml`. You can adjust these to change how different features contribute to the overall mismatch score:

```yaml
stats_weights:
  man_coverage_defense: 0.15      # Defensive man coverage importance
  zone_coverage_defense: 0.15     # Defensive zone coverage importance
  man_qb_rating_against: 0.1      # QB rating allowed in man
  zone_qb_rating_against: 0.1     # QB rating allowed in zone
  screen_efficiency: 0.1          # Screen play efficiency
  slot_efficiency: 0.1            # Slot receiving efficiency
  man_receiving_efficiency: 0.15  # Receiving vs man coverage
  zone_receiving_efficiency: 0.15 # Receiving vs zone coverage
```

All weights should sum to 1.0 for proper normalization.

### Settings Configuration

General settings are in `configs/settings.yaml`:

```yaml
# Enable/disable features
use_stats_files: true

# File paths
stats_paths:
  defense_coverage_scheme: "data/external/defense_coverage_scheme 2.csv"
  receiving_concept: "data/external/receiving_concept 2.csv"
  receiving_scheme: "data/external/receiving_scheme 2.csv"

# Output directory
output_dir: "data/out"
```

## Additional Resources

- **[README.md](README.md)** - Full project documentation
- **[USAGE.md](USAGE.md)** - Detailed usage examples
- **[FAQ.md](FAQ.md)** - Common questions about integration
- **[DATA_INTEGRATION.md](DATA_INTEGRATION.md)** - Data architecture details

## Support

If you encounter issues not covered in this guide:
1. Check the FAQ.md file
2. Review existing GitHub issues
3. Open a new issue with details about your problem

---

**Quick Reference Commands**

```bash
# Basic analysis - choose one method
python run_model.py           # Simple Python script
./run_model.sh                # Simple bash script
cfb-mismatch analyze          # Direct CLI command

# Custom output location
cfb-mismatch analyze --output-dir my_reports/

# With CFBD integration
export CFBD_API_KEY="your-key"
cfb-mismatch fetch-cfbd --season 2024 --season-type regular
cfb-mismatch analyze --season 2024

# Help
cfb-mismatch --help
cfb-mismatch analyze --help
cfb-mismatch fetch-cfbd --help
```
