# Soja: preco e clima

Local, dockerized proof of concept for Brazilian soy farmers. It shows the CEPEA/ESALQ
Paranagua soy price, local INMET weather, the two side by side, and a qualitative panel on
how weather affects soy production.

It makes no sell recommendations and does no forecasting.

## Running it

Requires Docker and Docker Compose. Nothing else needs to be installed locally.

```sh
make up        # start Postgres and create the schema
make ingest    # load every source, in dependency order
make forecast  # INMET five-day forecast (kept separate: it is time sensitive)
make app       # serve Streamlit at http://localhost:8501
```

The first `make ingest` downloads one INMET archive per year from 2008 (70-112 MB each,
about 1.4 GB in total) into `data/raw/` and takes 20-30 minutes. Later runs reuse the
cached archives. Ingestion is idempotent, so re-running it is safe and leaves row counts
unchanged.

There is no migration path. `db/schema.sql` is the whole schema and Postgres runs it once
on an empty volume; to change it, edit the file and run `make reset` followed by
`make ingest`. Every loader upserts, so the data is reproducible and rebuilding is cheap.

### Other targets

| Target | What it does |
|---|---|
| `make ingest-stations` | INMET automatic station list for the configured states |
| `make ingest-municipalities` | IBGE municipalities, and maps each station to one |
| `make ingest-weather` | Yearly INMET archives to daily aggregates |
| `make derive` | Rebuilds ET0, soil water, thermal time and the season features |
| `make ingest-price` | The CEPEA Excel file in `data/` |
| `make ingest-deral` | Parana producer prices, monthly and weekly |
| `make ingest-yield` | Municipal soy yield from IBGE |
| `make ingest-cost` | CONAB reference cost (needs a manual file, see below) |
| `make forecast` | INMET five-day forecast for every mapped municipality |
| `make test` | pytest over the pure functions; no database or network needed |
| `make lint` | ruff; `make fmt` to format |
| `make reset` | Drop the database and recreate it from `db/schema.sql` |
| `make psql` | psql shell on the database |
| `make logs` | Postgres logs |
| `make lock` | Refresh `uv.lock` after changing dependencies |
| `make down` | Stop containers, keep the data volume |
| `make clean` | Stop containers and drop the data volume (cached archives survive) |

`make ingest` runs these in dependency order: stations before municipalities (which maps
them), weather before `derive` (which reads it), municipalities before yield.

### Cost of production

`make ingest-cost` is not wired up. CONAB's portal exposes no API and its spreadsheets sit
behind a JavaScript download modal, so the file has to be downloaded by hand and its format
confirmed before a parser is written. Until then, enter your own cost on the **Meus dados**
screen: a farmer's own figure takes precedence over any reference anyway.

## Configuration

Copy `.env.example` to `.env` to override any of it. Defaults:

- `TARGET_UFS=PR,MS,MT,GO,RS` - the core soy states, 273 automatic stations
- `TARGET_YEARS=2008..2025`
- `FROST_THRESHOLD_C=3.0`, `HEAT_STRESS_C=34`, `FULL_COVERAGE_HOURS=20`
- `SOIL_CAPACITY_MM=100`, `SOIL_START_MM=50`, `SOIL_DEFICIT_MM=30`
- `MIN_SEASONS_FOR_COMPARISON=8`, `MIN_SEASONS_PER_GROUP=3`
- `CEPEA_FILE=data/cepea-consulta-20260903192503.xls`

Widening either list means a longer ingest; nothing else changes.

## The screens

1. **Preco** - the indicator over time in R$ or US$; the monthly pattern as each month's
   deviation from its own year's average; Paranagua against what Parana producers were
   actually paid; how much of each move was the bean and how much the dollar; and a
   breakeven line once you have entered a cost.
2. **Clima local** - the INMET five-day forecast with a refresh button, then daily rain,
   temperature range, wind and the reference soil water balance, with frost days flagged.
3. **Clima e preco** - the station's weather and the price on a shared time axis, with a
   correlation figure and a plain-language note on how to read it.
4. **Clima e producao** - municipal soy yield from IBGE, detrended, against the season
   measures from your station, with the station's own correlation and how consistently the
   region agrees; then the last season's counts and what each one means for a crop.
5. **Meus dados** - your yield and cost per field and season, compared immediately against
   the municipal average and the weather of those seasons.

The station selector in the sidebar drives every screen. The app opens on the station with
the most complete record.

## What the analysis does and does not claim

Screen 4 uses the **municipality average** from IBGE, never a single farm. Municipal yield
rises over time with technology, so it is detrended before any comparison, and what is
compared is the deviation from that trend.

Which weather measure to compare against was chosen by measuring, not by assumption. Over
1,612 season-observations across 122 stations:

| measure | pooled r | per-station median r | share negative |
|---|---|---|---|
| days of soil water deficit | -0.216 | -0.264 | 77% |
| days above 34 C | -0.189 | -0.393 | 83% |
| longest run without rain | -0.024 | -0.089 | 66% |
| longest run without rain, Jan-Mar | -0.043 | -0.103 | 59% |

Soil water deficit and heat track yield; **runs of days without rain barely do**. A
fortnight without rain on a full soil is not a drought.

A single station has 8 to 18 seasons, which is too few to settle anything, so its
correlation is always shown beside how many stations in the region share its sign. Where a
station disagrees with the region, the screen says so.

Everything here is association across seasons, never a causal estimate and never a loss
figure for a field.

## Data sources

- **CEPEA/ESALQ Soja Paranagua**, daily indicator, downloaded manually from the CEPEA site
  as `.xls` and committed under `data/`. Business days only, so weekend and holiday gaps
  are expected. The site returns 403 to scripts, so this one stays manual.
- **INMET** automatic stations, historical hourly archives, and the municipal five-day
  forecast.
- **IBGE** municipality list and municipal soy yield (PAM, SIDRA table 1612), 2008-2024.
  Published annually and in arrears, so the current season has no yield yet.
- **DERAL / SEAB Parana** monthly and weekly prices received by Parana producers.

INMET's hosts and DERAL's both drop the connection for the default `requests` user agent,
so ingestion sends a browser one. See `INMET_USER_AGENT` in `src/config.py`. A request
without it fails in a way that looks exactly like the source being down.

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
db/schema.sql          the whole schema, run by Postgres on an empty volume
src/config.py          settings, all env-overridable
src/db.py              the only module that talks to Postgres
src/domain/            pure functions, no I/O, covered by tests
  seasons.py           season windows, dry spells, season features
  agronomy.py          reference ET0, soil water balance, thermal time
  analysis.py          detrending and the yield-versus-weather comparison
src/ingestion/         source clients and loaders: read -> domain -> upsert
src/app/               Streamlit entry point, queries, theme, screens
tests/                 pytest over src/domain and the parsers
data/raw/              cached INMET and DERAL downloads (gitignored)
```

The layering is one-directional: `app` and `ingestion` both depend on `domain` and `db`,
and never on each other. The screens import `src.app.queries` and nothing else, so the one
place the app triggers ingestion (the forecast refresh button) goes through
`queries.refresh_forecast` rather than reaching into a loader.

Ingestion writes to Postgres; the app reads from it and never parses a source file at
runtime. Two deliberate exceptions, both calling the same functions the CLI does: the
forecast refresh button, and saving or deleting your own records.

`src/domain` must stay free of I/O — no database, no network, no file reads. That is what
keeps it testable, and `make test` runs in under a second because of it.

Design decisions and their trade-offs are in [DECISIONS.md](DECISIONS.md).
