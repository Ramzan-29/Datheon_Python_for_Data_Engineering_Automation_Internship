# Task 3 – Relational Database Auto-Ingestion & Upsert Engine

Loads Task 2's clean CSV into SQLite using batched, transaction-safe, idempotent upserts.

```bash
pip install -r requirements.txt
python db_loader.py        # creates books.db from ../Task2_Data_Cleaning/data/clean_books.csv
python verify_queries.py   # behaviour tests + verification queries (exit 0 = pass)
```

## Design
- `schema.sql`: `categories` and `books` tables, primary keys, foreign key, CHECK constraints, indexes
- `INSERT ... ON CONFLICT(book_id) DO UPDATE` upsert, only writes when a value changed
- Whole load in a single transaction; any error triggers full rollback
- Batched with `executemany` (500 rows)
- Uses stdlib `sqlite3`; the ON CONFLICT syntax is also valid in PostgreSQL

## Tests proved by `verify_queries.py`
Initial load, idempotent re-run (0 rows written), upsert-update without duplicates, rollback on a bad batch, no orphans/duplicates.
