import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data/rates.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rates (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            currency  TEXT    NOT NULL DEFAULT 'USD',
            buy       REAL,
            sell      REAL,
            source    TEXT    NOT NULL DEFAULT 'sp-today'
        )
    """)
    # Index for fast range queries (charts)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_rates_currency_time
        ON rates (currency, timestamp)
    """)
    conn.commit()
    conn.close()
    print("✅ Database initialized")


def save_rate(currency: str, buy: float, sell: float, source: str = "sp-today"):
    """Insert a new rate record."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO rates (timestamp, currency, buy, sell, source) VALUES (?, ?, ?, ?, ?)",
        (now, currency, buy, sell, source),
    )
    conn.commit()
    conn.close()


def get_latest(currency: str = "USD"):
    """Return the most recent rate for a currency."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM rates WHERE currency = ? ORDER BY timestamp DESC LIMIT 1",
        (currency,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_history(currency: str = "USD", limit: int = 500):
    """Return historical rates for charting (oldest first)."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT timestamp, buy, sell
        FROM rates
        WHERE currency = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (currency, limit),
    ).fetchall()
    conn.close()
    # Reverse so oldest is first (better for charts)
    return [dict(r) for r in reversed(rows)]


def get_history_range(currency: str, start: str, end: str):
    """Return rates between two ISO timestamps."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT timestamp, buy, sell
        FROM rates
        WHERE currency = ? AND timestamp BETWEEN ? AND ?
        ORDER BY timestamp ASC
        """,
        (currency, start, end),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
