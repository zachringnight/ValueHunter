import subprocess
import sys

import pandas as pd


def test_cli_analyze_generates_outputs(tmp_path):
    output_dir = tmp_path / "cli"
    output_dir.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cfb_mismatch.cli",
            "analyze",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    summary_path = output_dir / "team_summary.csv"
    defense_path = output_dir / "team_defense_coverage.csv"
    concept_path = output_dir / "team_receiving_concept.csv"
    scheme_path = output_dir / "team_receiving_scheme.csv"

    assert summary_path.exists(), result.stdout
    assert defense_path.exists()
    assert concept_path.exists()
    assert scheme_path.exists()

    summary_df = pd.read_csv(summary_path)
    assert not summary_df.empty
    assert {"team_name", "mismatch_score"}.issubset(summary_df.columns)
    assert summary_df["team_name"].notna().all()
