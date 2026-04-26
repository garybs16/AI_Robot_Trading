"""Backtest performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.math_utils import max_drawdown


def calculate_metrics(equity_curve: pd.Series, trades: pd.DataFrame, periods_per_year: int = 252) -> dict[str, float]:
    if equity_curve.empty:
        return {}
    returns = equity_curve.pct_change().dropna()
    total_return = float(equity_curve.iloc[-1] / equity_curve.iloc[0] - 1)
    years = max(len(equity_curve) / periods_per_year, 1 / periods_per_year)
    cagr = float((1 + total_return) ** (1 / years) - 1) if total_return > -1 else -1.0
    sharpe = float(np.sqrt(periods_per_year) * returns.mean() / returns.std(ddof=0)) if returns.std(ddof=0) else 0.0
    downside = returns[returns < 0]
    sortino = float(np.sqrt(periods_per_year) * returns.mean() / downside.std(ddof=0)) if downside.std(ddof=0) else 0.0

    pnl = trades["pnl"] if not trades.empty and "pnl" in trades else pd.Series(dtype=float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    gross_profit = wins.sum()
    gross_loss = abs(losses.sum())
    return {
        "total_return": total_return,
        "cagr": cagr,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown(equity_curve),
        "win_rate": float(len(wins) / len(pnl)) if len(pnl) else 0.0,
        "profit_factor": float(gross_profit / gross_loss) if gross_loss else float("inf") if gross_profit else 0.0,
        "average_win": float(wins.mean()) if len(wins) else 0.0,
        "average_loss": float(losses.mean()) if len(losses) else 0.0,
        "number_of_trades": float(len(pnl)),
    }

