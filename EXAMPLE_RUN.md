# Example Run: CFB Mismatch Model

This document shows an example of running the model with actual output.

## Basic Run

### Command
```bash
cfb-mismatch analyze
```

### Output
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

## What This Means

The model successfully analyzed **136 teams** based on:
- **3,530 defensive player records**
- **2,072 receiving concept records**
- **2,072 receiving scheme records**

### Top Teams

The analysis identified **5 Elite teams** with the highest mismatch scores:

1. **INDIANA** - 0.705 (Elite)
   - Strengths: High zone coverage grade (66.1), balanced defense
   
2. **ARIZONA** - 0.646 (Elite)
   - Strengths: Strong man and zone coverage grades
   
3. **MO STATE** - 0.616 (Elite)
   - Strengths: Excellent defensive metrics
   
4. **TEXAS** - 0.608 (Elite)
   - Strengths: Balanced offensive and defensive capabilities
   
5. **NOTRE DAME** - 0.599 (Elite)
   - Strengths: Strong receiving efficiency vs zone coverage

### Key Insights

#### Best Man Coverage Defenses
1. DOMINION - 67.3 grade
2. HAWAII - 66.1 grade
3. N ILLINOIS - 65.9 grade
4. OREGON - 65.8 grade
5. KANSAS ST - 65.0 grade

#### Best Zone Coverage Defenses
1. N TEXAS - 69.9 grade
2. TEXAS TECH - 68.3 grade
3. HOUSTON - 67.9 grade
4. UNLV - 67.3 grade
5. INDIANA - 66.1 grade

## Output Files Generated

After the run, four CSV files are created in `data/out/`:

### 1. team_summary.csv
Complete summary with all metrics and overall mismatch scores. Contains:
- Team names
- All individual feature scores
- Overall mismatch score (0-1 scale)
- Mismatch tier (Elite, Strong, Average, Below Average, Poor)

Sample data:
```csv
team_name,mismatch_score,mismatch_tier,man_coverage_grade,zone_coverage_grade
INDIANA,0.705147,Elite,62.88,66.12
ARIZONA,0.645588,Elite,64.03,65.41
MO STATE,0.616176,Elite,63.97,64.81
```

### 2. team_defense_coverage.csv (136 KB)
Detailed defensive coverage statistics for each team:
- Man coverage grades
- Zone coverage grades
- QB rating allowed in man/zone
- Number of players and games tracked

### 3. team_receiving_concept.csv (130 KB)
Receiving concept efficiency metrics:
- Screen yards per route run
- Slot yards per route run
- Player counts
- Games tracked

### 4. team_receiving_scheme.csv (139 KB)
Receiving scheme statistics:
- Yards per route run vs man coverage
- Yards per route run vs zone coverage
- Player and game counts

## File Sizes
```
-rw-rw-r-- 136K team_defense_coverage.csv
-rw-rw-r-- 130K team_receiving_concept.csv
-rw-rw-r-- 139K team_receiving_scheme.csv
-rw-rw-r--  49K team_summary.csv
```

## Running Time

The analysis typically completes in **under 5 seconds** on modern hardware.

## Next Steps

1. **View detailed results**: Open the CSV files in Excel, Google Sheets, or your preferred tool
2. **Filter by tier**: Focus on Elite and Strong teams for best matchups
3. **Compare metrics**: Look at specific defensive or offensive metrics
4. **Run with CFBD data**: Add game context with `--season 2024 --fetch-cfbd`

## Using the Results

The output can be used for:
- **Betting analysis**: Identify teams with statistical advantages
- **Fantasy sports**: Pick players from high-efficiency offenses
- **Game preparation**: Understand team strengths and weaknesses
- **Trend analysis**: Track team performance over time
- **Matchup predictions**: Compare opposing teams' metrics

## Custom Analysis

You can also load the data into Python for custom analysis:

```python
import pandas as pd

# Load the summary
summary = pd.read_csv('data/out/team_summary.csv')

# Find elite teams
elite = summary[summary['mismatch_tier'] == 'Elite']
print(f"Found {len(elite)} elite teams")

# Get top offensive teams
top_offense = summary.nlargest(10, 'man_yprr')
print("Top 10 teams in receiving efficiency vs man coverage:")
print(top_offense[['team_name', 'man_yprr']])

# Compare defense types
print("\nCorrelation between man and zone coverage grades:")
print(summary[['man_coverage_grade', 'zone_coverage_grade']].corr())
```

## Conclusion

The model provides comprehensive team-level analytics that aggregate thousands of player-level statistics into actionable insights. The mismatch scores help identify teams with statistical advantages across multiple dimensions of play.

For more details on interpretation and usage, see:
- [HOW_TO_RUN.md](HOW_TO_RUN.md) - Complete usage guide
- [README.md](README.md) - Project overview
- [USAGE.md](USAGE.md) - Additional examples
