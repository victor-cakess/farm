"""Load the INMET municipal forecast.

INMET publishes five days, not seven, and there is no longer product. Days one and two are
split into morning, afternoon and night; the rest are a single block. The forecast carries
no rain amount or probability, only the text summary, so nothing here can be turned into a
number of millimetres.

The app reads this table rather than calling INMET, and the screen's refresh button calls
refresh() so there is only one code path.
"""

from datetime import UTC, datetime

import requests

from src import config, db

PERIODS = config.FORECAST_PERIODS
WHOLE_DAY = config.FORECAST_WHOLE_DAY
COLUMNS = [
    "ibge_code",
    "forecast_date",
    "period",
    "issued_at",
    "resumo",
    "temp_min",
    "temp_max",
    "umidade_min",
    "umidade_max",
    "dir_vento",
    "int_vento",
    "cod_icone",
]


def fetch(ibge_code):
    """Return INMET's day dictionary for a municipality, or None if it has no forecast."""
    response = requests.get(
        config.INMET_FORECAST_URL.format(ibge_code=ibge_code),
        headers={"User-Agent": config.INMET_USER_AGENT},
        timeout=120,
    )
    response.raise_for_status()
    days = response.json().get(str(ibge_code))
    if not days:
        return None
    # An unknown municipality still returns HTTP 200, with every period an empty dict, so
    # the response has to be judged by content rather than status.
    if not any(_blocks(day) for day in days.values()):
        return None
    return days


def _blocks(day):
    """Yield (period, values) for a day, whichever shape INMET used."""
    if any(period in day for period in PERIODS):
        return [(period, day[period]) for period in PERIODS if day.get(period)]
    return [(WHOLE_DAY, day)] if day else []


def to_rows(ibge_code, days, issued_at):
    rows = []
    for label, day in days.items():
        # INMET labels days dd/mm/yyyy.
        d, m, y = label.split("/")
        for period, values in _blocks(day):
            rows.append(
                (
                    ibge_code,
                    f"{y}-{m}-{d}",
                    period,
                    issued_at,
                    values.get("resumo"),
                    values.get("temp_min"),
                    values.get("temp_max"),
                    values.get("umidade_min"),
                    values.get("umidade_max"),
                    values.get("dir_vento"),
                    values.get("int_vento"),
                    # Only the icon code is stored: the icon itself is a ~50 KB base64 PNG
                    # per period and the code already identifies it.
                    values.get("cod_icone"),
                )
            )
    return rows


def refresh(ibge_code):
    """Reload one municipality. Used by the loader and by the screen's refresh button."""
    days = fetch(ibge_code)
    if not days:
        return 0
    rows = to_rows(ibge_code, days, datetime.now(UTC))
    return db.upsert("forecast", COLUMNS, rows, ["ibge_code", "forecast_date", "period"])


def main():
    codes = db.read_sql(
        "SELECT DISTINCT s.ibge_code FROM stations s"
        " JOIN weather_daily w ON w.station_code = s.code"
        " WHERE s.ibge_code IS NOT NULL ORDER BY 1"
    )["ibge_code"].tolist()

    total, empty = 0, []
    for code in codes:
        try:
            count = refresh(code)
        except requests.RequestException as error:
            empty.append(f"{code}: {type(error).__name__}")
            continue
        if count:
            total += count
        else:
            empty.append(f"{code}: no forecast returned")

    print(f"upserted {total} forecast rows for {len(codes) - len(empty)} municipalities")
    for line in empty:
        print(f"  skipped {line}")


if __name__ == "__main__":
    main()
