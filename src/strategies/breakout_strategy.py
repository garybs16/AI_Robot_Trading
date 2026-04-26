"""Range breakout strategy with volume confirmation."""

from __future__ import annotations

import pandas as pd

from strategies.base_strategy import BaseStrategy


class BreakoutStrategy(BaseStrategy):
    name = "breakout"

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        lookback = int(self.params.get("lookback", 20))
        volume_multiplier = float(self.params.get("volume_multiplier", 1.5))
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        close = data["close"].astype(float)
        volume = data["volume"].astype(float)

        resistance = high.rolling(lookback).max().shift(1)
        support = low.rolling(lookback).min().shift(1)
        avg_volume = volume.rolling(lookback).mean().shift(1)
        signals = pd.Series(0, index=data.index, dtype=int)
        signals.loc[(close > resistance) & (volume > avg_volume * volume_multiplier)] = 1
        signals.loc[close < support] = -1
        return signals

