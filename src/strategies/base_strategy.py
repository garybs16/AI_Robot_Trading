"""Strategy contracts and signal types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pandas as pd


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT = "EXIT"


@dataclass(frozen=True)
class Signal:
    action: SignalAction
    confidence: float = 1.0
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    name = "base"

    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Return an integer series: 1 buy/long, -1 sell/exit, 0 hold."""

    def generate_signal(self, data: pd.DataFrame) -> Signal:
        signals = self.generate_signals(data)
        value = int(signals.iloc[-1]) if not signals.empty else 0
        if value > 0:
            return Signal(SignalAction.BUY, reason=f"{self.name} buy")
        if value < 0:
            return Signal(SignalAction.SELL, reason=f"{self.name} sell")
        return Signal(SignalAction.HOLD, reason=f"{self.name} hold")

