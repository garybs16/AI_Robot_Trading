"""Historical OHLCV loading and normalization."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

import numpy as np
import pandas as pd

AssetKind = Literal["stock", "crypto"]


REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def normalize_ohlcv(data: pd.DataFrame) -> pd.DataFrame:
    if data.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)
    frame = data.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)
    frame.columns = [str(col).strip().lower().replace("_", " ") for col in frame.columns]
    rename = {"adj close": "close"}
    frame = frame.rename(columns=rename)
    if "close" not in frame and "adj" in frame:
        frame["close"] = frame["adj"]
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    for col in missing:
        frame[col] = frame["close"] if col != "volume" and "close" in frame else 0.0
    frame = frame[REQUIRED_COLUMNS].astype(float)
    frame = frame.replace([np.inf, -np.inf], np.nan).ffill().dropna()
    frame.index = pd.to_datetime(frame.index, utc=True)
    return frame


class HistoricalDataLoader:
    """Downloads stock data with yfinance and crypto data with ccxt."""

    def __init__(self, exchange_id: str = "binance") -> None:
        self.exchange_id = exchange_id

    def load(
        self,
        symbol: str,
        asset_type: AssetKind | None = None,
        timeframe: str = "1h",
        limit: int = 500,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        kind = asset_type or ("crypto" if "/" in symbol else "stock")
        if kind == "crypto":
            return self.load_crypto(symbol, timeframe=timeframe, limit=limit)
        return self.load_stock(symbol, timeframe=timeframe, limit=limit, start=start, end=end)

    def load_stock(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 500,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        interval = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}.get(timeframe, "1h")
        period = "730d" if interval in {"1h", "1d"} else "60d"
        data = yf.download(
            symbol,
            start=start,
            end=end,
            period=None if start else period,
            interval=interval,
            auto_adjust=True,
            progress=False,
        )
        return normalize_ohlcv(data).tail(limit)

    def load_crypto(self, symbol: str, timeframe: str = "1h", limit: int = 500) -> pd.DataFrame:
        import ccxt

        exchange = getattr(ccxt, self.exchange_id)({"enableRateLimit": True})
        exchange_symbol = symbol
        if self.exchange_id == "binance" and symbol.endswith("/USD"):
            exchange_symbol = symbol.replace("/USD", "/USDT")
        rows = exchange.fetch_ohlcv(exchange_symbol, timeframe=timeframe, limit=limit)
        data = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        data["timestamp"] = pd.to_datetime(data["timestamp"], unit="ms", utc=True)
        data = data.set_index("timestamp")
        return normalize_ohlcv(data)

    @staticmethod
    def synthetic(symbol: str = "TEST", rows: int = 250, seed: int = 42) -> pd.DataFrame:
        rng = np.random.default_rng(seed)
        returns = rng.normal(0.0005, 0.015, rows)
        close = 100 * np.exp(np.cumsum(returns))
        high = close * (1 + rng.uniform(0.001, 0.01, rows))
        low = close * (1 - rng.uniform(0.001, 0.01, rows))
        open_ = np.r_[close[0], close[:-1]]
        volume = rng.integers(100_000, 1_000_000, rows)
        index = pd.date_range("2024-01-01", periods=rows, freq="h", tz="UTC")
        return pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=index,
        )
