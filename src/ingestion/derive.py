"""Fill the derived weather columns and rebuild the season features.

Two passes, both rebuilt from scratch each run:
  1. Per day: reference evapotranspiration, a single-bucket soil water store, thermal time.
  2. Per station per season: the counts the production screens compare against yield.

The maths lives in src.domain.agronomy and src.domain.seasons; this module only moves data.
"""

import pandas as pd

from src import db
from src.domain import agronomy, seasons

DAILY_COLUMNS = ["station_code", "date", "et0_mm", "soil_water_mm", "gdd"]


def derive_daily():
    """Compute the per-day columns for every station and write them back."""
    stations = db.read_sql("SELECT code, latitude FROM stations WHERE latitude IS NOT NULL")
    weather = db.read_sql(
        "SELECT station_code, date, rain_mm, temp_mean, temp_max, temp_min,"
        " hours_observed, frost_flag"
        " FROM weather_daily ORDER BY station_code, date"
    )
    print(f"deriving over {len(weather)} daily rows for {len(stations)} stations")

    latitudes = dict(zip(stations["code"], stations["latitude"], strict=True))
    parts = []
    for code, group in weather.groupby("station_code", sort=False):
        if code not in latitudes:
            continue
        group = group.copy()
        group["et0_mm"] = agronomy.hargreaves_et0(group, latitudes[code])
        group["soil_water_mm"] = agronomy.soil_water(group)
        group["gdd"] = agronomy.growing_degree_days(group)
        parts.append(group)

    derived = pd.concat(parts, ignore_index=True)
    frame = (
        derived[DAILY_COLUMNS].astype(object).where(pd.notna(derived[DAILY_COLUMNS]), None)
    )
    count = db.upsert(
        "weather_daily",
        DAILY_COLUMNS,
        list(frame.itertuples(index=False, name=None)),
        ["station_code", "date"],
    )
    print(f"updated {count} rows with et0, soil water and thermal time")
    return derived


def main():
    derived = derive_daily()

    rows = seasons.season_rows(derived)
    count = db.upsert(
        "season_features", seasons.SEASON_COLUMNS, rows, ["station_code", "harvest_year"]
    )
    sufficient = sum(1 for row in rows if row[-1])
    print(f"upserted {count} season rows, {sufficient} sufficient")


if __name__ == "__main__":
    main()
