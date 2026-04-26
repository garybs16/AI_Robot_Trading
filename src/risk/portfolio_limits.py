"""Portfolio-level risk limit checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioLimits:
    max_daily_loss: float = 0.03
    max_drawdown: float = 0.10
    max_open_trades: int = 5

    def daily_loss_ok(self, daily_pnl_fraction: float) -> bool:
        return daily_pnl_fraction > -abs(self.max_daily_loss)

    def drawdown_ok(self, drawdown_fraction: float) -> bool:
        return drawdown_fraction > -abs(self.max_drawdown)

    def open_trades_ok(self, open_trades: int) -> bool:
        return open_trades < self.max_open_trades

