"""Importacao historica em lote, com transacao e checkpoint por temporada/tipo."""
import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from nba_api.stats.endpoints import leaguegamelog
from nba_api.live.nba.endpoints import boxscore
from nba_api.stats.static import teams as static_teams
from psycopg import sql
from psycopg.types.json import Jsonb
from src.db import get_connection
from src.pipeline import start_run, finish_run

MAP = dict(points='PTS',rebounds='REB',assists='AST',steals='STL',blocks='BLK',
 turnovers='TOV',offensive_rebounds='OREB',defensive_rebounds='DREB',
 fg_made='FGM',fg_attempted='FGA',three_made='FG3M',three_attempted='FG3A',
 ft_made='FTM',ft_attempted='FTA',fouls='PF')
ROOT=Path(__file__).resolve().parents[1]

def bulk(cur,table,rows,keys):
    if not rows:
        return
    cols=list(rows[0])
    stmt=sql.SQL('INSERT INTO public.{} ({}) VALUES ({}) ON CONFLICT ({}) DO UPDATE SET {}').format(
        sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),
        sql.SQL(',').join(sql.Placeholder() for _ in cols),
        sql.SQL(',').join(map(sql.Identifier,keys)),
        sql.SQL(',').join(sql.SQL('{}=EXCLUDED.{}').format(sql.Identifier(c),sql.Identifier(c)) for c in cols if c not in keys))
    cur.executemany(stmt,([r[c] for c in cols] for r in rows))

def fetch(season,kind,mode):
    for attempt in range(3):
        try:
            frame=leaguegamelog.LeagueGameLog(season=season,season_type_all_star=kind,
                player_or_team_abbreviation=mode,timeout=45).get_data_frames()[0]
            return json.loads(frame.to_json(orient='records',date_format='iso'))
        except Exception:
            if attempt==2:
                raise
            time.sleep(5*(attempt+1))
        finally:
            time.sleep(2)

def prepare(season,kind,tr,pr):
    games=defaultdict(list); groups=defaultdict(list)
    seen=set()
    for t in tr:
        if t['WL'] not in ('W','L'):
            continue
        games[str(t['GAME_ID'])].append(t)
    for p in pr:
        key=(str(p['GAME_ID']),p['PLAYER_ID'])
        if key in seen:
            raise ValueError('Jogador duplicado na fonte')
        seen.add(key)
        if key[0] not in games:
            raise ValueError('Jogador sem jogo correspondente')
        groups[(key[0],p['TEAM_ID'])].append(p)
    gr=[]; ts=[]; ps=[]; players={}; team_ids=set()
    for gid,pair in games.items():
        if len(pair)!=2:
            raise ValueError(f'{gid}: esperado dois times')
        homes=[t for t in pair if 'vs.' in t['MATCHUP']]
        aways=[t for t in pair if ' @ ' in t['MATCHUP']]
        if len(homes)!=1 or len(aways)!=1:
            print(f'{gid}: conferindo mando no box score...',flush=True)
            detail=boxscore.BoxScore(gid,timeout=45).game.get_dict()
            time.sleep(2)
            if detail['gameId']!=gid:
                raise ValueError('Box score com identificador divergente')
            h=next(t for t in pair if t['TEAM_ID']==detail['homeTeam']['teamId'])
            a=next(t for t in pair if t['TEAM_ID']==detail['awayTeam']['teamId'])
            if h['PTS']!=detail['homeTeam']['score'] or a['PTS']!=detail['awayTeam']['score']:
                raise ValueError('Placar diverge entre fontes')
            # Guarda evidencia da resolucao junto ao payload bruto do lote.
            h['_resolved_home_team_id']=detail['homeTeam']['teamId']
            h['_resolved_away_team_id']=detail['awayTeam']['teamId']
        else:
            h,a=homes[0],aways[0]
        if h['GAME_DATE']!=a['GAME_DATE'] or h['TEAM_ID']==a['TEAM_ID']:
            raise ValueError('Partida inconsistente')
        gr.append(dict(game_id=gid,game_date=h['GAME_DATE'][:10],status_code=3,
            status_text='Final',home_team_id=h['TEAM_ID'],away_team_id=a['TEAM_ID'],
            home_score=h['PTS'],away_score=a['PTS'],season=season,season_type=kind))
        for t in pair:
            tid=t['TEAM_ID']; team_ids.add(tid)
            members=groups.get((gid,tid),[])
            if not members or sum(p['PTS'] for p in members)!=t['PTS']:
                raise ValueError(f'{gid}: pontos individuais divergem do time {tid}')
            row=dict(game_id=gid,team_id=tid,statistics=Jsonb(t))
            row.update({c:t[k] for c,k in MAP.items()}); ts.append(row)
            for p in members:
                players[p['PLAYER_ID']]=dict(player_id=p['PLAYER_ID'],name=p['PLAYER_NAME'])
                # LeagueGameLog lista atuacoes; MIN pode estar arredondado a zero.
                row=dict(game_id=gid,player_id=p['PLAYER_ID'],team_id=tid,
                    played=True,minutes=p['MIN'],plus_minus=p['PLUS_MINUS'],statistics=Jsonb(p))
                row.update({c:p[k] for c,k in MAP.items()}); ps.append(row)
    if len(ps)!=len(pr):
        raise ValueError('Participacoes nao mapeadas')
    refs={t['id']:t for t in static_teams.get_teams()}
    teams=[dict(team_id=tid,name=refs[tid]['nickname'],city=refs[tid]['city'],
                tricode=refs[tid]['abbreviation']) for tid in sorted(team_ids)]
    return teams,gr,list(players.values()),ts,ps

def views(cur,season):
    schema='season_'+season.replace('-','_')
    cur.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(sql.Identifier(schema)))
    queries={
      'games':'SELECT * FROM public.games WHERE season={s}',
      'player_stats':'SELECT * FROM analytics.player_games WHERE season={s}',
      'player_averages':'SELECT * FROM analytics.player_season_averages WHERE season={s}',
      'player_teams':'''SELECT player_id,player_name,team_id,team,season,
          min(game_time_utc) AS first_observed_game,max(game_time_utc) AS last_observed_game,
          count(*) FILTER(WHERE played) AS games_played,
          min(game_date) AS first_observed_game_date,max(game_date) AS last_observed_game_date
          FROM analytics.player_games WHERE season={s}
          GROUP BY player_id,player_name,team_id,team,season''',
      'team_stats':'''SELECT t.*,g.season,g.season_type,
          coalesce(g.game_date,(g.game_time_utc AT TIME ZONE 'America/New_York')::date) AS game_date
          FROM public.team_game_stats t JOIN public.games g USING(game_id) WHERE g.season={s}'''}
    for name,query in queries.items():
        cur.execute(sql.SQL('CREATE OR REPLACE VIEW {}.{} AS ').format(sql.Identifier(schema),sql.Identifier(name))
                    +sql.SQL(query).format(s=sql.Literal(season)))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seasons',nargs='+',default=['2017-18','2018-19','2019-20','2020-21','2021-22','2022-23','2023-24','2024-25','2025-26'])
    args=parser.parse_args()
    with get_connection() as conn:
        conn.execute((ROOT/'sql'/'history.sql').read_text(encoding='utf-8'))
    failed=[]
    for season in args.seasons:
        for kind in ('Regular Season','Playoffs','PlayIn'):
            if kind=='PlayIn' and season<'2019-20':
                continue
            with get_connection() as conn:
                done=conn.execute('SELECT game_count FROM public.historical_imports WHERE season=%s AND season_type=%s',
                                  (season,kind)).fetchone()
            if done:
                print(f'{season} {kind}: ja importado ({done[0]} jogos)',flush=True)
                continue
            run=start_run(); count=0
            try:
                print(f'{season} {kind}: consultando times e jogadores...',flush=True)
                tr=fetch(season,kind,'T'); pr=fetch(season,kind,'P')
                teams,games,players,ts,ps=prepare(season,kind,tr,pr); count=len(games)
                expected_regular={'2019-20':1059,'2020-21':1080}.get(season,1230)
                if kind=='Regular Season' and count!=expected_regular:
                    raise ValueError(f'Cobertura inesperada da temporada regular: {count}/{expected_regular}')
                if kind=='Playoffs' and not 60<=count<=105:
                    raise ValueError(f'Cobertura inesperada dos playoffs: {count}')
                expected_playin=1 if season=='2019-20' else 6
                if kind=='PlayIn' and count!=expected_playin:
                    raise ValueError(f'Cobertura inesperada do PlayIn: {count}/{expected_playin}')
                with get_connection() as conn,conn.cursor() as cur:
                    cur.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('history:'+season+kind,))
                    for table,rows,keys in (
                        ('teams',teams,['team_id']),('games',games,['game_id']),
                        ('players',players,['player_id']),('team_game_stats',ts,['game_id','team_id']),
                        ('player_game_stats',ps,['game_id','player_id'])):
                        bulk(cur,table,rows,keys)
                    cur.execute('''INSERT INTO public.historical_imports
                        (season,season_type,game_count,player_row_count,run_id,team_payload,player_payload)
                        VALUES(%s,%s,%s,%s,%s,%s,%s)''',
                        (season,kind,count,len(ps),run,Jsonb(tr),Jsonb(pr)))
                    cur.execute("UPDATE public.pipeline_runs SET status='success',finished_at=now(),games_found=%s,games_loaded=%s WHERE run_id=%s",
                                (count,count,run))
                    views(cur,season)
                print(f'{season} {kind}: OK {count} jogos, {len(ps)} atuacoes',flush=True)
            except Exception as exc:
                finish_run(run,'failed',count,0,type(exc).__name__)
                failed.append((season,kind))
                print(f'{season} {kind}: FALHA {type(exc).__name__}: {exc}',flush=True)
        with get_connection() as conn,conn.cursor() as cur:
            views(cur,season)
    with get_connection() as conn,conn.cursor() as cur:
        views(cur,'2026-27')
    if failed:
        raise SystemExit(f'Pendencias: {failed}')

if __name__=='__main__':
    main()
