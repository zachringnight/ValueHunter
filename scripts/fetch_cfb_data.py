#!/usr/bin/env python3
"""
Fetch CFB data using the CFBD Python API client.

This script replaces the R-based fetch_cfb_data.R script by using
the official cfbd Python package to fetch game and team data.
"""

import os
import sys
import argparse
import pandas as pd
import cfbd
from cfbd.rest import ApiException


def get_api_key():
    """Get API key from environment variable."""
    api_key = os.getenv("CFBD_API_KEY")
    if not api_key:
        print("[cfbd-python] Missing CFBD_API_KEY environment variable.", file=sys.stderr)
        print("Set it in your environment locally or as a GitHub Actions repository secret named CFBD_API_KEY.", file=sys.stderr)
        sys.exit(1)
    return api_key


def fetch_games(year, season_type="regular"):
    """
    Fetch game data for a given season.
    
    Args:
        year: Season year (e.g., 2024)
        season_type: Type of season ('regular' or 'postseason')
        
    Returns:
        DataFrame with game data
    """
    # Configure API client
    configuration = cfbd.Configuration()
    configuration.api_key['Authorization'] = get_api_key()
    configuration.api_key_prefix['Authorization'] = 'Bearer'
    
    # Create API instance
    api_instance = cfbd.GamesApi(cfbd.ApiClient(configuration))
    
    try:
        # Fetch games
        print(f"[cfbd-python] Fetching games for year={year}, season_type={season_type}")
        games = api_instance.get_games(year=year, season_type=season_type)
        
        # Convert to list of dictionaries
        games_data = []
        for game in games:
            game_dict = game.to_dict()
            games_data.append(game_dict)
        
        # Convert to DataFrame
        df = pd.DataFrame(games_data)
        print(f"[cfbd-python] Fetched {len(df)} games")
        return df
        
    except ApiException as e:
        print(f"[cfbd-python] Error fetching games: {e}", file=sys.stderr)
        sys.exit(2)


def fetch_team_info():
    """
    Fetch team information.
    
    Returns:
        DataFrame with team information
    """
    # Configure API client
    configuration = cfbd.Configuration()
    configuration.api_key['Authorization'] = get_api_key()
    configuration.api_key_prefix['Authorization'] = 'Bearer'
    
    # Create API instance
    api_instance = cfbd.TeamsApi(cfbd.ApiClient(configuration))
    
    try:
        # Fetch team info
        print("[cfbd-python] Fetching team information")
        teams = api_instance.get_teams()
        
        # Convert to list of dictionaries
        teams_data = []
        for team in teams:
            team_dict = team.to_dict()
            teams_data.append(team_dict)
        
        # Convert to DataFrame
        df = pd.DataFrame(teams_data)
        print(f"[cfbd-python] Fetched {len(df)} teams")
        return df
        
    except ApiException as e:
        print(f"[cfbd-python] Warning: could not fetch team info: {e}", file=sys.stderr)
        return None


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Fetch CFB data using CFBD API")
    parser.add_argument(
        "--season", "-s",
        type=int,
        help="Season year (e.g., 2024)"
    )
    parser.add_argument(
        "--season_type", "-t",
        type=str,
        default="regular",
        choices=["regular", "postseason"],
        help="Season type: regular or postseason"
    )
    
    args = parser.parse_args()
    
    # Default to current year if not specified
    if args.season is None:
        from datetime import datetime
        args.season = datetime.now().year
    
    # Validate season type
    if args.season_type not in ["regular", "postseason"]:
        args.season_type = "regular"
    
    # Create output directory
    out_dir = os.path.join("data", "cfbd")
    os.makedirs(out_dir, exist_ok=True)
    
    print(f"[cfbd-python] Fetching data for season={args.season}, season_type={args.season_type}")
    
    # Fetch games
    games_df = fetch_games(args.season, args.season_type)
    
    # Fetch team info
    team_info_df = fetch_team_info()
    
    # Write outputs
    prefix = os.path.join(out_dir, f"{args.season}_{args.season_type}")
    
    # Write games
    games_csv = f"{prefix}_games.csv"
    games_parquet = f"{prefix}_games.parquet"
    games_df.to_csv(games_csv, index=False)
    games_df.to_parquet(games_parquet, index=False)
    print(f"[cfbd-python] Wrote {games_csv}")
    print(f"[cfbd-python] Wrote {games_parquet}")
    
    # Write team info
    if team_info_df is not None:
        team_info_csv = os.path.join(out_dir, "team_info.csv")
        team_info_parquet = os.path.join(out_dir, "team_info.parquet")
        team_info_df.to_csv(team_info_csv, index=False)
        team_info_df.to_parquet(team_info_parquet, index=False)
        print(f"[cfbd-python] Wrote {team_info_csv}")
        print(f"[cfbd-python] Wrote {team_info_parquet}")
    
    print(f"[cfbd-python] Done. Files written to {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
