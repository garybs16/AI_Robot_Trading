"""Validation helpers."""

from __future__ import annotations

import re


CRYPTO_PAIR_PATTERN = re.compile(r"^[A-Z0-9]+/[A-Z0-9]+$")
STOCK_PATTERN = re.compile(r"^[A-Z.]{1,10}$")


def infer_asset_type(symbol: str) -> str:
    if CRYPTO_PAIR_PATTERN.match(symbol):
        return "crypto"
    if STOCK_PATTERN.match(symbol):
        return "stock"
    return "option"


def validate_positive_number(value: float, name: str) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")

