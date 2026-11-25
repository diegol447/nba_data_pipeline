ALTER TABLE public.games ADD COLUMN IF NOT EXISTS game_date DATE;
ALTER TABLE public.player_game_stats ALTER COLUMN starter DROP NOT NULL;
CREATE INDEX IF NOT EXISTS games_season_type_idx ON public.games(season,season_type);
CREATE TABLE IF NOT EXISTS public.historical_imports (
 season TEXT NOT NULL, season_type TEXT NOT NULL,
 imported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 game_count INTEGER NOT NULL, player_row_count INTEGER NOT NULL,
 run_id BIGINT REFERENCES public.pipeline_runs(run_id),
 source TEXT NOT NULL DEFAULT 'nba_api.LeagueGameLog',
 team_payload JSONB NOT NULL, player_payload JSONB NOT NULL,
 PRIMARY KEY(season,season_type)
);
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE OR REPLACE VIEW analytics.player_games AS
SELECT a.*, COALESCE(g.game_date,(g.game_time_utc AT TIME ZONE 'America/New_York')::date) AS game_date
FROM public.player_game_analysis a JOIN public.games g USING(game_id);
CREATE OR REPLACE VIEW analytics.player_season_averages AS
SELECT player_id,player_name,season,season_type,
 count(*) AS games_played,
 round(avg(points),2) AS points_per_game,
 round(avg(rebounds),2) AS rebounds_per_game,
 round(avg(assists),2) AS assists_per_game,
 round(avg(minutes),2) AS minutes_per_game,
 round(100.0*(sum(fg_made)+0.5*sum(three_made))/nullif(sum(fg_attempted),0),2) AS efg_pct,
 round(100.0*sum(points)/nullif(2*(sum(fg_attempted)+0.44*sum(ft_attempted)),0),2) AS ts_pct
FROM analytics.player_games WHERE played
GROUP BY player_id,player_name,season,season_type;
