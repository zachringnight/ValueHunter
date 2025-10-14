"""Command-line interface for CFB Mismatch Model."""
import argparse
import sys
import os
from pathlib import Path

from cfb_mismatch.main import build_week


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="CFB Mismatch Model - Compute weekly position-group mismatch scores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Week command
    week_parser = subparsers.add_parser(
        "week",
        help="Compute mismatch scores for a specific week",
    )
    week_parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Season year (default: 2025)",
    )
    week_parser.add_argument(
        "--week",
        type=int,
        help="Week number (if omitted, uses current week from CFBD)",
    )
    week_parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for CSV files (default: data/out/)",
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Check for CFBD API key
    if not os.environ.get("CFBD_API_KEY"):
        print("Error: CFBD_API_KEY environment variable is not set.", file=sys.stderr)
        print("Please set your CollegeFootballData API key:", file=sys.stderr)
        print("  export CFBD_API_KEY=your_api_key_here", file=sys.stderr)
        sys.exit(1)
    
    if args.command == "week":
        try:
            print(f"Computing mismatch scores for {args.year} week {args.week or 'current'}...")
            build_week(
                year=args.year,
                week=args.week,
                output_dir=args.output_dir,
            )
            print("✓ Mismatch scores computed successfully!")
            output_dir = args.output_dir or "data/out"
            print(f"  Output files written to: {output_dir}/")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
