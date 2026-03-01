"""
api.py v2 — with timeframe aggregation (1m,5m,15m,30m,1H,4H,1D,1W,1M)
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import database
import scraper

scheduler = AsyncIOScheduler()

PAIR_META = {
    "USD":      {"name":"US Dollar",       "group":"fx",     "icon":"🇺🇸","unit":"SYP"},
    "EUR":      {"name":"Euro",            "group":"fx",     "icon":"🇪🇺","unit":"SYP"},
    "TRY":      {"name":"Turkish Lira",    "group":"fx",     "icon":"🇹🇷","unit":"SYP"},
    "SAR":      {"name":"Saudi Riyal",     "group":"fx",     "icon":"🇸🇦","unit":"SYP"},
    "AED":      {"name":"UAE Dirham",      "group":"fx",     "icon":"🇦🇪","unit":"SYP"},
    "EGP":      {"name":"Egyptian Pound",  "group":"fx",     "icon":"🇪🇬","unit":"SYP"},
    "GBP":      {"name":"British Pound",   "group":"fx",     "icon":"🇬🇧","unit":"SYP"},
    "KWD":      {"name":"Kuwaiti Dinar",   "group":"fx",     "icon":"🇰🇼","unit":"SYP"},
    "JOD":      {"name":"Jordanian Dinar", "group":"fx",     "icon":"🇯🇴","unit":"SYP"},
    "QAR":      {"name":"Qatari Riyal",    "group":"fx",     "icon":"🇶🇦","unit":"SYP"},
    "BHD":      {"name":"Bahraini Dinar",  "group":"fx",     "icon":"🇧🇭","unit":"SYP"},
    "IQD":      {"name":"Iraqi Dinar",     "group":"fx",     "icon":"🇮🇶","unit":"SYP"},
    "BTC":      {"name":"Bitcoin",         "group":"crypto", "icon":"₿",  "unit":"USD"},
    "ETH":      {"name":"Ethereum",        "group":"crypto", "icon":"Ξ",  "unit":"USD"},
    "BNB":      {"name":"BNB",             "group":"crypto", "icon":"⬡",  "unit":"USD"},
    "USDT":     {"name":"Tether",          "group":"crypto", "icon":"₮",  "unit":"USD"},
    "XAU":      {"name":"Gold Ounce",      "group":"gold",   "icon":"🥇", "unit":"USD"},
    "XAU_24K":  {"name":"Gold 24K/g",      "group":"gold",   "icon":"🥇", "unit":"SYP"},
    "XAU_21K":  {"name":"Gold 21K/g",      "group":"gold",   "icon":"🥇", "unit":"SYP"},
    "XAU_18K":  {"name":"Gold 18K/g",      "group":"gold",   "icon":"🥇", "unit":"SYP"},
    "FUEL_GAS": {"name":"Gasoline",        "group":"fuel",   "icon":"⛽", "unit":"SYP"},
    "FUEL_DSL": {"name":"Diesel",          "group":"fuel",   "icon":"🛢️", "unit":"SYP"},
}

# Timeframe → seconds per candle
TF_SECONDS = {
    "1m":  60,
    "5m":  300,
    "15m": 900,
    "30m": 1800,
    "1H":  3600,
    "4H":  14400,
    "1D":  86400,
    "1W":  604800,
    "1M":  2592000,
}

def aggregate_candles(rows: list[dict], tf: str) -> list[dict]:
    """
    Aggregate raw tick rows into OHLC candles for the given timeframe.
    Each row has: timestamp (ISO str), buy (float), sell (float)
    Returns: [{time (unix), open, high, low, close, buy, sell}]
    """
    step = TF_SECONDS.get(tf, 3600)
    buckets: dict[int, list] = {}

    for row in rows:
        ts   = int(datetime.fromisoformat(row["timestamp"]).replace(tzinfo=timezone.utc).timestamp())
        slot = (ts // step) * step   # floor to candle boundary
        if slot not in buckets:
            buckets[slot] = []
        mid = (row["buy"] + row["sell"]) / 2
        buckets[slot].append({"mid": mid, "buy": row["buy"], "sell": row["sell"]})

    candles = []
    for slot in sorted(buckets.keys()):
        pts   = buckets[slot]
        mids  = [p["mid"]  for p in pts]
        buys  = [p["buy"]  for p in pts]
        sells = [p["sell"] for p in pts]
        candles.append({
            "time":  slot,
            "open":  buys[0],
            "high":  max(sells),
            "low":   min(buys),
            "close": sells[-1],
            "buy":   buys[-1],
            "sell":  sells[-1],
        })

    return candles


def scheduled_scrape():
    try:
        scraper.scrape_and_save()
    except Exception as e:
        print(f"Scheduler error: {e}")


@asynccontextmanager
async def lifespan(app):
    database.init_db()
    scraper.scrape_and_save()
    scheduler.add_job(scheduled_scrape, "interval", minutes=5)
    scheduler.start()
    print("🚀 Running — scraping every 5 min")
    yield
    scheduler.shutdown()


app = FastAPI(title="SYP Markets API", version="3.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/pairs")
def list_pairs():
    available = database.get_available_currencies()
    result = []
    for sym in available:
        meta   = PAIR_META.get(sym, {"name":sym,"group":"other","icon":"💱","unit":"SYP"})
        latest = database.get_latest(sym)
        result.append({
            "symbol": sym,
            "name":   meta["name"],
            "group":  meta["group"],
            "icon":   meta["icon"],
            "unit":   meta["unit"],
            "buy":    latest["buy"]  if latest else None,
            "sell":   latest["sell"] if latest else None,
        })
    group_order = {"fx":0,"crypto":1,"gold":2,"fuel":3,"other":4}
    result.sort(key=lambda x: (group_order.get(x["group"],99), x["symbol"]))
    return result


@app.get("/api/latest")
def latest_rate(currency: str = Query(default="USD")):
    row = database.get_latest(currency.upper())
    if not row:
        raise HTTPException(404, f"No data for {currency}")
    return row


@app.get("/api/history")
def history(
    currency: str = Query(default="USD"),
    tf:       str = Query(default="1H", description="Timeframe: 1m,5m,15m,30m,1H,4H,1D,1W,1M"),
    limit:    int = Query(default=5000, ge=1, le=50000),
):
    """
    Returns OHLC candles aggregated to the requested timeframe.
    Always returns REAL data only — no padding or fake data.
    """
    currency = currency.upper()
    if tf not in TF_SECONDS:
        raise HTTPException(400, f"Invalid timeframe. Use: {list(TF_SECONDS.keys())}")

    rows = database.get_history(currency, limit=limit)
    if not rows:
        raise HTTPException(404, f"No data for {currency}. Backend is still collecting — check back in a few minutes.")

    candles = aggregate_candles(rows, tf)
    return {
        "currency":  currency,
        "tf":        tf,
        "count":     len(candles),
        "real_ticks": len(rows),
        "data":      candles,
    }


@app.post("/api/scrape")
def manual_scrape():
    try:
        scraper.scrape_and_save()
        return {"status": "ok", "pairs": database.get_available_currencies()}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/health")
def health():
    return {
        "status": "ok",
        "pairs":  database.get_available_currencies(),
        "time":   datetime.utcnow().isoformat(),
    }
