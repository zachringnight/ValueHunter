import pandas as pd

from cfb_mismatch.adapters.receiving_scheme import aggregate_receiving_scheme_by_team


def test_aggregate_receiving_scheme_by_team_weights_player_counts():
    df = pd.DataFrame(
        {
            "team_name": ["Alpha", "Alpha", "Bravo"],
            "player": ["A", "B", "C"],
            "player_id": [1, 2, 3],
            "position": ["WR", "WR", "WR"],
            "player_game_count": [10, 5, 8],
            "man_yprr": [2.0, 4.0, 3.0],
            "zone_yprr": [3.0, 6.0, 4.0],
        }
    )

    team_stats = aggregate_receiving_scheme_by_team(df)

    alpha = team_stats.loc[team_stats["team_name"] == "Alpha"].iloc[0]
    bravo = team_stats.loc[team_stats["team_name"] == "Bravo"].iloc[0]

    expected_alpha_man = (2.0 * 10 + 4.0 * 5) / (10 + 5)
    expected_alpha_zone = (3.0 * 10 + 6.0 * 5) / (10 + 5)

    assert alpha["man_yprr"] == expected_alpha_man
    assert alpha["zone_yprr"] == expected_alpha_zone
    assert alpha["player_count"] == 2
    assert alpha["player_game_count_total"] == 15

    assert bravo["man_yprr"] == 3.0
    assert bravo["player_count"] == 1
