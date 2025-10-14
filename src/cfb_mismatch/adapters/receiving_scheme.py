"""
Adapter for loading receiving scheme statistics.
"""

import pandas as pd
from typing import Optional


def load_receiving_scheme(file_path: str) -> pd.DataFrame:
    """
    Load receiving scheme data from CSV.
    
    Args:
        file_path: Path to the receiving_scheme CSV file
        
    Returns:
        DataFrame with receiving scheme statistics by player and team
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
        raise FileNotFoundError(f"Receiving scheme file not found: {file_path}")
    except Exception as e:
        raise RuntimeError(f"Error loading receiving scheme data: {e}")


def aggregate_receiving_scheme_by_team(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate receiving scheme stats by team.
    
    Args:
        df: DataFrame from load_receiving_scheme
        
    Returns:
        DataFrame with team-level receiving scheme statistics
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
