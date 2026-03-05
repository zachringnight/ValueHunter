-- 010_add_zone_playtype_opponent.sql
-- Add granular opponent defensive data: shooting zones and play-type defense.

-- Add zone-level shooting columns to team_opponent_shooting
ALTER TABLE team_opponent_shooting
    ADD COLUMN IF NOT EXISTS opp_paint_fga         NUMERIC(6,1),
    ADD COLUMN IF NOT EXISTS opp_paint_fg_pct      NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS opp_midrange_fga      NUMERIC(6,1),
    ADD COLUMN IF NOT EXISTS opp_midrange_fg_pct   NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS opp_corner_3pa        NUMERIC(6,1),
    ADD COLUMN IF NOT EXISTS opp_corner_3p_pct     NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS opp_above_break_3pa   NUMERIC(6,1),
    ADD COLUMN IF NOT EXISTS opp_above_break_3p_pct NUMERIC(5,3),
    ADD COLUMN IF NOT EXISTS opp_fga_allowed       NUMERIC(6,1),
    ADD COLUMN IF NOT EXISTS opp_fg_pct_allowed    NUMERIC(5,3);

-- Play-type defense table
CREATE TABLE IF NOT EXISTS team_playtype_defense (
    team_abbr               VARCHAR(5)      NOT NULL,
    season                  VARCHAR(10)     NOT NULL,
    play_type               VARCHAR(30)     NOT NULL,
    gp                      INTEGER,
    poss_pct                NUMERIC(5,3),
    poss                    NUMERIC(7,1),
    pts                     NUMERIC(7,1),
    fga                     NUMERIC(7,1),
    fgm                     NUMERIC(7,1),
    fg_pct                  NUMERIC(5,3),
    efg_pct                 NUMERIC(5,3),
    ft_freq                 NUMERIC(5,3),
    tov_freq                NUMERIC(5,3),
    score_freq              NUMERIC(5,3),
    percentile              NUMERIC(5,1),
    ppp                     NUMERIC(5,3),
    created_at              TIMESTAMPTZ     DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     DEFAULT NOW(),

    PRIMARY KEY (team_abbr, season, play_type)
);

CREATE INDEX IF NOT EXISTS idx_playtype_def_team
    ON team_playtype_defense (team_abbr);
