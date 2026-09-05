"""Configuration, all overridable by environment variable."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

PGHOST = os.getenv("PGHOST", "localhost")
PGPORT = os.getenv("PGPORT", "5432")
PGDATABASE = os.getenv("PGDATABASE", "farm")
PGUSER = os.getenv("PGUSER", "farm")
PGPASSWORD = os.getenv("PGPASSWORD", "farm")

# Core Brazilian soy states.
TARGET_UFS = os.getenv("TARGET_UFS", "PR,MS,MT,GO,RS").split(",")
TARGET_YEARS = [
    int(y)
    for y in os.getenv("TARGET_YEARS", ",".join(str(y) for y in range(2008, 2026))).split(
        ","
    )
]

# A daily minimum temperature at or below this counts as a frost day. This is a rough
# proxy: station air temperature is measured in a shelter roughly 1.5 m above ground, so
# real ground frost can occur while the shelter reading is still a few degrees above zero.
FROST_THRESHOLD_C = float(os.getenv("FROST_THRESHOLD_C", "3.0"))

CEPEA_FILE = PROJECT_ROOT / os.getenv(
    "CEPEA_FILE", "data/cepea-consulta-20260903192503.xls"
)

# INMET rejects the default requests/curl user agent with a connection reset, so every
# request to either INMET host must present a browser user agent.
INMET_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
INMET_STATIONS_URL = "https://apitempo.inmet.gov.br/estacoes/T"
INMET_HISTORICAL_URL = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{year}.zip"
# Returns 5 days, not 7: INMET publishes no longer product. Unknown municipality codes
# come back as HTTP 200 with empty day dicts, so responses are validated by content.
INMET_FORECAST_URL = "https://apiprevmet3.inmet.gov.br/previsao/{ibge_code}"
# Days 1 and 2 are split into these periods, in this order; days 3 to 5 are one block.
FORECAST_PERIODS = ("manha", "tarde", "noite")
FORECAST_WHOLE_DAY = "dia"

# IBGE. No user agent needed on either host.
IBGE_MUNICIPALITIES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
# SIDRA table 1612 (temporary crops), c81/2713 = soy in grain, n6 = municipality.
# Variables: 112 yield kg/ha, 216 harvested area ha, 214 production t.
SIDRA_YIELD_URL = (
    "https://apisidra.ibge.gov.br/values/t/1612/n6/in%20n3%20{uf_code}"
    "/v/112,216,214/p/{first_year}-{last_year}/c81/2713?formato=json"
)
UF_CODES = {"RS": 43, "PR": 41, "MS": 50, "MT": 51, "GO": 52}
YIELD_FIRST_YEAR = int(os.getenv("YIELD_FIRST_YEAR", "2008"))
YIELD_LAST_YEAR = int(os.getenv("YIELD_LAST_YEAR", "2024"))

# DERAL/SEAB Parana producer prices, R$ per 60 kg bag. Plain downloads, no user agent.
DERAL_MONTHLY_URL = (
    "https://www.agricultura.pr.gov.br/system/files/publico/Precos/sh95recebido.xls"
)
DERAL_WEEKLY_URL = "https://www.agricultura.pr.gov.br/system/files/publico/Precos/prp.xls"

# Soy season: 1 October of year-1 through 30 April of year, which is also the harvest year
# IBGE reports against.
SEASON_START_MONTH = 10
SEASON_END_MONTH = 4
SEASON_END_DAY = 30

# A day with at least this many hourly temperature readings is treated as fully observed.
FULL_COVERAGE_HOURS = int(os.getenv("FULL_COVERAGE_HOURS", "20"))
HEAT_STRESS_C = float(os.getenv("HEAT_STRESS_C", "34"))
# A season is usable only if at least this share of its days carry rain and complete
# temperature readings. Below it the season is excluded from every comparison.
SEASON_SUFFICIENT_SHARE = float(os.getenv("SEASON_SUFFICIENT_SHARE", "0.5"))
# Minimum sufficient seasons before any yield comparison is shown at all.
MIN_SEASONS_FOR_COMPARISON = int(os.getenv("MIN_SEASONS_FOR_COMPARISON", "8"))
# Minimum seasons on each side of the dry/not-dry split. Without this a single drought
# year becomes a headline percentage, which is one observation wearing the clothes of a
# finding.
MIN_SEASONS_PER_GROUP = int(os.getenv("MIN_SEASONS_PER_GROUP", "3"))
# A dry spell of at least this many days inside January-March marks a season as dry.
DRY_SPELL_THRESHOLD_DAYS = int(os.getenv("DRY_SPELL_THRESHOLD_DAYS", "15"))

# Reference water balance. Single bucket, no crop coefficient, so it describes the
# weather rather than a particular field.
SOIL_CAPACITY_MM = float(os.getenv("SOIL_CAPACITY_MM", "100"))
SOIL_START_MM = float(os.getenv("SOIL_START_MM", "50"))
SOIL_DEFICIT_MM = float(os.getenv("SOIL_DEFICIT_MM", "30"))
# Soy thermal time: base 10 C, upper cap 30 C.
GDD_BASE_C = float(os.getenv("GDD_BASE_C", "10"))
GDD_CAP_C = float(os.getenv("GDD_CAP_C", "30"))

SACA_KG = 60.0
