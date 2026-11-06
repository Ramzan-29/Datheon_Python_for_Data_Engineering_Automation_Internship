"""Idempotent loader: cleaned CSV -> SQLite with batch upserts and transaction safety.

Usage:
    python db_loader.py --csv ../Task2_Data_Cleaning/data/clean_books.csv --db books.db

Design notes
- Whole load runs in ONE transaction: any error => full rollback, DB never half-loaded.
- Upsert uses INSERT ... ON CONFLICT(book_id) DO UPDATE (SQLite >= 3.24, same syntax in PostgreSQL).
- The UPDATE only fires when a value actually changed, so re-running is a true no-op.
- Batched with executemany for speed.
"""
import argparse
import logging
import sqlite3
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
BATCH = 500
log = logging.getLogger("loader")

UPSERT_CATEGORY = "INSERT INTO categories(name) VALUES (?) ON CONFLICT(name) DO NOTHING"

UPSERT_BOOK = """
INSERT INTO books (book_id, title, price_gbp, rating, in_stock, category_id, scraped_date, reviews)
VALUES (:book_id, :title, :price_gbp, :rating, :in_stock, :category_id, :scraped_date, :reviews)
ON CONFLICT(book_id) DO UPDATE SET
    title        = excluded.title,
    price_gbp    = excluded.price_gbp,
    rating       = excluded.rating,
    in_stock     = excluded.in_stock,
    category_id  = excluded.category_id,
    scraped_date = excluded.scraped_date,
    reviews      = excluded.reviews,
    updated_at   = CURRENT_TIMESTAMP
WHERE title        IS NOT excluded.title
   OR price_gbp    IS NOT excluded.price_gbp
   OR rating       IS NOT excluded.rating
   OR in_stock     IS NOT excluded.in_stock
   OR category_id  IS NOT excluded.category_id
   OR scraped_date IS NOT excluded.scraped_date
   OR reviews      IS NOT excluded.reviews
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript((HERE / "schema.sql").read_text())


def _py(v):
    """Convert pandas NA/NaT/numpy types to plain Python for sqlite3."""
    if pd.isna(v):
        return None
    return v.item() if hasattr(v, "item") else v


def load_csv(conn: sqlite3.Connection, csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    df["scraped_date"] = df["scraped_date"].astype("string")
    df["in_stock"] = df["in_stock"].map({True: 1, False: 0, "True": 1, "False": 0})

    before_total = conn.total_changes
    try:
        conn.execute("BEGIN")
        conn.executemany(UPSERT_CATEGORY, [(c,) for c in df["category"].dropna().unique()])
        cat_ids = {r["name"]: r["category_id"] for r in conn.execute("SELECT * FROM categories")}

        existing = {r["book_id"] for r in conn.execute("SELECT book_id FROM books")}
        rows = []
        for rec in df.to_dict("records"):
            rows.append({
                "book_id": rec["book_id"], "title": rec["title"],
                "price_gbp": _py(rec["price_gbp"]), "rating": _py(rec["rating"]),
                "in_stock": _py(rec["in_stock"]),
                "category_id": cat_ids.get(rec["category"]),
                "scraped_date": _py(rec["scraped_date"]), "reviews": _py(rec["reviews"]),
            })
        for i in range(0, len(rows), BATCH):
            conn.executemany(UPSERT_BOOK, rows[i:i + BATCH])
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        log.exception("Load failed; transaction rolled back")
        raise

    incoming = {r["book_id"] for r in rows}
    result = {"rows_in_file": len(rows), "new_ids": len(incoming - existing),
              "existing_ids_seen": len(incoming & existing),
              "rows_written": conn.total_changes - before_total}
    log.info("Load complete: %s", result)
    return result


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=HERE.parent / "Task2_Data_Cleaning/data/clean_books.csv")
    ap.add_argument("--db", default=str(HERE / "books.db"))
    args = ap.parse_args()
    with connect(args.db) as conn:
        conn.isolation_level = None  # manual transaction control
        create_schema(conn)
        load_csv(conn, args.csv)


if __name__ == "__main__":
    main()
