"""Every read the screens perform. The app never touches source files."""

import pandas as pd
import streamlit as st

from src.db import get_engine


def _read(sql, params=None):
    with get_engine().connect() as connection:
        frame = pd.read_sql(sql, connection, params=params)
    # Postgres date columns arrive as datetime.date, which has no .dt accessor.
    for column in ("date", "month"):
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column])
    return frame


@st.cache_data(ttl=600)
def get_stations():
    # observed_days drives which station the app opens on, so a first-time visitor does
    # not land on one too sparse to show anything. The list itself stays alphabetical.
    return _read(
        """
        SELECT s.code, s.name, s.uf, count(w.rain_mm) AS observed_days
        FROM stations s JOIN weather_daily w ON w.station_code = s.code
        GROUP BY s.code, s.name, s.uf
        ORDER BY s.uf, s.name
        """
    )


@st.cache_data(ttl=600)
def get_price():
    return _read("SELECT date, price_brl, price_usd FROM price_daily ORDER BY date")


@st.cache_data(ttl=600)
def get_weather(station_code):
    return _read(
        "SELECT date, rain_mm, temp_mean, temp_max, temp_min, wind_mean, "
        "frost_flag, hours_observed FROM weather_daily "
        "WHERE station_code = %(code)s ORDER BY date",
        {"code": station_code},
    )


@st.cache_data(ttl=600)
def get_monthly(station_code):
    """Monthly means for the station and the price, over their overlapping months."""
    return _read(
        """
        WITH w AS (
            SELECT date_trunc('month', date) AS month,
                   avg(temp_mean) AS temp_mean,
                   sum(rain_mm)   AS rain_mm
            FROM weather_daily WHERE station_code = %(code)s
            GROUP BY 1
        ), p AS (
            SELECT date_trunc('month', date) AS month,
                   avg(price_brl) AS price_brl
            FROM price_daily GROUP BY 1
        )
        SELECT w.month, w.temp_mean, w.rain_mm, p.price_brl
        FROM w JOIN p USING (month) ORDER BY w.month
        """,
        {"code": station_code},
    )
