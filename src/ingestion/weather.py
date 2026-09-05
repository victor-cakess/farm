"""Reduce hourly INMET station CSVs to daily aggregates and load them."""

import io
import re
import zipfile

import pandas as pd

from src import config, db
from src.ingestion import inmet_client

# 2025/INMET_S_PR_A807_CURITIBA_01-01-2025_A_31-12-2025.CSV
MEMBER_PATTERN = re.compile(r"INMET_[A-Z]+_([A-Z]{2})_([A-Z0-9]+)_")

# Column names carry units and vary across years, so match on a keyword instead.
RAIN_KEYWORD = "PRECIPITA"
TEMP_KEYWORD = "TEMPERATURA DO AR"
WIND_KEYWORD = "VELOCIDADE HORARIA"

COLUMNS = [
    "station_code",
    "date",
    "rain_mm",
    "temp_mean",
    "temp_max",
    "temp_min",
    "wind_mean",
    "frost_flag",
    "hours_observed",
]


def find_column(columns, keyword, member):
    """Return the single column containing keyword, or fail loudly."""
    matches = [c for c in columns if keyword in c.upper()]
    if len(matches) != 1:
        raise ValueError(
            f"{member}: expected 1 column containing {keyword!r}, found {matches}"
        )
    return matches[0]


# Archives from 2008 to about 2018 write ISO dates, recent ones use slashes. Failing to
# match would silently drop every row of a year, so an unmatched file raises instead.
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y")


def parse_dates(series, member):
    """Parse the date column, trying each format INMET has used."""
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(series, format=fmt, errors="coerce")
        if not parsed.isna().all():
            return parsed
    raise ValueError(
        f"{member}: no date format in {DATE_FORMATS} matched {series.iloc[0]!r}"
    )


def to_numeric(series):
    values = pd.to_numeric(series, errors="coerce")
    # Older archives use -9999 as the missing-value sentinel.
    return values.mask(values <= -9999)


def aggregate(raw, member):
    """Hourly rows to one row per day."""
    frame = pd.read_csv(
        io.BytesIO(raw),
        sep=";",
        decimal=",",
        encoding="latin-1",
        skiprows=8,
    )
    # Trailing semicolons on every line produce an empty final column.
    frame = frame.loc[:, ~frame.columns.str.startswith("Unnamed")]

    rain = find_column(frame.columns, RAIN_KEYWORD, member)
    temp = find_column(frame.columns, TEMP_KEYWORD, member)
    wind = find_column(frame.columns, WIND_KEYWORD, member)

    frame["date"] = parse_dates(frame.iloc[:, 0], member)
    frame["rain"] = to_numeric(frame[rain])
    # temp_max and temp_min come from the hourly air temperature rather than the
    # max/min-in-previous-hour columns: one keyword match instead of three, and the
    # difference is immaterial at daily resolution.
    frame["temp"] = to_numeric(frame[temp])
    frame["wind"] = to_numeric(frame[wind])
    frame = frame.dropna(subset=["date"])

    daily = frame.groupby("date").agg(
        # min_count=1 so a day with no rain reading at all stays null instead of
        # summing to 0.0, which would read as a genuine dry day.
        rain_mm=("rain", lambda s: s.sum(min_count=1)),
        temp_mean=("temp", "mean"),
        temp_max=("temp", "max"),
        temp_min=("temp", "min"),
        wind_mean=("wind", "mean"),
        hours_observed=("temp", "count"),
    )
    # Object dtype so that a day with no temperature reading can hold None rather than
    # being forced to a True/False frost verdict.
    daily["frost_flag"] = (daily["temp_min"] <= config.FROST_THRESHOLD_C).astype(object)
    daily.loc[daily["temp_min"].isna(), "frost_flag"] = None
    return daily.reset_index()


def known_station_codes():
    return set(db.read_sql("SELECT code FROM stations")["code"])


def ingest_year(year, codes):
    path = inmet_client.download_year(year)
    archive = zipfile.ZipFile(path)

    total, skipped = 0, []
    for member in archive.namelist():
        match = MEMBER_PATTERN.search(member)
        if not match:
            continue
        uf, code = match.groups()
        if uf not in config.TARGET_UFS or code not in codes:
            continue

        try:
            daily = aggregate(archive.read(member), member)
        except Exception as error:  # one bad file must not end the run
            skipped.append(f"{member}: {error}")
            continue

        daily.insert(0, "station_code", code)
        daily = daily.astype(object).where(pd.notna(daily), None)
        total += db.upsert(
            "weather_daily",
            COLUMNS,
            list(daily[COLUMNS].itertuples(index=False, name=None)),
            ["station_code", "date"],
        )

    print(f"{year}: upserted {total} daily rows, skipped {len(skipped)} files")
    for line in skipped:
        print(f"  skipped {line}")
    return total


def main():
    codes = known_station_codes()
    if not codes:
        raise SystemExit("stations table is empty, run src.ingestion.stations first")
    print(f"{len(codes)} stations in scope")

    total = sum(ingest_year(year, codes) for year in config.TARGET_YEARS)
    print(f"total {total} daily weather rows")


if __name__ == "__main__":
    main()
