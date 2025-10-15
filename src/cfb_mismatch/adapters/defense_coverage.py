"""
Adapter for loading defense coverage scheme statistics.
"""

import numpy as np
import pandas as pd


def load_defense_coverage_scheme(file_path: str) -> pd.DataFrame:
    """
    Load defense coverage scheme data from CSV.
    
    Args:
        file_path: Path to the defense_coverage_scheme CSV file
        
    Returns:
        DataFrame with defense coverage statistics by player and team
    """
    try:
        df = pd.read_csv(file_path)
        
        # Ensure required columns exist
        required_cols = ['player', 'player_id', 'position', 'team_name', 'player_game_count']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        return df
    except FileNotFoundError:
        raise FileNotFoundError(f"Defense coverage scheme file not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error loading defense coverage scheme data: {e}")


def aggregate_defense_by_team(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate defensive coverage stats by team using player-game counts as weights.

    Args:
        df: DataFrame from ``load_defense_coverage_scheme``

    Returns:
        DataFrame with weighted team-level defensive coverage statistics
    """

    weight_col = 'player_game_count'
    if weight_col not in df.columns:
        raise ValueError("Expected 'player_game_count' column for weighting")

    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    exclude_cols = {'player_id', 'franchise_id', weight_col}
    agg_cols = [col for col in numeric_cols if col not in exclude_cols]

    grouped = df.groupby('team_name', dropna=True)
    records = []

    for team, group in grouped:
        weights = group[weight_col].fillna(0)
        weight_sum = weights.sum()
        record = {
            'team_name': team,
            'player_count': len(group),
            'player_game_count_total': weight_sum,
        }

        for col in agg_cols:
            series = group[col]
            mask = series.notna()
            if not mask.any():
                record[col] = np.nan
                continue

            values = series[mask]
            w = weights[mask]
            w_sum = w.sum()

            if w_sum > 0:
                record[col] = float((values * w).sum() / w_sum)
            else:
                record[col] = float(values.mean())

        records.append(record)

    team_stats = pd.DataFrame(records)
    return team_stats.sort_values('team_name').reset_index(drop=True)
