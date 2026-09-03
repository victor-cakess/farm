"""HTTP access to INMET. Both endpoints require a browser user agent."""

import requests

from src import config

_HEADERS = {"User-Agent": config.INMET_USER_AGENT}


def get_stations():
    """Return the automatic station list as parsed JSON."""
    response = requests.get(config.INMET_STATIONS_URL, headers=_HEADERS, timeout=120)
    response.raise_for_status()
    return response.json()


def download_year(year):
    """Download the yearly historical archive, or reuse the cached copy."""
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RAW_DIR / f"{year}.zip"
    if path.exists():
        print(f"{year}: using cached {path}")
        return path

    url = config.INMET_HISTORICAL_URL.format(year=year)
    print(f"{year}: downloading {url}")
    partial = path.with_suffix(".zip.part")
    with requests.get(url, headers=_HEADERS, stream=True, timeout=600) as response:
        response.raise_for_status()
        with open(partial, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1 << 20):
                handle.write(chunk)

    # Rename only after a complete download so an interrupted run does not poison the cache.
    partial.rename(path)
    print(f"{year}: saved {path} ({path.stat().st_size} bytes)")
    return path
