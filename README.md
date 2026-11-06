# Datheon Python for Data Engineering & Automation Internship

An end-to-end data pipeline: **scrape → clean & validate → load into a SQL database**.

| Task | Folder | What it does |
|---|---|---|
| 1 | `Task1_Web_Scraper/` | Scrapes 1,000 records across 50 paginated pages with requests + BeautifulSoup4 (retries, user-agent headers, CSV/JSON export) |
| 2 | `Task2_Data_Cleaning/` | Pandas pipeline: handles nulls, normalizes currency and dates, removes duplicates, validates schema, writes a validation report |
| 3 | `Task3_Database_Upsert/` | Idempotent SQLite loader with batch upserts, transaction rollback, and automated verification queries |

## How to run
Each folder has its own README. In short:
​```
pip install -r requirements.txt
python scraper.py              # Task 1
python clean_data.py           # Task 2
python db_loader.py            # Task 3
python verify_queries.py       # Task 3 tests
​```

**Tech stack:** Python 3, requests, BeautifulSoup4, Pandas, SQLite
