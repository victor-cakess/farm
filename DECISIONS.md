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

**Trade-off:** schema changes are manual edits to `db/init.sql` against a fresh volume.
Acceptable for a POC; a real deployment needs migrations.

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
