# CFB Mismatch Model

This repository contains a Python package and command‑line interface for computing
weekly position‑group mismatch scores for college football games.  It pulls
play‑by‑play and team metrics from the CollegeFootballData API and optionally
incorporates proprietary data from Pro Football Focus (PFF) and FantasyPoints to
capture offensive line, defensive line, run‑concept, coverage, and receiver
splits at a more granular level.  The output is a set of CSV files ranking
matchups by their projected edges in the run game, pass protection versus pass
rush, passing game versus coverage, and an overall “tilt” score.

## Features

* **CFBD integration** – fetches EPA, success rate, explosiveness, havoc and
  pace metrics for all FBS teams for the specified week and year.
* **PFF & FantasyPoints adapters** – optional loaders for CSV exports of
  offensive line/pass rush win rates, defensive fronts and coverages, run
  concept usage and efficiency, and receiver splits vs man/zone coverage.  See
  `configs/settings.yaml` for how to enable them and specify file paths.
* **Configurable weights** – tune the relative importance of each feature via
  YAML in `configs/weights.yaml` without touching code.
* **Extensible architecture** – most logic lives in `cfb_mismatch/main.py` and
  `cfb_mismatch/ext_features.py` so you can add new metrics or adjust the
  computation pipeline easily.
* **Command‑line interface** – run `cfb‑mismatch week` with year and week
  arguments to produce CSVs of top mismatches.

## Quick start

### Prerequisites

1. **Python** – This package targets Python 3.9+.  Other versions may work but
   are untested.
2. **CFBD API key** – Required for fetching team metrics from CollegeFootballData API.
   See the [Setting Up Your API Key](#setting-up-your-api-key) section below for detailed instructions.
3. **Optional: PFF & FantasyPoints exports** – For a more comprehensive model,
   export the following CSV files and place them in `data/external/`:

   * `pff_ol_dl.csv` – Offensive line and defensive line win rates and
     protection tendencies by team.
   * `pff_def_front_cov.csv` – Defensive front, box and coverage shell
     frequencies by team.
   * `pff_run_concepts.csv` – Offensive run concept usage and efficiency by
     team.
   * `fp_receiver_splits.csv` – Receiver yards per route run, targets and
     alignment splits vs man and zone coverage from FantasyPoints.

   The exact column names expected by the adapters are documented in
   `cfb_mismatch/adapters/pff.py` and `cfb_mismatch/adapters/fantasypoints.py`.
   If a file is missing or disabled in `configs/settings.yaml`, the package
   gracefully falls back to the base metrics only.

> **💡 New to the integration?** Check out the [FAQ](FAQ.md) for common questions about integrating your stats files with CFBD API data.

## Setting Up Your API Key

The CFBD API key is required to fetch college football data. Here's how to set it up:

### 1. Get Your API Key

1. Visit https://collegefootballdata.com/key
2. Sign up for a free account (if you don't have one)
3. Generate your API key
4. Copy the key - you'll need it in the next step

### 2. Set the API Key in Your Environment

Choose the method that works best for your situation:

#### For a Single Session (Temporary)

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

#### Make It Permanent (Recommended for Local Development)

**On Linux/Mac:**

Add the export line to your shell configuration file:
```bash
# For bash users (add to ~/.bashrc or ~/.bash_profile)
echo 'export CFBD_API_KEY="your-api-key-here"' >> ~/.bashrc
source ~/.bashrc

# For zsh users (add to ~/.zshrc)
echo 'export CFBD_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

**On Windows:**

1. Search for "Environment Variables" in Windows settings
2. Click "Edit the system environment variables"
3. Click "Environment Variables" button
4. Under "User variables", click "New"
5. Variable name: `CFBD_API_KEY`
6. Variable value: your API key
7. Click OK and restart your terminal

**For R Users:**

If you're using the R scripts, you can add to your `~/.Renviron` file:
```bash
echo 'CFBD_API_KEY=your-api-key-here' >> ~/.Renviron
```
Then restart R.

#### For GitHub Actions (Automated Workflows)

If you want to use GitHub Actions to fetch data automatically:

1. Go to your repository on GitHub
2. Navigate to: Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `CFBD_API_KEY`
5. Value: your API key from step 1
6. Click "Add secret"

### 3. Verify Your Setup

Test that your API key is set correctly:

**On Linux/Mac:**
```bash
echo $CFBD_API_KEY
```

**On Windows (Command Prompt):**
```cmd
echo %CFBD_API_KEY%
```

**On Windows (PowerShell):**
```powershell
echo $env:CFBD_API_KEY
```

You should see your API key printed. If it's empty, revisit step 2.

### Security Note

⚠️ **Never commit your API key to the repository!** The key should only be stored as an environment variable or in GitHub repository secrets. The `.gitignore` file is configured to prevent accidental commits of sensitive data.

### Installation

Clone this repository and install it in editable mode:

```bash
git clone <your‑repo‑url> cfb-mismatch
cd cfb-mismatch
pip install -e .
```

Alternatively, you can run it in place with `python -m cfb_mismatch.cli`.

### Analyzing the Integrated Stats

The repository includes three stats files that have been integrated:
- Defense coverage scheme statistics (man vs zone coverage)
- Receiving concept statistics (screen, slot, etc.)
- Receiving scheme statistics (man vs zone)

To analyze these stats and generate team-level aggregations:

```bash
cfb-mismatch analyze
```

This will:
- Load defense coverage scheme, receiving concept, and receiving scheme data
- Aggregate player-level stats to team-level metrics
- Generate team comparison reports in `data/out/`

Output files include:
- `team_defense_coverage.csv` – Team-level defensive coverage statistics
- `team_receiving_concept.csv` – Team-level receiving concept metrics
- `team_receiving_scheme.csv` – Team-level receiving scheme metrics
- `team_summary.csv` – Combined summary with key metrics

#### Integrating with CFBD API Data

You can combine your player-level stats with CFBD game data for a more complete analysis:

```bash
# 1. Set up your API key (see "Setting Up Your API Key" section above)
# Then fetch CFBD data
Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular

# 2. Run integrated analysis
cfb-mismatch analyze --season 2024
```

This creates an integrated report that combines:
- **Your player stats**: Coverage grades, receiving efficiency, scheme tendencies
- **CFBD game data**: Win/loss records, points scored/allowed, game context

The integrated summary adds team-level metrics like win percentage and point differential.

You can specify a custom output directory:

```bash
cfb-mismatch analyze --season 2024 --output-dir reports/analysis
```

### Running the model

To compute mismatch scores for week 7 of the 2025 season:

```bash
cfb-mismatch week --year 2025 --week 7
```

If `--week` is omitted the current week per CFBD will be used.  The command
will output CSVs under `data/out/` such as `top_run_mismatches.csv`,
`top_pass_mismatches.csv`, `top_passpro_mismatches.csv` and a combined
`cfb_unit_mismatches_week.csv` for the entire slate.

Use the `--output-dir` option to change where files are written:

```bash
cfb-mismatch week --year 2025 --week 7 --output-dir reports/week7
```

### Configuration

Global settings live in `configs/settings.yaml`.  At a minimum you may want to
adjust:

* `use_pff` – Set to `true` to include PFF‑derived features.
* `use_fantasypoints` – Set to `true` to include FantasyPoints‑derived
  receiver splits.
* `pff_paths` – Override default CSV locations if your exports live
  elsewhere.
* `fp_paths` – Override the FantasyPoints export path.

Weights for the base and extended features live in `configs/weights.yaml`.  You
can experiment with different values to better align mismatch scores with
observed outcomes.  See the docstrings in `cfb_mismatch/main.py` for details on
each feature.

## Development

The code is structured as a Python package under `src/cfb_mismatch/`.  Key
components include:

* `cfb_mismatch/cli.py` – Defines the command‑line interface using
  `argparse`.  Additional subcommands can be added here.
* `cfb_mismatch/main.py` – Contains functions to download CFBD metrics,
  compute base mismatch scores and integrate extended features.
* `cfb_mismatch/ext_features.py` – Computes PFF and FantasyPoints derived
  features such as edge/interior pressure expectations, run concept fit index
  and route‑family fit.
* `cfb_mismatch/adapters/` – Loaders for PFF and FantasyPoints CSV exports.

### Testing your data

You can run the pipeline on past seasons to validate your weights.  See the
`build_week()` function in `cfb_mismatch/main.py` for details on how data is
assembled.  Feel free to write your own analysis scripts to backtest and
calibrate the model over 2021–2024.  Because the code uses a single week of
data at a time, you can iterate quickly.

## College Football data via cfbfastR

This repo includes a simple, secure pipeline to fetch College Football data using the R package [cfbfastR](https://cfbfastR.sportsdataverse.org/), which wraps the [CollegeFootballData API](https://collegefootballdata.com/).

**Important: Never commit API keys.** See the [Setting Up Your API Key](#setting-up-your-api-key) section for proper setup instructions.

### 1. Set Up Your API Key

Before fetching data, you need to configure your CFBD API key. See the detailed [Setting Up Your API Key](#setting-up-your-api-key) section above for complete instructions on:
- Getting your API key from https://collegefootballdata.com/key
- Setting it as an environment variable
- Making it persistent across sessions
- Setting it up for GitHub Actions

### 2. Run the data fetch workflow (GitHub Actions)

Once your API key is set up as a repository secret:

- Navigate to the Actions tab → "Fetch CFB data (cfbfastR)"
- Click "Run workflow"
- Provide a `season` (e.g., 2024) and optionally set `season_type` (regular or postseason)
- The job will produce an artifact named like `cfb-data-<season>-<season_type>` containing Parquet and CSV files under `data/cfbd`.

### 3. Run locally (optional)

Once your API key is set up in your environment:

- Install R (https://cloud.r-project.org) and optionally RStudio
- Install packages in an R console:
  ```r
  install.packages(c("arrow"), repos = "https://cloud.r-project.org")
  if (!requireNamespace("remotes", quietly = TRUE)) install.packages("remotes")
  remotes::install_github("sportsdataverse/cfbfastR")
  ```
- Run the script (the API key will be read from your environment):
  ```bash
  Rscript scripts/fetch_cfb_data.R --season 2024 --season_type regular
  ```
- Outputs are written to `data/cfbd` as Parquet and CSV.

### Notes

- Data files are git-ignored to keep the repository small. Download them from the Actions run artifacts or manage them locally.
- If you hit API rate limits, try a smaller query or wait a bit and re-run.

## Additional Documentation

- **[FAQ](FAQ.md)** - Common questions about integrating your files with CFBD API
- **[Data Integration Guide](DATA_INTEGRATION.md)** - Architecture and data flow details
- **[Integration Examples](INTEGRATION_EXAMPLES.md)** - Detailed usage examples and Python API
- **[Usage Guide](USAGE.md)** - Command-line reference

## License

This project is released under the MIT License.  See the `LICENSE` file for
Details.
