"""
Example: Basic usage of CFB Mismatch Model

This script demonstrates how to use the package to compute
mismatch scores for a specific week.
"""
import os
from cfb_mismatch.main import build_week, load_config, load_weights

# Note: You must set CFBD_API_KEY environment variable before running
# export CFBD_API_KEY=your_api_key_here

def example_basic_usage():
    """Example of basic package usage."""
    print("Example 1: Computing mismatches for a specific week")
    print("-" * 60)
    
    # Check if API key is set
    if not os.environ.get('CFBD_API_KEY'):
        print("⚠️  CFBD_API_KEY not set. This is required for actual API calls.")
        print("   Set it with: export CFBD_API_KEY=your_api_key")
        return
    
    try:
        # Compute mismatches for Week 1 of 2024
        build_week(
            year=2024,
            week=1,
            output_dir='examples/output'
        )
        print("✓ Successfully computed mismatches!")
        print("  Check examples/output/ for CSV files")
    except Exception as e:
        print(f"✗ Error: {e}")


def example_load_configs():
    """Example of loading and inspecting configurations."""
    print("\nExample 2: Loading and inspecting configurations")
    print("-" * 60)
    
    # Load settings
    settings = load_config('settings')
    print("Settings:")
    print(f"  - PFF enabled: {settings['use_pff']}")
    print(f"  - FantasyPoints enabled: {settings['use_fantasypoints']}")
    print(f"  - Output directory: {settings['output']['default_dir']}")
    
    # Load weights
    weights = load_weights()
    print("\nBase Weights (sample):")
    for key, value in list(weights['base_weights'].items())[:5]:
        print(f"  - {key}: {value}")


def example_batch_processing():
    """Example of processing multiple weeks."""
    print("\nExample 3: Batch processing multiple weeks")
    print("-" * 60)
    
    if not os.environ.get('CFBD_API_KEY'):
        print("⚠️  CFBD_API_KEY not set - skipping API call example")
        print("   This example would process weeks 1-4 of the 2024 season")
        return
    
    # Process first 4 weeks of 2024 season
    for week in range(1, 5):
        print(f"Processing week {week}...")
        try:
            build_week(
                year=2024,
                week=week,
                output_dir=f'examples/output/week{week}'
            )
            print(f"  ✓ Week {week} complete")
        except Exception as e:
            print(f"  ✗ Week {week} failed: {e}")


if __name__ == "__main__":
    # Run examples
    example_load_configs()
    example_basic_usage()
    # example_batch_processing()  # Uncomment to run batch processing
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
