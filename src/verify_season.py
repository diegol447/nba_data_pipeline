"""Confere integridade, totais e repeticao de uma carga salva, sem nova consulta NBA."""
from src.db import get_connection
from src.season import store, minutes

def main():
    assert minutes('PT33M15.00S') == 33.25
    assert minutes('PT00M00.00S') == 0
    with get_connection() as conn:
        for table in ('players','player_game_stats','team_game_stats'):
            print(table,conn.execute('SELECT count(*) FROM public.'+table).fetchone()[0])
        assert conn.execute('''SELECT count(*) FROM (
            SELECT game_id FROM public.team_game_stats GROUP BY game_id HAVING count(*)<>2
        ) q''').fetchone()[0]==0
        assert conn.execute('''SELECT count(*) FROM public.team_game_stats t
            JOIN (SELECT game_id,team_id,sum(points) pts FROM public.player_game_stats
                  GROUP BY game_id,team_id) p USING(game_id,team_id)
            WHERE p.pts<>t.points''').fetchone()[0]==0
        assert conn.execute('''SELECT count(*) FROM public.player_game_stats s
            JOIN public.games g USING(game_id)
            WHERE s.team_id NOT IN (g.home_team_id,g.away_team_id)''').fetchone()[0]==0
        row=conn.execute('''SELECT r.payload,g.season,g.season_type,r.run_id
            FROM public.raw_game_data r JOIN public.games g USING(game_id)
            WHERE data_type='boxscore' ORDER BY raw_id LIMIT 1''').fetchone()
        before=conn.execute('SELECT count(*) FROM public.player_game_stats WHERE game_id=%s',
                            (row[0]['gameId'],)).fetchone()[0]
    store(*row)
    with get_connection() as conn:
        after=conn.execute('SELECT count(*) FROM public.player_game_stats WHERE game_id=%s',
                           (row[0]['gameId'],)).fetchone()[0]
        assert before==after
        print('Integridade e repeticao sem duplicatas: OK')
        print('Amostra:')
        for r in conn.execute('''SELECT player_name,team,points,rebounds,assists,ts_pct
            FROM public.player_game_analysis WHERE played ORDER BY points DESC LIMIT 5'''):
            print(r)

if __name__=='__main__':
    main()
