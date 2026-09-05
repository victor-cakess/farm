"""Load Parana producer prices from DERAL/SEAB.

CEPEA Paranagua is a port price. What a farmer receives is lower by freight, margin and
quality discounts. DERAL publishes the price actually received by Parana producers, which
is the closest verified series to a farm gate price, so the two together show the basis.

Two files, both OLE2 .xls read with the same corruption override as the CEPEA file:
  sh95recebido.xls  sheet SOJA, monthly state average 1995 onwards, R$ per 60 kg
  prp.xls           one sheet, current week by regional, R$ per 60 kg
"""

import re
import unicodedata

import requests
import xlrd

from src import config, db

MONTHLY_SHEET = "SOJA"
MONTHLY_HEADER_ROW = 7  # row 7 is ANO, JAN..DEZ; data starts at row 8
MONTHLY_FIRST_DATA_ROW = 8
WEEKLY_PERIOD_CELL = (0, 15)  # "PERIODO: 31/08/2026 a 04/09/2026"
WEEKLY_REGIONAL_ROW = 1
WEEKLY_FIRST_COLUMN = 3
SOY_LABEL = "SOJA"
# Aggregates in the regional row that are not places. Compared accent-free, because the
# sheet writes "MEDIA" with an accent and upper() alone would not match it.
WEEKLY_SKIP = {"MEDIA", "MSA", "%MSA"}


def strip_accents(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def download(url, name):
    path = config.RAW_DIR / "deral" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url}")
    # Like INMET, this host drops the connection for the default requests user agent
    # (verified: curl exit 52 with "python-requests/2.31.0", HTTP 200 with a browser one).
    response = requests.get(
        url, headers={"User-Agent": config.INMET_USER_AGENT}, timeout=300
    )
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def open_sheet(path, name=None):
    book = xlrd.open_workbook(path, ignore_workbook_corruption=True)
    return book.sheet_by_name(name) if name else book.sheet_by_index(0)


def load_monthly():
    sheet = open_sheet(
        download(config.DERAL_MONTHLY_URL, "sh95recebido.xls"), MONTHLY_SHEET
    )

    rows = []
    for index in range(MONTHLY_FIRST_DATA_ROW, sheet.nrows):
        values = sheet.row_values(index)
        year = str(values[1]).strip()
        # The data block ends at a blank year; footer rows follow ("Obs.:", "Fonte:").
        if not year or not year.replace(".", "").isdigit():
            break
        for month in range(1, 13):
            price = values[1 + month]
            if price in ("", None):
                continue  # months not yet published
            rows.append((int(float(year)), month, float(price)))

    count = db.upsert(
        "price_monthly_pr", ["year", "month", "price_brl_sc"], rows, ["year", "month"]
    )
    span = f"{rows[0][0]}-{rows[-1][0]}" if rows else "none"
    print(f"upserted {count} monthly Parana prices, {span}")


def parse_week_end(sheet):
    """Read the week from the sheet header. The period cell is verified at (0, 15)."""
    label = str(sheet.cell_value(*WEEKLY_PERIOD_CELL))
    dates = re.findall(r"(\d{2}/\d{2}/\d{4})", label)
    if not dates:
        raise ValueError(f"no period found in {label!r} at cell {WEEKLY_PERIOD_CELL}")
    day, month, year = dates[-1].split("/")
    return f"{year}-{month}-{day}"


def load_weekly():
    sheet = open_sheet(download(config.DERAL_WEEKLY_URL, "prp.xls"))
    week_date = parse_week_end(sheet)

    regionals = sheet.row_values(WEEKLY_REGIONAL_ROW)
    soy_row = next(
        (
            sheet.row_values(index)
            for index in range(sheet.nrows)
            if str(sheet.cell_value(index, 1)).strip().upper() == SOY_LABEL
        ),
        None,
    )
    if soy_row is None:
        raise ValueError("no row labelled Soja in the weekly sheet")

    rows = []
    for column in range(WEEKLY_FIRST_COLUMN, len(regionals)):
        name = str(regionals[column]).strip()
        if not name or strip_accents(name).upper() in WEEKLY_SKIP:
            continue
        price = soy_row[column] if column < len(soy_row) else ""
        rows.append((week_date, name, float(price) if price not in ("", None) else None))

    count = db.upsert(
        "price_weekly_pr",
        ["week_date", "regional", "price_brl_sc"],
        rows,
        ["week_date", "regional"],
    )
    quoted = sum(1 for row in rows if row[2] is not None)
    print(f"upserted {count} regional prices for week ending {week_date}, {quoted} quoted")


def main():
    load_monthly()
    load_weekly()


if __name__ == "__main__":
    main()
