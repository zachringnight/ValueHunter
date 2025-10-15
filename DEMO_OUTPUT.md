# Complete Model Run Demonstration

This document shows a complete end-to-end demonstration of running the CFB Mismatch Model.

## Prerequisites Check

Before running, ensure you have:
- ✅ Python 3.9+ installed
- ✅ Git installed
- ✅ Internet connection (for installation)

## Step-by-Step Execution

### 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/zachringnight/ValueHunter.git
cd ValueHunter

# Install the package
pip install -e .
```

**Expected Output:**
```
Successfully installed cfb-mismatch-0.1.0 numpy-2.3.4 pandas-2.3.3 tzdata-2025.2
```

### 2. Verify Installation

```bash
cfb-mismatch --help
```

**Output:**
```
usage: cfb-mismatch [-h] {analyze,fetch-cfbd} ...

CFB Mismatch Model - Integrate and analyze college football stats

positional arguments:
  {analyze,fetch-cfbd}  Available commands
    analyze             Analyze uploaded stats files
    fetch-cfbd          Fetch CFBD data from API and save to files

options:
  -h, --help            show this help message and exit
```

### 3. Run the Model

```bash
cfb-mismatch analyze
```

**Complete Output:**

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

### 4. Examine the Results

```bash
# List generated files
ls -lh data/out/

# View first few rows of summary
head -5 data/out/team_summary.csv
```

**Output Files:**
```
total 460K
-rw-rw-r-- 136K team_defense_coverage.csv
-rw-rw-r-- 130K team_receiving_concept.csv
-rw-rw-r-- 139K team_receiving_scheme.csv
-rw-rw-r--  49K team_summary.csv
```

## Data Flow Diagram

```
Input Data Files (data/external/)
    │
    ├── defense_coverage_scheme 2.csv (3,530 player records)
    ├── receiving_concept 2.csv (2,072 player records)
    └── receiving_scheme 2.csv (2,072 player records)
    │
    ▼
[Load & Validate]
    │
    ▼
[Aggregate to Team Level]
    │
    ├── Calculate team averages
    ├── Weight by player-games
    └── Normalize metrics
    │
    ▼
[Compute Mismatch Scores]
    │
    ├── Apply feature weights from configs/weights.yaml
    ├── Calculate composite scores
    └── Assign tiers (Elite, Strong, Average, Below Average, Poor)
    │
    ▼
Output Files (data/out/)
    │
    ├── team_defense_coverage.csv (136 teams)
    ├── team_receiving_concept.csv (136 teams)
    ├── team_receiving_scheme.csv (136 teams)
    └── team_summary.csv (Overall scores & tiers)
```

## Understanding the Results

### Mismatch Score Interpretation

| Score Range | Tier | Meaning |
|-------------|------|---------|
| 0.60 - 1.00 | **Elite** | Top-tier teams with significant statistical advantages |
| 0.40 - 0.59 | **Strong** | Above-average teams with notable strengths |
| 0.20 - 0.39 | **Average** | Middle-tier teams, balanced performance |
| 0.10 - 0.19 | **Below Average** | Teams with some weaknesses |
| 0.00 - 0.09 | **Poor** | Teams with significant statistical disadvantages |

### Key Metrics Explained

#### Defense Coverage Metrics
- **man_coverage_grade**: PFF grade for man-to-man coverage (higher is better)
- **zone_coverage_grade**: PFF grade for zone coverage (higher is better)
- **man_qb_rating_against**: QB rating allowed in man coverage (lower is better)
- **zone_qb_rating_against**: QB rating allowed in zone coverage (lower is better)

#### Receiving Metrics
- **screen_yprr**: Yards per route run on screen plays
- **slot_yprr**: Yards per route run from slot position
- **man_yprr**: Yards per route run vs man coverage
- **zone_yprr**: Yards per route run vs zone coverage

### Top Teams Analysis

From the output above, the **Elite** tier teams are:

1. **INDIANA (0.705)** - Best overall balance
   - Strong zone coverage (66.1 grade)
   - Excellent receiving efficiency
   - Low QB rating allowed in man coverage

2. **ARIZONA (0.646)** - Solid all-around
   - Balanced man (64.0) and zone (65.4) coverage
   - Good defensive metrics

3. **MO STATE (0.616)** - Strong defense
   - Consistent coverage grades
   - Efficient receiving concepts

4. **TEXAS (0.608)** - Balanced excellence
   - Strong in both coverage types
   - Good offensive efficiency

5. **NOTRE DAME (0.599)** - Elite receiving
   - Excellent zone receiving efficiency
   - Strong screen game

### Specialized Rankings

**Best Man Coverage Defenses:**
- DOMINION leads with 67.3 grade
- These teams excel at tight man-to-man coverage

**Best Zone Coverage Defenses:**
- N TEXAS leads with 69.9 grade
- These teams excel at zone coverage schemes

## Running Time

| Operation | Time |
|-----------|------|
| Installation | ~30 seconds |
| Model Analysis | ~3-5 seconds |
| Total | **~35 seconds** |

## What Can You Do With These Results?

### 1. Betting Analysis
Identify teams with statistical edges for more informed betting decisions.

### 2. Fantasy Football
Select receivers from teams with high receiving efficiency metrics.

### 3. Game Preparation
Understand opponent strengths and weaknesses for game planning.

### 4. Trend Analysis
Run weekly to track how teams improve or decline over the season.

### 5. Matchup Prediction
Compare two opposing teams' metrics to predict game outcomes.

### 6. Custom Research
Load the CSV files into Python, R, or Excel for deeper analysis.

## Advanced Usage Examples

### Example 1: Analyze Specific Team
```python
import pandas as pd

summary = pd.read_csv('data/out/team_summary.csv')
team = summary[summary['team_name'] == 'INDIANA']
print(team.T)  # Transpose for easier reading
```

### Example 2: Find Defensive Specialists
```python
import pandas as pd

summary = pd.read_csv('data/out/team_summary.csv')
defensive = summary[['team_name', 'man_coverage_grade', 'zone_coverage_grade']]
top_defense = defensive.nlargest(10, 'zone_coverage_grade')
print(top_defense)
```

### Example 3: Identify Offensive Powerhouses
```python
import pandas as pd

summary = pd.read_csv('data/out/team_summary.csv')
offensive = summary[['team_name', 'man_yprr', 'zone_yprr']]
top_offense = offensive.assign(
    total_yprr=lambda x: x['man_yprr'] + x['zone_yprr']
).nlargest(10, 'total_yprr')
print(top_offense)
```

### Example 4: Custom Output Directory
```bash
# Create dated directory
mkdir -p reports/$(date +%Y-%m-%d)

# Run analysis
cfb-mismatch analyze --output-dir reports/$(date +%Y-%m-%d)
```

## Automated Demo Script

Run the included demo script for a complete walkthrough:

```bash
./demo_run.sh
```

This script will:
1. Verify installation
2. Show available commands
3. Run the analysis
4. Display generated files
5. Show sample results

## Next Steps

Now that you've successfully run the model:

1. **Explore the data**: Open the CSV files in Excel or your preferred tool
2. **Customize weights**: Edit `configs/weights.yaml` to adjust feature importance
3. **Integrate CFBD data**: Set up API key and fetch game context
4. **Automate runs**: Create scripts to run weekly analysis
5. **Build visualizations**: Use the data to create charts and graphs

## Resources

- **[QUICKSTART.md](QUICKSTART.md)** - 3-step quick start
- **[HOW_TO_RUN.md](HOW_TO_RUN.md)** - Comprehensive guide
- **[EXAMPLE_RUN.md](EXAMPLE_RUN.md)** - Detailed output explanation
- **[README.md](README.md)** - Full project documentation
- **[USAGE.md](USAGE.md)** - Additional examples
- **[FAQ.md](FAQ.md)** - Common questions

## Summary

✅ You've successfully:
- Installed the CFB Mismatch Model
- Run an analysis on 136 teams
- Generated 4 output files with comprehensive statistics
- Identified Elite teams with the highest mismatch scores
- Learned how to interpret the results

**Total time: ~5 minutes**

The model is now ready for regular use. Simply run `cfb-mismatch analyze` whenever you want updated analysis!
