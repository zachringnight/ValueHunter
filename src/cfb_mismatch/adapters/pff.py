"""Adapter for loading Pro Football Focus (PFF) CSV exports.

This module provides functions to load and parse PFF data exports including:
- Offensive line and defensive line win rates
- Defensive front and coverage shell frequencies
- Run concept usage and efficiency

Expected CSV column names:
- pff_ol_dl.csv:
  * team, ol_pass_block_wr, ol_run_block_wr, dl_pass_rush_wr, dl_run_stop_wr
- pff_def_front_cov.csv:
  * team, front_heavy_pct, front_light_pct, cover_man_pct, cover_zone_pct
- pff_run_concepts.csv:
  * team, inside_zone_rate, outside_zone_rate, gap_rate, power_rate,
    inside_zone_epa, outside_zone_epa, gap_epa, power_epa
"""
from pathlib import Path
from typing import Dict

import pandas as pd


def load_pff_data(pff_paths: Dict[str, str]) -> Dict[str, pd.DataFrame]:
    """Load all PFF CSV exports.
    
    Args:
        pff_paths: Dictionary mapping data type to file path
        
    Returns:
        Dictionary mapping data type to DataFrame
        
    Raises:
        FileNotFoundError: If a required CSV file is missing
        ValueError: If a CSV has unexpected format
    """
    data = {}
    
    # Load OL/DL data
    if "ol_dl" in pff_paths:
        ol_dl_path = Path(pff_paths["ol_dl"])
        if ol_dl_path.exists():
            data["ol_dl"] = load_ol_dl_data(ol_dl_path)
        else:
            print(f"Warning: PFF OL/DL file not found: {ol_dl_path}")
    
    # Load defensive front/coverage data
    if "def_front_cov" in pff_paths:
        def_front_path = Path(pff_paths["def_front_cov"])
        if def_front_path.exists():
            data["def_front_cov"] = load_def_front_cov_data(def_front_path)
        else:
            print(f"Warning: PFF defensive front/coverage file not found: {def_front_path}")
    
    # Load run concepts data
    if "run_concepts" in pff_paths:
        run_concepts_path = Path(pff_paths["run_concepts"])
        if run_concepts_path.exists():
            data["run_concepts"] = load_run_concepts_data(run_concepts_path)
        else:
            print(f"Warning: PFF run concepts file not found: {run_concepts_path}")
    
    return data


def load_ol_dl_data(file_path: Path) -> pd.DataFrame:
    """Load offensive/defensive line win rate data.
    
    Expected columns:
    - team: Team name
    - ol_pass_block_wr: OL pass block win rate (0-1)
    - ol_run_block_wr: OL run block win rate (0-1)
    - dl_pass_rush_wr: DL pass rush win rate (0-1)
    - dl_run_stop_wr: DL run stop win rate (0-1)
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with OL/DL metrics
    """
    df = pd.read_csv(file_path)
    
    required_cols = [
        "team",
        "ol_pass_block_wr",
        "ol_run_block_wr",
        "dl_pass_rush_wr",
        "dl_run_stop_wr",
    ]
    
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns in OL/DL data: {missing_cols}")
    
    return df[required_cols]


def load_def_front_cov_data(file_path: Path) -> pd.DataFrame:
    """Load defensive front and coverage shell data.
    
    Expected columns:
    - team: Team name
    - front_heavy_pct: Percentage of snaps in heavy front (0-1)
    - front_light_pct: Percentage of snaps in light front (0-1)
    - cover_man_pct: Percentage of snaps in man coverage (0-1)
    - cover_zone_pct: Percentage of snaps in zone coverage (0-1)
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with defensive front/coverage metrics
    """
    df = pd.read_csv(file_path)
    
    required_cols = [
        "team",
        "front_heavy_pct",
        "front_light_pct",
        "cover_man_pct",
        "cover_zone_pct",
    ]
    
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns in def front/cov data: {missing_cols}")
    
    return df[required_cols]


def load_run_concepts_data(file_path: Path) -> pd.DataFrame:
    """Load run concept usage and efficiency data.
    
    Expected columns:
    - team: Team name
    - inside_zone_rate: Inside zone usage rate (0-1)
    - outside_zone_rate: Outside zone usage rate (0-1)
    - gap_rate: Gap scheme usage rate (0-1)
    - power_rate: Power scheme usage rate (0-1)
    - inside_zone_epa: EPA per inside zone play
    - outside_zone_epa: EPA per outside zone play
    - gap_epa: EPA per gap scheme play
    - power_epa: EPA per power scheme play
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with run concept metrics
    """
    df = pd.read_csv(file_path)
    
    required_cols = [
        "team",
        "inside_zone_rate",
        "outside_zone_rate",
        "gap_rate",
        "power_rate",
        "inside_zone_epa",
        "outside_zone_epa",
        "gap_epa",
        "power_epa",
    ]
    
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns in run concepts data: {missing_cols}")
    
    return df[required_cols]
