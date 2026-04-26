import pandas as pd

from backtesting.backtest_engine import BacktestEngine
from strategies.base_strategy import BaseStrategy


class BuyThenSellStrategy(BaseStrategy):
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        signals = pd.Series(0, index=data.index)
        signals.iloc[1] = 1
        signals.iloc[-2] = -1
        return signals


def test_backtest_engine_generates_metrics_and_trades():
    index = pd.date_range("2024-01-01", periods=20, freq="D", tz="UTC")
    close = pd.Series(range(100, 120), index=index, dtype=float)
    data = pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1000},
        index=index,
    )
    result = BacktestEngine(starting_cash=100_000, fee_rate=0, slippage_rate=0).run(data, BuyThenSellStrategy())
    assert result.metrics["number_of_trades"] == 2
    assert result.metrics["total_return"] > 0
    assert not result.equity_curve.empty

