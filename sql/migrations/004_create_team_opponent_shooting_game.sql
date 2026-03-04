-- 004_create_team_opponent_shooting_game.sql
-- Creates the `team_opponent_shooting_game` table to store per-game
-- opponent shooting allowed by a team, broken down by dribble count,
-- touch time, and closest-defender distance buckets.

CREATE TABLE IF NOT EXISTS team_opponent_shooting_game (
    nba_game_id                 VARCHAR(20)     NOT NULL,
    team_abbr                   VARCHAR(5)      NOT NULL,
    opponent_abbr               VARCHAR(5),
    opp_fga_allowed             INTEGER,
    opp_fg_pct_allowed          NUMERIC(5,3),
    opp_3pa_allowed             INTEGER,
    opp_3pm_allowed             INTEGER,
    opp_fg3_pct_allowed         NUMERIC(5,3),
    opp_dribbles_0_fga          INTEGER,
    opp_dribbles_1_2_fga        INTEGER,
    opp_dribbles_3_6_fga        INTEGER,
    opp_dribbles_7plus_fga      INTEGER,
    opp_touch_lt2_fga           INTEGER,
    opp_touch_2_6_fga           INTEGER,
    opp_touch_6plus_fga         INTEGER,
    opp_closest_def_0_2_fga     INTEGER,
    opp_closest_def_2_4_fga     INTEGER,
    opp_closest_def_4_6_fga     INTEGER,
    opp_closest_def_6plus_fga   INTEGER,
    created_at                  TIMESTAMPTZ     DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     DEFAULT NOW(),

    PRIMARY KEY (nba_game_id, team_abbr),

    CONSTRAINT fk_team_opp_shooting_game
        FOREIGN KEY (nba_game_id) REFERENCES games (nba_game_id)
);

CREATE INDEX IF NOT EXISTS idx_team_opp_shooting_team_abbr
    ON team_opponent_shooting_game (team_abbr);

CREATE INDEX IF NOT EXISTS idx_team_opp_shooting_opponent_abbr
    ON team_opponent_shooting_game (opponent_abbr);
