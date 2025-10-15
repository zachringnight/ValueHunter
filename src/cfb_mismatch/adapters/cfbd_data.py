"""
Adapter for loading and fetching CFBD (College Football Data) API data.

This module provides functions to:
1. Fetch game data and team information directly from the CFBD API using HTTP requests
2. Load game data and team information from CSV/Parquet files (for cached/pre-fetched data)
"""

import os
import pandas as pd
import requests
from typing import Optional, Tuple


# Helper to normalize CFBD games columns to snake_case expected by this package
# Handles both API (camelCase) and previously saved files
# Only renames the columns used downstream
_DEF_GAMES_COL_MAP = {
    'homeTeam': 'home_team',
    'awayTeam': 'away_team',
    'homePoints': 'home_points',
    'awayPoints': 'away_points',
    'id': 'game_id'
}

def _normalize_games_columns(df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
    if df is None or df.empty:
        return df
    # Build a mapping only for columns that exist in the dataframe
    rename_map = {c: _DEF_GAMES_COL_MAP[c] for c in _DEF_GAMES_COL_MAP.keys() if c in df.columns}
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


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
        df = pd.read_csv(csv_path)
        return _normalize_games_columns(df)
    elif os.path.exists(parquet_path):
        df = pd.read_parquet(parquet_path)
        return _normalize_games_columns(df)
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
    
    # Aggregate by team (handle missing game_id by falling back to row count)
    group = all_games.groupby('team', as_index=False)
    if 'game_id' in all_games.columns:
        team_stats = group.agg({
            'game_id': 'count',
            'win': 'sum',
            'points_for': 'mean',
            'points_against': 'mean',
        }).rename(columns={'game_id': 'games_played'})
    else:
        team_stats = group.agg({
            'win': 'sum',
            'points_for': 'mean',
            'points_against': 'mean',
        })
        # If game_id missing, derive games_played from counts per team
        counts = all_games.groupby('team').size().reset_index(name='games_played')
        team_stats = team_stats.merge(counts, on='team', how='left')
    
    team_stats.rename(columns={
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
    data_dir: str = "data/cfbd",
    fetch_from_api: bool = False,
    api_key: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Load and aggregate all CFBD data.
    
    Args:
        season: Year of the season
        season_type: Type of season ('regular' or 'postseason')
        data_dir: Directory containing CFBD data files
        fetch_from_api: If True, fetch data from API instead of loading from files
        api_key: CFBD API key (only used if fetch_from_api=True)
        
    Returns:
        Tuple of (games_df, team_info_df, team_stats_df)
    """
    if fetch_from_api:
        # Fetch from API
        games_df = fetch_cfbd_games_from_api(season, season_type, api_key)
        team_info_df = fetch_cfbd_team_info_from_api(api_key)
    else:
        # Load from files
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


def fetch_cfbd_games_from_api(
    season: int,
    season_type: str = "regular",
    api_key: Optional[str] = None
) -> Optional[pd.DataFrame]:
    """
    Fetch game data directly from CFBD API using HTTP requests.
    
    Args:
        season: Year of the season (e.g., 2024)
        season_type: Type of season ('regular' or 'postseason')
        api_key: CFBD API key. If None, will try to get from CFBD_API_KEY environment variable
        
    Returns:
        DataFrame with game data, or None if fetch fails
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv("CFBD_API_KEY")
    
    if not api_key:
        print("⚠ CFBD_API_KEY not found in environment")
        return None
    
    # API endpoint
    url = "https://api.collegefootballdata.com/games"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "year": season,
        "seasonType": season_type
    }
    
    try:
        # Fetch games
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Convert to DataFrame
        games_data = response.json()
        df = pd.DataFrame(games_data)
        return _normalize_games_columns(df)
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching games from CFBD API: {e}")
        return None
    except Exception as e:
        print(f"✗ Unexpected error fetching games: {e}")
        return None


def fetch_cfbd_team_info_from_api(api_key: Optional[str] = None) -> Optional[pd.DataFrame]:
    """
    Fetch team information directly from CFBD API using HTTP requests.
    
    Args:
        api_key: CFBD API key. If None, will try to get from CFBD_API_KEY environment variable
        
    Returns:
        DataFrame with team info, or None if fetch fails
    """
    # Get API key
    if api_key is None:
        api_key = os.getenv("CFBD_API_KEY")
    
    if not api_key:
        print("⚠ CFBD_API_KEY not found in environment")
        return None
    
    # API endpoint
    url = "https://api.collegefootballdata.com/teams"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        # Fetch teams
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Convert to DataFrame
        teams_data = response.json()
        return pd.DataFrame(teams_data)
        
    except requests.exceptions.RequestException as e:
        print(f"⚠ Warning: could not fetch team info from CFBD API: {e}")
        return None
    except Exception as e:
        print(f"⚠ Unexpected error fetching team info: {e}")
        return None


def fetch_and_save_cfbd_data(
    season: int,
    season_type: str = "regular",
    data_dir: str = "data/cfbd",
    api_key: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Fetch CFBD data from API and save to files.
    
    Args:
        season: Year of the season
        season_type: Type of season ('regular' or 'postseason')
        data_dir: Directory to save data files
        api_key: CFBD API key. If None, will try to get from CFBD_API_KEY environment variable
        
    Returns:
        Tuple of (games_df, team_info_df)
    """
    os.makedirs(data_dir, exist_ok=True)
    
    # Fetch games
    games_df = fetch_cfbd_games_from_api(season, season_type, api_key)
    
    # Fetch team info
    team_info_df = fetch_cfbd_team_info_from_api(api_key)
    
    # Save to files if fetch was successful
    if games_df is not None:
        games_df = _normalize_games_columns(games_df)
        prefix = os.path.join(data_dir, f"{season}_{season_type}")
        games_csv = f"{prefix}_games.csv"
        games_parquet = f"{prefix}_games.parquet"
        games_df.to_csv(games_csv, index=False)
        games_df.to_parquet(games_parquet, index=False)
        print(f"✓ Saved games to {games_csv} and {games_parquet}")
    
    if team_info_df is not None:
        team_info_csv = os.path.join(data_dir, "team_info.csv")
        team_info_parquet = os.path.join(data_dir, "team_info.parquet")
        team_info_df.to_csv(team_info_csv, index=False)
        team_info_df.to_parquet(team_info_parquet, index=False)
        print(f"✓ Saved team info to {team_info_csv} and {team_info_parquet}")
    
    return games_df, team_info_df

