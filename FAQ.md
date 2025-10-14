# Frequently Asked Questions

## Q: Is this integrating my files and the CFBD API?

**Short answer:** Yes! The repository now integrates both your player-level stats files AND CFBD API data.

**How it works:**

1. **Your Stats Files** (Player-level data):
   - `defense_coverage_scheme 2.csv` - Defensive player performance by coverage type
   - `receiving_concept 2.csv` - Receiver performance by route concept
   - `receiving_scheme 2.csv` - Receiver performance by scheme (man/zone)
   
   These are **always loaded** when you run `cfb-mismatch analyze`.

2. **CFBD API Data** (Team-level game data):
   - Fetched using the R script: `scripts/fetch_cfb_data.R`
   - Contains games, scores, team info
   - Provides win/loss records, points scored/allowed
   
   This is **optionally integrated** when you provide the `--season` parameter.

### Usage Examples

**Without CFBD Integration (User stats only):**
```bash
cfb-mismatch analyze
```
Output: Team-level aggregations of your player data.

**With CFBD Integration (Both data sources):**
```bash
# First, fetch CFBD data
export CFBD_API_KEY="your-key"
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular

# Then analyze with integration
cfb-mismatch analyze --season 2024
```
Output: Team-level aggregations PLUS game results, win percentage, scoring data.

### What Gets Integrated?

When you use `--season`, the system:
1. Loads your player-level stats and aggregates to team level
2. Loads CFBD game data for that season
3. Calculates team-level metrics (wins, scoring averages, etc.)
4. **Merges both datasets** by team name
5. Produces an integrated summary with all metrics

### Example Integrated Output

The `team_summary.csv` file contains:

**From your stats:**
- `man_coverage_grade` - Defensive man coverage grade
- `zone_coverage_grade` - Defensive zone coverage grade
- `man_qb_rating_against` - QB rating allowed vs man coverage
- `zone_qb_rating_against` - QB rating allowed vs zone coverage
- `screen_yprr` - Yards per route run on screen plays
- `slot_yprr` - Yards per route run in slot
- `man_yprr` - Receiving yards per route run vs man
- `zone_yprr` - Receiving yards per route run vs zone

**From CFBD API:**
- `games_played` - Number of games played
- `wins` - Number of wins
- `win_pct` - Win percentage
- `avg_points_scored` - Average points scored per game
- `avg_points_allowed` - Average points allowed per game
- `point_differential` - Average point differential

### Why Integrate?

Combining both sources lets you:
- Correlate player performance with team outcomes
- Identify which coverage schemes lead to wins
- Compare receiving efficiency with scoring output
- Find mismatches between scheme tendencies and results

## Q: Do I need to use both data sources?

**No!** You can use either or both:

- **Your stats only**: Run `cfb-mismatch analyze` without `--season`
- **CFBD data only**: Run the R script to fetch data (no Python analysis needed)
- **Both integrated**: Run `cfb-mismatch analyze --season 2024`

## Q: How do I get a CFBD API key?

1. Go to https://collegefootballdata.com/key
2. Sign up for a free account
3. Generate an API key
4. Set it in your environment: `export CFBD_API_KEY="your-key"`

## Q: What if team names don't match between datasets?

The integration normalizes team names (uppercase, trimmed spaces) to improve matching. If a team from your stats doesn't have CFBD data, the CFBD columns will be empty for that team.

## Q: Can I use this for multiple seasons?

Yes! Fetch data for multiple seasons and analyze each:

```bash
# Fetch multiple seasons
Rscript scripts/fetch_cfb_data.R --season 2023 --season_type regular
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular

# Analyze each
cfb-mismatch analyze --season 2023 --output-dir reports/2023
cfb-mismatch analyze --season 2024 --output-dir reports/2024
```

## Q: Where can I learn more?

- `DATA_INTEGRATION.md` - Architecture and data flow details
- `INTEGRATION_EXAMPLES.md` - Detailed usage examples and Python API
- `README.md` - Overall project documentation
- `USAGE.md` - Command-line reference
