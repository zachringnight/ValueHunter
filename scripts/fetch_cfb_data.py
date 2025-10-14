#!/usr/bin/env python3
"""
Fetch CFB data using direct HTTP requests to the CFBD API.

This script fetches game and team data directly from the
CollegeFootballData API at https://api.collegefootballdata.com/
"""

import os
import sys
import argparse
import pandas as pd
import requests


def get_api_key():
    """Get API key from environment variable."""
    api_key = os.getenv("CFBD_API_KEY")
    if not api_key:
        print("[cfbd-api] Missing CFBD_API_KEY environment variable.", file=sys.stderr)
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
    api_key = get_api_key()
    
    # API endpoint
    url = "https://api.collegefootballdata.com/games"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    params = {
        "year": year,
        "seasonType": season_type
    }
    
    try:
        # Fetch games
        print(f"[cfbd-api] Fetching games for year={year}, season_type={season_type}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        # Convert to DataFrame
        games_data = response.json()
        df = pd.DataFrame(games_data)
        print(f"[cfbd-api] Fetched {len(df)} games")
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"[cfbd-api] Error fetching games: {e}", file=sys.stderr)
        sys.exit(2)


def fetch_team_info():
    """
    Fetch team information.
    
    Returns:
        DataFrame with team information
    """
    api_key = get_api_key()
    
    # API endpoint
    url = "https://api.collegefootballdata.com/teams"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    try:
        # Fetch teams
        print("[cfbd-api] Fetching team information")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        # Convert to DataFrame
        teams_data = response.json()
        df = pd.DataFrame(teams_data)
        print(f"[cfbd-api] Fetched {len(df)} teams")
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"[cfbd-api] Warning: could not fetch team info: {e}", file=sys.stderr)
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
    
    print(f"[cfbd-api] Fetching data for season={args.season}, season_type={args.season_type}")
    
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
    print(f"[cfbd-api] Wrote {games_csv}")
    print(f"[cfbd-api] Wrote {games_parquet}")
    
    # Write team info
    if team_info_df is not None:
        team_info_csv = os.path.join(out_dir, "team_info.csv")
        team_info_parquet = os.path.join(out_dir, "team_info.parquet")
        team_info_df.to_csv(team_info_csv, index=False)
        team_info_df.to_parquet(team_info_parquet, index=False)
        print(f"[cfbd-api] Wrote {team_info_csv}")
        print(f"[cfbd-api] Wrote {team_info_parquet}")
    
    print(f"[cfbd-api] Done. Files written to {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
