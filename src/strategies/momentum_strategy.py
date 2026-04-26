"""Moving-average crossover momentum strategy."""

from __future__ import annotations

import pandas as pd

from strategies.base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        short_window = int(self.params.get("short_window", 20))
        long_window = int(self.params.get("long_window", 50))
        min_periods = int(self.params.get("min_periods", long_window))
        close = data["close"].astype(float)
        short_ma = close.rolling(short_window, min_periods=min(short_window, min_periods)).mean()
        long_ma = close.rolling(long_window, min_periods=min(long_window, min_periods)).mean()
        above = short_ma > long_ma
        previous_above = above.shift(1, fill_value=False)
        cross_up = above & (~previous_above)
        cross_down = (~above) & previous_above
        signals = pd.Series(0, index=data.index, dtype=int)
        signals.loc[cross_up] = 1
        signals.loc[cross_down] = -1
        return signals
