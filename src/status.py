from src.db import get_connection


def main():
    with get_connection() as connection:
        with connection.cursor() as cursor:
            for table in ("teams", "games", "raw_game_data", "pipeline_runs"):
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                print(f"{table}: {cursor.fetchone()[0]}")

            cursor.execute(
                """
                SELECT g.game_id, a.tricode, g.away_score,
                       h.tricode, g.home_score, g.status_text
                  FROM games g
                  JOIN teams h ON h.team_id = g.home_team_id
                  JOIN teams a ON a.team_id = g.away_team_id
                 ORDER BY g.game_time_utc, g.game_id
                """
            )
            print("\nPartidas:")
            for game_id, away, away_score, home, home_score, status in cursor.fetchall():
                print(f"{game_id}: {away} {away_score} x {home_score} {home} ({status})")


if __name__ == "__main__":
    main()

