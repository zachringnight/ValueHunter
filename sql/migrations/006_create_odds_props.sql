-- 006_create_odds_props.sql
-- Creates the `odds_props` table to store time-series snapshots of
-- sportsbook player-prop odds (primarily 3-point made lines), including
-- raw and no-vig implied probabilities and hold percentage.

CREATE TABLE IF NOT EXISTS odds_props (
    odds_prop_id                BIGSERIAL       PRIMARY KEY,
    snapshot_timestamp_utc      TIMESTAMPTZ     NOT NULL,
    sportsbook                  VARCHAR(50)     NOT NULL,
    market                      VARCHAR(50)     NOT NULL DEFAULT 'player_3pt_made',
    nba_game_id                 VARCHAR(20),
    nba_player_id               VARCHAR(20),
    line                        NUMERIC(4,1)    NOT NULL,
    odds_format                 VARCHAR(20)     DEFAULT 'american',
    over_price                  NUMERIC(8,2),
    under_price                 NUMERIC(8,2),
    over_implied_prob_raw       NUMERIC(6,5),
    under_implied_prob_raw      NUMERIC(6,5),
    over_implied_prob_novig     NUMERIC(6,5),
    under_implied_prob_novig    NUMERIC(6,5),
    hold_pct                    NUMERIC(6,5),
    is_closing_snapshot         BOOLEAN         DEFAULT FALSE,
    source                      VARCHAR(100),
    source_request_id           VARCHAR(100),
    created_at                  TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_odds_props_player_game_ts
    ON odds_props (nba_player_id, nba_game_id, snapshot_timestamp_utc DESC);

CREATE INDEX IF NOT EXISTS idx_odds_props_market_ts
    ON odds_props (market, snapshot_timestamp_utc DESC);

CREATE INDEX IF NOT EXISTS idx_odds_props_game_market_closing
    ON odds_props (nba_game_id, market, is_closing_snapshot);
