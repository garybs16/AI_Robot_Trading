"""Stop loss and take profit helpers."""

from __future__ import annotations


def stop_loss_price(entry_price: float, stop_pct: float, side: str = "long") -> float:
    return entry_price * (1 - stop_pct if side == "long" else 1 + stop_pct)


def take_profit_price(entry_price: float, profit_pct: float, side: str = "long") -> float:
    return entry_price * (1 + profit_pct if side == "long" else 1 - profit_pct)


def trailing_stop(previous_stop: float, latest_price: float, trail_pct: float, side: str = "long") -> float:
    candidate = stop_loss_price(latest_price, trail_pct, side)
    return max(previous_stop, candidate) if side == "long" else min(previous_stop, candidate)

