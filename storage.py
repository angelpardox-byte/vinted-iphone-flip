"""
Persistencia simple en SQLite:
  - Guarda cada anuncio visto (para no notificar duplicados)
  - Guarda histórico de precios por grupo (modelo+capacidad) para calcular medias
"""
import sqlite3
import os
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            model TEXT,
            storage TEXT,
            price REAL,
            title TEXT,
            url TEXT,
            notified INTEGER DEFAULT 0,
            seen_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_model_storage ON listings(model, storage)
    """)
    conn.commit()
    return conn


def already_seen(conn, listing_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM listings WHERE id = ?", (str(listing_id),))
    return cur.fetchone() is not None


def save_listing(conn, listing_id, model, storage, price, title, url, notified=False):
    conn.execute(
        "INSERT OR IGNORE INTO listings (id, model, storage, price, title, url, notified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(listing_id), model, storage, price, title, url, int(notified)),
    )
    conn.commit()


def get_average_price(conn, model: str, storage: str):
    cur = conn.execute(
        "SELECT AVG(price), COUNT(*) FROM listings WHERE model = ? AND storage = ?",
        (model, storage),
    )
    avg, count = cur.fetchone()
    return (avg or 0.0), (count or 0)


def mark_notified(conn, listing_id: str):
    conn.execute("UPDATE listings SET notified = 1 WHERE id = ?", (str(listing_id),))
    conn.commit()
