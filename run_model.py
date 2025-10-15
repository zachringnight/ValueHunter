#!/usr/bin/env python3
"""
Simple script to run the CFB Mismatch Model.

This is a convenience wrapper around the cfb-mismatch CLI tool.
Usage: python run_model.py
"""

import sys
import subprocess


def main():
    """Run the CFB mismatch model analysis."""
    print("=" * 60)
    print("CFB Mismatch Model - Quick Run")
    print("=" * 60)
    print()
    print("Running model analysis...")
    print()
    
    try:
        # Run the analyze command
        result = subprocess.run(
            ["cfb-mismatch", "analyze"],
            check=True
        )
        
        print()
        print("=" * 60)
        print("✓ Model run complete!")
        print("=" * 60)
        print()
        print("Output files are in: data/out/")
        print("  - team_summary.csv (main results)")
        print("  - team_defense_coverage.csv")
        print("  - team_receiving_concept.csv")
        print("  - team_receiving_scheme.csv")
        print()
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print()
        print("=" * 60)
        print("✗ Error running model")
        print("=" * 60)
        print()
        print("Make sure you have installed the package:")
        print("  pip install -e .")
        print()
        return 1
    except FileNotFoundError:
        print()
        print("=" * 60)
        print("✗ cfb-mismatch command not found")
        print("=" * 60)
        print()
        print("Please install the package first:")
        print("  pip install -e .")
        print()
        print("Or run directly with:")
        print("  python -m cfb_mismatch.cli analyze")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
