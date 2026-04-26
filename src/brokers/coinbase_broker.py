"""Coinbase Advanced Trade broker adapter.

The official Coinbase Advanced Trade API supports REST trading and market data.
This adapter reads credentials from environment variables and keeps order
submission disabled unless a reviewed live implementation is added.
"""

from __future__ import annotations

import os
from typing import Any

from brokers.base_broker import AccountInfo, BaseBroker, BrokerPosition, OrderRequest, OrderResult, OrderStatus


class CoinbaseBroker(BaseBroker):
    name = "coinbase"

    def __init__(
        self,
        api_key_env: str = "COINBASE_API_KEY",
        api_secret_env: str = "COINBASE_API_SECRET",
        key_file_env: str = "COINBASE_KEY_FILE",
    ) -> None:
        self.api_key = os.getenv(api_key_env, "")
        self.api_secret = os.getenv(api_secret_env, "")
        self.key_file = os.getenv(key_file_env, "")
        self.client = None

    @staticmethod
    def normalize_product_id(symbol: str) -> str:
        return symbol.replace("/", "-").upper()

    def validate_credentials(self) -> bool:
        return bool((self.api_key and self.api_secret) or self.key_file)

    def _client(self):
        if not self.validate_credentials():
            raise PermissionError("Missing Coinbase API credentials")
        if self.client is None:
            try:
                from coinbase.rest import RESTClient
            except ImportError as exc:
                raise ImportError("Install coinbase-advanced-py to use CoinbaseBroker") from exc
            if self.key_file:
                self.client = RESTClient(key_file=self.key_file)
            else:
                self.client = RESTClient(api_key=self.api_key, api_secret=self.api_secret)
        return self.client

    @staticmethod
    def _as_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if hasattr(value, "to_dict"):
            return value.to_dict()
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return {}

    def get_account(self) -> AccountInfo:
        accounts_response = self._client().get_accounts()
        data = self._as_dict(accounts_response)
        accounts = data.get("accounts", data if isinstance(data, list) else [])
        cash = 0.0
        for account in accounts:
            account_data = self._as_dict(account)
            currency = account_data.get("currency")
            available = self._as_dict(account_data.get("available_balance", {}))
            if currency in {"USD", "USDC"}:
                cash += float(available.get("value", 0.0))
        return AccountInfo(cash=cash, equity=cash, buying_power=cash, currency="USD")

    def get_latest_price(self, symbol: str) -> float:
        product = self._client().get_product(self.normalize_product_id(symbol))
        data = self._as_dict(product)
        price = data.get("price") or data.get("mid_market_price")
        if price is None:
            raise ValueError(f"Coinbase product response did not include a price for {symbol}")
        return float(price)

    def submit_order(self, order: OrderRequest) -> OrderResult:
        return OrderResult(
            order_id=self.new_order_id("coinbase"),
            request=order,
            status=OrderStatus.REJECTED,
            message="Coinbase live order submission is disabled until explicitly implemented and reviewed",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        return {}
