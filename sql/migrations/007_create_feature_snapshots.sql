-- 007_create_feature_snapshots.sql
-- Creates the `feature_snapshots` table to store frozen feature vectors
-- used at prediction time.  Each snapshot captures the full feature JSON,
-- archetype label, minutes projections, predicted 3PA/make-prob
-- distributions, and the resulting model over/under probabilities.

CREATE TABLE IF NOT EXISTS feature_snapshots (
    feature_snapshot_id             BIGSERIAL       PRIMARY KEY,
    nba_game_id                     VARCHAR(20)     NOT NULL,
    nba_player_id                   VARCHAR(20)     NOT NULL,
    freeze_timestamp_utc            TIMESTAMPTZ     NOT NULL,
    injury_snapshot_timestamp_utc   TIMESTAMPTZ,
    odds_snapshot_timestamp_utc     TIMESTAMPTZ,
    tracking_available              BOOLEAN         DEFAULT FALSE,
    feature_json                    JSONB           NOT NULL,
    feature_json_hash               VARCHAR(64)     NOT NULL,
    archetype                       VARCHAR(50),
    minutes_p10                     NUMERIC(5,1),
    minutes_p50                     NUMERIC(5,1),
    minutes_p90                     NUMERIC(5,1),
    pred_3pa_mean                   NUMERIC(5,2),
    pred_3pa_dispersion             NUMERIC(5,3),
    pred_make_prob_mean             NUMERIC(5,4),
    pred_make_prob_uncertainty      NUMERIC(5,4),
    model_p_over                    NUMERIC(6,5),
    model_p_under                   NUMERIC(6,5),
    created_at                      TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feature_snapshots_game_player_ts
    ON feature_snapshots (nba_game_id, nba_player_id, freeze_timestamp_utc DESC);

CREATE INDEX IF NOT EXISTS idx_feature_snapshots_hash
    ON feature_snapshots (feature_json_hash);
