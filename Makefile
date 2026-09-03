RUN := docker compose run --rm app uv run --no-sync python -m

.PHONY: up down logs app psql lock clean \
        ingest ingest-stations ingest-weather ingest-price

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

# Stations must run before weather: weather_daily has a foreign key on stations.
ingest: ingest-stations ingest-weather ingest-price

ingest-stations:
	$(RUN) src.ingestion.stations

ingest-weather:
	$(RUN) src.ingestion.weather

ingest-price:
	$(RUN) src.ingestion.price

# Drops the database volume. Cached INMET zips in data/raw are left intact.
clean:
	docker compose down -v
