-- 009_create_bet_decisions.sql
-- Creates the `bet_decisions` table to log every betting decision the
-- engine produces.  Captures the model edge, recommended side/stake,
-- closing-line value (CLV), actual outcome, and P&L for post-hoc
-- performance analysis.

CREATE TABLE IF NOT EXISTS bet_decisions (
    decision_id                 BIGSERIAL       PRIMARY KEY,
    feature_snapshot_id         BIGINT          REFERENCES feature_snapshots (feature_snapshot_id),
    model_run_id                BIGINT          REFERENCES model_runs (model_run_id),
    nba_game_id                 VARCHAR(20),
    nba_player_id               VARCHAR(20),
    sportsbook                  VARCHAR(50),
    line                        NUMERIC(4,1),
    odds_over                   NUMERIC(8,2),
    odds_under                  NUMERIC(8,2),
    model_p_over                NUMERIC(6,5),
    model_p_under               NUMERIC(6,5),
    fair_odds_over              NUMERIC(8,2),
    fair_odds_under             NUMERIC(8,2),
    edge_over                   NUMERIC(6,5),
    edge_under                  NUMERIC(6,5),
    recommended_side            VARCHAR(10),
    stake_pct                   NUMERIC(6,5),
    decision_timestamp_utc      TIMESTAMPTZ     NOT NULL,
    close_over_prob_novig       NUMERIC(6,5),
    close_under_prob_novig      NUMERIC(6,5),
    clv_prob_pts                NUMERIC(6,5),
    actual_3pm                  INTEGER,
    bet_result                  VARCHAR(10),
    pnl_units                   NUMERIC(8,4),
    created_at                  TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bet_decisions_game_player
    ON bet_decisions (nba_game_id, nba_player_id);

CREATE INDEX IF NOT EXISTS idx_bet_decisions_ts
    ON bet_decisions (decision_timestamp_utc DESC);

CREATE INDEX IF NOT EXISTS idx_bet_decisions_result
    ON bet_decisions (bet_result);
