"""
Adapter for loading defense coverage scheme statistics.
"""

import pandas as pd
from typing import Optional


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
    Aggregate defensive coverage stats by team.
    
    Args:
        df: DataFrame from load_defense_coverage_scheme
        
    Returns:
        DataFrame with team-level defensive coverage statistics
    """
    # Identify numeric columns for aggregation
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    # Remove ID columns from aggregation
    exclude_cols = ['player_id', 'franchise_id']
    agg_cols = [col for col in numeric_cols if col not in exclude_cols]
    
    # Group by team and calculate weighted averages
    team_stats = df.groupby('team_name')[agg_cols].mean().reset_index()
    
    # Add player count
    team_stats['player_count'] = df.groupby('team_name').size().values
    
    return team_stats
