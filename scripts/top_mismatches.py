#!/usr/bin/env python3
"""
Generate a top-10 list of passing mismatches for the specified college football
season and season type. The script reads the CFBD games file and a team
summary CSV produced by the `cfb-mismatch analyze` command, computes a
simple passing-tilt metric for each matchup, and writes the top 10 mismatches
to both CSV and Markdown files.

Usage:
    python scripts/top_mismatches.py \
        --season 2025 \
        --season-type regular \
        --cfbd-dir data/cfbd \
        --summary-path reports/weekly/team_summary.csv \
        --outdir reports/weekly

This script makes reasonable assumptions about the column names in the
team_summary.csv. It looks for columns containing "YPRR" to derive an
offensive efficiency metric and for coverage-grade columns containing
"coverage" along with "man" or "zone" for defensive efficiency. If your
summary file uses different names, you may need to adjust the heuristics
below.
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from typing import List, Optional

import numpy as np
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Top 10 passing mismatches from a CFB season"
    )
    parser.add_argument("--season", type=int, required=True, help="Year, e.g. 2025")
    parser.add_argument(
        "--season-type",
        type=str,
        default="regular",
        help="Season type: regular, postseason, or both",
    )
    parser.add_argument(
        "--cfbd-dir",
        type=str,
        required=True,
        help="Directory containing CFBD games CSVs",
    )
    parser.add_argument(
        "--summary-path",
        type=str,
        required=True,
        help="Path to team_summary.csv produced by cfb-mismatch analyze",
    )
    parser.add_argument(
        "--outdir",
        type=str,
        default="reports/weekly",
        help="Output directory for mismatch summaries",
    )
    return parser.parse_args()


def load_games(season: int, season_type: str, cfbd_dir: str) -> pd.DataFrame:
    """Load CFBD games CSV for the given season and type."""
    file_name = f"{season}_{season_type}_games.csv"
    path = os.path.join(cfbd_dir, file_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing CFBD games file: {path}")
    games = pd.read_csv(path)
    # Ensure string columns for merge keys
    games["home_team"] = games["home_team"].astype(str)
    games["away_team"] = games["away_team"].astype(str)
    return games


def load_summary(summary_path: str) -> pd.DataFrame:
    """Load the team summary CSV produced by cfb-mismatch."""
    summary = pd.read_csv(summary_path)
    # Identify the team name column heuristically
    possible_team_cols = [
        col
        for col in summary.columns
        if col.lower() in {"team", "team_name", "school", "school_name"}
    ]
    team_col = possible_team_cols[0] if possible_team_cols else summary.columns[0]
    summary = summary.rename(columns={team_col: "Team"})
    return summary


def compute_metrics(summary: pd.DataFrame) -> pd.DataFrame:
    """Compute offensive and defensive metrics based on available columns."""
    # Offensive metric: average yards per route run (YPRR) across available facets
    offense_cols = [col for col in summary.columns if "yprr" in col.lower()]
    if offense_cols:
        summary["OffenseMetric"] = summary[offense_cols].mean(axis=1)
    else:
        # Fallback: use any receiving efficiency metric
        summary["OffenseMetric"] = np.nan

    # Defensive coverage metric: average of man/zone coverage grades
    coverage_cols: List[str] = []
    for col in summary.columns:
        low = col.lower()
        if "coverage" in low and any(x in low for x in ("man", "zone")):
            coverage_cols.append(col)
    if coverage_cols:
        summary["CoverageMetric"] = summary[coverage_cols].mean(axis=1)
    else:
        summary["CoverageMetric"] = np.nan
    # Add a key for joining
    summary["TeamKey"] = summary["Team"].str.upper()
    return summary


def merge_and_score(
    games: pd.DataFrame, summary: pd.DataFrame
) -> pd.DataFrame:
    """Merge team metrics into games and compute pass tilt for each matchup."""
    # Prepare merge keys
    games = games.copy()
    games["home_team_key"] = games["home_team"].str.upper()
    games["away_team_key"] = games["away_team"].str.upper()

    # Merge home and away teams
    merged = games.merge(
        summary[["TeamKey", "OffenseMetric", "CoverageMetric", "Team"]],
        left_on="home_team_key",
        right_on="TeamKey",
        how="left",
    ).rename(
        columns={
            "OffenseMetric": "HomeOffense",
            "CoverageMetric": "HomeCoverage",
            "Team": "HomeTeamName",
        }
    )
    merged = merged.merge(
        summary[["TeamKey", "OffenseMetric", "CoverageMetric", "Team"]],
        left_on="away_team_key",
        right_on="TeamKey",
        how="left",
    ).rename(
        columns={
            "OffenseMetric": "AwayOffense",
            "CoverageMetric": "AwayCoverage",
            "Team": "AwayTeamName",
        }
    )

    # Compute pass tilt: offense minus opponent coverage, summed for both sides
    merged["home_pass_tilt"] = merged["HomeOffense"] - merged["AwayCoverage"]
    merged["away_pass_tilt"] = merged["AwayOffense"] - merged["HomeCoverage"]
    merged["tilt"] = merged["home_pass_tilt"] + merged["away_pass_tilt"]

    # Determine week number if present; if not, default to NaN
    week_col = None
    for candidate in ["week", "Week"]:
        if candidate in merged.columns:
            week_col = candidate
            break
    if week_col:
        merged["week"] = merged[week_col]
    else:
        merged["week"] = np.nan

    merged["matchup"] = merged["home_team"] + " vs " + merged["away_team"]
    return merged


def write_outputs(
    top: pd.DataFrame, outdir: str, season: int, week: Optional[int]
) -> None:
    """Write CSV and Markdown summaries to the output directory."""
    os.makedirs(outdir, exist_ok=True)
    week_str = str(int(week)) if week is not None and not np.isnan(week) else "unknown"
    # Output filenames incorporate the week
    csv_filename = f"top_mismatches_week_{week_str}.csv"
    md_filename = f"top_mismatches_week_{week_str}.md"
    csv_path = os.path.join(outdir, csv_filename)
    md_path = os.path.join(outdir, md_filename)

    top_fields = ["matchup", "week", "home_pass_tilt", "away_pass_tilt", "tilt"]
    top[top_fields].to_csv(csv_path, index=False)

    # Generate Markdown overview
    md_lines = ["# Top 10 Passing Mismatches", ""]
    for _, row in top.iterrows():
        wk = int(row["week"]) if not np.isnan(row["week"]) else week_str
        md_lines.append(f"## {row['matchup']} (Week {wk})")
        md_lines.append(f"- Home pass tilt: {row['home_pass_tilt']:.2f}")
        md_lines.append(f"- Away pass tilt: {row['away_pass_tilt']:.2f}")
        md_lines.append(f"- Overall tilt: **{row['tilt']:.2f}**")
        md_lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"Wrote {csv_path} and {md_path}")


def main() -> None:
    args = parse_args()
    games = load_games(args.season, args.season_type, args.cfbd_dir)
    summary = compute_metrics(load_summary(args.summary_path))
    merged = merge_and_score(games, summary)
    # Sort by overall tilt descending and select top 10
    top10 = merged.nlargest(10, "tilt").reset_index(drop=True)
    # Determine week to use in output naming; use first valid week if available
    week_val = None
    if not top10["week"].isnull().all():
        # Use the week from the first matchup
        try:
            week_val = int(top10["week"].dropna().iloc[0])
        except Exception:
            week_val = None
    write_outputs(top10, args.outdir, args.season, week_val)


if __name__ == "__main__":
    main()
