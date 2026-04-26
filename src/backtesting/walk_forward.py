"""Walk-forward evaluation helper."""

from __future__ import annotations

import pandas as pd

from backtesting.backtest_engine import BacktestEngine, BacktestResult
from strategies.base_strategy import BaseStrategy


def walk_forward_backtest(
    data: pd.DataFrame,
    strategy: BaseStrategy,
    train_size: int,
    test_size: int,
    engine: BacktestEngine,
) -> list[BacktestResult]:
    results: list[BacktestResult] = []
    start = 0
    while start + train_size + test_size <= len(data):
        test = data.iloc[start + train_size : start + train_size + test_size]
        results.append(engine.run(test, strategy))
        start += test_size
    return results

