"""Database access: one engine and one set of helpers, no ORM.

Everything that touches Postgres goes through here, so connection handling exists once and
every caller gets the same column types back.
"""

from contextlib import contextmanager

import pandas as pd
from psycopg2.extras import execute_values
from sqlalchemy import create_engine

from src import config

# Columns coerced to datetime on read, so callers can rely on the .dt accessor. Postgres
# date columns otherwise arrive as datetime.date, which has no .dt.
DATE_COLUMNS = ("date", "month", "week_date", "forecast_date")

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


def read_sql(sql, params=None):
    """Run a query and return a DataFrame with date columns already parsed."""
    with get_engine().connect() as connection:
        frame = pd.read_sql(sql, connection, params=params)
    for column in DATE_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column])
    return frame


@contextmanager
def _cursor():
    """A committed cursor. The one place connection handling is written."""
    raw = get_engine().raw_connection()
    try:
        with raw.cursor() as cursor:
            yield cursor
        raw.commit()
    finally:
        raw.close()


def execute(sql, params=None):
    """Run one statement that returns nothing."""
    with _cursor() as cursor:
        cursor.execute(sql, params)


def execute_many(sql, rows):
    """Run one statement once per row of parameters."""
    if not rows:
        return 0
    with _cursor() as cursor:
        cursor.executemany(sql, rows)
    return len(rows)


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

    with _cursor() as cursor:
        execute_values(cursor, sql, rows, page_size=1000)
    return len(rows)
