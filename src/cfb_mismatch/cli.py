"""
Command-line interface for CFB Mismatch Model.
"""

import argparse
import sys
import os
from cfb_mismatch.main import (
    load_config,
    load_weights,
    load_all_stats,
    load_cfbd_data,
    compute_team_stats,
    save_team_stats,
    generate_summary_report,
    generate_integrated_report
)
from cfb_mismatch.adapters.cfbd_data import fetch_and_save_cfbd_data


def analyze_stats(args):
    """Analyze the uploaded stats files."""
    print("\n=== CFB Mismatch Model - Stats Analysis ===\n")
    
    # Load configuration
    print("Loading configuration...")
    config = load_config(args.config)
    weights = load_weights(args.weights)
    
    # Load stats files
    print("\nLoading stats files...")
    defense_df, receiving_concept_df, receiving_scheme_df = load_all_stats(config)
    
    # Compute team-level stats
    print("\nComputing team-level statistics...")
    team_stats = compute_team_stats(defense_df, receiving_concept_df, receiving_scheme_df)
    
    # Optionally load CFBD data if season is specified
    cfbd_team_stats = None
    if hasattr(args, 'season') and args.season:
        print(f"\nLoading CFBD data for season {args.season}...")
        season_type = getattr(args, 'season_type', 'regular')
        cfbd_data_dir = config.get('cfbd_paths', {}).get('data_dir', 'data/cfbd')
        fetch_from_api = getattr(args, 'fetch_cfbd', False)
        api_key = os.getenv("CFBD_API_KEY") if fetch_from_api else None
        _, _, cfbd_team_stats = load_cfbd_data(
            args.season, 
            season_type, 
            cfbd_data_dir, 
            fetch_from_api=fetch_from_api,
            api_key=api_key
        )
    
    # Save team stats
    output_dir = args.output_dir or config.get('output_dir', 'data/out')
    print(f"\nSaving team statistics to {output_dir}...")
    save_team_stats(team_stats, output_dir)
    
    # Generate summary report
    print("\nGenerating summary report...")
    if cfbd_team_stats is not None:
        summary = generate_integrated_report(team_stats, cfbd_team_stats, weights=weights)
        print("✓ Generated integrated report with CFBD data")
    else:
        summary = generate_summary_report(team_stats, weights=weights)
        print("✓ Generated summary report (user stats only)")
    
    summary_path = f"{output_dir}/team_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"✓ Saved {summary_path}")
    
    print("\n=== Analysis Complete ===\n")
    print(f"Total teams analyzed: {len(summary)}")
    print(f"Output directory: {output_dir}")
    
    # Display top teams by various metrics
    if not summary.empty:
        if 'mismatch_score' in summary.columns:
            print("\n--- Top 5 Teams by Overall Mismatch Score ---")
            top_mismatch = summary.nlargest(5, 'mismatch_score')[['team_name', 'mismatch_score', 'mismatch_tier']]
            print(top_mismatch.to_string(index=False))

        print("\n--- Top 5 Teams by Man Coverage Grade ---")
        if 'man_coverage_grade' in summary.columns:
            top_man = summary.nlargest(5, 'man_coverage_grade')[['team_name', 'man_coverage_grade']]
            print(top_man.to_string(index=False))
        
        print("\n--- Top 5 Teams by Zone Coverage Grade ---")
        if 'zone_coverage_grade' in summary.columns:
            top_zone = summary.nlargest(5, 'zone_coverage_grade')[['team_name', 'zone_coverage_grade']]
            print(top_zone.to_string(index=False))
        
        # If CFBD data is available, show additional metrics
        if 'win_pct' in summary.columns:
            print("\n--- Top 5 Teams by Win Percentage ---")
            top_wins = summary.nlargest(5, 'win_pct')[['team_name', 'win_pct', 'wins', 'games_played']]
            print(top_wins.to_string(index=False))


def fetch_cfbd(args):
    """Fetch CFBD data from API."""
    print("\n=== CFB Mismatch Model - Fetch CFBD Data ===\n")
    
    # Load configuration to get data directory
    config = load_config(args.config)
    data_dir = args.data_dir or config.get('cfbd_paths', {}).get('data_dir', 'data/cfbd')
    
    # Get API key
    api_key = args.api_key or os.getenv("CFBD_API_KEY")
    if not api_key:
        print("✗ Error: CFBD_API_KEY not found", file=sys.stderr)
        print("Set it as an environment variable or pass via --api-key", file=sys.stderr)
        sys.exit(1)
    
    print(f"Fetching CFBD data for season {args.season}, type: {args.season_type}")
    print(f"Output directory: {data_dir}\n")
    
    # Fetch and save data
    games_df, team_info_df = fetch_and_save_cfbd_data(
        args.season,
        args.season_type,
        data_dir,
        api_key
    )
    
    if games_df is not None:
        print(f"\n✓ Successfully fetched {len(games_df)} games")
    else:
        print("\n✗ Failed to fetch games data", file=sys.stderr)
        sys.exit(1)
    
    if team_info_df is not None:
        print(f"✓ Successfully fetched {len(team_info_df)} teams")
    
    print("\n=== Fetch Complete ===\n")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='CFB Mismatch Model - Integrate and analyze college football stats',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Analyze command
    analyze_parser = subparsers.add_parser(
        'analyze',
        help='Analyze uploaded stats files'
    )
    analyze_parser.add_argument(
        '--config',
        default='configs/settings.yaml',
        help='Path to configuration file (default: configs/settings.yaml)'
    )
    analyze_parser.add_argument(
        '--weights',
        default='configs/weights.yaml',
        help='Path to weights file (default: configs/weights.yaml)'
    )
    analyze_parser.add_argument(
        '--output-dir',
        help='Output directory for results (overrides config)'
    )
    analyze_parser.add_argument(
        '--season',
        type=int,
        help='Season year to load CFBD data (e.g., 2024). If provided, integrates CFBD game data'
    )
    analyze_parser.add_argument(
        '--season-type',
        default='regular',
        choices=['regular', 'postseason'],
        help='Type of season for CFBD data (default: regular)'
    )
    analyze_parser.add_argument(
        '--fetch-cfbd',
        action='store_true',
        help='Fetch CFBD data from API instead of loading from files'
    )
    analyze_parser.set_defaults(func=analyze_stats)
    
    # Fetch CFBD data command
    fetch_parser = subparsers.add_parser(
        'fetch-cfbd',
        help='Fetch CFBD data from API and save to files'
    )
    fetch_parser.add_argument(
        '--config',
        default='configs/settings.yaml',
        help='Path to configuration file (default: configs/settings.yaml)'
    )
    fetch_parser.add_argument(
        '--season',
        type=int,
        required=True,
        help='Season year to fetch (e.g., 2024)'
    )
    fetch_parser.add_argument(
        '--season-type',
        default='regular',
        choices=['regular', 'postseason'],
        help='Type of season to fetch (default: regular)'
    )
    fetch_parser.add_argument(
        '--data-dir',
        help='Output directory for CFBD data (overrides config)'
    )
    fetch_parser.add_argument(
        '--api-key',
        help='CFBD API key (or set CFBD_API_KEY environment variable)'
    )
    fetch_parser.set_defaults(func=fetch_cfbd)
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Execute command
    try:
        args.func(args)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
