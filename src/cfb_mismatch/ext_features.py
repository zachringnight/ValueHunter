"""Extended features computation using PFF and FantasyPoints data."""
from typing import Dict, Any
from pathlib import Path

import pandas as pd

from cfb_mismatch.adapters.pff import load_pff_data
from cfb_mismatch.adapters.fantasypoints import load_fantasypoints_data


def compute_extended_features(
    mismatches_df: pd.DataFrame,
    settings: Dict[str, Any],
    weights: Dict[str, Any],
) -> pd.DataFrame:
    """Compute extended features from PFF and FantasyPoints data.
    
    This function enhances base mismatch scores with:
    - OL/DL win rates and pass protection metrics (PFF)
    - Defensive front and coverage shell frequencies (PFF)
    - Run concept usage and efficiency (PFF)
    - Receiver splits vs man/zone coverage (FantasyPoints)
    
    Args:
        mismatches_df: DataFrame with base mismatch scores
        settings: Configuration dictionary
        weights: Feature weights dictionary
        
    Returns:
        Enhanced DataFrame with extended features
    """
    df = mismatches_df.copy()
    
    # Load PFF data if enabled
    if settings["use_pff"]:
        try:
            pff_data = load_pff_data(settings["pff_paths"])
            df = enhance_with_pff_features(df, pff_data, weights["pff_weights"])
        except Exception as e:
            print(f"Warning: Could not load PFF data: {e}")
    
    # Load FantasyPoints data if enabled
    if settings["use_fantasypoints"]:
        try:
            fp_data = load_fantasypoints_data(settings["fp_paths"])
            df = enhance_with_fp_features(df, fp_data, weights["fp_weights"])
        except Exception as e:
            print(f"Warning: Could not load FantasyPoints data: {e}")
    
    return df


def enhance_with_pff_features(
    df: pd.DataFrame,
    pff_data: Dict[str, pd.DataFrame],
    weights: Dict[str, float],
) -> pd.DataFrame:
    """Enhance mismatch scores with PFF features.
    
    Computes:
    - Edge/interior pressure expectations from OL/DL matchups
    - Run concept fit index based on team tendencies
    - Coverage shell matchup advantages
    
    Args:
        df: DataFrame with base scores
        pff_data: Dictionary of PFF DataFrames
        weights: PFF feature weights
        
    Returns:
        Enhanced DataFrame
    """
    # For demo purposes, add placeholder PFF-enhanced scores
    # In a real implementation, these would be computed from actual PFF metrics
    df["pff_ol_dl_advantage"] = 0.0
    df["pff_run_concept_fit"] = 0.0
    df["pff_coverage_advantage"] = 0.0
    
    # Adjust overall scores with PFF features
    pff_factor = (
        df["pff_ol_dl_advantage"] * 0.4 +
        df["pff_run_concept_fit"] * 0.3 +
        df["pff_coverage_advantage"] * 0.3
    )
    
    df["passpro_mismatch"] += pff_factor * 0.2
    df["run_mismatch"] += pff_factor * 0.15
    
    return df


def enhance_with_fp_features(
    df: pd.DataFrame,
    fp_data: Dict[str, pd.DataFrame],
    weights: Dict[str, float],
) -> pd.DataFrame:
    """Enhance mismatch scores with FantasyPoints features.
    
    Computes:
    - Route-family fit scores based on receiver tendencies
    - Man/zone coverage matchup advantages
    - Target distribution efficiency
    
    Args:
        df: DataFrame with base scores
        fp_data: Dictionary of FantasyPoints DataFrames
        weights: FantasyPoints feature weights
        
    Returns:
        Enhanced DataFrame
    """
    # For demo purposes, add placeholder FP-enhanced scores
    # In a real implementation, these would be computed from actual FP metrics
    df["fp_route_fit"] = 0.0
    df["fp_coverage_matchup"] = 0.0
    df["fp_target_efficiency"] = 0.0
    
    # Adjust pass mismatch with FP features
    fp_factor = (
        df["fp_route_fit"] * 0.4 +
        df["fp_coverage_matchup"] * 0.4 +
        df["fp_target_efficiency"] * 0.2
    )
    
    df["pass_mismatch"] += fp_factor * 0.2
    
    return df
