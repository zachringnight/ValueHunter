-- 002_create_player_game.sql
-- Creates the `player_game` table to store per-player box-score statistics
-- for each game, including shooting splits, usage, and schedule context
-- (rest days, back-to-back, 3-in-4).

CREATE TABLE IF NOT EXISTS player_game (
    nba_game_id     VARCHAR(20)     NOT NULL,
    nba_player_id   VARCHAR(20)     NOT NULL,
    team_abbr       VARCHAR(5),
    opponent_abbr   VARCHAR(5),
    is_home         BOOLEAN,
    started         BOOLEAN,
    minutes_played  NUMERIC(5,1),
    three_pa        INTEGER,
    three_pm        INTEGER,
    fg3_pct         NUMERIC(5,3),
    usage_rate      NUMERIC(5,3),
    assist_rate     NUMERIC(5,3),
    turnovers       INTEGER,
    personal_fouls  INTEGER,
    rest_days       INTEGER,
    is_back_to_back BOOLEAN,
    is_3in4         BOOLEAN,
    created_at      TIMESTAMPTZ     DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     DEFAULT NOW(),

    PRIMARY KEY (nba_game_id, nba_player_id),

    CONSTRAINT fk_player_game_game
        FOREIGN KEY (nba_game_id) REFERENCES games (nba_game_id)
);

CREATE INDEX IF NOT EXISTS idx_player_game_nba_player_id
    ON player_game (nba_player_id);

CREATE INDEX IF NOT EXISTS idx_player_game_nba_game_id
    ON player_game (nba_game_id);

CREATE INDEX IF NOT EXISTS idx_player_game_team_abbr
    ON player_game (team_abbr);
