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

## Q: How do I get and set up a CFBD API key?

### Getting Your API Key

1. Visit https://collegefootballdata.com/key
2. Sign up for a free account (if you don't have one)
3. Generate your API key
4. Copy the key for use in the next step

### Setting Up the API Key

The API key must be set as an environment variable named `CFBD_API_KEY`. Choose the method appropriate for your use case:

#### Quick Setup (Current Terminal Session Only)

**Linux/Mac:**
```bash
export CFBD_API_KEY="your-api-key-here"
```

**Windows Command Prompt:**
```cmd
set CFBD_API_KEY=your-api-key-here
```

**Windows PowerShell:**
```powershell
$env:CFBD_API_KEY="your-api-key-here"
```

#### Permanent Setup (Recommended)

**Linux/Mac - Add to Shell Configuration:**
```bash
# For bash users
echo 'export CFBD_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc

# For zsh users
echo 'export CFBD_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

**Windows - System Environment Variables:**
1. Search for "Environment Variables" in Windows settings
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Under "User variables", click "New"
5. Set Variable name: `CFBD_API_KEY`
6. Set Variable value: your API key
7. Click OK and restart your terminal

**R Users - Add to .Renviron:**
```bash
echo 'CFBD_API_KEY=your-api-key-here' >> ~/.Renviron
```
Then restart R.

#### For GitHub Actions

1. Go to: Settings → Secrets and variables → Actions → New repository secret
2. Name: `CFBD_API_KEY`
3. Value: your API key
4. Click "Add secret"

### Verify Your Setup

**Linux/Mac:**
```bash
echo $CFBD_API_KEY
```

**Windows Command Prompt:**
```cmd
echo %CFBD_API_KEY%
```

**Windows PowerShell:**
```powershell
echo $env:CFBD_API_KEY
```

Your API key should be displayed. If it's empty, the environment variable isn't set correctly.

### Security

⚠️ **Important:** Never commit your API key to version control! Always use environment variables or repository secrets.

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
