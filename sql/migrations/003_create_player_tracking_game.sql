-- 003_create_player_tracking_game.sql
-- Creates the `player_tracking_game` table to store NBA player-tracking
-- data per game: touches, passing, catch-and-shoot vs pull-up shooting
-- breakdowns, and secondary assist metrics.

CREATE TABLE IF NOT EXISTS player_tracking_game (
    nba_game_id             VARCHAR(20)     NOT NULL,
    nba_player_id           VARCHAR(20)     NOT NULL,
    tracking_available      BOOLEAN         DEFAULT FALSE,
    tracking_provider       VARCHAR(50),
    touches                 NUMERIC(6,1),
    passes_made             INTEGER,
    passes_received         INTEGER,
    time_of_possession_sec  NUMERIC(7,2),
    avg_seconds_per_touch   NUMERIC(5,2),
    avg_dribbles_per_touch  NUMERIC(5,2),
    catch_shoot_fga         INTEGER,
    catch_shoot_fgm         INTEGER,
    catch_shoot_3pa         INTEGER,
    catch_shoot_3pm         INTEGER,
    pull_up_fga             INTEGER,
    pull_up_fgm             INTEGER,
    pull_up_3pa             INTEGER,
    pull_up_3pm             INTEGER,
    potential_assists        INTEGER,
    secondary_assists       INTEGER,
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     DEFAULT NOW(),

    PRIMARY KEY (nba_game_id, nba_player_id),

    CONSTRAINT fk_player_tracking_game_game
        FOREIGN KEY (nba_game_id) REFERENCES games (nba_game_id)
);

CREATE INDEX IF NOT EXISTS idx_player_tracking_game_provider
    ON player_tracking_game (tracking_provider);

CREATE INDEX IF NOT EXISTS idx_player_tracking_game_player_id
    ON player_tracking_game (nba_player_id);
