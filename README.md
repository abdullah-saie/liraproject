# 🇸🇾 SYP Exchange Rate Tracker — Backend

A lightweight Python backend that scrapes USD/SYP (and EUR, TRY) rates from
**sp-today.com**, stores them in SQLite, and serves them via a FastAPI REST API.

---

## 📁 Project Structure

```
syp-tracker/
├── backend/
│   ├── api.py           ← FastAPI app (main entry point)
│   ├── scraper.py       ← Fetches rates from sp-today.com
│   ├── database.py      ← SQLite helpers
│   └── requirements.txt
└── data/
    └── rates.db         ← Auto-created on first run
```

---

## 🚀 Setup & Run

```bash
# 1. Create a virtual environment
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Run the API server
cd backend
uvicorn api:app --reload --port 8000
```

The server will:
- Create the SQLite database automatically
- Scrape sp-today.com **immediately** on startup
- Then scrape every **5 minutes** in the background

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/currencies` | List tracked currencies |
| GET | `/api/latest?currency=USD` | Latest USD/SYP rate |
| GET | `/api/history?currency=USD&limit=200` | Historical rates |
| GET | `/api/history?currency=USD&start=2024-01-01&end=2024-12-31` | Date range |
| POST | `/api/scrape` | Manually trigger scrape |
| GET | `/health` | Health check |

**Interactive docs:** http://localhost:8000/docs

---

## 📊 History Response Format

Each data point is ready for **lightweight-charts** (TradingView's open-source library):

```json
{
  "currency": "USD",
  "count": 144,
  "data": [
    {
      "time": 1704067200,
      "open": 11780,
      "high": 11850,
      "low":  11780,
      "close": 11850,
      "buy":  11780,
      "sell": 11850
    }
  ]
}
```

---

## ⚙️ Configuration

To change scrape interval or add currencies, edit `scraper.py`:

```python
# Track more currencies
CURRENCIES = {
    "us-dollar":    "USD",
    "euro":         "EUR",
    "turkish-lira": "TRY",
    "saudi-riyal":  "SAR",   # ← add more here
}
```

And in `api.py` change the scheduler interval:
```python
scheduler.add_job(scheduled_scrape, "interval", minutes=5)  # Change to 1 for more frequent
```

---

## 🔌 Connecting the Frontend

Your React/HTML frontend should call:
```
GET http://localhost:8000/api/history?currency=USD&limit=500
```

CORS is enabled for all origins in development. In production, restrict it:
```python
allow_origins=["https://yourdomain.com"]
```
