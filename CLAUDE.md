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
- Column names carry units and vary across years. Match by keyword, not exact string. Examples: rain contains "PRECIPITA", air temperature contains "TEMPERATURA DO AR", wind speed contains "VELOCIDADE HORARIA". The keyword matches are unique in both the 2010 and 2025 layouts.
- There is a trailing empty "Unnamed" column from line-ending semicolons. Drop it.
- **The date format changes across years.** Archives from around 2008 to 2018 write `2010-01-01` and an hour column of `00:00`; recent ones write `2025/01/01` and `0000 UTC`. Try `%Y-%m-%d`, then `%Y/%m/%d`, then `%d/%m/%Y`, and raise if none match: a silent mismatch drops every row of a year.
- Older archives use `-9999` as a missing-value sentinel; recent ones use empty strings. Handle both.
- Archives exist from 2000, but the automatic network only fills out from about 2007. Sizes run 40-112 MB per year.

### INMET station list
- URL: `https://apitempo.inmet.gov.br/estacoes/T` returns JSON of automatic stations.
- Useful fields: CD_ESTACAO, DC_NOME, SG_ESTADO (or UF field), VL_LATITUDE, VL_LONGITUDE.

### INMET forecast
- URL: `https://apiprevmet3.inmet.gov.br/previsao/{ibge_code}`, keyed by IBGE municipality code. Needs the browser User-Agent like the other INMET hosts.
- Returns **five days, not seven**. INMET publishes no longer product; do not imply one.
- Days 1 and 2 are split into `manha` / `tarde` / `noite`; days 3 to 5 are a single flat block. Sort periods explicitly, since alphabetical order puts `noite` before `tarde`.
- Fields: `resumo`, `temp_max`, `temp_min`, `umidade_max`, `umidade_min`, `dir_vento`, `int_vento`, `cod_icone`, `icone`. There is **no rain amount and no rain probability**, only the text summary.
- `icone` is a base64 PNG of roughly 50 KB per period. Store `cod_icone` only.
- An unknown municipality still returns **HTTP 200** with empty period dicts, so validate by content, not status.

### IBGE
- Municipality list: `https://servicodados.ibge.gov.br/api/v1/localidades/municipios`, 5,571 rows, no User-Agent needed. UF is at `microrregiao.mesorregiao.UF.sigla`, but some rows have a null `microrregiao`; fall back to `regiao-imediata.regiao-intermediaria.UF.sigla`.
- Municipal soy yield (PAM): `https://apisidra.ibge.gov.br/values/t/1612/n6/in n3 {uf_code}/v/112,216,214/p/{first}-{last}/c81/2713?formato=json`. Table 1612 is temporary crops, `c81/2713` is soy in grain, `n6` is municipality. Variables: 112 yield kg/ha, 216 harvested area ha, 214 production t. UF codes: PR 41, RS 43, MS 50, MT 51, GO 52.
- **Row 0 is a header row of labels, not data.** Fields: `D1C` municipality code, `D3C` year, `D2C` variable, `V` value. Missing values are the string `-`.
- Years 2008-2024 are available; IBGE publishes annually and in arrears, so the current season has no yield yet.
- `D1N` is formatted differently in single-municipality and bulk queries; join on `D1C`.
- Station names are not municipality names. Normalising (strip accents, cut at ` - ` or `(`) plus UF matches 265 of 273 stations; the remaining 8 are hand-mapped in `src/ingestion/municipalities.py`.

### DERAL / SEAB Parana producer prices
- `https://www.agricultura.pr.gov.br/system/files/publico/Precos/sh95recebido.xls` and `.../prp.xls`. OLE2, same `xlrd` corruption override as the CEPEA file.
- **This host also drops the connection for the default `requests` User-Agent** (verified: curl exit 52 with `python-requests/2.31.0`, HTTP 200 with a browser one). Send the browser agent.
- `sh95recebido.xls`: 38 sheets, one per product. Sheet `SOJA` is the monthly state average received by producers, R$ per 60 kg, 1995 onwards. Header at row 7 (`ANO`, `JAN`..`DEZ`), data from row 8 until a blank year, then footer rows starting `Obs.:` / `Fonte:`. Unpublished months are blank.
- `prp.xls`: one sheet, current week by regional. The week is in cell `(0, 15)` as `PERIODO: 31/08/2026 a 04/09/2026`. Regional names are row 1 from column 3; the `Soja` row is labelled in column 1. Skip the `MEDIA`, `MSA` and `%MSA` aggregate columns, comparing accent-free (the sheet writes `MÉDIA`).

### Sources that are not automatable
- CEPEA site returns HTTP 403 even with a browser User-Agent. The price file stays a manual download.
- IMEA is a Vue application with no data links in the HTML.
- CONAB's portal is an Angular app with no API in its bundle; cost spreadsheets sit behind a download modal. Cost of production is therefore a manual file plus farmer entry.

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

## Derived measures

- `et0_mm`: FAO-56 Hargreaves reference evapotranspiration, from Tmax/Tmin/Tmean and the station latitude. No new inputs required.
- `soil_water_mm`: single bucket, 100 mm capacity, starting at 50 mm, `store = clamp(store + rain - et0, 0, 100)`. A day missing rain or ET0 leaves the store untouched and records NULL, so a gap never reads as drying soil. No crop coefficient and no soil survey: it describes the weather, not a field.
- `gdd`: soy thermal time, base 10 C, **both** Tmax and Tmin clipped into [10, 30]. Clipping only Tmax lets a tropical night push a day past the theoretical daily maximum.
- `season_features`: one row per station per harvest year. A season labelled Y runs 1 Oct (Y-1) to 30 Apr Y, which is the year IBGE reports the harvest against. `sufficient` is false when the station reported under half the season; insufficient seasons are excluded from every comparison, never quietly averaged in.

## Which weather measure actually tracks yield

Measured over 1,612 season-observations across 122 stations, correlation with detrended municipal yield:

| measure | pooled r | per-station median r | share negative |
|---|---|---|---|
| water_deficit_days | -0.216 | -0.264 | 77% |
| heat_days | -0.189 | -0.393 | 83% |
| longest_dry_spell_days | -0.024 | -0.089 | 66% |
| dry_spell_jan_mar_days | -0.043 | -0.103 | 59% |

Days of soil water deficit and days above 34 C track yield; **runs of days without rain barely do**. Do not build a drought claim on consecutive dry days. Municipal yield must be detrended before any comparison, because it rises over time with technology.

## Database

Tables, kept simple:
- stations: code, name, uf, latitude, longitude, ibge_code
- weather_daily: station_code, date, rain_mm, temp_mean, temp_max, temp_min, wind_mean, frost_flag, hours_observed, et0_mm, soil_water_mm, gdd
- price_daily: date, price_brl, price_usd
- municipalities, yield_municipal, season_features, price_monthly_pr, price_weekly_pr, forecast, farm_records, cost_reference

`db/schema.sql` is the whole schema and the only DDL. Postgres runs it once on an empty volume. There is no migration path and no `ALTER TABLE`: to change the schema, edit the file and run `make reset` then `make ingest`. Every loader upserts, so the data is reproducible from cached sources.

## Code layout rules

- `src/db.py` is the only module that talks to Postgres. Use `read_sql`, `execute`, `execute_many`, `upsert`; do not open connections elsewhere.
- `src/domain/` holds pure functions only: no database, no network, no file reads. This is what makes it testable, and it is where the season definition, the agronomic maths and the yield analysis live. Ingestion and the app both depend on it; it depends on neither.
- The screens import `src.app.queries` and nothing else. When a screen needs to trigger ingestion, add a wrapper in `queries` rather than importing a loader.
- `make test` covers `src/domain` and the parsers and needs no database. `make lint` must pass.

## Streamlit screens

1. Price overview: price over time (toggle R$ / US$), the monthly pattern as each month's deviation from its own year's mean, Paranagua against DERAL's Parana producer price (the basis), the split of each move into bean and dollar, and a breakeven line when a cost is known.
2. Local weather overview: station selector, the INMET five-day forecast with a refresh button, daily rain / temp max-min / wind charts, frost days flagged, and the reference soil water balance.
3. Weather vs price: selected station weather and price on a shared time axis, a correlation figure, and a clear plain-language note that seasonality is the likely shared driver and that local weather does not set the Paranagua price.
4. Weather impact on production: municipal yield from IBGE, detrended, against the season measures from the station, with the station's own correlation and how consistently the region agrees. Then the season's counts, then the qualitative mechanisms.
5. My data: the farmer enters yield and optional cost per field and season, and immediately sees it against the municipal average and the season's weather.

## The app reads from Postgres

Ingestion writes to Postgres. Streamlit reads from Postgres. The app should not parse source files at runtime.

Two exceptions, both deliberate and both going through the same ingestion functions the CLI uses: the forecast refresh button, and saving or deleting a farmer's own records.

## Honesty constraints for the content

- The weather-to-price link must be presented honestly. A single station's weather does not drive the Paranagua price. Any correlation shown is most likely seasonal coincidence. Do not word any screen to imply local weather sets price.
- Screen 4's quantitative part uses the **municipality average** from IBGE. It is never the farmer's own yield, and it is association across seasons, never a causal estimate or a loss figure for a field.
- Withhold rather than caveat. A number the data cannot support is not shown at all: no comparison under 8 sufficient seasons, no correlation where the measure barely varies, no season counts where the station reported under half the season, no group mean with fewer than 3 seasons in it. A caveat under a confident-looking figure does not get read.
- When one station's correlation disagrees with the regional majority, say so plainly. Two numbers pointing opposite ways with no explanation is worse than either one alone.
- The forecast is INMET's five days, presented as theirs and dated. Never extend it, average it, or turn its text into millimetres.
- The basis series is Parana. For a station in another state, say on screen that it is an illustration and not that state's price.