# Data Validation Report

- Raw rows: **1270**
- Exact duplicates removed: **70**
- Duplicate business keys (book_id) removed: **0**
- Rejected (failed schema validation): **65**
- Clean rows delivered: **1135**
- Retention: **89.4%**

## Nulls per column (raw, incl. blank strings)

- title: 5
- price: 27
- rating: 47
- availability: 27
- category: 37
- scraped_date: 28
- reviews: 55

## Nulls per column after normalising 'N/A', 'null', 'unknown' etc.

- title: 5
- price: 49
- rating: 63
- availability: 27
- category: 37
- scraped_date: 39
- reviews: 55

## Schema rule violations

- book_id is null: 0
- title is null: 5
- price_gbp is null: 47
- price_gbp <= 0: 8
- rating outside 1-5: 5
- book_id format invalid: 0

## Final schema

| column | dtype | nullable |
|---|---|---|
| book_id | string | no |
| title | string | no |
| price_gbp | float64 | no |
| rating | Int64 | yes |
| in_stock | boolean | yes |
| category | string | yes |
| scraped_date | datetime64[ns] | yes |
| reviews | Int64 | yes |

## Clean data summary

- Price (GBP): min 10.03, mean 35.44, max 59.89
- Date range: 2026-01-01 to 2026-10-28
- Categories: 9

_Currency conversion uses fixed rates: 1 USD = 0.787 GBP, 1 EUR = 0.855 GBP._