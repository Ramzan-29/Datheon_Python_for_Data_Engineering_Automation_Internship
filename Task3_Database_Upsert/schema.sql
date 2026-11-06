PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS books (
    book_id      TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    price_gbp    REAL NOT NULL CHECK (price_gbp > 0),
    rating       INTEGER CHECK (rating BETWEEN 1 AND 5),
    in_stock     INTEGER CHECK (in_stock IN (0, 1)),
    category_id  INTEGER REFERENCES categories(category_id),
    scraped_date TEXT,
    reviews      INTEGER DEFAULT 0,
    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_books_category ON books(category_id);
CREATE INDEX IF NOT EXISTS idx_books_price    ON books(price_gbp);
