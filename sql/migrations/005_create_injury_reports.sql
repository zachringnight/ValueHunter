-- 005_create_injury_reports.sql
-- Creates the `injury_reports` table to store timestamped injury/status
-- reports for players.  Each unique report (per game, player, hash) is
-- stored once; the hash prevents duplicate ingestion.

CREATE TABLE IF NOT EXISTS injury_reports (
    injury_report_id        BIGSERIAL       PRIMARY KEY,
    nba_game_id             VARCHAR(20),
    nba_player_id           VARCHAR(20),
    team_abbr               VARCHAR(5),
    report_timestamp_utc    TIMESTAMPTZ     NOT NULL,
    report_source           VARCHAR(100),
    report_url              TEXT,
    report_hash             VARCHAR(64),
    status                  VARCHAR(50)     NOT NULL,
    reason_text             TEXT,
    minutes_limit_flag      BOOLEAN         DEFAULT FALSE,
    created_at              TIMESTAMPTZ     DEFAULT NOW(),

    CONSTRAINT uq_injury_reports_game_player_hash
        UNIQUE (nba_game_id, nba_player_id, report_hash)
);

CREATE INDEX IF NOT EXISTS idx_injury_reports_player_ts
    ON injury_reports (nba_player_id, report_timestamp_utc DESC);

CREATE INDEX IF NOT EXISTS idx_injury_reports_game_ts
    ON injury_reports (nba_game_id, report_timestamp_utc DESC);
