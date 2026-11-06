"""Generate a deliberately messy 'scraped books' dataset (seeded, reproducible).

Dirt injected: null/blank values, mixed currencies and symbols, five date formats,
inconsistent casing/whitespace, rating as words/digits/text, exact + near duplicates,
junk values ('N/A', 'null', negative prices).
"""
import random
from pathlib import Path

import pandas as pd

random.seed(42)
N = 1200
CATEGORIES = ["Fiction", "Mystery", "History", "Science", "Poetry", "Travel", "Humor", "Music"]
WORDS = ["Silent", "Garden", "Night", "River", "Last", "Hidden", "Winter", "Paper", "Glass",
         "Ocean", "Secret", "Broken", "Golden", "Shadow", "Letters", "Road", "Empire", "Dream"]
RATING_VARIANTS = {1: ["One", "1", "1 star"], 2: ["Two", "2", "2 stars"], 3: ["Three", "3", "3 stars"],
                   4: ["Four", "4", "4 stars"], 5: ["Five", "5", "5 stars"]}


def messy_price(p: float) -> str:
    return random.choice([f"£{p:.2f}", f"{p:.2f} GBP", f"${p * 1.27:.2f}", f"USD {p * 1.27:,.2f}",
                          f"€{p * 1.17:.2f}", f"{p:.2f}", f" £{p:.2f} "])


def messy_date(d: pd.Timestamp) -> str:
    return random.choice([d.strftime("%Y-%m-%d"), d.strftime("%d/%m/%Y"), d.strftime("%b %d, %Y"),
                          d.strftime("%d-%b-%Y"), d.strftime("%Y/%m/%d")])


rows = []
for i in range(N):
    title = " ".join(random.sample(WORDS, 3)) + f" #{i}"
    price = round(random.uniform(10, 60), 2)
    date = pd.Timestamp("2026-01-01") + pd.Timedelta(days=random.randint(0, 300))
    cat = random.choice(CATEGORIES)
    rows.append({
        "book_id": f"BK{i:05d}",
        "title": random.choice([title, title.upper(), f"  {title}  ", title.lower()]),
        "price": messy_price(price),
        "rating": random.choice(RATING_VARIANTS[random.randint(1, 5)]),
        "availability": random.choice(["In stock", "in stock", "IN STOCK", "Out of stock", "out of stock", "yes", "no"]),
        "category": random.choice([cat, cat.upper(), cat.lower(), f" {cat} "]),
        "scraped_date": messy_date(date),
        "reviews": random.randint(0, 250),
    })

df = pd.DataFrame(rows)

# inject nulls / junk
for col, frac, junk in [("price", .04, ["", "N/A", None]), ("rating", .05, ["", None, "null"]),
                        ("category", .03, ["", None]), ("scraped_date", .03, ["", "unknown", None]),
                        ("reviews", .04, [None]), ("availability", .02, [None, ""])]:
    idx = df.sample(frac=frac, random_state=hash(col) % 1000).index
    df[col] = df[col].astype(object)
    df.loc[idx, col] = [random.choice(junk) for _ in idx]
df.loc[df.sample(8, random_state=1).index, "price"] = "-5.00"      # invalid negatives
df.loc[df.sample(5, random_state=2).index, "rating"] = "9"          # out of range
df.loc[df.sample(5, random_state=3).index, "title"] = None          # missing key field

# duplicates: exact + near (same id, tweaked casing/price)
exact = df.sample(40, random_state=4)
near = df.sample(30, random_state=5).copy()
near["title"] = near["title"].astype(str).str.upper()
df = pd.concat([df, exact, near]).sample(frac=1, random_state=6).reset_index(drop=True)

out = Path("data"); out.mkdir(exist_ok=True)
df.to_csv(out / "raw_books.csv", index=False)
print(f"Wrote {len(df)} dirty rows to {out / 'raw_books.csv'}")
