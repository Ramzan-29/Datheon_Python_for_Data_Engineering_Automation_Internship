"""Autonomous web scraper: paginated catalogue -> clean CSV/JSON.

Target: https://books.toscrape.com (a sandbox site built for scraping practice).
Usage:
    python scraper.py                 # all pages, basic fields
    python scraper.py --details       # also visit each book page (category, UPC)
    python scraper.py --max-pages 5   # quick test run
"""
import argparse
import csv
import json
import logging
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://books.toscrape.com/catalogue/page-1.html"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("scraper")


def make_session() -> requests.Session:
    """Session with user-agent header and automatic retry/backoff."""
    session = requests.Session()
    session.headers.update(HEADERS)
    retry = Retry(total=4, backoff_factor=1.0,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def fetch(session: requests.Session, url: str) -> BeautifulSoup | None:
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = "utf-8"  # avoids "Â£" mojibake
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return None


def parse_listing(soup: BeautifulSoup, page_url: str) -> list[dict]:
    records = []
    for card in soup.select("article.product_pod"):
        try:
            link = card.h3.a
            price_text = card.select_one("p.price_color").get_text(strip=True)
            rating_word = card.select_one("p.star-rating")["class"][1]
            records.append({
                "title": link["title"],
                "price_gbp": float(price_text.replace("£", "").replace("Â", "")),
                "rating": RATINGS.get(rating_word),
                "availability": card.select_one("p.availability").get_text(strip=True),
                "url": urljoin(page_url, link["href"]),
            })
        except (AttributeError, KeyError, ValueError, TypeError) as exc:
            log.warning("Skipping malformed card on %s: %s", page_url, exc)
    return records


def parse_details(soup: BeautifulSoup) -> dict:
    crumbs = soup.select("ul.breadcrumb li a")
    table = {r.th.get_text(strip=True): r.td.get_text(strip=True)
             for r in soup.select("table.table-striped tr")}
    return {
        "category": crumbs[2].get_text(strip=True) if len(crumbs) > 2 else None,
        "upc": table.get("UPC"),
        "reviews": int(table.get("Number of reviews", 0) or 0),
    }


def scrape(max_pages: int | None, details: bool, delay: float) -> list[dict]:
    session = make_session()
    url, page, records = BASE_URL, 0, []
    while url and (max_pages is None or page < max_pages):
        soup = fetch(session, url)
        if soup is None:
            break
        page += 1
        items = parse_listing(soup, url)
        if details:
            for item in items:
                detail_soup = fetch(session, item["url"])
                if detail_soup:
                    item.update(parse_details(detail_soup))
                time.sleep(delay / 2)
        records.extend(items)
        log.info("Page %d: %d items (total %d)", page, len(items), len(records))
        nxt = soup.select_one("li.next a")
        url = urljoin(url, nxt["href"]) if nxt else None
        time.sleep(delay)  # be polite
    return records


def save(records: list[dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not records:
        log.warning("No records to save.")
        return
    fields = list({k: None for r in records for k in r})
    with open(out_dir / "books.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    with open(out_dir / "books.json", "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    log.info("Saved %d records to %s", len(records), out_dir)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--details", action="store_true")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--out", type=Path, default=Path("data"))
    args = ap.parse_args()
    save(scrape(args.max_pages, args.details, args.delay), args.out)


if __name__ == "__main__":
    main()
