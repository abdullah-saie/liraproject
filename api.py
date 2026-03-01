"""
api.py
------
FastAPI backend — exposes exchange rate data to the frontend.

Endpoints
---------
GET /api/latest?currency=USD          → latest rate
GET /api/history?currency=USD&limit=500  → historical rates for charting
GET /api/history?currency=USD&start=2024-01-01&end=2024-12-31
GET /api/currencies                   → list of tracked currencies
POST /api/scrape                      → manually trigger a scrape (dev use)
"""

from contextlib import asynccontextmanager
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import database
import scraper

# ── Scheduler (runs every 5 minutes) ────────────────────────────────────────

scheduler = AsyncIOScheduler()


def scheduled_scrape():
    try:
        scraper.scrape_and_save()
    except Exception as e:
        print(f"Scheduler scrape error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    database.init_db()
    scraper.scrape_and_save()          # Fetch once immediately on boot
    scheduler.add_job(scheduled_scrape, "interval", minutes=5)
    scheduler.start()
    print("🚀 Scheduler started — fetching every 5 minutes")
    yield
    # Shutdown
    scheduler.shutdown()


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="SYP Exchange Rate API",
    description="Live & historical USD/SYP rates scraped from sp-today.com",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the React frontend (localhost:3000) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Restrict to your domain in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/currencies")
def list_currencies():
    """Return the list of currencies this API tracks."""
    return {
        "currencies": [
            {"symbol": "USD", "name": "US Dollar"},
            {"symbol": "EUR", "name": "Euro"},
            {"symbol": "TRY", "name": "Turkish Lira"},
        ]
    }


@app.get("/api/latest")
def latest_rate(currency: str = Query(default="USD", description="Currency symbol, e.g. USD")):
    """Return the most recently scraped rate for a currency."""
    currency = currency.upper()
    row = database.get_latest(currency)
    if not row:
        raise HTTPException(status_code=404, detail=f"No data found for {currency}")
    return row


@app.get("/api/history")
def history(
    currency: str = Query(default="USD"),
    limit: int = Query(default=500, ge=1, le=5000),
    start: str | None = Query(default=None, description="ISO date, e.g. 2024-01-01"),
    end: str | None = Query(default=None, description="ISO date, e.g. 2024-12-31"),
):
    """
    Return historical rates suitable for a candlestick / line chart.
    Each row: { timestamp, buy, sell }
    """
    currency = currency.upper()

    if start and end:
        rows = database.get_history_range(currency, start, end)
    else:
        rows = database.get_history(currency, limit)

    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for {currency}")

    # Convert to lightweight-charts format: { time, open, high, low, close }
    # Since we only have buy/sell, we model: open=buy, close=sell, high=sell, low=buy
    chart_data = []
    for r in rows:
        # lightweight-charts expects UNIX timestamp (seconds)
        ts = int(datetime.fromisoformat(r["timestamp"]).timestamp())
        chart_data.append({
            "time": ts,
            "open":  r["buy"],
            "high":  r["sell"],
            "low":   r["buy"],
            "close": r["sell"],
            "buy":   r["buy"],
            "sell":  r["sell"],
        })

    return {"currency": currency, "count": len(chart_data), "data": chart_data}


@app.post("/api/scrape")
def manual_scrape():
    """Manually trigger a scrape (useful for development)."""
    try:
        scraper.scrape_and_save()
        latest = database.get_latest("USD")
        return {"status": "ok", "latest_usd": latest}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}
