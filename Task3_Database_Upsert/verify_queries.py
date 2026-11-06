"""Query verification + idempotency / upsert / rollback tests.

Usage: python verify_queries.py --db books.db
Exit code 0 = all checks passed.
"""
import argparse
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pandas as pd

import db_loader

HERE = Path(__file__).parent
CSV = HERE.parent / "Task2_Data_Cleaning/data/clean_books.csv"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def one(conn, sql, *a):
    return conn.execute(sql, a).fetchone()[0]


def run_tests() -> None:
    tmp = Path(tempfile.mkdtemp())
    db = str(tmp / "test.db")
    with db_loader.connect(db) as conn:
        conn.isolation_level = None
        db_loader.create_schema(conn)

        r1 = db_loader.load_csv(conn, CSV)
        n1 = one(conn, "SELECT COUNT(*) FROM books")
        check("initial load inserts all rows", n1 == r1["rows_in_file"], f"({n1} rows)")

        r2 = db_loader.load_csv(conn, CSV)
        n2 = one(conn, "SELECT COUNT(*) FROM books")
        check("IDEMPOTENT: re-run adds no rows", n2 == n1, f"({n2} rows)")
        check("IDEMPOTENT: re-run writes nothing", r2["rows_written"] == 0, f"(rows_written={r2['rows_written']})")

        # upsert-update: change one row in a copy of the CSV
        df = pd.read_csv(CSV)
        target = df.loc[0, "book_id"]
        df.loc[0, "price_gbp"] = 99.99
        changed = tmp / "changed.csv"
        df.to_csv(changed, index=False)
        db_loader.load_csv(conn, changed)
        check("UPSERT: existing row updated", one(conn, "SELECT price_gbp FROM books WHERE book_id=?", target) == 99.99)
        check("UPSERT: no duplicate created", one(conn, "SELECT COUNT(*) FROM books") == n1)

        # rollback: one bad row (negative price violates CHECK) must roll back the whole batch
        bad = pd.read_csv(CSV).head(3)
        bad.loc[2, "price_gbp"] = -1
        bad.loc[0, "price_gbp"] = 1.23
        bad_path = tmp / "bad.csv"
        bad.to_csv(bad_path, index=False)
        try:
            db_loader.load_csv(conn, bad_path)
            check("ROLLBACK: bad batch rejected", False)
        except sqlite3.IntegrityError:
            first = bad.loc[0, "book_id"]
            check("ROLLBACK: bad batch rejected, nothing partially applied",
                  one(conn, "SELECT price_gbp FROM books WHERE book_id=?", first) != 1.23)
    shutil.rmtree(tmp)


def show_queries(db: str) -> None:
    conn = sqlite3.connect(db)
    queries = {
        "Row counts": "SELECT (SELECT COUNT(*) FROM books) AS books, (SELECT COUNT(*) FROM categories) AS categories",
        "Orphan books (should be 0)": "SELECT COUNT(*) FROM books b LEFT JOIN categories c USING(category_id) WHERE b.category_id IS NOT NULL AND c.category_id IS NULL",
        "Duplicate book_ids (should be 0)": "SELECT COUNT(*) FROM (SELECT book_id FROM books GROUP BY book_id HAVING COUNT(*)>1)",
        "Avg price & count by category": "SELECT c.name, COUNT(*) n, ROUND(AVG(b.price_gbp),2) avg_price FROM books b JOIN categories c USING(category_id) GROUP BY c.name ORDER BY n DESC LIMIT 5",
        "Top 5 rated & most reviewed": "SELECT title, rating, reviews FROM books WHERE rating=5 ORDER BY reviews DESC LIMIT 5",
        "In-stock share": "SELECT ROUND(100.0*SUM(in_stock)/COUNT(in_stock),1) AS pct_in_stock FROM books",
    }
    for label, sql in queries.items():
        cur = conn.execute(sql)
        print(f"\n-- {label}")
        print(" | ".join(d[0] for d in cur.description))
        for row in cur.fetchall():
            print(" | ".join(str(x) for x in row))
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(HERE / "books.db"))
    args = ap.parse_args()
    print("=== Behaviour tests (run on a temp DB) ===")
    run_tests()
    print("\n=== Verification queries on", args.db, "===")
    show_queries(args.db)
    sys.exit(0 if all(results) else 1)
