"""Tests for run_model.py wrapper script."""
import subprocess
import sys
import os
from pathlib import Path


def test_run_model_without_cfbd_key(tmp_path):
    """Test run_model.py without CFBD_API_KEY - should analyze without fetching."""
    # Run with output dir in temp to avoid conflicts
    env = os.environ.copy()
    env.pop('CFBD_API_KEY', None)  # Ensure no API key
    
    result = subprocess.run(
        [sys.executable, "run_model.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0, f"Failed: {result.stderr}"
    assert "CFBD_API_KEY not set" in result.stdout
    assert "Running analysis without fetching CFBD data" in result.stdout
    assert "Model run complete!" in result.stdout
    assert "$ cfb-mismatch analyze" in result.stdout or "$ python -m cfb_mismatch.cli analyze" in result.stdout


def test_run_model_with_cfbd_key():
    """Test run_model.py with CFBD_API_KEY - should attempt to fetch."""
    env = os.environ.copy()
    env['CFBD_API_KEY'] = 'test_key_for_testing'
    
    result = subprocess.run(
        [sys.executable, "run_model.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    # Should complete even if fetch fails with bad key
    assert result.returncode == 0, f"Failed: {result.stderr}"
    assert "CFBD_API_KEY detected" in result.stdout
    assert "--season" in result.stdout
    assert "--fetch-cfbd" in result.stdout


def test_run_model_with_custom_season():
    """Test run_model.py with RUN_SEASON environment variable."""
    env = os.environ.copy()
    env['CFBD_API_KEY'] = 'test_key'
    env['RUN_SEASON'] = '2023'
    
    result = subprocess.run(
        [sys.executable, "run_model.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0, f"Failed: {result.stderr}"
    assert "season 2023" in result.stdout or "--season 2023" in result.stdout


def test_run_model_shows_environment_info():
    """Test that run_model.py prints environment information."""
    env = os.environ.copy()
    env.pop('CFBD_API_KEY', None)
    
    result = subprocess.run(
        [sys.executable, "run_model.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0
    assert "Python:" in result.stdout
    assert "Platform:" in result.stdout
    assert "CFB Mismatch Model - Quick Run" in result.stdout


def test_run_model_checks_output_files():
    """Test that run_model.py checks for expected output files."""
    env = os.environ.copy()
    env.pop('CFBD_API_KEY', None)
    
    result = subprocess.run(
        [sys.executable, "run_model.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    assert result.returncode == 0
    assert "Checking expected outputs under data/out/" in result.stdout
    assert "team_summary.csv" in result.stdout
    assert "team_defense_coverage.csv" in result.stdout
    assert "team_receiving_concept.csv" in result.stdout
    assert "team_receiving_scheme.csv" in result.stdout


def test_run_model_fallback_to_module_invocation():
    """Test that run_model.py falls back to module invocation when CLI not found."""
    env = os.environ.copy()
    env.pop('CFBD_API_KEY', None)
    # Set PATH to minimal path that won't include cfb-mismatch
    env['PATH'] = '/usr/bin:/bin'
    
    result = subprocess.run(
        [sys.executable, "run_model.py"],
        capture_output=True,
        text=True,
        env=env
    )
    
    # Should still succeed via fallback
    assert result.returncode == 0, f"Failed: {result.stderr}"
    # Check for fallback message or module invocation
    assert ("'cfb-mismatch' not found on PATH" in result.stdout or 
            "-m cfb_mismatch.cli" in result.stdout)


def test_run_model_error_handling():
    """Test that run_model.py handles errors with appropriate exit code."""
    # Create a scenario that will fail - temporarily rename configs
    configs_path = Path("configs")
    backup_path = Path("configs_test_backup")
    
    if configs_path.exists():
        configs_path.rename(backup_path)
    
    try:
        env = os.environ.copy()
        env.pop('CFBD_API_KEY', None)
        
        result = subprocess.run(
            [sys.executable, "run_model.py"],
            capture_output=True,
            text=True,
            env=env
        )
        
        # Should fail with non-zero exit code
        assert result.returncode != 0, "Should fail when configs are missing"
        assert "Error running model" in result.stdout
        assert "Troubleshooting steps:" in result.stdout
    finally:
        # Restore configs
        if backup_path.exists():
            backup_path.rename(configs_path)
