# Soja: preco e clima

Local, dockerized proof of concept for Brazilian soy farmers. It shows the CEPEA/ESALQ
Paranagua soy price, local INMET weather, the two side by side, and a qualitative panel on
how weather affects soy production.

It makes no sell recommendations and does no forecasting.

## Running it

Requires Docker and Docker Compose. Nothing else needs to be installed locally.

```sh
make up        # start Postgres and create the schema
make ingest    # load stations, then weather, then price
make app       # serve Streamlit at http://localhost:8501
```

The first `make ingest` downloads one INMET archive per year (about 90 MB each) into
`data/raw/` and takes a few minutes. Later runs reuse the cached archives. Ingestion is
idempotent, so re-running it is safe and leaves row counts unchanged.

### Other targets

| Target | What it does |
|---|---|
| `make ingest-stations` | INMET automatic station list for the configured states |
| `make ingest-weather` | Yearly INMET archives to daily aggregates |
| `make ingest-price` | The CEPEA Excel file in `data/` |
| `make psql` | psql shell on the database |
| `make logs` | Postgres logs |
| `make lock` | Refresh `uv.lock` after changing dependencies |
| `make down` | Stop containers, keep the data volume |
| `make clean` | Stop containers and drop the data volume (cached archives survive) |

Run `ingest-stations` before `ingest-weather`: `weather_daily` has a foreign key on
`stations`.

## Configuration

Copy `.env.example` to `.env` to override any of it. Defaults:

- `TARGET_UFS=PR,MS,MT,GO,RS` - the core soy states, 273 automatic stations
- `TARGET_YEARS=2023,2024,2025`
- `FROST_THRESHOLD_C=3.0`
- `CEPEA_FILE=data/cepea-consulta-20260903192503.xls`

Widening either list means a longer ingest; nothing else changes.

## The screens

1. **Preco** - the indicator over time in R$ or US$, plus the monthly pattern expressed as
   each month's deviation from its own year's average.
2. **Clima local** - daily rain, temperature range and wind for the selected station, with
   frost days flagged.
3. **Clima e preco** - the station's weather and the price on a shared time axis, with a
   correlation figure and a plain-language note on how to read it.
4. **Clima e producao** - what the selected station recorded last season, and what each of
   those numbers means for a soy crop.

The station selector in the sidebar drives screens 2, 3 and 4. The app opens on the station
with the most complete record.

## Data sources

- **CEPEA/ESALQ Soja Paranagua**, daily indicator, downloaded manually from the CEPEA site
  as `.xls` and committed under `data/`. Business days only, so weekend and holiday gaps
  are expected.
- **INMET** automatic stations
  (`https://apitempo.inmet.gov.br/estacoes/T`) and historical hourly archives
  (`https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip`).

Both INMET hosts reject the default `requests` user agent, so ingestion sends a browser
one. See `src/config.py`.

## How the weather data is treated

Hourly station records are reduced to one row per station per day: rain summed,
temperature averaged with its daily max and min, wind averaged, and a frost flag from the
daily minimum.

Two properties of the source shape the screens:

- Stations often report only part of a day. `weather_daily.hours_observed` records how many
  hours carried a temperature reading, and frost and heat counts are taken only over days
  with at least 20 of them.
- A day with no rain reading is stored as NULL, not as zero, so a gap in the record can
  never be presented as a dry day.

Screen 4 hides its counts entirely for a station that reported less than half of the
season, and screen 3 withholds a correlation below 24 overlapping months.

## Layout

```
db/init.sql            schema, run once by Postgres on first start
src/config.py          settings, all env-overridable
src/db.py              engine and upsert helper
src/ingestion/         stations, weather, price loaders
src/app/               Streamlit entry point, queries, screens
data/raw/              cached INMET archives (gitignored)
```

Ingestion writes to Postgres; the app only reads from it and never parses a source file at
runtime.

Design decisions and their trade-offs are in [DECISIONS.md](DECISIONS.md).
