"""What a soy season is, and what gets counted inside one. Pure functions, no I/O.

A season labelled with harvest year Y runs from 1 October of Y-1 to 30 April of Y, which is
the year IBGE reports the harvest against. Ingestion and the screens both import from here
so they can never describe a season differently.
"""

import pandas as pd

from src import config

# Columns of a season_features row, in the order season_rows emits them.
SEASON_COLUMNS = [
    "station_code",
    "harvest_year",
    "total_days",
    "rain_days_observed",
    "complete_days",
    "rain_total_mm",
    "longest_dry_spell_days",
    "dry_spell_jan_mar_days",
    "frost_days",
    "heat_days",
    "gdd_total",
    "water_deficit_days",
    "sufficient",
]

GRAIN_FILL_MONTHS = (1, 2, 3)


def season_bounds(harvest_year):
    """Return (start, end) timestamps for the season ending in harvest_year."""
    start = pd.Timestamp(year=harvest_year - 1, month=config.SEASON_START_MONTH, day=1)
    end = pd.Timestamp(
        year=harvest_year, month=config.SEASON_END_MONTH, day=config.SEASON_END_DAY
    )
    return start, end


def season_slice(weather, harvest_year):
    """Rows of a station's daily weather that fall inside the season."""
    start, end = season_bounds(harvest_year)
    return weather[(weather["date"] >= start) & (weather["date"] <= end)]


def latest_harvest_year(last_date):
    """The most recent season that has already ended on last_date."""
    if last_date.month > config.SEASON_END_MONTH:
        return last_date.year
    return last_date.year - 1


def longest_dry_spell(rain):
    """Longest run of consecutive observed days that recorded no rain.

    A day the station did not report is unknown, not dry, so it ends the run rather than
    extending it. Otherwise a gap in the record would show up as a drought.
    """
    best = run = 0
    for value in rain:
        run = run + 1 if value == 0 else 0
        best = max(best, run)
    return best


def season_rows(derived):
    """One row per station per season, counting only what the station actually reported."""
    rows = []
    for code, group in derived.groupby("station_code", sort=False):
        group = group.sort_values("date")
        first, last = group["date"].min(), group["date"].max()
        for harvest_year in range(first.year, last.year + 2):
            start, end = season_bounds(harvest_year)
            if end < first or start > last:
                continue
            window = group[(group["date"] >= start) & (group["date"] <= end)]
            if window.empty:
                continue

            # Denominator is the calendar length of the season, not the rows present, so a
            # season the station only partly covered is measured against the whole thing.
            total_days = (end - start).days + 1
            rain = window["rain_mm"].dropna()
            complete = window[window["hours_observed"] >= config.FULL_COVERAGE_HOURS]
            jan_mar = window[window["date"].dt.month.isin(GRAIN_FILL_MONTHS)]

            share = config.SEASON_SUFFICIENT_SHARE * total_days
            rows.append(
                (
                    code,
                    harvest_year,
                    total_days,
                    len(rain),
                    len(complete),
                    float(rain.sum()) if len(rain) else None,
                    longest_dry_spell(window["rain_mm"]),
                    longest_dry_spell(jan_mar["rain_mm"]),
                    int(complete["frost_flag"].sum()) if len(complete) else None,
                    int((complete["temp_max"] >= config.HEAT_STRESS_C).sum())
                    if len(complete)
                    else None,
                    float(window["gdd"].sum()) if window["gdd"].notna().any() else None,
                    int((window["soil_water_mm"] < config.SOIL_DEFICIT_MM).sum()),
                    len(rain) >= share and len(complete) >= share,
                )
            )
    return rows
