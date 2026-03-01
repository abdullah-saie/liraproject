"""
scraper.py — fetches all pairs from sp-today.com
Tracks: FX currencies, crypto (via CoinGecko free API), gold, fuel
"""

import re
import httpx
from bs4 import BeautifulSoup
from database import save_rate

BASE     = "https://sp-today.com"
COINGECKO = "https://api.coingecko.com/api/v3"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://sp-today.com/en",
}

# All currency slugs on sp-today → symbol
FX_CURRENCIES = {
    "us-dollar":       "USD",
    "euro":            "EUR",
    "turkish-lira":    "TRY",
    "saudi-riyal":     "SAR",
    "uae-dirham":      "AED",
    "egyptian-pound":  "EGP",
    "british-pound":   "GBP",
    "kuwaiti-dinar":   "KWD",
    "jordanian-dinar": "JOD",
    "qatari-riyal":    "QAR",
    "bahraini-dinar":  "BHD",
    "iraqi-dinar":     "IQD",
}

# Crypto IDs on CoinGecko → our symbol
CRYPTO_IDS = {
    "bitcoin":  "BTC",
    "ethereum": "ETH",
    "binancecoin": "BNB",
    "tether":   "USDT",
}

# Gold karat slugs on sp-today
GOLD_SLUGS = {
    "24k": "XAU_24K",
    "21k": "XAU_21K",
    "18k": "XAU_18K",
}

# Fuel slugs
FUEL_SLUGS = {
    "benzin": "FUEL_GAS",
    "diesel": "FUEL_DSL",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _num(text: str) -> float | None:
    try:
        return float(str(text).replace(",", "").strip())
    except (ValueError, AttributeError):
        return None

def _extract_buy_sell(soup: BeautifulSoup) -> tuple[float | None, float | None]:
    """Extract buy/sell from an sp-today currency page."""
    text    = soup.get_text(separator=" ")
    numbers = re.findall(r"[\d,]{3,}", text)
    cleaned = sorted(set(
        n for raw in numbers
        if (n := _num(raw)) and n > 100
    ))
    if len(cleaned) >= 2:
        return cleaned[0], cleaned[1]
    return None, None


# ── FX Scraper ───────────────────────────────────────────────────────────────

def scrape_fx(client: httpx.Client) -> list[dict]:
    results = []
    for slug, symbol in FX_CURRENCIES.items():
        try:
            r = client.get(f"{BASE}/en/currency/{slug}", headers=HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            buy, sell = _extract_buy_sell(soup)
            if buy and sell:
                results.append({"currency": symbol, "buy": buy, "sell": sell, "source": "sp-today"})
                print(f"  ✅ FX  {symbol}: {buy} / {sell}")
            else:
                print(f"  ⚠️  FX  {symbol}: could not parse")
        except Exception as e:
            print(f"  ❌ FX  {symbol}: {e}")
    return results


# ── Gold Scraper ─────────────────────────────────────────────────────────────

def scrape_gold(client: httpx.Client) -> list[dict]:
    results = []
    for slug, symbol in GOLD_SLUGS.items():
        try:
            r = client.get(f"{BASE}/en/gold/{slug}/syp", headers=HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            buy, sell = _extract_buy_sell(soup)
            if buy and sell:
                # Gold prices are in SYP per gram — values will be in millions range
                results.append({"currency": symbol, "buy": buy, "sell": sell, "source": "sp-today-gold"})
                print(f"  ✅ GOLD {symbol}: {buy} / {sell}")
            else:
                print(f"  ⚠️  GOLD {symbol}: could not parse")
        except Exception as e:
            print(f"  ❌ GOLD {symbol}: {e}")
    return results


# ── Fuel Scraper ─────────────────────────────────────────────────────────────

def scrape_fuel(client: httpx.Client) -> list[dict]:
    results = []
    for slug, symbol in FUEL_SLUGS.items():
        try:
            r = client.get(f"{BASE}/en/energy/{slug}", headers=HEADERS, timeout=12)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            text    = soup.get_text(separator=" ")
            numbers = re.findall(r"[\d,]{3,}", text)
            cleaned = [n for raw in numbers if (n := _num(raw)) and n > 1000]
            if cleaned:
                price = cleaned[0]
                # For fuel, buy == sell (fixed price)
                results.append({"currency": symbol, "buy": price, "sell": price, "source": "sp-today-fuel"})
                print(f"  ✅ FUEL {symbol}: {price}")
            else:
                print(f"  ⚠️  FUEL {symbol}: could not parse")
        except Exception as e:
            print(f"  ❌ FUEL {symbol}: {e}")
    return results


# ── Crypto (CoinGecko free, no key needed) ───────────────────────────────────

def scrape_crypto(client: httpx.Client) -> list[dict]:
    results = []
    try:
        ids = ",".join(CRYPTO_IDS.keys())
        r = client.get(
            f"{COINGECKO}/simple/price",
            params={"ids": ids, "vs_currencies": "usd"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()
        for cg_id, symbol in CRYPTO_IDS.items():
            price_usd = data.get(cg_id, {}).get("usd")
            if price_usd:
                # Store price in USD (not SYP) — frontend converts
                results.append({
                    "currency": symbol,
                    "buy":  float(price_usd),
                    "sell": float(price_usd),
                    "source": "coingecko",
                })
                print(f"  ✅ CRYPTO {symbol}: ${price_usd}")
    except Exception as e:
        print(f"  ❌ Crypto fetch failed: {e}")
    return results


# ── Gold ounce (CoinGecko XAU) ───────────────────────────────────────────────

def scrape_gold_ounce(client: httpx.Client) -> list[dict]:
    try:
        r = client.get(
            f"{COINGECKO}/simple/price",
            params={"ids": "gold", "vs_currencies": "usd"},
            timeout=15,
        )
        # CoinGecko doesn't have gold, use XAU from sp-today ounce page
        r2 = client.get(f"{BASE}/en/gold/ounce", headers=HEADERS, timeout=12)
        r2.raise_for_status()
        soup = BeautifulSoup(r2.text, "html.parser")
        text = soup.get_text(separator=" ")
        # Look for price like $5,278
        matches = re.findall(r"\$[\d,]+\.?\d*", text)
        if matches:
            price = _num(matches[0].replace("$", ""))
            if price:
                print(f"  ✅ XAU ounce: ${price}")
                return [{"currency": "XAU", "buy": price, "sell": price, "source": "sp-today-gold"}]
    except Exception as e:
        print(f"  ❌ Gold ounce: {e}")
    return []


# ── Main ─────────────────────────────────────────────────────────────────────

def scrape_and_save():
    print("🔄 Starting full scrape...")
    all_results = []

    with httpx.Client(follow_redirects=True) as client:
        print("── FX currencies ──")
        all_results += scrape_fx(client)

        print("── Gold (SYP) ──")
        all_results += scrape_gold(client)

        print("── Gold ounce (USD) ──")
        all_results += scrape_gold_ounce(client)

        print("── Fuel ──")
        all_results += scrape_fuel(client)

        print("── Crypto ──")
        all_results += scrape_crypto(client)

    # Save all to DB
    for r in all_results:
        save_rate(r["currency"], r["buy"], r["sell"], r.get("source", "sp-today"))

    print(f"\n✅ Scrape done — {len(all_results)} pairs saved.")
    return all_results


if __name__ == "__main__":
    from database import init_db
    init_db()
    scrape_and_save()
