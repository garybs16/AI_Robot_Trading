"""RSI and Bollinger Band mean reversion strategy."""

from __future__ import annotations

import pandas as pd

from strategies.base_strategy import BaseStrategy
from utils.math_utils import bollinger_bands, rsi


class MeanReversionStrategy(BaseStrategy):
    name = "mean_reversion"

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        close = data["close"].astype(float)
        rsi_period = int(self.params.get("rsi_period", 14))
        oversold = float(self.params.get("oversold", 30))
        overbought = float(self.params.get("overbought", 70))
        window = int(self.params.get("bollinger_window", 20))
        std = float(self.params.get("bollinger_std", 2.0))
        rsi_values = rsi(close, rsi_period)
        middle, _, lower = bollinger_bands(close, window, std)
        signals = pd.Series(0, index=data.index, dtype=int)
        signals.loc[(close < lower) & (rsi_values < oversold)] = 1
        signals.loc[(close >= middle) | (rsi_values > overbought)] = -1
        return signals

