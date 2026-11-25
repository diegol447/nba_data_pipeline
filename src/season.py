"""Carga retomavel dos box scores. python -m src.season --season 2026-27"""
import argparse
import re
import time
from pathlib import Path
from nba_api.stats.endpoints import leaguegamelog
from nba_api.live.nba.endpoints import boxscore
from psycopg import sql
from psycopg.types.json import Jsonb
from src.db import get_connection
from src.pipeline import upsert_game, start_run, finish_run

FIELDS = dict(points='points', rebounds='reboundsTotal', assists='assists',
 steals='steals', blocks='blocks', turnovers='turnovers',
 offensive_rebounds='reboundsOffensive', defensive_rebounds='reboundsDefensive',
 fg_made='fieldGoalsMade', fg_attempted='fieldGoalsAttempted',
 three_made='threePointersMade', three_attempted='threePointersAttempted',
 ft_made='freeThrowsMade', ft_attempted='freeThrowsAttempted', fouls='foulsPersonal')

def minutes(value):
    if not value:
        return None
    match = re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?', value)
    if not match:
        raise ValueError('Formato de minutos desconhecido')
    h,m,s = match.groups()
    return 60*float(h or 0)+float(m or 0)+float(s or 0)/60

def upsert(cur, table, row, keys):
    cols=list(row)
    statement=sql.SQL('INSERT INTO public.{} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}').format(
        sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),
        sql.SQL(',').join(sql.Placeholder() for _ in cols),
        sql.SQL(',').join(map(sql.Identifier,keys)),
        sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in cols if c not in keys))
    cur.execute(statement,list(row.values()))

def store(game, season, kind, run):
    if game['gameStatus'] != 3:
        raise ValueError('Partida ainda nao encerrada')
    for side in ('homeTeam','awayTeam'):
        team=game[side]
        if not team.get('players') or not team.get('statistics'):
            raise ValueError('Box score incompleto')
        if sum(p['statistics'].get('points',0) for p in team['players']) != team['score']:
            raise ValueError('Pontos dos jogadores divergem do placar')
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(game['gameId'],))
        upsert_game(cur,game)
        cur.execute('UPDATE public.games SET season=%s, season_type=%s WHERE game_id=%s',
                    (season,kind,game['gameId']))
        # Substitui somente o snapshot desta partida; rollback preserva a versao anterior.
        cur.execute('DELETE FROM public.player_game_stats WHERE game_id=%s',(game['gameId'],))
        for side in ('homeTeam','awayTeam'):
            team=game[side]; stats=team['statistics']
            row={'game_id':game['gameId'],'team_id':team['teamId']}
            row.update({c:stats.get(k) for c,k in FIELDS.items()})
            row['points']=team['score']; row['statistics']=Jsonb(stats)
            upsert(cur,'team_game_stats',row,['game_id','team_id'])
            for p in team['players']:
                upsert(cur,'players',dict(player_id=p['personId'],name=p['name'],
                       first_name=p.get('firstName'),last_name=p.get('familyName')),['player_id'])
                stats=p['statistics']
                row=dict(game_id=game['gameId'],player_id=p['personId'],team_id=team['teamId'],
                         played=str(p.get('played'))=='1',starter=str(p.get('starter'))=='1',
                         position=p.get('position'),minutes=minutes(stats.get('minutes')),
                         plus_minus=stats.get('plusMinusPoints'),statistics=Jsonb(stats))
                row.update({c:stats.get(k) for c,k in FIELDS.items()})
                upsert(cur,'player_game_stats',row,['game_id','player_id'])
        cur.execute("INSERT INTO public.raw_game_data(run_id,game_id,data_type,payload) VALUES(%s,%s,'boxscore',%s)",
                    (run,game['gameId'],Jsonb(game)))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--season',required=True)
    parser.add_argument('--refresh',action='store_true',help='Reconsulta jogos ja carregados para correcoes')
    args=parser.parse_args()
    with get_connection() as conn:
        conn.execute((Path(__file__).resolve().parents[1]/'sql'/'statistics.sql').read_text(encoding='utf-8'))
    run=start_run(); targets={}; loaded=0; failures=[]
    try:
        for kind in ('Regular Season','Playoffs','PlayIn'):
            rows=leaguegamelog.LeagueGameLog(season=args.season,season_type_all_star=kind,
                 player_or_team_abbreviation='T',timeout=45).get_data_frames()[0]
            for _,r in rows.iterrows():
                if r.get('WL') in ('W','L'):
                    targets[str(r['GAME_ID'])]=kind
            time.sleep(1.5)
        with get_connection() as conn:
            done={r[0] for r in conn.execute("SELECT DISTINCT game_id FROM public.raw_game_data WHERE data_type='boxscore'")}
        pending=[g for g in sorted(targets) if args.refresh or g not in done]
        print(f'Encontrados {len(targets)} jogos encerrados; pendentes {len(pending)}.',flush=True)
        for index,gid in enumerate(pending,1):
            for attempt in range(3):
                try:
                    game=boxscore.BoxScore(gid,timeout=30).game.get_dict()
                    if game['gameId']!=gid:
                        raise ValueError('Identificador divergente')
                    store(game,args.season,targets[gid],run)
                    loaded+=1
                    print(f'{index}/{len(pending)} OK {gid}',flush=True)
                    break
                except Exception as exc:
                    if attempt==2:
                        failures.append(gid)
                        print(f'FALHA {gid}: {type(exc).__name__}',flush=True)
                    else:
                        time.sleep(3*(attempt+1))
            time.sleep(1.5)
        finish_run(run,'failed' if failures else 'success',len(targets),loaded,
                   ','.join(failures) or None)
        print(f'Concluido: {loaded} carregados; {len(failures)} falhas.',flush=True)
        if failures:
            raise SystemExit(1)
    except Exception as exc:
        finish_run(run,'failed',len(targets),loaded,type(exc).__name__)
        raise

if __name__=='__main__':
    main()
