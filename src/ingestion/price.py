"""Load the CEPEA/ESALQ Paranagua soy indicator into the price_daily table."""

import pandas as pd
import xlrd

from src import config, db

# The export is OLE2 but slightly malformed, hence the corruption override.
# Rows 0-2 are metadata (Nota, Fonte, the date header), so data starts at row 3.
METADATA_ROWS = 3


def to_number(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(".", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def read_price_file(path):
    book = xlrd.open_workbook(path, ignore_workbook_corruption=True)
    frame = pd.read_excel(book, engine="xlrd")

    frame = frame.iloc[METADATA_ROWS:, :3]
    frame.columns = ["date", "price_brl", "price_usd"]

    frame["date"] = pd.to_datetime(frame["date"], format="%d/%m/%Y", errors="coerce")
    frame["price_brl"] = frame["price_brl"].map(to_number)
    frame["price_usd"] = frame["price_usd"].map(to_number)
    # Business days only, so weekend and holiday gaps are expected and left as gaps.
    return frame.dropna(subset=["date"])


def main():
    frame = read_price_file(config.CEPEA_FILE)
    rows = [
        (row.date.date(), row.price_brl, row.price_usd)
        for row in frame.itertuples(index=False)
    ]

    count = db.upsert("price_daily", ["date", "price_brl", "price_usd"], rows, ["date"])
    print(f"upserted {count} price rows")
    print(f"range {frame['date'].min().date()} to {frame['date'].max().date()}")
    print(
        f"price_brl min {frame['price_brl'].min():.2f} max {frame['price_brl'].max():.2f}"
    )


if __name__ == "__main__":
    main()
