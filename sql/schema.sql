CREATE TABLE IF NOT EXISTS teams (
    team_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT,
    tricode VARCHAR(3) NOT NULL UNIQUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
    game_id VARCHAR(20) PRIMARY KEY,
    game_time_utc TIMESTAMPTZ,
    status_code SMALLINT NOT NULL,
    status_text TEXT NOT NULL,
    period SMALLINT,
    home_team_id BIGINT NOT NULL REFERENCES teams(team_id),
    away_team_id BIGINT NOT NULL REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT different_teams CHECK (home_team_id <> away_team_id),
    CONSTRAINT nonnegative_home_score CHECK (home_score IS NULL OR home_score >= 0),
    CONSTRAINT nonnegative_away_score CHECK (away_score IS NULL OR away_score >= 0)
);

CREATE INDEX IF NOT EXISTS games_time_idx ON games (game_time_utc DESC);
CREATE INDEX IF NOT EXISTS games_status_idx ON games (status_code);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    games_found INTEGER NOT NULL DEFAULT 0,
    games_loaded INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    CONSTRAINT valid_run_status CHECK (status IN ('running', 'success', 'failed'))
);

CREATE TABLE IF NOT EXISTS raw_game_data (
    raw_id BIGSERIAL PRIMARY KEY,
    run_id BIGINT REFERENCES pipeline_runs(run_id),
    game_id VARCHAR(20),
    data_type VARCHAR(30) NOT NULL,
    payload JSONB NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS raw_game_data_game_idx
    ON raw_game_data (game_id, fetched_at DESC);

