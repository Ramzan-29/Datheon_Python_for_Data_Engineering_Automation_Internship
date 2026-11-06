"""Automated data cleaning, schema transformation and validation.

Pipeline:  load -> strip/normalise text -> nulls -> currency -> dates -> types
           -> deduplicate -> schema validation (quarantine bad rows) -> save + report

Usage:
    python clean_data.py --input data/raw_books.csv --out data
Outputs:
    data/clean_books.csv           validated production-ready rows
    data/rejected_rows.csv         rows that failed validation, with reasons
    data/validation_report.md      human-readable quality log
    data/cleaning.log              step-by-step log
"""
import argparse
import logging
import re
from pathlib import Path

import pandas as pd

# Fixed reference rates (documented assumption; swap for a live FX source in production)
GBP_RATES = {"GBP": 1.0, "USD": 1 / 1.27, "EUR": 1 / 1.17}
SYMBOLS = {"£": "GBP", "$": "USD", "€": "EUR"}
NULL_TOKENS = ["", "n/a", "na", "null", "none", "nan", "unknown", "-"]
RATING_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%b %d, %Y", "%d-%b-%Y", "%Y/%m/%d"]

SCHEMA = {  # column -> (dtype, nullable)
    "book_id": ("string", False), "title": ("string", False), "price_gbp": ("float64", False),
    "rating": ("Int64", True), "in_stock": ("boolean", True), "category": ("string", True),
    "scraped_date": ("datetime64[ns]", True), "reviews": ("Int64", True),
}

log = logging.getLogger("cleaner")
stats: dict = {}


def to_na(s: pd.Series) -> pd.Series:
    """Strip whitespace and convert null-like tokens to NA."""
    s = s.astype("string").str.strip()
    return s.mask(s.str.lower().isin(NULL_TOKENS))


def parse_price(raw) -> float:
    if pd.isna(raw):
        return float("nan")
    text = str(raw).upper()
    currency = next((c for sym, c in SYMBOLS.items() if sym in text), None)
    currency = currency or next((c for c in GBP_RATES if c in text), "GBP")
    num = re.sub(r"[^\d.\-]", "", text.replace(",", ""))
    try:
        return round(float(num) * GBP_RATES[currency], 2)
    except ValueError:
        return float("nan")


def parse_date(raw):
    if pd.isna(raw):
        return pd.NaT
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(raw, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def parse_rating(raw):
    if pd.isna(raw):
        return pd.NA
    t = str(raw).lower()
    for word, n in RATING_WORDS.items():
        if word in t:
            return n
    m = re.search(r"\d+", t)
    return int(m.group()) if m else pd.NA


def clean(df: pd.DataFrame) -> pd.DataFrame:
    stats["rows_raw"] = len(df)
    stats["nulls_raw"] = {c: int(v) for c, v in df.replace(r"^\s*$", pd.NA, regex=True).isna().sum().items() if v}

    for col in df.columns:
        df[col] = to_na(df[col])
    stats["nulls_after_token_normalisation"] = {c: int(v) for c, v in df.isna().sum().items() if v}

    df["title"] = df["title"].str.replace(r"\s+", " ", regex=True).str.title()
    df["category"] = df["category"].str.title().fillna("Unknown")
    log.info("Normalised text; missing categories filled with 'Unknown'")

    df["price_gbp"] = df["price"].apply(parse_price)
    df["rating"] = df["rating"].apply(parse_rating).astype("Int64")
    df["scraped_date"] = df["scraped_date"].apply(parse_date)
    df["reviews"] = pd.to_numeric(df["reviews"], errors="coerce").astype("Int64").fillna(0)
    avail = df["availability"].str.lower()
    df["in_stock"] = avail.map({"in stock": True, "yes": True, "out of stock": False, "no": False}).astype("boolean")
    log.info("Parsed currency, dates, ratings, availability")

    df = df[list(SCHEMA)]
    before = len(df)
    df = df.drop_duplicates()
    stats["exact_duplicates_removed"] = before - len(df)
    # near-duplicates: same business key -> keep the most complete record
    df = df.assign(_filled=df.notna().sum(axis=1)).sort_values("_filled", ascending=False)
    before = len(df)
    df = df.drop_duplicates(subset="book_id", keep="first").drop(columns="_filled")
    stats["key_duplicates_removed"] = before - len(df)
    return df.sort_values("book_id").reset_index(drop=True)


def validate(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Enforce schema rules; return (valid, rejected_with_reasons)."""
    reasons = pd.Series("", index=df.index)

    def flag(mask, msg):
        nonlocal reasons
        reasons = reasons.mask(mask, reasons + msg + "; ")
        stats.setdefault("rule_violations", {})[msg] = int(mask.sum())

    for col, (_, nullable) in SCHEMA.items():
        if not nullable:
            flag(df[col].isna(), f"{col} is null")
    flag(df["price_gbp"] <= 0, "price_gbp <= 0")
    flag(~df["rating"].isna() & ~df["rating"].between(1, 5), "rating outside 1-5")
    flag(~df["book_id"].isna() & ~df["book_id"].str.match(r"^BK\d{5}$", na=False), "book_id format invalid")

    bad = reasons != ""
    rejected = df[bad].assign(reject_reason=reasons[bad].str.rstrip("; "))
    valid = df[~bad].copy()
    for col, (dtype, _) in SCHEMA.items():
        valid[col] = valid[col].astype(dtype)
    return valid.reset_index(drop=True), rejected.reset_index(drop=True)


def write_report(valid, rejected, path: Path) -> None:
    lines = ["# Data Validation Report", "",
             f"- Raw rows: **{stats['rows_raw']}**",
             f"- Exact duplicates removed: **{stats['exact_duplicates_removed']}**",
             f"- Duplicate business keys (book_id) removed: **{stats['key_duplicates_removed']}**",
             f"- Rejected (failed schema validation): **{len(rejected)}**",
             f"- Clean rows delivered: **{len(valid)}**",
             f"- Retention: **{len(valid) / stats['rows_raw']:.1%}**", "",
             "## Nulls per column (raw, incl. blank strings)", ""]
    lines += [f"- {c}: {n}" for c, n in stats["nulls_raw"].items()] or ["- none"]
    lines += ["", "## Nulls per column after normalising 'N/A', 'null', 'unknown' etc.", ""]
    lines += [f"- {c}: {n}" for c, n in stats["nulls_after_token_normalisation"].items()] or ["- none"]
    lines += ["", "## Schema rule violations", ""]
    lines += [f"- {rule}: {n}" for rule, n in stats["rule_violations"].items()]
    lines += ["", "## Final schema", "", "| column | dtype | nullable |", "|---|---|---|"]
    lines += [f"| {c} | {valid[c].dtype} | {'yes' if SCHEMA[c][1] else 'no'} |" for c in SCHEMA]
    lines += ["", "## Clean data summary", "",
              f"- Price (GBP): min {valid.price_gbp.min():.2f}, mean {valid.price_gbp.mean():.2f}, max {valid.price_gbp.max():.2f}",
              f"- Date range: {valid.scraped_date.min():%Y-%m-%d} to {valid.scraped_date.max():%Y-%m-%d}",
              f"- Categories: {valid.category.nunique()}", "",
              "_Currency conversion uses fixed rates: 1 USD = 0.787 GBP, 1 EUR = 0.855 GBP._"]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", type=Path, default=Path("data/raw_books.csv"))
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(args.out / "cleaning.log", mode="w")])

    df = pd.read_csv(args.input, dtype=str, keep_default_na=False)
    valid, rejected = validate(clean(df))
    valid.to_csv(args.out / "clean_books.csv", index=False)
    rejected.to_csv(args.out / "rejected_rows.csv", index=False)
    write_report(valid, rejected, args.out / "validation_report.md")
    log.info("Done: %d clean, %d rejected", len(valid), len(rejected))


if __name__ == "__main__":
    main()
