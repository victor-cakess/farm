# CLAUDE.md

## What this project is

A local, dockerized proof of concept for Brazilian soy farmers. It shows CEPEA soy price, local INMET weather, the relationship between the two, and a qualitative panel on how weather affects production. The goal is to earn farmer trust so they later share their yield data. It is not a recommendation engine and does no forecasting.

## Golden rules

- Keep it simple. Do not overengineer. Do not add abstraction, patterns, or dependencies that are not needed for this POC. If something can be a plain function, it is a plain function.
- Only add complexity if explicitly asked. If you think something needs more structure, ask first, do not build it preemptively.
- Only use verified facts about the data sources. The specifics below were confirmed against the real sources. Do not invent endpoints, column names, or file formats.
- No sell recommendations, no forecasting. Out of scope entirely.
- Professional code. No emojis anywhere in code or comments.

## Stack

- Python for ingestion scripts.
- PostgreSQL as the store.
- Streamlit for the local frontend, reading from Postgres.
- Docker and docker-compose for everything (postgres service + app service).
- Database connection via environment variables.

## Data source facts (verified, do not guess)

### INMET requires a browser User-Agent (both hosts)
- Requests with the default `curl` or `requests` user agent are reset by the server (curl exit 56), which looks exactly like INMET being down. The same request with a browser User-Agent returns 200.
- Every call to `portal.inmet.gov.br` and `apitempo.inmet.gov.br` must send one. See `INMET_USER_AGENT` in `src/config.py`.

### INMET historical weather
- URL pattern: `https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip`
- Members are nested under a `{year}/` folder, named `INMET_{REGION}_{UF}_{CODE}_{NAME}_{start}_A_{end}.CSV`. Some stations cover only part of the year; that is normal.
- One ZIP per year (2000 to current), one CSV per station inside.
- CSV format: `;` separator, `,` decimal, latin-1 encoding.
- First 8 rows are station metadata (region, uf, station name, WMO code, lat, lon, altitude, founding date). The real header row is row index 8.
- Records are hourly. Aggregate to daily.
- Column names carry units and vary across years. Match by keyword, not exact string. Examples: rain contains "PRECIPITA", air temperature contains "TEMPERATURA DO AR", wind speed contains "VELOCIDADE HORARIA".
- There is a trailing empty "Unnamed" column from line-ending semicolons. Drop it.

### INMET station list
- URL: `https://apitempo.inmet.gov.br/estacoes/T` returns JSON of automatic stations.
- Useful fields: CD_ESTACAO, DC_NOME, SG_ESTADO (or UF field), VL_LATITUDE, VL_LONGITUDE.

### CEPEA soy price
- Manually downloaded Excel (Indicador Soja CEPEA/ESALQ Paranagua, daily periodicity).
- File is OLE2 `.xls` but slightly malformed. Read with:
  `xlrd.open_workbook(path, ignore_workbook_corruption=True)` then `pd.read_excel(book, engine="xlrd")`.
- First 3 rows are metadata (Nota, Fonte, Data header). Real data starts at row index 3.
- Columns: date, price in R$/saca, price in US$/saca.
- Dates are DD/MM/YYYY. Decimals use comma.
- Business days only, so weekend and holiday gaps are expected and normal.

## Daily aggregation for weather

From hourly INMET data, per station per day:
- rain_mm: sum of hourly precipitation, with `min_count=1` so a day with no rain reading stays NULL instead of summing to 0. A missing day must never be presented as a dry day.
- hours_observed: count of hours with a temperature reading. Only about half of station-days report all 24 hours, and a partial day biases the daily minimum warm, so frost and heat counts are taken only over days with at least 20 hours.
- temp_mean, temp_max, temp_min: from hourly air temperature
- wind_mean: mean of hourly wind speed
- frost_flag: true if daily min temperature is at or below a threshold (default 3 C, make it a constant that is easy to change). Note in a comment that this is a rough proxy, since station air temp is measured in a shelter and real ground frost can occur a few degrees above zero.

## Database

Three tables, kept simple:
- stations: code, name, uf, latitude, longitude
- weather_daily: station_code, date, rain_mm, temp_mean, temp_max, temp_min, wind_mean, frost_flag, hours_observed
- price_daily: date, price_brl, price_usd

One init script to create them. Ingestion scripts upsert into them.

## Streamlit screens

1. Price overview: price over time (toggle R$ / US$), average price by month to show seasonality.
2. Local weather overview: station selector, daily rain / temp max-min / wind charts, frost days flagged.
3. Weather vs price: selected station weather and price on a shared time axis, a correlation figure, and a clear plain-language note that seasonality is the likely shared driver and that local weather does not set the Paranagua price.
4. Weather impact on production (qualitative): narrative on how frost, drought, excess rain, and heat at key growth stages affect soy yield, anchored to the selected station's recent season, framed as what can be quantified once the farmer shares yield data.

## The app reads from Postgres

Ingestion writes to Postgres. Streamlit reads from Postgres. The app should not parse source files at runtime.

## Honesty constraints for the content

- The weather-to-price link must be presented honestly. A single station's weather does not drive the Paranagua price. Any correlation shown is most likely seasonal coincidence. Do not word any screen to imply local weather sets price.
- Screen 4 is qualitative because there is no yield data yet. Do not fabricate a quantitative production analysis.