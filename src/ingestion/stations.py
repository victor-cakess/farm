"""Load the INMET automatic station list into the stations table."""

from src import config, db
from src.ingestion import inmet_client


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def main():
    stations = inmet_client.get_stations()
    print(f"fetched {len(stations)} stations")

    rows = [
        (
            s["CD_ESTACAO"],
            s["DC_NOME"],
            s["SG_ESTADO"],
            to_float(s["VL_LATITUDE"]),
            to_float(s["VL_LONGITUDE"]),
        )
        for s in stations
        if s.get("SG_ESTADO") in config.TARGET_UFS
    ]

    count = db.upsert(
        "stations",
        ["code", "name", "uf", "latitude", "longitude"],
        rows,
        ["code"],
    )
    print(f"upserted {count} stations for {', '.join(config.TARGET_UFS)}")


if __name__ == "__main__":
    main()
