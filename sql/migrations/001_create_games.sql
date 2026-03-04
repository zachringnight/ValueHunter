-- 001_create_games.sql
-- Creates the `games` table to store NBA game-level metadata,
-- schedule information, venue details, and closing betting lines.

CREATE TABLE IF NOT EXISTS games (
    nba_game_id         VARCHAR(20)     PRIMARY KEY,
    season              VARCHAR(10)     NOT NULL,
    season_type         VARCHAR(20)     NOT NULL DEFAULT 'Regular Season',
    game_date           DATE            NOT NULL,
    tipoff_time_utc     TIMESTAMPTZ,
    arena_name          VARCHAR(200),
    home_team_abbr      VARCHAR(5)      NOT NULL,
    away_team_abbr      VARCHAR(5)      NOT NULL,
    sr_game_id          VARCHAR(50),
    closing_spread_home NUMERIC(5,2),
    closing_total       NUMERIC(5,2),
    home_points_final   INTEGER,
    away_points_final   INTEGER,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_games_game_date
    ON games (game_date);

CREATE INDEX IF NOT EXISTS idx_games_season_season_type
    ON games (season, season_type);

CREATE INDEX IF NOT EXISTS idx_games_home_team_abbr
    ON games (home_team_abbr);

CREATE INDEX IF NOT EXISTS idx_games_away_team_abbr
    ON games (away_team_abbr);
