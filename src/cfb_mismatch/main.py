"""
Main module for computing team-level stats and mismatch analysis.
"""

import os
import pandas as pd
import yaml
from typing import Dict, Optional, Tuple

from cfb_mismatch.adapters.defense_coverage import (
    load_defense_coverage_scheme,
    aggregate_defense_by_team
)
from cfb_mismatch.adapters.receiving_concept import (
    load_receiving_concept,
    aggregate_receiving_concept_by_team
)
from cfb_mismatch.adapters.receiving_scheme import (
    load_receiving_scheme,
    aggregate_receiving_scheme_by_team
)
from cfb_mismatch.adapters.cfbd_data import (
    load_and_aggregate_cfbd_data,
    merge_with_user_stats
)


def load_config(config_path: str = "configs/settings.yaml") -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Expand environment variables
    if 'cfbd_api_key' in config and config['cfbd_api_key']:
        config['cfbd_api_key'] = os.path.expandvars(config['cfbd_api_key'])
    
    return config


def load_weights(weights_path: str = "configs/weights.yaml") -> Dict:
    """Load feature weights from YAML file."""
    with open(weights_path, 'r') as f:
        return yaml.safe_load(f)


def load_all_stats(config: Dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load all stats files based on configuration.
    
    Args:
        config: Configuration dictionary from settings.yaml
        
    Returns:
        Tuple of (defense_coverage_df, receiving_concept_df, receiving_scheme_df)
    """
    stats_paths = config.get('stats_paths', {})
    
    defense_df = None
    receiving_concept_df = None
    receiving_scheme_df = None
    
    if config.get('use_stats_files', False):
        # Load defense coverage scheme
        if 'defense_coverage_scheme' in stats_paths:
            path = stats_paths['defense_coverage_scheme']
            try:
                defense_df = load_defense_coverage_scheme(path)
                print(f"✓ Loaded {len(defense_df)} defensive player records")
            except Exception as e:
                print(f"✗ Failed to load defense coverage: {e}")
        
        # Load receiving concept
        if 'receiving_concept' in stats_paths:
            path = stats_paths['receiving_concept']
            try:
                receiving_concept_df = load_receiving_concept(path)
                print(f"✓ Loaded {len(receiving_concept_df)} receiving concept records")
            except Exception as e:
                print(f"✗ Failed to load receiving concept: {e}")
        
        # Load receiving scheme
        if 'receiving_scheme' in stats_paths:
            path = stats_paths['receiving_scheme']
            try:
                receiving_scheme_df = load_receiving_scheme(path)
                print(f"✓ Loaded {len(receiving_scheme_df)} receiving scheme records")
            except Exception as e:
                print(f"✗ Failed to load receiving scheme: {e}")
    
    return defense_df, receiving_concept_df, receiving_scheme_df


def load_cfbd_data(
    season: Optional[int] = None,
    season_type: str = "regular",
    data_dir: Optional[str] = None
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Load CFBD API data (games, team info, aggregated stats).
    
    Args:
        season: Year of season to load (required)
        season_type: 'regular' or 'postseason'
        data_dir: Directory containing CFBD data files
        
    Returns:
        Tuple of (games_df, team_info_df, team_stats_df)
    """
    if season is None:
        print("⚠ No season specified for CFBD data, skipping")
        return None, None, None
    
    if data_dir is None:
        data_dir = "data/cfbd"
    
    try:
        games_df, team_info_df, team_stats_df = load_and_aggregate_cfbd_data(
            season, season_type, data_dir
        )
        
        if games_df is not None:
            print(f"✓ Loaded {len(games_df)} CFBD games for {season} {season_type} season")
        else:
            print(f"⚠ No CFBD games data found for {season} {season_type} season")
            
        if team_info_df is not None:
            print(f"✓ Loaded CFBD team info for {len(team_info_df)} teams")
        else:
            print(f"⚠ No CFBD team info found")
            
        if team_stats_df is not None:
            print(f"✓ Aggregated CFBD stats for {len(team_stats_df)} teams")
        
        return games_df, team_info_df, team_stats_df
        
    except Exception as e:
        print(f"✗ Failed to load CFBD data: {e}")
        return None, None, None


def compute_team_stats(
    defense_df: Optional[pd.DataFrame],
    receiving_concept_df: Optional[pd.DataFrame],
    receiving_scheme_df: Optional[pd.DataFrame]
) -> Dict[str, pd.DataFrame]:
    """
    Compute team-level aggregated statistics.
    
    Args:
        defense_df: Defense coverage scheme DataFrame
        receiving_concept_df: Receiving concept DataFrame
        receiving_scheme_df: Receiving scheme DataFrame
        
    Returns:
        Dictionary with team-level stats for each category
    """
    team_stats = {}
    
    if defense_df is not None:
        team_stats['defense_coverage'] = aggregate_defense_by_team(defense_df)
        print(f"✓ Aggregated defense stats for {len(team_stats['defense_coverage'])} teams")
    
    if receiving_concept_df is not None:
        team_stats['receiving_concept'] = aggregate_receiving_concept_by_team(receiving_concept_df)
        print(f"✓ Aggregated receiving concept stats for {len(team_stats['receiving_concept'])} teams")
    
    if receiving_scheme_df is not None:
        team_stats['receiving_scheme'] = aggregate_receiving_scheme_by_team(receiving_scheme_df)
        print(f"✓ Aggregated receiving scheme stats for {len(team_stats['receiving_scheme'])} teams")
    
    return team_stats


def save_team_stats(team_stats: Dict[str, pd.DataFrame], output_dir: str = "data/out"):
    """
    Save team-level statistics to CSV files.
    
    Args:
        team_stats: Dictionary of team statistics DataFrames
        output_dir: Directory to save output files
    """
    os.makedirs(output_dir, exist_ok=True)
    
    for category, df in team_stats.items():
        output_path = os.path.join(output_dir, f"team_{category}.csv")
        df.to_csv(output_path, index=False)
        print(f"✓ Saved {output_path}")


def generate_summary_report(team_stats: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Generate a summary report combining key metrics from all categories.
    
    Args:
        team_stats: Dictionary of team statistics DataFrames
        
    Returns:
        Combined summary DataFrame
    """
    summary_data = []
    
    # Get all unique teams across all stats
    all_teams = set()
    for df in team_stats.values():
        if df is not None:
            all_teams.update(df['team_name'].unique())
    
    for team in sorted(all_teams):
        team_row = {'team_name': team}
        
        # Add key defensive metrics
        if 'defense_coverage' in team_stats:
            defense = team_stats['defense_coverage']
            team_defense = defense[defense['team_name'] == team]
            if not team_defense.empty:
                team_row['man_coverage_grade'] = team_defense['man_grades_coverage_defense'].values[0]
                team_row['zone_coverage_grade'] = team_defense['zone_grades_coverage_defense'].values[0]
                team_row['man_qb_rating_against'] = team_defense['man_qb_rating_against'].values[0]
                team_row['zone_qb_rating_against'] = team_defense['zone_qb_rating_against'].values[0]
        
        # Add key receiving concept metrics
        if 'receiving_concept' in team_stats:
            concept = team_stats['receiving_concept']
            team_concept = concept[concept['team_name'] == team]
            if not team_concept.empty:
                team_row['screen_yprr'] = team_concept['screen_yprr'].values[0]
                team_row['slot_yprr'] = team_concept['slot_yprr'].values[0]
        
        # Add key receiving scheme metrics
        if 'receiving_scheme' in team_stats:
            scheme = team_stats['receiving_scheme']
            team_scheme = scheme[scheme['team_name'] == team]
            if not team_scheme.empty:
                team_row['man_yprr'] = team_scheme['man_yprr'].values[0]
                team_row['zone_yprr'] = team_scheme['zone_yprr'].values[0]
        
        summary_data.append(team_row)
    
    return pd.DataFrame(summary_data)


def generate_integrated_report(
    team_stats: Dict[str, pd.DataFrame],
    cfbd_team_stats: Optional[pd.DataFrame] = None
) -> pd.DataFrame:
    """
    Generate an integrated report combining user stats and CFBD data.
    
    Args:
        team_stats: Dictionary of user team statistics DataFrames
        cfbd_team_stats: Optional CFBD aggregated team statistics
        
    Returns:
        Combined summary DataFrame with both user and CFBD metrics
    """
    # Start with user stats summary
    summary = generate_summary_report(team_stats)
    
    # If CFBD data is available, merge it
    if cfbd_team_stats is not None and not cfbd_team_stats.empty:
        summary = merge_with_user_stats(summary, cfbd_team_stats, 'team_name')
        print(f"✓ Integrated CFBD data for {len(summary)} teams")
    
    return summary
