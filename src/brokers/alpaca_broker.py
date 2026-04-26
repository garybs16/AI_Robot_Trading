"""Alpaca broker adapter with safe placeholder behavior."""

from __future__ import annotations

import os

import requests

from brokers.base_broker import AccountInfo, BaseBroker, BrokerPosition, OrderRequest, OrderResult, OrderStatus


class AlpacaBroker(BaseBroker):
    """Minimal Alpaca adapter.

    Order submission is intentionally not implemented here; production live trading
    should use Alpaca's official SDK with additional account and permission checks.
    """

    name = "alpaca"

    def __init__(self, base_url: str | None = None) -> None:
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        self.base_url = base_url or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def _headers(self) -> dict[str, str]:
        return {"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key}

    def get_account(self) -> AccountInfo:
        if not self.validate_credentials():
            raise PermissionError("Missing Alpaca credentials")
        response = requests.get(f"{self.base_url}/v2/account", headers=self._headers(), timeout=10)
        response.raise_for_status()
        data = response.json()
        return AccountInfo(
            cash=float(data["cash"]),
            equity=float(data["equity"]),
            buying_power=float(data["buying_power"]),
            currency=data.get("currency", "USD"),
        )

    def get_latest_price(self, symbol: str) -> float:
        raise NotImplementedError("Use MarketDataProvider for Alpaca market data integration")

    def submit_order(self, order: OrderRequest) -> OrderResult:
        return OrderResult(
            order_id=self.new_order_id("alpaca"),
            request=order,
            status=OrderStatus.REJECTED,
            message="Alpaca live order submission placeholder is disabled by default",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        return {}

