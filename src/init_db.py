from pathlib import Path

from src.db import get_connection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_FILE = PROJECT_ROOT / "sql" / "schema.sql"


def main():
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)
    print("Esquema criado com sucesso.")


if __name__ == "__main__":
    main()

