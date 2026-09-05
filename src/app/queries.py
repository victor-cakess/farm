"""Every database call the screens make.

The screens import only this module, so the app never reaches into ingestion and never
touches a source file. Caching lives here because it is an app concern; the queries
themselves go through src.db like every other caller.
"""

import pandas as pd
import streamlit as st

from src import db
from src.ingestion import forecast as forecast_loader

_read = db.read_sql


@st.cache_data(ttl=600)
def get_stations():
    # observed_days drives which station the app opens on, so a first-time visitor does
    # not land on one too sparse to show anything. The list itself stays alphabetical.
    return _read(
        """
        SELECT s.code, s.name, s.uf, s.ibge_code,
               m.name AS municipio, count(w.rain_mm) AS observed_days
        FROM stations s
        JOIN weather_daily w ON w.station_code = s.code
        LEFT JOIN municipalities m ON m.ibge_code = s.ibge_code
        GROUP BY s.code, s.name, s.uf, s.ibge_code, m.name
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
        "frost_flag, hours_observed, et0_mm, soil_water_mm, gdd FROM weather_daily "
        "WHERE station_code = %(code)s ORDER BY date",
        {"code": station_code},
    )


@st.cache_data(ttl=600)
def get_seasons(station_code):
    """Season features for one station, newest first."""
    return _read(
        "SELECT * FROM season_features WHERE station_code = %(code)s "
        "ORDER BY harvest_year DESC",
        {"code": station_code},
    )


@st.cache_data(ttl=600)
def get_municipal_yield(ibge_code):
    """Municipal average soy yield, in sacas per hectare. Never a single farm."""
    return _read(
        "SELECT year, yield_kg_ha, area_ha FROM yield_municipal "
        "WHERE ibge_code = %(code)s AND yield_kg_ha IS NOT NULL ORDER BY year",
        {"code": int(ibge_code)},
    )


@st.cache_data(ttl=600)
def get_pooled_seasons():
    """Every station's sufficient seasons joined to its municipal yield.

    Used to say how consistently the region shows the same direction, which is what makes
    a single station's noisy correlation readable.
    """
    return _read(
        """
        SELECT f.station_code, y.year, y.yield_kg_ha,
               f.water_deficit_days, f.heat_days, f.rain_total_mm,
               f.longest_dry_spell_days, f.dry_spell_jan_mar_days
        FROM season_features f
        JOIN stations s ON s.code = f.station_code
        JOIN yield_municipal y
          ON y.ibge_code = s.ibge_code AND y.year = f.harvest_year
        WHERE f.sufficient AND y.yield_kg_ha IS NOT NULL
        """
    )


@st.cache_data(ttl=600)
def get_price_monthly_pr():
    """DERAL monthly average received by Parana producers, R$ per saca."""
    return _read(
        "SELECT make_date(year::int, month::int, 1) AS month, price_brl_sc "
        "FROM price_monthly_pr ORDER BY year, month"
    )


@st.cache_data(ttl=600)
def get_price_weekly_pr():
    return _read(
        "SELECT week_date, regional, price_brl_sc FROM price_weekly_pr "
        "WHERE week_date = (SELECT max(week_date) FROM price_weekly_pr) "
        "ORDER BY price_brl_sc DESC NULLS LAST"
    )


@st.cache_data(ttl=600)
def get_forecast(ibge_code):
    if ibge_code is None or pd.isna(ibge_code):
        return pd.DataFrame()
    return _read(
        "SELECT forecast_date, period, issued_at, resumo, temp_min, temp_max, "
        "umidade_min, umidade_max, dir_vento, int_vento FROM forecast "
        "WHERE ibge_code = %(code)s ORDER BY forecast_date, period",
        {"code": int(ibge_code)},
    )


@st.cache_data(ttl=60)
def get_farm_records():
    return _read(
        "SELECT season_year, field_name, area_ha, yield_sc_ha, cost_brl_ha, notes "
        "FROM farm_records ORDER BY season_year DESC, field_name"
    )


@st.cache_data(ttl=600)
def get_cost_reference(uf):
    return _read(
        "SELECT season_year, cost_brl_ha, yield_sc_ha, source FROM cost_reference "
        "WHERE uf = %(uf)s ORDER BY season_year",
        {"uf": uf},
    )


def save_farm_record(record):
    """Upsert one field-season. The only write the app performs besides the forecast."""
    db.upsert(
        "farm_records",
        ["season_year", "field_name", "area_ha", "yield_sc_ha", "cost_brl_ha", "notes"],
        [record],
        ["season_year", "field_name"],
    )


def delete_farm_record(season_year, field_name):
    db.execute(
        "DELETE FROM farm_records WHERE season_year = %s AND field_name = %s",
        (season_year, field_name),
    )


def refresh_forecast(ibge_code):
    """Reload one municipality's forecast from INMET. Returns rows written.

    The screens call this rather than the loader, so the app depends on one module.
    """
    return forecast_loader.refresh(int(ibge_code))


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
