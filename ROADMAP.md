# Roadmap - weather and price POC

## Goal

A local, dockerized POC that shows Brazilian soy farmers the CEPEA soy price, their local INMET weather, the relationship between the two, and a qualitative panel on how weather affects production. The POC's job is to earn farmer trust so they share their yield data. No sell recommendations, no forecasting yet.

## Stack

- Python ingestion scripts (weather from INMET API, price from CEPEA Excel).
- PostgreSQL as the store.
- Streamlit as the local frontend, reading from Postgres.
- Everything dockerized (Postgres + app via docker-compose).

## Data sources

- INMET historical: `https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip`. One ZIP per year, one CSV per station. Hourly records. CSVs: `;` separator, `,` decimal, latin-1 encoding, 8 metadata rows before the header. Column names carry units and vary across years, so match by keyword not exact string.
- INMET station list: `https://apitempo.inmet.gov.br/estacoes/T` (automatic stations, codes and coordinates).
- CEPEA soy price: manual Excel download from the CEPEA site (Indicador Soja Paranaguá, daily). OLE2 `.xls` that needs `xlrd` with `ignore_workbook_corruption=True`. 3 metadata rows, then columns date / R$ / US$, comma decimals, DD/MM/YYYY dates.

## Steps

### 1. Project skeleton
- Create repo structure: ingestion scripts, db layer, streamlit app, docker files.
- docker-compose with two services: postgres and the streamlit app.
- Config for db connection via environment variables.

### 2. Database schema
- Table for stations (code, name, uf, latitude, longitude).
- Table for daily weather (station code, date, rain, temp mean/max/min, wind mean, frost flag).
- Table for daily price (date, price_brl, price_usd).
- Keep it simple, one migration/init script.

### 3. Station ingestion
- Pull the station list from the INMET stations endpoint.
- Load into the stations table.

### 4. Weather ingestion
- Download one or more yearly ZIPs from the INMET historical archive.
- For each station CSV: skip metadata rows, parse with the right separator/decimal/encoding, match columns by keyword.
- Reduce hourly to daily aggregates (rain sum, temp mean/max/min, wind mean, frost flag from min temp threshold).
- Load into the weather table.
- Make the year(s) and station set configurable.

### 5. Price ingestion
- Read the CEPEA Excel with the xlrd corruption workaround.
- Drop metadata rows, rename columns, parse dates and comma decimals.
- Load into the price table.
- Input file path configurable.

### 6. Streamlit app - screen 1: price overview
- Line chart of CEPEA price over time, toggle R$ / US$.
- Average price by month bar chart to show seasonality.

### 7. Streamlit app - screen 2: local weather overview
- Station selector (from stations table).
- Daily weather charts for the selected station: rain, temp max/min, wind.
- Frost days flagged.

### 8. Streamlit app - screen 3: weather vs price
- Selected station weather series and price series over a shared time axis.
- A correlation figure, with a clear plain-language note that seasonality is the likely shared driver and local weather does not set the Paranaguá price.

### 9. Streamlit app - screen 4: weather impact on production (qualitative)
- Narrative panel on how frost, drought, excess rain, and heat at key growth stages affect soy yield.
- Anchor to the selected station's recent season (e.g. count of frost days, dry spells) so it feels specific.
- Framed explicitly as what can be quantified once the farmer shares their yield data.

### 10. Wire up and polish
- Ensure app reads everything from Postgres, not from files at runtime.
- Basic layout and navigation across the four screens.
- README with how to run: bring up compose, run ingestion, open Streamlit.

## Phase 2 - done

Steps 1 to 10 above are complete. Phase 2 added:

11. **Weather backfill to 2008.** 959k daily rows, 203 stations. Older archives use ISO dates and `-9999` sentinels.
12. **IBGE municipalities and yield.** All 273 stations mapped to a municipality; municipal soy yield 2008-2024 from SIDRA table 1612.
13. **Agronomic derivations.** Hargreaves ET0, a single-bucket soil water balance, thermal time, and per-season features.
14. **Screen 4 made quantitative.** Detrended municipal yield against the season measures, with the station's correlation and the region's consistency beside it.
15. **Screen 5, "Meus dados".** Yield and cost per field and season, with an immediate comparison against the municipality. This is the point of the tool: everything else exists to earn the trust to reach it.
16. **Basis.** DERAL Parana producer prices beside CEPEA Paranagua, so the farmer sees a number closer to the farm gate.
17. **FX decomposition.** Each monthly move split into bean and dollar, from the two CEPEA series alone.
18. **INMET five-day forecast**, stored in Postgres with an in-app refresh button.
19. **Breakeven line**, from the farmer's own cost when present.

## Cleanup pass - done

20. **One schema file.** `db/schema.sql` replaced the init/migrate pair; no `ALTER TABLE`, no migration path, rebuild with `make reset`.
21. **One database API.** `src/db.py` is the only module that opens a connection.
22. **A pure domain package.** `src/domain/{seasons,agronomy,analysis}.py`, free of I/O, with `src/ingestion` and `src/app` depending on it and not on each other.
23. **Tests and linting.** 53 pytest cases over the domain and the parsers, plus ruff. Verified by rebuilding the database and matching the previous checksum exactly.

## Next

- **Cost of production from CONAB.** Gated: their portal has no API and the spreadsheets sit behind a download modal, so it needs a manual file and a format spike before a parser is written. Farmer-entered cost already works without it.
- **Regional prices outside Parana.** No verified automatable source yet for MT, MS, GO or RS. IMEA is a JavaScript app, CEPEA blocks scraping, CONAB has no API. Would need either manual files or a different provider.
- **NDVI / satellite (Sentinel-2 via Copernicus).** Free imagery, and the thing that would let a farmer see their own fields rather than a municipal average. **Prerequisite: field boundaries**, which is itself a significant data ask, larger than the yield one. Decide after the "Meus dados" loop has real records: if farmers will not enter a yield number, they will not draw field polygons either. Worth revisiting once there is evidence the loop works.
- **Per-farm analysis.** Once a farmer has 8 or more seasons entered, run the same detrend-and-compare on their own numbers instead of the municipality's. The code path already exists; only the data source changes.

## Out of scope

- Sell recommendations.
- Price forecasting.
- Any weather forecast beyond republishing INMET's own five days.
- Cloud deployment.
- Auth or multi-user.
- Real-time data.