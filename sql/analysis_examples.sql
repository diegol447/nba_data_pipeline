-- Execute no banco nba, no Query Tool do pgAdmin.
-- Jogadores e seus times observados nesta temporada:
SELECT * FROM public.player_team_history ORDER BY player_name, team;

-- Melhores pontuacoes individuais por partida:
SELECT player_name, team, game_time_utc, points, rebounds, assists,
       minutes, plus_minus, efg_pct, ts_pct
FROM public.player_game_analysis
WHERE played
ORDER BY points DESC LIMIT 50;

-- Medias na amostra carregada (somente quem entrou em quadra).
-- Percentuais agregados calculados pelos totais, nao pela media dos percentuais.
SELECT player_name, team, COUNT(*) AS games_played,
       ROUND(AVG(points),2) AS points_per_game,
       ROUND(AVG(rebounds),2) AS rebounds_per_game,
       ROUND(AVG(assists),2) AS assists_per_game,
       ROUND(100.0*SUM(points)/NULLIF(2*(SUM(fg_attempted)+0.44*SUM(ft_attempted)),0),2) AS ts_pct
FROM public.player_game_analysis
WHERE played AND season='2026-27'
GROUP BY player_name,team ORDER BY points_per_game DESC;

-- Auditoria das cargas:
SELECT * FROM public.pipeline_runs ORDER BY run_id DESC;
