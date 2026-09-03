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

## Out of scope

- Sell recommendations.
- Any forecasting (weather or price).
- Cloud deployment.
- Auth or multi-user.
- Real-time data.