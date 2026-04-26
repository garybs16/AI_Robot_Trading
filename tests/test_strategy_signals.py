import pandas as pd

from strategies.momentum_strategy import MomentumStrategy


def test_momentum_strategy_emits_crossover_signal():
    index = pd.date_range("2024-01-01", periods=12, freq="D", tz="UTC")
    close = pd.Series([10, 10, 10, 10, 10, 11, 12, 13, 14, 15, 16, 17], index=index, dtype=float)
    data = pd.DataFrame({"close": close, "open": close, "high": close, "low": close, "volume": 1000})
    signals = MomentumStrategy({"short_window": 2, "long_window": 4, "min_periods": 4}).generate_signals(data)
    assert (signals == 1).any()

