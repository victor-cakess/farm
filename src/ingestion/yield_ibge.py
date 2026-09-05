"""Load municipal soy yield from IBGE PAM (SIDRA table 1612) into yield_municipal.

This is the municipality average, never a single farm. It exists so the production screen
can show a real relationship between weather and yield before any farmer shares data.
"""

import requests

from src import config, db

# SIDRA variable codes, in the order requested.
VARIABLES = {"112": "yield_kg_ha", "216": "area_ha", "214": "production_t"}
MISSING = "-"


def fetch_uf(uf, uf_code):
    url = config.SIDRA_YIELD_URL.format(
        uf_code=uf_code,
        first_year=config.YIELD_FIRST_YEAR,
        last_year=config.YIELD_LAST_YEAR,
    )
    print(f"{uf}: requesting SIDRA")
    response = requests.get(url, timeout=600)
    response.raise_for_status()
    payload = response.json()
    # Row 0 repeats the field labels rather than carrying data.
    return payload[1:]


def to_number(value):
    if value == MISSING:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def main():
    known = set(db.read_sql("SELECT ibge_code FROM municipalities")["ibge_code"])
    if not known:
        raise SystemExit(
            "municipalities table is empty, run src.ingestion.municipalities first"
        )

    collected = {}
    for uf, uf_code in config.UF_CODES.items():
        if uf not in config.TARGET_UFS:
            continue
        for record in fetch_uf(uf, uf_code):
            ibge_code = int(record["D1C"])
            if ibge_code not in known:
                continue
            key = (ibge_code, int(record["D3C"]))
            column = VARIABLES.get(record["D2C"])
            if column:
                collected.setdefault(key, {})[column] = to_number(record["V"])

    rows = [
        (
            ibge_code,
            year,
            values.get("yield_kg_ha"),
            values.get("area_ha"),
            values.get("production_t"),
        )
        for (ibge_code, year), values in collected.items()
    ]

    count = db.upsert(
        "yield_municipal",
        ["ibge_code", "year", "yield_kg_ha", "area_ha", "production_t"],
        rows,
        ["ibge_code", "year"],
    )
    with_yield = sum(1 for row in rows if row[2] is not None)
    print(f"upserted {count} municipality-year rows, {with_yield} with a yield value")


if __name__ == "__main__":
    main()
