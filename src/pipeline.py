import json
import logging

from nba_api.live.nba.endpoints import scoreboard
from psycopg.types.json import Jsonb

from src.db import get_connection


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def collect_games():
    """Consulta o placar do dia e devolve a lista de partidas."""
    logger.info("Consultando o placar da NBA...")
    return scoreboard.ScoreBoard(timeout=30).games.get_dict()


def start_run():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO pipeline_runs (status) VALUES ('running') RETURNING run_id"
            )
            return cursor.fetchone()[0]


def finish_run(run_id, status, games_found=0, games_loaded=0, error=None):
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE pipeline_runs
                   SET finished_at = NOW(), status = %s, games_found = %s,
                       games_loaded = %s, error_message = %s
                 WHERE run_id = %s
                """,
                (status, games_found, games_loaded, error, run_id),
            )


def upsert_team(cursor, team):
    cursor.execute(
        """
        INSERT INTO teams (team_id, name, city, tricode)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (team_id) DO UPDATE SET
            name = EXCLUDED.name,
            city = EXCLUDED.city,
            tricode = EXCLUDED.tricode,
            updated_at = NOW()
        """,
        (
            team["teamId"],
            team["teamName"],
            team.get("teamCity"),
            team["teamTricode"],
        ),
    )


def upsert_game(cursor, game):
    home = game["homeTeam"]
    away = game["awayTeam"]
    upsert_team(cursor, home)
    upsert_team(cursor, away)

    cursor.execute(
        """
        INSERT INTO games (
            game_id, game_time_utc, status_code, status_text, period,
            home_team_id, away_team_id, home_score, away_score
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (game_id) DO UPDATE SET
            game_time_utc = EXCLUDED.game_time_utc,
            status_code = EXCLUDED.status_code,
            status_text = EXCLUDED.status_text,
            period = EXCLUDED.period,
            home_team_id = EXCLUDED.home_team_id,
            away_team_id = EXCLUDED.away_team_id,
            home_score = EXCLUDED.home_score,
            away_score = EXCLUDED.away_score,
            updated_at = NOW()
        """,
        (
            game["gameId"],
            game.get("gameTimeUTC"),
            game["gameStatus"],
            game["gameStatusText"],
            game.get("period"),
            home["teamId"],
            away["teamId"],
            home.get("score"),
            away.get("score"),
        ),
    )


def load_games(run_id, games):
    """Grava JSON, times e partidas em uma única transação."""
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for game in games:
                cursor.execute(
                    """
                    INSERT INTO raw_game_data (run_id, game_id, data_type, payload)
                    VALUES (%s, %s, 'scoreboard', %s)
                    """,
                    (run_id, game["gameId"], Jsonb(game)),
                )
                upsert_game(cursor, game)


def main():
    run_id = start_run()
    games = []
    try:
        games = collect_games()
        load_games(run_id, games)
        finish_run(run_id, "success", len(games), len(games))
        logger.info("Carga concluída: %s partidas processadas.", len(games))
    except Exception as exc:
        finish_run(run_id, "failed", len(games), 0, str(exc))
        logger.exception("A carga falhou.")
        raise


if __name__ == "__main__":
    main()

