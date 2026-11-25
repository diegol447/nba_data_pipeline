ALTER TABLE public.games ADD COLUMN IF NOT EXISTS season TEXT;
ALTER TABLE public.games ADD COLUMN IF NOT EXISTS season_type TEXT;
CREATE TABLE IF NOT EXISTS public.players (
 player_id BIGINT PRIMARY KEY, name TEXT NOT NULL,
 first_name TEXT, last_name TEXT
);
CREATE TABLE IF NOT EXISTS public.team_game_stats (
 game_id VARCHAR(20) REFERENCES public.games(game_id),
 team_id BIGINT REFERENCES public.teams(team_id),
 points INTEGER NOT NULL, rebounds INTEGER, assists INTEGER, steals INTEGER,
 blocks INTEGER, turnovers INTEGER, offensive_rebounds INTEGER, defensive_rebounds INTEGER,
 fg_made INTEGER, fg_attempted INTEGER, three_made INTEGER, three_attempted INTEGER,
 ft_made INTEGER, ft_attempted INTEGER, fouls INTEGER,
 statistics JSONB NOT NULL,
 PRIMARY KEY(game_id, team_id)
);
CREATE TABLE IF NOT EXISTS public.player_game_stats (
 game_id VARCHAR(20) NOT NULL,
 player_id BIGINT REFERENCES public.players(player_id),
 team_id BIGINT NOT NULL,
 played BOOLEAN NOT NULL, starter BOOLEAN NOT NULL, position TEXT,
 minutes NUMERIC(9,4), plus_minus NUMERIC,
 points INTEGER, rebounds INTEGER, assists INTEGER, steals INTEGER,
 blocks INTEGER, turnovers INTEGER, offensive_rebounds INTEGER, defensive_rebounds INTEGER,
 fg_made INTEGER, fg_attempted INTEGER, three_made INTEGER, three_attempted INTEGER,
 ft_made INTEGER, ft_attempted INTEGER, fouls INTEGER,
 statistics JSONB NOT NULL,
 PRIMARY KEY(game_id, player_id),
 FOREIGN KEY(game_id, team_id) REFERENCES public.team_game_stats(game_id, team_id)
);
CREATE INDEX IF NOT EXISTS player_stats_player_idx ON public.player_game_stats(player_id);
CREATE OR REPLACE VIEW public.player_game_analysis AS
SELECT s.*, p.name AS player_name, t.tricode AS team, g.game_time_utc, g.season, g.season_type,
 ROUND(100.0*(s.fg_made+0.5*s.three_made)/NULLIF(s.fg_attempted,0),2) AS efg_pct,
 ROUND(100.0*s.points/NULLIF(2*(s.fg_attempted+0.44*s.ft_attempted),0),2) AS ts_pct
FROM public.player_game_stats s JOIN public.players p USING(player_id)
JOIN public.teams t USING(team_id) JOIN public.games g USING(game_id);
CREATE OR REPLACE VIEW public.player_team_history AS
SELECT s.player_id,p.name AS player_name,s.team_id,t.tricode AS team,g.season,
 MIN(g.game_time_utc) AS first_observed_game, MAX(g.game_time_utc) AS last_observed_game,
 COUNT(*) FILTER (WHERE s.played) AS games_played
FROM public.player_game_stats s JOIN public.players p USING(player_id)
JOIN public.teams t USING(team_id) JOIN public.games g USING(game_id)
GROUP BY s.player_id,p.name,s.team_id,t.tricode,g.season;
