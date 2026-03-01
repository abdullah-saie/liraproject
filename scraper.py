"""
scraper.py
----------
Fetches USD/SYP (and optionally other currencies) from sp-today.com.

Strategy
--------
1. Try the unofficial JSON endpoint that the site's own JS uses.
2. Fall back to HTML parsing with BeautifulSoup if the JSON fails.
"""

import httpx
from bs4 import BeautifulSoup
from database import save_rate

BASE_URL = "https://sp-today.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://sp-today.com/en",
}

# Currencies to track  (slug on sp-today → our symbol)
CURRENCIES = {
    "us-dollar": "USD",
    "euro": "EUR",
    "turkish-lira": "TRY",
}


# ── Helper ──────────────────────────────────────────────────────────────────

def _parse_number(text: str) -> float | None:
    """Clean and convert a price string like '11,780' → 11780.0"""
    try:
        return float(text.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


# ── Strategy 1: JSON endpoint ────────────────────────────────────────────────

def fetch_via_json(client: httpx.Client) -> list[dict]:
    """
    The site fetches rates from /api/currencies (undocumented).
    Returns a list of dicts: [{currency, buy, sell}, ...]
    """
    try:
        resp = client.get(f"{BASE_URL}/api/currencies", headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data:
            slug = item.get("slug", "")
            symbol = CURRENCIES.get(slug)
            if not symbol:
                continue
            buy = _parse_number(str(item.get("buy", "")))
            sell = _parse_number(str(item.get("sell", "")))
            if buy and sell:
                results.append({"currency": symbol, "buy": buy, "sell": sell})
        return results

    except Exception as e:
        print(f"⚠️  JSON endpoint failed: {e}")
        return []


# ── Strategy 2: HTML scraping ────────────────────────────────────────────────

def fetch_via_html(client: httpx.Client, slug: str, symbol: str) -> dict | None:
    """Scrape a single currency page for buy/sell prices."""
    url = f"{BASE_URL}/en/currency/{slug}"
    try:
        resp = client.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # The page shows something like: "11,780 - 11,850 SYP  Buy - Sell"
        # Look for elements containing both buy and sell numbers.
        text = soup.get_text(separator=" ")

        # Quick regex fallback
        import re
        numbers = re.findall(r"[\d,]{4,}", text)
        cleaned = [_parse_number(n) for n in numbers if _parse_number(n) and _parse_number(n) > 1000]

        if len(cleaned) >= 2:
            buy, sell = sorted(cleaned[:2])
            return {"currency": symbol, "buy": buy, "sell": sell}

    except Exception as e:
        print(f"⚠️  HTML scrape failed for {slug}: {e}")
    return None


# ── Main entry point ─────────────────────────────────────────────────────────

def scrape_and_save():
    """Fetch all tracked currencies and persist to DB."""
    print("🔄 Starting scrape...")

    with httpx.Client(follow_redirects=True) as client:
        # Try JSON first (faster, one request)
        results = fetch_via_json(client)

        if not results:
            print("↩️  Falling back to HTML scraping...")
            results = []
            for slug, symbol in CURRENCIES.items():
                r = fetch_via_html(client, slug, symbol)
                if r:
                    results.append(r)

        # Persist
        for r in results:
            save_rate(r["currency"], r["buy"], r["sell"])
            print(f"  ✅ Saved {r['currency']}: buy={r['buy']}, sell={r['sell']}")

    if not results:
        print("❌ No data fetched.")
    else:
        print(f"✅ Scrape done — {len(results)} currencies saved.")


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_and_save()
