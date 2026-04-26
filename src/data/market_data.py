"""Market data facade for historical and latest prices."""

from __future__ import annotations

import logging

import pandas as pd

from data.historical_data import HistoricalDataLoader


class MarketDataProvider:
    def __init__(self, logger: logging.Logger | None = None, crypto_exchange: str = "coinbase") -> None:
        self.historical = HistoricalDataLoader(exchange_id=crypto_exchange)
        self.logger = logger or logging.getLogger(__name__)

    def get_history(
        self,
        symbol: str,
        asset_type: str | None,
        timeframe: str,
        limit: int,
        min_rows: int = 50,
    ) -> pd.DataFrame:
        try:
            data = self.historical.load(symbol, asset_type=asset_type, timeframe=timeframe, limit=limit)
            if len(data) < min_rows:
                raise ValueError("insufficient downloaded rows")
            return data
        except Exception as exc:
            self.logger.warning("Falling back to synthetic data for %s: %s", symbol, exc)
            return self.historical.synthetic(symbol=symbol, rows=limit)

    def latest_price(self, symbol: str, asset_type: str | None = None) -> float:
        data = self.get_history(symbol, asset_type=asset_type, timeframe="1h", limit=5, min_rows=1)
        return float(data["close"].iloc[-1])
