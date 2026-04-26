"""Broker abstractions shared by live, paper, and placeholder brokers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class AssetType(str, Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    OPTION = "option"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderStatus(str, Enum):
    NEW = "new"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class OrderRequest:
    symbol: str
    side: OrderSide
    quantity: float
    asset_type: AssetType
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    stop_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    order_id: str
    request: OrderRequest
    status: OrderStatus
    filled_quantity: float = 0.0
    average_price: float | None = None
    message: str = ""
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BrokerPosition:
    symbol: str
    quantity: float
    average_price: float
    asset_type: AssetType


@dataclass
class AccountInfo:
    cash: float
    equity: float
    buying_power: float
    currency: str = "USD"


class BaseBroker(ABC):
    """Broker contract used by execution and paper trading."""

    name = "base"

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Return account cash, equity, and buying power."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """Return a latest executable price for a symbol."""

    @abstractmethod
    def submit_order(self, order: OrderRequest) -> OrderResult:
        """Submit an order after risk checks."""

    @abstractmethod
    def get_positions(self) -> dict[str, BrokerPosition]:
        """Return current positions keyed by symbol."""

    def validate_credentials(self) -> bool:
        return False

    @staticmethod
    def new_order_id(prefix: str = "ord") -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

