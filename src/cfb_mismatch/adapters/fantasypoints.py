"""Adapter for loading FantasyPoints CSV exports.

This module provides functions to load and parse FantasyPoints data exports including:
- Receiver yards per route run, targets and alignment splits vs man and zone coverage

Expected CSV column names for fp_receiver_splits.csv:
- team: Team name
- player: Player name
- yprr_vs_man: Yards per route run vs man coverage
- yprr_vs_zone: Yards per route run vs zone coverage
- targets_vs_man: Target count vs man coverage
- targets_vs_zone: Target count vs zone coverage
- slot_rate: Percentage of snaps in slot alignment (0-1)
- target_share: Player's share of team targets (0-1)
"""
from pathlib import Path
from typing import Dict

import pandas as pd


def load_fantasypoints_data(fp_paths: Dict[str, str]) -> Dict[str, pd.DataFrame]:
    """Load all FantasyPoints CSV exports.
    
    Args:
        fp_paths: Dictionary mapping data type to file path
        
    Returns:
        Dictionary mapping data type to DataFrame
        
    Raises:
        FileNotFoundError: If a required CSV file is missing
        ValueError: If a CSV has unexpected format
    """
    data = {}
    
    # Load receiver splits data
    if "receiver_splits" in fp_paths:
        receiver_path = Path(fp_paths["receiver_splits"])
        if receiver_path.exists():
            data["receiver_splits"] = load_receiver_splits_data(receiver_path)
        else:
            print(f"Warning: FantasyPoints receiver splits file not found: {receiver_path}")
    
    return data


def load_receiver_splits_data(file_path: Path) -> pd.DataFrame:
    """Load receiver splits data (yards per route run, targets vs man/zone).
    
    Expected columns:
    - team: Team name
    - player: Player name
    - yprr_vs_man: Yards per route run vs man coverage
    - yprr_vs_zone: Yards per route run vs zone coverage
    - targets_vs_man: Target count vs man coverage
    - targets_vs_zone: Target count vs zone coverage
    - slot_rate: Percentage of snaps in slot (0-1)
    - target_share: Share of team targets (0-1)
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with receiver metrics
    """
    df = pd.read_csv(file_path)
    
    required_cols = [
        "team",
        "player",
        "yprr_vs_man",
        "yprr_vs_zone",
        "targets_vs_man",
        "targets_vs_zone",
        "slot_rate",
        "target_share",
    ]
    
    missing_cols = set(required_cols) - set(df.columns)
    if missing_cols:
        raise ValueError(f"Missing required columns in receiver splits data: {missing_cols}")
    
    return df[required_cols]


def aggregate_team_receiver_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate player-level receiver metrics to team level.
    
    Computes weighted averages based on target share.
    
    Args:
        df: DataFrame with player-level receiver metrics
        
    Returns:
        DataFrame with team-level aggregated metrics
    """
    # Group by team and compute weighted averages
    team_metrics = df.groupby("team").apply(
        lambda x: pd.Series({
            "team_yprr_vs_man": (x["yprr_vs_man"] * x["target_share"]).sum(),
            "team_yprr_vs_zone": (x["yprr_vs_zone"] * x["target_share"]).sum(),
            "team_slot_rate": (x["slot_rate"] * x["target_share"]).sum(),
            "total_targets": x["targets_vs_man"].sum() + x["targets_vs_zone"].sum(),
        })
    ).reset_index()
    
    return team_metrics
