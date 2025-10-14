"""
Adapter for loading CFBD (College Football Data) API data fetched by the R script.

This module provides functions to load game data and team information
that was fetched from the CollegeFootballData API using cfbfastR.
"""

import os
import pandas as pd
from typing import Optional, Tuple


def load_cfbd_games(
    season: int,
    season_type: str = "regular",
    data_dir: str = "data/cfbd"
) -> Optional[pd.DataFrame]:
    """
    Load CFBD games data for a specific season.
    
    Args:
        season: Year of the season (e.g., 2024)
        season_type: Type of season ('regular' or 'postseason')
        data_dir: Directory containing CFBD data files
        
    Returns:
        DataFrame with game data, or None if file doesn't exist
    """
    # Try CSV first, then Parquet
    csv_path = os.path.join(data_dir, f"{season}_{season_type}_games.csv")
    parquet_path = os.path.join(data_dir, f"{season}_{season_type}_games.parquet")
    
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    elif os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    else:
        return None


def load_cfbd_team_info(data_dir: str = "data/cfbd") -> Optional[pd.DataFrame]:
    """
    Load CFBD team information.
    
    Args:
        data_dir: Directory containing CFBD data files
        
    Returns:
        DataFrame with team info, or None if file doesn't exist
    """
    # Try CSV first, then Parquet
    csv_path = os.path.join(data_dir, "team_info.csv")
    parquet_path = os.path.join(data_dir, "team_info.parquet")
    
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    elif os.path.exists(parquet_path):
        return pd.read_parquet(parquet_path)
    else:
        return None


def aggregate_team_games(games_df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate game-level data to team-level statistics.
    
    Args:
        games_df: DataFrame with game data from CFBD
        
    Returns:
        DataFrame with team-level aggregated stats
    """
    if games_df is None or games_df.empty:
        return pd.DataFrame()
    
    # Create separate records for home and away teams
    home_games = games_df.copy()
    home_games['team'] = home_games['home_team']
    home_games['opponent'] = home_games['away_team']
    home_games['points_for'] = home_games['home_points']
    home_games['points_against'] = home_games['away_points']
    home_games['is_home'] = True
    
    away_games = games_df.copy()
    away_games['team'] = away_games['away_team']
    away_games['opponent'] = away_games['home_team']
    away_games['points_for'] = away_games['away_points']
    away_games['points_against'] = away_games['home_points']
    away_games['is_home'] = False
    
    # Combine all games
    all_games = pd.concat([home_games, away_games], ignore_index=True)
    
    # Calculate wins
    all_games['win'] = (all_games['points_for'] > all_games['points_against']).astype(int)
    
    # Aggregate by team
    team_stats = all_games.groupby('team').agg({
        'game_id': 'count',  # games played
        'win': 'sum',        # wins
        'points_for': 'mean',    # avg points scored
        'points_against': 'mean', # avg points allowed
    }).reset_index()
    
    team_stats.rename(columns={
        'game_id': 'games_played',
        'win': 'wins',
        'points_for': 'avg_points_scored',
        'points_against': 'avg_points_allowed'
    }, inplace=True)
    
    # Calculate win percentage
    team_stats['win_pct'] = team_stats['wins'] / team_stats['games_played']
    
    # Calculate point differential
    team_stats['point_differential'] = (
        team_stats['avg_points_scored'] - team_stats['avg_points_allowed']
    )
    
    return team_stats


def load_and_aggregate_cfbd_data(
    season: int,
    season_type: str = "regular",
    data_dir: str = "data/cfbd"
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Load and aggregate all CFBD data.
    
    Args:
        season: Year of the season
        season_type: Type of season ('regular' or 'postseason')
        data_dir: Directory containing CFBD data files
        
    Returns:
        Tuple of (games_df, team_info_df, team_stats_df)
    """
    games_df = load_cfbd_games(season, season_type, data_dir)
    team_info_df = load_cfbd_team_info(data_dir)
    team_stats_df = aggregate_team_games(games_df) if games_df is not None else None
    
    return games_df, team_info_df, team_stats_df


def merge_with_user_stats(
    user_team_stats: pd.DataFrame,
    cfbd_team_stats: pd.DataFrame,
    team_name_col: str = 'team_name'
) -> pd.DataFrame:
    """
    Merge user-provided team stats with CFBD team stats.
    
    Args:
        user_team_stats: DataFrame with user stats (from analyze command)
        cfbd_team_stats: DataFrame with CFBD aggregated stats
        team_name_col: Column name for team in user stats
        
    Returns:
        Merged DataFrame with both user and CFBD stats
    """
    # Normalize team names for matching (uppercase, strip whitespace)
    user_stats_copy = user_team_stats.copy()
    cfbd_stats_copy = cfbd_team_stats.copy()
    
    user_stats_copy['team_name_normalized'] = (
        user_stats_copy[team_name_col].str.upper().str.strip()
    )
    cfbd_stats_copy['team_normalized'] = (
        cfbd_stats_copy['team'].str.upper().str.strip()
    )
    
    # Merge on normalized team names
    merged = user_stats_copy.merge(
        cfbd_stats_copy,
        left_on='team_name_normalized',
        right_on='team_normalized',
        how='left',
        suffixes=('', '_cfbd')
    )
    
    # Drop normalized columns
    merged.drop(['team_name_normalized', 'team_normalized'], axis=1, inplace=True)
    
    return merged
