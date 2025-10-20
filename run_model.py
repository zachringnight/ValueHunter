#!/usr/bin/env python3
"""
Simple script to run the CFB Mismatch Model.

This enhanced wrapper will:
- If CFBD_API_KEY is set: fetch fresh CFBD data for the current season and analyze
- Otherwise: run analysis with existing local inputs only
- Fall back to module invocation if the `cfb-mismatch` console command isn't found
- Print helpful environment info and check for expected outputs

Usage: python run_model.py
Optional: set RUN_SEASON=YYYY to override the current year.
"""

import sys
import os
import platform
import shutil
import subprocess
from datetime import datetime

EXPECTED_FILES = [
    "data/out/team_summary.csv",
    "data/out/team_defense_coverage.csv",
    "data/out/team_receiving_concept.csv",
    "data/out/team_receiving_scheme.csv",
]


def run_cmd(cmd):
    print(f"$ {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode
    except subprocess.CalledProcessError as e:
        return e.returncode or 1
    except FileNotFoundError:
        return 127


essential_help = """
Troubleshooting steps:
1) Install the package into your active environment:
   pip install -e .
2) Verify the CLI is available:
   cfb-mismatch --help   (or)
   {py} -m cfb_mismatch.cli --help
3) To enable fresh CFBD data fetch, set your API key:
   export CFBD_API_KEY="your-key"    # macOS/Linux
   $env:CFBD_API_KEY="your-key"     # Windows PowerShell
4) Re-run this script.
""".strip()


def main():
    print("=" * 60)
    print("CFB Mismatch Model - Quick Run")
    print("=" * 60)
    print(f"Python: {sys.version.split()[0]}  Executable: {sys.executable}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print()

    # Determine season year
    season = os.getenv("RUN_SEASON")
    if season is not None:
        try:
            season = int(season)
        except ValueError:
            season = None
    if season is None:
        season = datetime.now().year

    # CLI availability
    have_cli = shutil.which("cfb-mismatch") is not None

    # CFBD API key presence decides whether we fetch fresh data
    api_key = os.getenv("CFBD_API_KEY")
    use_cfbd = bool(api_key)

    print("Running model analysis...")
    if use_cfbd:
        print(f"CFBD_API_KEY detected. Will fetch and analyze for season {season}.")
    else:
        print("CFBD_API_KEY not set. Running analysis without fetching CFBD data.")
        print("You can set RUN_SEASON to override season year when CFBD is enabled.")
    print()

    # Build command
    if have_cli:
        base = ["cfb-mismatch"]
    else:
        print("'cfb-mismatch' not found on PATH. Using module invocation...")
        base = [sys.executable, "-m", "cfb_mismatch.cli"]

    cmd = base + ["analyze"]
    if use_cfbd:
        cmd += ["--season", str(season), "--fetch-cfbd"]

    code = run_cmd(cmd)

    if code == 0:
        print()
        print("=" * 60)
        print("\u2713 Model run complete!")
        print("=" * 60)
        print()
        # Check expected outputs
        print("Checking expected outputs under data/out/:")
        missing = []
        for rel in EXPECTED_FILES:
            if os.path.exists(rel):
                print(f"  \u2714 {rel}")
            else:
                print(f"  \u2026 not found: {rel}")
                missing.append(rel)

        print()
        if missing:
            print("Note: Some expected outputs were not found. This may be okay if your")
            print("configuration disables certain outputs. If unexpected, check the CLI")
            print("logs above for warnings or errors.")
        else:
            print("All expected outputs are present.")
        print()
        print("Output files are in: data/out/")
        print("  - team_summary.csv (main results)")
        print("  - team_defense_coverage.csv")
        print("  - team_receiving_concept.csv")
        print("  - team_receiving_scheme.csv")
        print()
        return 0

    print()
    print("=" * 60)
    print("\u2717 Error running model")
    print("=" * 60)
    print()
    print(essential_help.format(py=os.path.basename(sys.executable)))
    print()
    # Also suggest direct module invocation with args that were attempted
    if have_cli:
        alt = [os.path.basename(sys.executable), "-m", "cfb_mismatch.cli"] + cmd[1:]
        print("Try:")
        print(" ", " ".join(alt))
        print()
    return 1


if __name__ == "__main__":
    sys.exit(main())
