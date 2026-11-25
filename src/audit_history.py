"""Auditoria de cobertura historica e views do pgAdmin."""
from src.db import get_connection

def main():
    with get_connection() as conn:
        print('SEASON / TYPE / GAMES / PLAYER ROWS')
        for r in conn.execute('''SELECT g.season,g.season_type,count(distinct g.game_id),count(p.player_id)
            FROM public.games g JOIN public.player_game_stats p USING(game_id)
            GROUP BY g.season,g.season_type ORDER BY g.season,g.season_type'''):
            print(r)
        bad=conn.execute('''SELECT count(*) FROM public.historical_imports h WHERE
            h.game_count<>(SELECT count(*) FROM public.games g WHERE g.season=h.season AND g.season_type=h.season_type)
            OR h.player_row_count<>(SELECT count(*) FROM public.player_game_stats p JOIN public.games g USING(game_id)
                                   WHERE g.season=h.season AND g.season_type=h.season_type)''').fetchone()[0]
        assert bad==0,'Contagens divergem do manifesto'
        assert conn.execute('''SELECT count(*) FROM public.team_game_stats t LEFT JOIN
            (SELECT game_id,team_id,sum(points) pts FROM public.player_game_stats GROUP BY game_id,team_id) p
            USING(game_id,team_id) WHERE p.pts IS DISTINCT FROM t.points''').fetchone()[0]==0
        assert conn.execute('''SELECT count(*) FROM public.team_game_stats t JOIN public.games g USING(game_id)
            WHERE t.team_id NOT IN(g.home_team_id,g.away_team_id)
            OR t.points<>CASE WHEN t.team_id=g.home_team_id THEN g.home_score ELSE g.away_score END''').fetchone()[0]==0
        assert conn.execute('''SELECT count(*) FROM (SELECT game_id FROM public.team_game_stats
            GROUP BY game_id HAVING count(*)<>2) t''').fetchone()[0]==0
        assert conn.execute('''SELECT count(*) FROM public.player_game_stats p JOIN public.games g USING(game_id)
            WHERE g.season BETWEEN '2017-18' AND '2025-26' AND g.game_date IS NULL''').fetchone()[0]==0
        print('Integridade e cobertura dos lotes: OK')
        for table in ('games','players','player_game_stats','team_game_stats','historical_imports'):
            print(table,conn.execute('SELECT count(*) FROM public.'+table).fetchone()[0])
        print('Tatum, medias por temporada:')
        for r in conn.execute("""SELECT season,games_played,points_per_game,rebounds_per_game,assists_per_game
             FROM analytics.player_season_averages WHERE player_name='Jayson Tatum'
             AND season_type='Regular Season' ORDER BY season"""):
            print(r)

if __name__=='__main__':
    main()
