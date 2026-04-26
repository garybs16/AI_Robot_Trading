"""Options strategy framework for defined-risk structures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

from strategies.base_strategy import BaseStrategy


OptionType = Literal["call", "put"]


@dataclass(frozen=True)
class OptionContract:
    underlying: str
    expiration: date
    strike: float
    option_type: OptionType
    premium: float


@dataclass(frozen=True)
class OptionRiskProfile:
    max_loss: float
    max_gain: float | None
    breakeven: float
    defined_risk: bool


class OptionsStrategy(BaseStrategy):
    name = "options"

    @staticmethod
    def long_call(contract: OptionContract) -> OptionRiskProfile:
        return OptionRiskProfile(
            max_loss=contract.premium * 100,
            max_gain=None,
            breakeven=contract.strike + contract.premium,
            defined_risk=True,
        )

    @staticmethod
    def long_put(contract: OptionContract) -> OptionRiskProfile:
        return OptionRiskProfile(
            max_loss=contract.premium * 100,
            max_gain=max((contract.strike - contract.premium) * 100, 0.0),
            breakeven=contract.strike - contract.premium,
            defined_risk=True,
        )

    @staticmethod
    def vertical_spread(
        long_leg: OptionContract,
        short_leg: OptionContract,
        net_debit: float,
    ) -> OptionRiskProfile:
        width = abs(short_leg.strike - long_leg.strike)
        max_loss = max(net_debit * 100, 0.0)
        max_gain = max((width - net_debit) * 100, 0.0)
        if long_leg.option_type == "call":
            breakeven = long_leg.strike + net_debit
        else:
            breakeven = long_leg.strike - net_debit
        return OptionRiskProfile(max_loss=max_loss, max_gain=max_gain, breakeven=breakeven, defined_risk=True)

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        return pd.Series(0, index=data.index, dtype=int)

