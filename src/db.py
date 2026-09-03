"""Database access. One engine helper and one upsert helper, no ORM."""

from psycopg2.extras import execute_values
from sqlalchemy import create_engine

from src import config

_engine = None


def get_engine():
    """Return the shared SQLAlchemy engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            f"postgresql+psycopg2://{config.PGUSER}:{config.PGPASSWORD}"
            f"@{config.PGHOST}:{config.PGPORT}/{config.PGDATABASE}"
        )
    return _engine


def upsert(table, columns, rows, conflict_columns):
    """Insert rows, updating the non-key columns on conflict. Returns rows sent."""
    if not rows:
        return 0

    updates = [c for c in columns if c not in conflict_columns]
    set_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE SET {set_clause}"
    )

    raw = get_engine().raw_connection()
    try:
        with raw.cursor() as cur:
            execute_values(cur, sql, rows, page_size=1000)
        raw.commit()
    finally:
        raw.close()
    return len(rows)
