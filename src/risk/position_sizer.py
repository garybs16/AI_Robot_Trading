"""Position sizing methods."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PositionSizer:
    max_position_fraction: float = 0.20
    default_risk_fraction: float = 0.01
    kelly_cap: float = 0.05

    def fixed_dollar(self, dollar_amount: float, price: float) -> float:
        self._validate_price(price)
        return max(dollar_amount, 0.0) / price

    def percent_of_portfolio(self, equity: float, price: float, percent: float | None = None) -> float:
        self._validate_price(price)
        fraction = min(max(percent if percent is not None else self.default_risk_fraction, 0.0), self.max_position_fraction)
        return max(equity, 0.0) * fraction / price

    def risk_based(self, equity: float, entry_price: float, stop_price: float, risk_fraction: float | None = None) -> float:
        self._validate_price(entry_price)
        risk_per_unit = abs(entry_price - stop_price)
        if risk_per_unit <= 0:
            return 0.0
        risk_budget = equity * min(max(risk_fraction if risk_fraction is not None else self.default_risk_fraction, 0.0), 0.05)
        max_notional_qty = equity * self.max_position_fraction / entry_price
        return max(min(risk_budget / risk_per_unit, max_notional_qty), 0.0)

    def volatility_adjusted(self, equity: float, price: float, volatility: float, target_risk: float | None = None) -> float:
        self._validate_price(price)
        if volatility <= 0:
            return self.percent_of_portfolio(equity, price, target_risk)
        risk = min(target_risk if target_risk is not None else self.default_risk_fraction, 0.05)
        notional = equity * risk / volatility
        notional = min(notional, equity * self.max_position_fraction)
        return max(notional / price, 0.0)

    def kelly_fraction(self, win_rate: float, win_loss_ratio: float) -> float:
        if win_loss_ratio <= 0:
            return 0.0
        raw = win_rate - ((1 - win_rate) / win_loss_ratio)
        return min(max(raw * 0.25, 0.0), self.kelly_cap)

    @staticmethod
    def _validate_price(price: float) -> None:
        if price <= 0:
            raise ValueError("price must be positive")

