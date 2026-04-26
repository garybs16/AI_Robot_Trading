"""Portfolio position models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Position:
    symbol: str
    quantity: float
    average_price: float

    def market_value(self, price: float) -> float:
        return self.quantity * price

    def unrealized_pnl(self, price: float) -> float:
        return (price - self.average_price) * self.quantity

