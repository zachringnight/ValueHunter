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
2. **CFBD API key** – Set the environment variable `CFBD_API_KEY` to your
   [CollegeFootballData](https://collegefootballdata.com/) API token.  Without
   a key the script cannot pull team metrics.
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

### Installation

Clone this repository and install it in editable mode:

```bash
git clone <your‑repo‑url> cfb-mismatch
cd cfb-mismatch
pip install -e .
```

Alternatively, you can run it in place with `python -m cfb_mismatch.cli`.

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

## License

This project is released under the MIT License.  See the `LICENSE` file for
Details.
