# Decisions

Judgment calls made while building the POC, with what was rejected and why.

## Dependencies managed with uv

**Chosen:** `pyproject.toml` plus a committed `uv.lock`, installed in Docker with
`uv sync --frozen`.

**Alternatives:** a plain `requirements.txt`; Poetry.

**Why:** locked, reproducible installs and a dependency layer that caches independently of
the source. There is exactly one dependency file, no `requirements.txt` alongside it.

**Trade-off:** contributors need `uv` on the host to run `make lock`. Nothing else does.

## Commands wrapped in a Makefile

**Chosen:** every operation is a `make` target over `docker compose run --rm app ...`.

**Alternative:** documenting the raw compose commands in the README.

**Why:** the ingestion commands are long and order-dependent. `make ingest` encodes the
order (stations before weather, which has the foreign key) so it cannot be run wrong.

**Trade-off:** one more file, and the README must not drift from it.

## Postgres accessed with SQLAlchemy, no ORM

**Chosen:** one `get_engine()` helper and one `upsert()` helper over `execute_values`.

**Alternatives:** bare psycopg2; SQLAlchemy ORM models; an existing migration tool.

**Why:** `pandas.read_sql` warns on a raw psycopg2 connection, and an engine removes that
without pulling in an ORM. Three tables with natural keys do not need models or migrations.

**Trade-off:** schema changes are manual edits to the schema file against a fresh volume.
Acceptable for a POC; a real deployment needs migrations.

*Partly superseded by the cleanup pass: the helpers moved into a single `src/db.py` API
(`read_sql` / `execute` / `execute_many` / `upsert`) and `db/init.sql` became
`db/schema.sql`. The no-ORM, no-migration-tool choice stands.*

## Ingestion upserts rather than truncating

**Chosen:** `INSERT ... ON CONFLICT DO UPDATE` on `code`, `(station_code, date)`, `date`.

**Why:** re-running any loader has to be safe. Verified: a full second `make ingest` leaves
row counts and a checksum of `weather_daily` byte-identical.

**Trade-off:** rows deleted upstream are never removed locally. The sources are append-only
archives, so this does not arise.

## INMET requests send a browser user agent

**Chosen:** a Chrome user agent on every INMET request, in `src/config.INMET_USER_AGENT`.

**Why:** not a preference, a requirement. Both INMET hosts reset the connection on the
default `curl`/`requests` agent (curl exit 56) and return 200 with a browser one. Without
it, ingestion fails in a way that looks like INMET being down.

**Trade-off:** it misrepresents the client. There is no documented alternative and no API
key to request.

## temp_max and temp_min come from the hourly air temperature

**Chosen:** daily max and min of the hourly air-temperature column.

**Alternative:** the dedicated "maximum/minimum in the previous hour" columns.

**Why:** one keyword match instead of three, against headers whose exact text varies by
year. At daily resolution the difference is immaterial.

**Trade-off:** the daily extremes can be marginally inside the true ones, since they only
see values on the hour.

## Days with no rain reading are stored NULL, not 0

**Chosen:** `sum(min_count=1)`, so a day with no rain observation is NULL.

**Why:** pandas sums an all-missing day to `0.0`. That made a station's silence look like a
dry day, and produced a headline "longest dry spell: 164 days" that was purely missing
data. For a tool whose whole purpose is earning farmer trust, a fabricated drought is the
worst possible failure. 41,912 of 174,897 days (24 percent) are affected.

**Trade-off:** season rainfall totals are now understated for sparse stations. That is
labelled on screen as a measured minimum rather than silently wrong.

## weather_daily records hours_observed

**Chosen:** a `smallint` column counting hours with a temperature reading.

**Alternatives:** nulling all aggregates below a coverage threshold; ignoring coverage.

**Why:** only about half of station-days report all 24 hours. A partial day biases
`temp_min` warm and would under-count frost. Keeping the count lets each screen qualify its
own numbers instead of hiding the gap, and keeps the partial data available.

**Trade-off:** one extra column, and every consumer has to decide what to do with it.

## Screen 3 stacks two charts instead of using two y-axes

**Chosen:** price and weather as separate charts on a shared x-axis.

**Alternative:** one chart with two y-scales, as originally planned.

**Why:** a second y-axis can be scaled until any two series appear to move together. Since
the honesty requirement is that local weather must never look like it sets the Paranagua
price, the chart form that manufactures apparent correlation is the wrong one.

**Trade-off:** slightly harder to compare turning points across two plots.

## Screens withhold numbers that the data cannot support

**Chosen:** screen 4 hides its counts when a station reported under half the season
(76 of 187 stations); screen 3 shows no correlation below 24 overlapping months
(50 of 187 stations).

**Alternative:** always show the number, with a caveat.

**Why:** a correlation over one month, or a frost count over a tenth of a season, is noise
with a decimal point. A caveat under a confident-looking figure does not get read.

**Trade-off:** many stations show less than the full screen. That is the honest state of
the source data, and the message says which station to pick instead.

## Charts pinned to a single light theme

**Chosen:** one light palette, blue and orange, pinned via `.streamlit/config.toml`.

**Alternative:** supporting the viewer's dark mode.

**Why:** the palette was validated for contrast and colour-vision separation against the
light surface it actually renders on. A dark variant needs its own steps and its own
validation, which is not POC work.

**Trade-off:** the app ignores an OS dark-mode preference.

## The screens are written in Portuguese

**Chosen:** all user-facing text in Portuguese; code, comments and docs in English.

**Why:** the audience is Brazilian soy farmers, and screens 3 and 4 carry the honesty
message that the POC depends on. It only works in the reader's language.

**Trade-off:** text is unaccented ASCII, per the project's no-special-characters
convention, so it reads slightly off to a native speaker. Worth revisiting before this is
shown to actual farmers.

---

# Phase 2

## Weather backfilled to 2008

**Chosen:** `TARGET_YEARS` defaults to 2008-2025, about 1.4 GB cached in `data/raw/`.

**Why:** IBGE publishes municipal yield from 2008. Comparing weather to yield over two
seasons would have been meaningless; 17 seasons per municipality makes it a real
comparison.

**Trade-off:** the first ingest takes 20-30 minutes and a gigabyte and a half of disk.
Cached archives make every later run fast.

## Date parsing raises instead of returning empty

**Chosen:** try `%Y-%m-%d`, `%Y/%m/%d`, `%d/%m/%Y`; raise naming the file if none match.

**Why:** archives from 2008 to about 2018 use ISO dates, which the phase-1 parser matched
against neither format. It would have coerced every row to NaT and loaded the year as
zero rows without any error. A loud failure is the whole point here.

**Trade-off:** a genuinely new format stops the run rather than degrading. That is correct
for a loader whose silent failure mode is an empty year.

## Rain and soil water are treated as different questions

**Chosen:** the soil water balance drives the drought measure; consecutive rain-free days
is kept but demoted.

**Why:** measured, not assumed. Across 1,612 season-observations in 122 stations, days of
soil water deficit correlate with detrended yield at -0.216 pooled (77% of stations
negative) and heat days at -0.189 (83% negative), while the longest dry spell manages
-0.024 (66%) and the January-March dry spell -0.043 (59%). A fortnight without rain on a
full soil is not a drought; a week without rain on an empty one is.

**Trade-off:** the water balance has no crop coefficient and no soil survey, so it
describes the weather at the station rather than water available in a field. Every screen
that shows it says so.

## The dry/not-dry split was dropped for a correlation

**Chosen:** show the scatter of every season plus a correlation, not a two-group mean.

**Alternative:** the binary comparison the plan called for.

**Why:** with an honest minimum of 3 seasons per group, only 27 of 273 stations qualified,
and among those the difference was median -0.7pp with 14 of 27 negative: a coin flip. The
split was also usually 1 drought season against 16 normal ones, which produces a large
confident-looking percentage from a single observation.

**Trade-off:** a correlation is harder to read than "X% lower in dry years". The scatter
with one labelled point per season is what makes it legible.

## Regional consistency shown beside the local number

**Chosen:** the station's own correlation next to how many stations in the five states
share its sign.

**Why:** one station has 8 to 18 seasons, which is far too few to settle anything. The
regional count is what turns a noisy local number into evidence, and it is also what
explains a station whose sign disagrees. Where the local sign contradicts the region, the
screen says that outright.

**Trade-off:** it invites a farmer to weigh two numbers instead of one. Hiding the
disagreement would be worse.

## Season features are a table, not a query

**Chosen:** `season_features`, rebuilt by `make derive`.

**Why:** the same season definition is needed by three screens and by the yield join.
Recomputing 2,819 seasons from 959k daily rows on each page load would be slow and would
risk two screens defining a season differently.

**Trade-off:** it can go stale after a weather ingest. `make ingest` runs `derive`
immediately after `ingest-weather` for that reason.

## Forecast stored in Postgres with an in-app refresh

**Chosen:** `make forecast` loads all municipalities; the screen's button calls the same
`refresh()` function for one.

**Alternative:** fetching live in the app.

**Why:** keeps "the app reads from Postgres", shows the farmer how old the forecast is,
and means an INMET outage leaves the last forecast on screen instead of breaking the page.

**Trade-off:** the forecast is only as fresh as the last refresh, which is why the issue
time is always displayed.

## Only the icon code is stored

**Chosen:** keep `cod_icone`, discard `icone`.

**Why:** the icon is a base64 PNG of about 50 KB per period, roughly 190 KB per
municipality per refresh, and the code already identifies it.

## Farmer cost overrides the reference cost

**Chosen:** breakeven uses the farmer's own cost when present, a CONAB reference
otherwise, and nothing at all if neither exists.

**Why:** the farmer's number is always the better one, and a breakeven line drawn from a
state average would be quietly wrong for their farm.

**Trade-off:** the CONAB half is not built. Their portal exposes no API and the
spreadsheets sit behind a download modal, so writing a parser blind would have violated
the rule about verified formats. `cost_reference` exists and stays empty until a file is
in hand.

## Parana is the only regional price

**Chosen:** DERAL's Parana series for every station, labelled as Parana.

**Why:** it is the only source that verified as a direct, automatable download. CEPEA
returns 403, IMEA is a JavaScript application, CONAB has no API.

**Trade-off:** a farmer in Mato Grosso sees an illustration rather than their own basis.
The screen says exactly that, and notes their real gap is likely larger because freight to
the port is longer.

## The exchange rate needs no source

**Chosen:** derive the rate from CEPEA's own two series.

**Why:** CEPEA publishes the same indicator in R$ and US$, so their ratio is the rate used
for conversion. Checked against BCB PTAX it agrees within 0.4%. The decomposition is exact
by construction: the bean and dollar log-changes sum to the total to within 3e-14.

**Trade-off:** it is CEPEA's conversion rate, not an independent one. That is the right
one here, since the goal is to explain CEPEA's own R$ series.

## The screens withhold rather than caveat

**Chosen:** no comparison under 8 sufficient seasons, no group mean under 3 seasons, no
correlation where the measure barely varies, no season counts where the station covered
under half the season.

**Why:** a caveat printed under a large confident number does not get read. For a tool
whose only purpose is trust, showing nothing is cheaper than showing something wrong.

**Trade-off:** 59 of 203 stations show a reduced screen 4. That is the honest state of the
source data, and the screen says which station to try instead.

---

# Cleanup pass

## One schema file, no migrations

**Chosen:** `db/schema.sql` with final `CREATE TABLE` statements, ordered so the foreign
keys resolve. `db/init.sql` and `db/migrate_phase2.sql` are gone, and so is `make migrate`.

**Alternative:** keeping the `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` file, or adopting a
migration tool.

**Why:** the migration existed only to get phase-2 columns into a database that already
held data. Keeping it means a reader has to replay a migration in their head to know what a
table looks like. Every source is either cached locally or re-downloadable and every loader
upserts, so the data is reproducible; a rebuild costs about fifteen minutes and no
downloads.

**Trade-off:** a schema change now means dropping the database. That is the correct trade
for a local POC and would be the wrong one the moment there is data that cannot be rebuilt
— farmer-entered records are exactly that, so this decision should be revisited before
anyone relies on `farm_records`.

## src/db.py is the only module that touches Postgres

**Chosen:** `read_sql`, `execute`, `execute_many` and `upsert`, all sharing one private
cursor context manager.

**Why:** there were three ways to read (`pd.read_sql`, `exec_driver_sql`, a private
`_read`) and three hand-copied connection/cursor/commit blocks. The date-coercion that
turns Postgres `date` columns into something with a `.dt` accessor lived in the app layer,
so ingestion silently got different types from the same table.

**Trade-off:** one more indirection between a loader and psycopg2. It removes three copies
of the same eight lines, so the rule of three is satisfied twice over.

## A pure domain package

**Chosen:** `src/domain/` holding `seasons`, `agronomy` and `analysis`, with no I/O.
Ingestion and the app both depend on it and never on each other.

**Why:** the ET0, soil-bucket and thermal-time maths sat inside an ingestion script, which
made the functions carrying the product's central claim reachable only by running a loader
against a database. Moving them made a real test suite possible; the tests found nothing in
the code but did catch a degenerate fixture, which is its own small lesson.

**Trade-off:** one more package level. It is the boundary the tests rely on, so it earns
its place.

## Tests cover pure functions only

**Chosen:** pytest over `src/domain` and the source parsers. No database, no network, runs
in under a second.

**Alternative:** also round-tripping upserts against a throwaway Postgres.

**Why:** the honesty rules are all decisions in pure code — that a gap breaks a dry spell
rather than extending it, that GDD caps at exactly 20, that a comparison is withheld below
eight seasons. Those are worth locking down. Integration behaviour is already covered by a
full rebuild plus a 1,015-render sweep of the screens, which is stronger evidence than a
mocked round trip.

**Trade-off:** nothing asserts the schema matches what the loaders write, beyond the
end-to-end run. Acceptable while that run is part of every change.

## ruff, and a one-time format pass

**Chosen:** ruff for linting and formatting, line length 92, `make lint` / `make fmt`.

**Why:** style consistency should be mechanical rather than argued about. The one-time
format pass touched 14 files and 196 lines, all mechanical.

**Trade-off:** it makes this commit's diff larger than the logic changes alone. Worth it
once, at a point where the behaviour is independently verified by checksum.

## Verified by checksum, not by inspection

The refactor's acceptance test was that a full rebuild reproduces the previous database
exactly: same row counts in all eight tables, and `weather_daily` including the derived
`soil_water_mm` and `gdd` columns hashing to `234e0cd06c35c13fdd70d886ef778ae1` both before
and after. Moving the maths between modules is exactly the kind of change that can silently
alter a result, and reading the diff would not have proved otherwise.
