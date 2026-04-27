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
http://localhost:8501
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

