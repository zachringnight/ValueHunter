#!/usr/bin/env python
"""
Simple integration test for CFB Mismatch Model.

This script demonstrates how to use the package programmatically
and validates that the core functionality works.
"""
import sys
from pathlib import Path

# Test imports
try:
    from cfb_mismatch.main import load_config, load_weights
    from cfb_mismatch.ext_features import compute_extended_features
    from cfb_mismatch.adapters.pff import load_pff_data
    from cfb_mismatch.adapters.fantasypoints import load_fantasypoints_data
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test config loading
try:
    settings = load_config("settings")
    weights = load_weights()
    print("✓ Configuration files loaded successfully")
    print(f"  - Settings keys: {list(settings.keys())}")
    print(f"  - Weights categories: {list(weights.keys())}")
except Exception as e:
    print(f"✗ Config loading error: {e}")
    sys.exit(1)

# Test data directory structure
data_dir = Path("data")
if data_dir.exists():
    print("✓ Data directory structure exists")
    print(f"  - External: {(data_dir / 'external').exists()}")
    print(f"  - Output: {(data_dir / 'out').exists()}")
else:
    print("✗ Data directory not found")
    sys.exit(1)

# Test PFF adapter (without actual file)
try:
    # This should handle missing files gracefully
    pff_paths = settings["pff_paths"]
    print("✓ PFF adapter can be configured")
    print(f"  - Expected paths: {list(pff_paths.keys())}")
except Exception as e:
    print(f"✗ PFF adapter error: {e}")
    sys.exit(1)

# Test FantasyPoints adapter (without actual file)
try:
    fp_paths = settings["fp_paths"]
    print("✓ FantasyPoints adapter can be configured")
    print(f"  - Expected paths: {list(fp_paths.keys())}")
except Exception as e:
    print(f"✗ FantasyPoints adapter error: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("All integration tests passed! ✓")
print("="*60)
print("\nTo use the CLI:")
print("  1. Set CFBD_API_KEY environment variable")
print("  2. Run: cfb-mismatch week --year 2025 --week 7")
print("\nOr use programmatically:")
print("  from cfb_mismatch.main import build_week")
print("  build_week(year=2025, week=7)")
