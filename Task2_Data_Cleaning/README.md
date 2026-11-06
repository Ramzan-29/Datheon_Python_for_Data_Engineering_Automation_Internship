# Task 2 – Automated Data Cleaning & Schema Transformation

Pandas pipeline that turns a messy scraped dataset into validated, production-ready tabular data.

```bash
pip install -r requirements.txt
python generate_dirty_data.py      # creates data/raw_books.csv (1,270 intentionally dirty rows)
python clean_data.py               # or: --input your_file.csv
```

## What it handles
| Problem | Fix |
|---|---|
| Blank / "N/A" / "null" / "unknown" | Normalised to real nulls, counted in report |
| Mixed currencies (£, $, €, "USD 12.5", "GBP") | Parsed and converted to GBP (fixed documented rates) |
| 5 date formats | Parsed to a single datetime type |
| Rating as "Three" / "3 stars" / "3" | Integer 1–5 |
| Casing/whitespace in text | Stripped, title-cased |
| Exact and key duplicates | Removed (keeps most complete record) |
| Invalid rows (null title/price, price ≤ 0, rating outside 1–5) | Quarantined in `rejected_rows.csv` with reasons |

## Outputs (`data/`)
`clean_books.csv`, `rejected_rows.csv`, `validation_report.md`, `cleaning.log`

Latest run: 1,270 raw → 70 duplicates removed → 66 rejected → **1,134 clean rows (89.3%)**.
