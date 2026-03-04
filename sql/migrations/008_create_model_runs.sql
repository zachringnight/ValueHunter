-- 008_create_model_runs.sql
-- Creates the `model_runs` table to track trained model versions,
-- their hyperparameters, validation metrics, training windows,
-- and artifact locations.

CREATE TABLE IF NOT EXISTS model_runs (
    model_run_id        BIGSERIAL       PRIMARY KEY,
    model_name          VARCHAR(100)    NOT NULL,
    model_version       VARCHAR(50)     NOT NULL,
    git_commit_hash     VARCHAR(40),
    train_start_date    DATE,
    train_end_date      DATE,
    validation_window   VARCHAR(50),
    hyperparams_json    JSONB,
    metrics_json        JSONB,
    artifact_uri        TEXT,
    created_at          TIMESTAMPTZ     DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_model_runs_name_version
    ON model_runs (model_name, model_version);
