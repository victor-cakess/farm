RUN := docker compose run --rm app uv run --no-sync python -m

.PHONY: up down logs app psql lock clean reset test lint fmt \
        ingest ingest-stations ingest-weather ingest-price \
        ingest-municipalities ingest-yield ingest-deral derive forecast ingest-cost

up:
	docker compose up -d db

down:
	docker compose down

logs:
	docker compose logs db

app:
	docker compose up app

psql:
	docker compose exec db psql -U $${PGUSER:-farm} -d $${PGDATABASE:-farm}

lock:
	uv lock

# Drop the database and recreate it from db/schema.sql. There is no migration path: the
# data is reproducible with `make ingest`, and cached archives make that cheap.
reset:
	docker compose down -v
	docker compose up -d db

test:
	uv run --group dev pytest -q

lint:
	uv run --group dev ruff check .

fmt:
	uv run --group dev ruff format .

# Order matters: stations before municipalities (which maps them), weather before derive
# (which reads it), municipalities before yield (which references them).
ingest: ingest-stations ingest-municipalities ingest-weather derive ingest-price \
        ingest-deral ingest-yield

ingest-stations:
	$(RUN) src.ingestion.stations

ingest-municipalities:
	$(RUN) src.ingestion.municipalities

ingest-weather:
	$(RUN) src.ingestion.weather

ingest-price:
	$(RUN) src.ingestion.price

ingest-yield:
	$(RUN) src.ingestion.yield_ibge

ingest-deral:
	$(RUN) src.ingestion.deral

# Reference cost of production. Needs a CONAB spreadsheet downloaded by hand into data/.
ingest-cost:
	$(RUN) src.ingestion.cost_conab

# Rebuilds the daily agronomic columns and the per-season features.
derive:
	$(RUN) src.ingestion.derive

# Time sensitive, so it is kept out of `make ingest` and run on its own.
forecast:
	$(RUN) src.ingestion.forecast

# Drops the database volume. Cached INMET zips in data/raw are left intact.
clean:
	docker compose down -v
