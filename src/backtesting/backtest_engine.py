"""Vector-aware event backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from backtesting.performance_metrics import calculate_metrics
from strategies.base_strategy import BaseStrategy


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: pd.DataFrame
    metrics: dict[str, float]


class BacktestEngine:
    def __init__(
        self,
        starting_cash: float = 100_000.0,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
        allocation_fraction: float = 0.20,
    ) -> None:
        self.starting_cash = float(starting_cash)
        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)
        self.allocation_fraction = float(allocation_fraction)

    def run(self, data: pd.DataFrame, strategy: BaseStrategy) -> BacktestResult:
        if data.empty:
            raise ValueError("backtest data is empty")
        signals = strategy.generate_signals(data).reindex(data.index).fillna(0).astype(int)
        execution_signals = signals.shift(1).fillna(0).astype(int)

        cash = self.starting_cash
        quantity = 0.0
        entry_price = 0.0
        equity_points: list[tuple[pd.Timestamp, float]] = []
        trades: list[dict[str, Any]] = []

        for timestamp, row in data.iterrows():
            price = float(row["close"])
            signal = int(execution_signals.loc[timestamp])
            if signal > 0 and quantity == 0:
                fill = price * (1 + self.slippage_rate)
                notional = cash * self.allocation_fraction
                qty = notional / fill
                fee = notional * self.fee_rate
                if notional + fee <= cash:
                    cash -= notional + fee
                    quantity = qty
                    entry_price = fill
                    trades.append({"timestamp": timestamp, "side": "buy", "price": fill, "quantity": qty, "pnl": 0.0})
            elif signal < 0 and quantity > 0:
                fill = price * (1 - self.slippage_rate)
                notional = quantity * fill
                fee = notional * self.fee_rate
                pnl = (fill - entry_price) * quantity - fee
                cash += notional - fee
                trades.append({"timestamp": timestamp, "side": "sell", "price": fill, "quantity": quantity, "pnl": pnl})
                quantity = 0.0
                entry_price = 0.0
            equity_points.append((timestamp, cash + quantity * price))

        if quantity > 0:
            timestamp = data.index[-1]
            price = float(data["close"].iloc[-1])
            fill = price * (1 - self.slippage_rate)
            notional = quantity * fill
            fee = notional * self.fee_rate
            pnl = (fill - entry_price) * quantity - fee
            cash += notional - fee
            trades.append({"timestamp": timestamp, "side": "sell", "price": fill, "quantity": quantity, "pnl": pnl})
            equity_points[-1] = (timestamp, cash)

        equity_curve = pd.Series({ts: equity for ts, equity in equity_points}, name="equity")
        trades_df = pd.DataFrame(trades)
        metrics = calculate_metrics(equity_curve, trades_df)
        return BacktestResult(equity_curve=equity_curve, trades=trades_df, metrics=metrics)

    @staticmethod
    def export(result: BacktestResult, output_dir: str | Path) -> None:
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        result.equity_curve.to_csv(path / "equity_curve.csv", header=True)
        result.trades.to_csv(path / "trades.csv", index=False)
        pd.DataFrame([result.metrics]).to_csv(path / "metrics.csv", index=False)
        fig, ax = plt.subplots(figsize=(10, 5))
        result.equity_curve.plot(ax=ax, title="Equity Curve")
        ax.set_ylabel("Equity")
        fig.tight_layout()
        fig.savefig(path / "equity_curve.png")
        plt.close(fig)

