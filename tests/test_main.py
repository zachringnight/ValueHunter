import pandas as pd

from cfb_mismatch.main import _compute_weighted_scores, _normalize_metric


def test_normalize_metric_constant_values_returns_zeros():
    series = pd.Series([5.0, 5.0, 5.0])

    normalized = _normalize_metric(series)

    assert all(value == 0.0 for value in normalized)


def test_compute_weighted_scores_prioritizes_better_metrics():
    summary = pd.DataFrame(
        {
            "team_name": ["Alpha", "Bravo"],
            "man_coverage_grade": [70.0, 50.0],
            "zone_coverage_grade": [65.0, 45.0],
            "man_qb_rating_against": [80.0, 120.0],
            "zone_qb_rating_against": [75.0, 130.0],
            "screen_yprr": [2.0, 1.0],
            "slot_yprr": [1.8, 0.9],
            "man_yprr": [2.2, 1.1],
            "zone_yprr": [2.5, 1.3],
        }
    )

    weights = {
        "stats_weights": {
            "man_coverage_defense": 1.0,
            "zone_coverage_defense": 1.0,
            "man_qb_rating_against": 1.0,
            "zone_qb_rating_against": 1.0,
            "screen_efficiency": 0.5,
            "slot_efficiency": 0.5,
            "man_receiving_efficiency": 0.5,
            "zone_receiving_efficiency": 0.5,
        }
    }

    scored = _compute_weighted_scores(summary.copy(), weights)

    assert "mismatch_score" in scored.columns
    assert scored.loc[0, "team_name"] == "Alpha"
    assert scored.loc[0, "mismatch_score"] > scored.loc[1, "mismatch_score"]
    assert all(
        column.endswith("_score") for column in scored.columns if column.endswith("_score")
    )
