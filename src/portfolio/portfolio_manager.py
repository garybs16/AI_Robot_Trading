"""Portfolio tracking for simulated trading loops."""

from __future__ import annotations

from brokers.base_broker import BaseBroker


class PortfolioManager:
    def __init__(self, broker: BaseBroker) -> None:
        self.broker = broker
        self.peak_equity = broker.get_account().equity

    def snapshot(self) -> dict[str, float]:
        account = self.broker.get_account()
        self.peak_equity = max(self.peak_equity, account.equity)
        drawdown = account.equity / self.peak_equity - 1 if self.peak_equity else 0.0
        return {
            "cash": account.cash,
            "equity": account.equity,
            "buying_power": account.buying_power,
            "drawdown": drawdown,
        }

