"""Simple slippage model."""

from __future__ import annotations


class SlippageModel:
    def __init__(self, base_rate: float = 0.0005) -> None:
        self.base_rate = base_rate

    def estimate(self, price: float, quantity: float, average_volume: float | None = None) -> float:
        if average_volume and average_volume > 0:
            participation = min(quantity / average_volume, 1.0)
            return self.base_rate + participation * 0.01
        return self.base_rate

    def apply(self, price: float, side: str, quantity: float, average_volume: float | None = None) -> float:
        rate = self.estimate(price, quantity, average_volume)
        return price * (1 + rate if side.lower() == "buy" else 1 - rate)

