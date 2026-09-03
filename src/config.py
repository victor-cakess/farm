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
TARGET_YEARS = [int(y) for y in os.getenv("TARGET_YEARS", "2023,2024,2025").split(",")]

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
