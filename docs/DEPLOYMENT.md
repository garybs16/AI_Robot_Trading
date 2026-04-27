# Deployment

## Local Dashboard

```powershell
cd C:\Users\Admin\Documents\Trading_Robot\trading_bot
streamlit run src/dashboard.py
```

## Docker

```powershell
docker compose up --build
```

Open:

```text
Dashboard: http://localhost:8501
API docs:  http://localhost:8000/docs
```

## API Service

```powershell
uvicorn api.app:app --app-dir src --host 127.0.0.1 --port 8000
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

## Environment

Create `.env` from `.env.example` and use paper/sandbox credentials only:

```text
LIVE_TRADING=false
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

Never commit `.env`.
