"""Load IBGE municipalities and map each weather station to one.

Station names are not municipality names: they carry abbreviations, district names and
accents. Normalised name plus UF matches 265 of 273 target stations to exactly one
municipality; the rest are listed below, each checked by hand against the IBGE list.
"""

import re
import unicodedata

import requests

from src import config, db

# Verified against the IBGE municipality list; each resolves to exactly one municipality.
STATION_MUNICIPALITY_OVERRIDES = {
    "A905": 5102637,  # CAMPO NOVO DOS PARECIS -> Campo Novo do Parecis (MT)
    "A963": 5103304,  # COMODORO NORTE -> Comodoro (MT)
    "A970": 5107859,  # ESPIGAO DO LESTE -> Sao Felix do Araguaia (MT), district
    "A820": 4114609,  # MAL. CANDIDO RONDON -> Marechal Candido Rondon (PR)
    "A717": 5003207,  # NHUMIRIM -> Corumba (MS), Embrapa Pantanal farm
    "B810": 4306767,  # PARQUE ELDORADO -> Eldorado do Sul (RS)
    "A903": 5107305,  # S.J. DO RIO CLARO -> Sao Jose do Rio Claro (MT)
    "A969": 5107800,  # SANTO ANTONIO DO LEVERGER -> Santo Antonio de Leverger (MT)
}


def normalise(name):
    """Strip accents and anything after a dash or bracket, so names compare equal."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().upper()
    text = re.split(r"\s*[-(]", text)[0]
    return re.sub(r"[^A-Z ]", "", text).strip()


def municipality_uf(entry):
    """UF of a municipality. Some rows carry a null microrregiao, so fall back."""
    micro = entry.get("microrregiao")
    if micro:
        return micro["mesorregiao"]["UF"]["sigla"]
    return entry["regiao-imediata"]["regiao-intermediaria"]["UF"]["sigla"]


def fetch_municipalities():
    response = requests.get(config.IBGE_MUNICIPALITIES_URL, timeout=180)
    response.raise_for_status()
    return response.json()


def main():
    entries = fetch_municipalities()
    print(f"fetched {len(entries)} municipalities")

    rows, index = [], {}
    for entry in entries:
        uf = municipality_uf(entry)
        if uf not in config.TARGET_UFS:
            continue
        rows.append((entry["id"], entry["nome"], uf))
        index.setdefault((normalise(entry["nome"]), uf), []).append(entry["id"])

    db.upsert("municipalities", ["ibge_code", "name", "uf"], rows, ["ibge_code"])
    print(f"upserted {len(rows)} municipalities for {', '.join(config.TARGET_UFS)}")

    stations = db.read_sql("SELECT code, name, uf FROM stations")

    mapped, unmatched = [], []
    for code, name, uf in stations.itertuples(index=False, name=None):
        ibge_code = STATION_MUNICIPALITY_OVERRIDES.get(code)
        if ibge_code is None:
            candidates = index.get((normalise(name), uf), [])
            # Only an unambiguous single match is trusted; anything else is listed.
            if len(candidates) == 1:
                ibge_code = candidates[0]
        if ibge_code is None:
            unmatched.append((code, name, uf))
        else:
            mapped.append((ibge_code, code))

    db.execute_many("UPDATE stations SET ibge_code = %s WHERE code = %s", mapped)

    print(f"mapped {len(mapped)} of {len(stations)} stations to a municipality")
    for row in unmatched:
        print(f"  unmatched {row}")


if __name__ == "__main__":
    main()
