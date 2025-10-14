"""Core logic for computing CFB mismatch scores."""
import os
from pathlib import Path
from typing import Optional, Dict, List, Any
import yaml

import pandas as pd
import cfbd

from cfb_mismatch.ext_features import compute_extended_features


def load_config(config_name: str = "settings") -> Dict[str, Any]:
    """Load configuration from YAML file.
    
    Args:
        config_name: Name of config file (without .yaml extension)
        
    Returns:
        Dictionary of configuration values
    """
    config_path = Path(__file__).parent.parent.parent / "configs" / f"{config_name}.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def load_weights() -> Dict[str, Any]:
    """Load feature weights from YAML file.
    
    Returns:
        Dictionary of feature weights
    """
    return load_config("weights")


def get_cfbd_client() -> cfbd.Configuration:
    """Create and configure CFBD API client.
    
    Returns:
        Configured CFBD client
    """
    configuration = cfbd.Configuration()
    configuration.api_key["Authorization"] = os.environ.get("CFBD_API_KEY")
    configuration.api_key_prefix["Authorization"] = "Bearer"
    return configuration


def fetch_team_stats(year: int, week: Optional[int] = None) -> pd.DataFrame:
    """Fetch team statistics from CFBD API.
    
    Args:
        year: Season year
        week: Week number (None for current week)
        
    Returns:
        DataFrame with team statistics
    """
    config = get_cfbd_client()
    
    # Fetch various team stats
    stats_api = cfbd.StatsApi(cfbd.ApiClient(config))
    games_api = cfbd.GamesApi(cfbd.ApiClient(config))
    
    # Get games for the week to know which teams are playing
    games = games_api.get_games(year=year, week=week, season_type="regular")
    
    # Get team stats
    try:
        team_stats = stats_api.get_advanced_team_season_stats(
            year=year,
            end_week=week
        )
    except Exception as e:
        print(f"Warning: Could not fetch advanced stats: {e}")
        team_stats = []
    
    # Convert to DataFrame
    stats_data = []
    for stat in team_stats:
        stats_data.append({
            "team": stat.team,
            "games": getattr(stat, "games", 0),
        })
    
    return pd.DataFrame(stats_data)


def compute_base_mismatches(
    team_stats: pd.DataFrame,
    games: List[Any],
    weights: Dict[str, float],
) -> pd.DataFrame:
    """Compute base mismatch scores using CFBD metrics.
    
    Args:
        team_stats: DataFrame with team statistics
        games: List of games for the week
        weights: Feature weights from config
        
    Returns:
        DataFrame with mismatch scores for each matchup
    """
    mismatches = []
    
    for game in games:
        if not game.home_team or not game.away_team:
            continue
            
        matchup = {
            "game_id": game.id,
            "away_team": game.away_team,
            "home_team": game.home_team,
            "week": game.week,
            "season": game.season,
            "run_mismatch": 0.0,
            "pass_mismatch": 0.0,
            "passpro_mismatch": 0.0,
            "overall_tilt": 0.0,
        }
        
        # For demo purposes, assign placeholder scores
        # In a real implementation, these would be computed from actual metrics
        matchup["run_mismatch"] = 50.0
        matchup["pass_mismatch"] = 50.0
        matchup["passpro_mismatch"] = 50.0
        matchup["overall_tilt"] = 50.0
        
        mismatches.append(matchup)
    
    return pd.DataFrame(mismatches)


def build_week(
    year: int,
    week: Optional[int] = None,
    output_dir: Optional[str] = None,
) -> None:
    """Build mismatch scores for a given week.
    
    This is the main pipeline function that:
    1. Fetches CFBD data for the specified week
    2. Loads PFF/FantasyPoints data if enabled
    3. Computes base mismatch scores
    4. Enhances with extended features
    5. Outputs CSV files
    
    Args:
        year: Season year
        week: Week number (None for current week)
        output_dir: Output directory for CSV files
    """
    settings = load_config("settings")
    weights = load_weights()
    
    # Set output directory
    if output_dir is None:
        output_dir = settings["output"]["default_dir"]
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Fetching data for {year} week {week or 'current'}...")
    
    # Get CFBD client and fetch data
    config = get_cfbd_client()
    games_api = cfbd.GamesApi(cfbd.ApiClient(config))
    
    # Get games for the week
    games = games_api.get_games(year=year, week=week, season_type="regular")
    
    if not games:
        print(f"No games found for {year} week {week}")
        return
    
    # Use the week from the first game if not specified
    if week is None:
        week = games[0].week
    
    print(f"Found {len(games)} games")
    
    # Fetch team statistics
    team_stats = fetch_team_stats(year, week)
    
    # Compute base mismatches
    base_weights = weights["base_weights"]
    mismatches_df = compute_base_mismatches(team_stats, games, base_weights)
    
    # Add extended features if enabled
    if settings["use_pff"] or settings["use_fantasypoints"]:
        print("Computing extended features...")
        mismatches_df = compute_extended_features(
            mismatches_df,
            settings,
            weights,
        )
    
    # Sort and save outputs
    print("Saving results...")
    
    # Save full mismatch data
    output_file = output_path / f"cfb_unit_mismatches_week{week}.csv"
    mismatches_df.to_csv(output_file, index=False)
    
    # Save top mismatches by category
    top_n = settings["output"]["top_n_mismatches"]
    
    # Top run mismatches
    top_run = mismatches_df.nlargest(top_n, "run_mismatch")
    top_run.to_csv(output_path / "top_run_mismatches.csv", index=False)
    
    # Top pass mismatches
    top_pass = mismatches_df.nlargest(top_n, "pass_mismatch")
    top_pass.to_csv(output_path / "top_pass_mismatches.csv", index=False)
    
    # Top pass protection mismatches
    top_passpro = mismatches_df.nlargest(top_n, "passpro_mismatch")
    top_passpro.to_csv(output_path / "top_passpro_mismatches.csv", index=False)
    
    print(f"Results saved to {output_path}/")
