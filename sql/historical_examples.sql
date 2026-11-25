-- Schema de uma temporada, view de medias:
SELECT * FROM season_2025_26.player_averages
WHERE player_name = 'Jayson Tatum' AND season_type = 'Regular Season';

-- Evolucao do mesmo jogador, separando temporada regular de playoffs:
SELECT season, season_type, games_played, points_per_game, rebounds_per_game,
       assists_per_game, minutes_per_game, efg_pct, ts_pct
FROM analytics.player_season_averages
WHERE player_name = 'Jayson Tatum'
ORDER BY season, season_type;

-- Jogos antes/depois de uma data: use game_date para o historico.
SELECT game_date, player_name, team, points, rebounds, assists, minutes
FROM analytics.player_games
WHERE player_name = 'Jayson Tatum'
ORDER BY game_date;

-- Cobertura importada:
SELECT season,season_type,game_count,player_row_count,imported_at
FROM public.historical_imports ORDER BY season,season_type;
