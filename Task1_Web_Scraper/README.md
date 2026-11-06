# Task 1 – Autonomous Web Scraper & Data Extractor

Scrapes the paginated catalogue at https://books.toscrape.com using `requests` + `BeautifulSoup4`
and exports a clean dataset of 1,000 records to CSV and JSON.

## Features
- Browser-like User-Agent header
- Automatic retries with exponential backoff (429/5xx) and exception handling
- Pagination loop that follows the "next" link until the last page
- Skips malformed items instead of crashing
- Optional `--details` mode visits each book page for category, UPC and review count
- Polite request delay

## Setup & Run
```bash
pip install -r requirements.txt
python scraper.py                 # outputs data/books.csv and data/books.json
python scraper.py --details       # richer metadata (slower, ~1000 extra requests)
python scraper.py --max-pages 3   # quick test
```

## Output fields
`title, price_gbp, rating (1-5), availability, url` (+ `category, upc, reviews` with `--details`)

## Structure
```
Task1_Web_Scraper/
├── scraper.py
├── requirements.txt
├── README.md
└── data/            # generated: books.csv, books.json
```
