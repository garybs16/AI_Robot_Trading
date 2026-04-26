"""Coinbase Advanced Trade broker adapter.

The official Coinbase Advanced Trade API supports REST trading and market data.
This adapter reads credentials from environment variables and keeps order
submission disabled unless a reviewed live implementation is added.
"""

from __future__ import annotations

import os
from typing import Any

from brokers.base_broker import (
    AccountInfo,
    AssetType,
    BaseBroker,
    BrokerPosition,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
)


class CoinbaseBroker(BaseBroker):
    name = "coinbase"

    def __init__(
        self,
        api_key_env: str = "COINBASE_API_KEY",
        api_secret_env: str = "COINBASE_API_SECRET",
        key_file_env: str = "COINBASE_KEY_FILE",
        base_url: str = "api-sandbox.coinbase.com",
        sandbox: bool = True,
    ) -> None:
        self.api_key = os.getenv(api_key_env, "")
        self.api_secret = os.getenv(api_secret_env, "")
        self.key_file = os.getenv(key_file_env, "")
        self.base_url = base_url
        self.sandbox = sandbox
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
                self.client = RESTClient(key_file=self.key_file, base_url=self.base_url)
            else:
                self.client = RESTClient(api_key=self.api_key, api_secret=self.api_secret, base_url=self.base_url)
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
        if not self.sandbox and os.getenv("LIVE_TRADING", "false").lower() != "true":
            return OrderResult(
                order_id=self.new_order_id("coinbase"),
                request=order,
                status=OrderStatus.REJECTED,
                message="Coinbase live endpoint refused because LIVE_TRADING is not true",
            )
        if order.asset_type != AssetType.CRYPTO:
            return OrderResult(
                order_id=self.new_order_id("coinbase"),
                request=order,
                status=OrderStatus.REJECTED,
                message="CoinbaseBroker only supports crypto assets",
            )

        client_order_id = str(order.metadata.get("client_order_id", self.new_order_id("cb")))
        product_id = self.normalize_product_id(order.symbol)
        try:
            if order.order_type == OrderType.MARKET:
                if order.side == OrderSide.BUY:
                    data = self._client().market_order_buy(client_order_id, product_id, base_size=str(order.quantity))
                else:
                    data = self._client().market_order_sell(client_order_id, product_id, base_size=str(order.quantity))
            elif order.order_type == OrderType.LIMIT:
                if order.limit_price is None:
                    raise ValueError("limit_price is required for Coinbase limit orders")
                if order.side == OrderSide.BUY:
                    data = self._client().limit_order_gtc_buy(
                        client_order_id, product_id, base_size=str(order.quantity), limit_price=str(order.limit_price)
                    )
                else:
                    data = self._client().limit_order_gtc_sell(
                        client_order_id, product_id, base_size=str(order.quantity), limit_price=str(order.limit_price)
                    )
            else:
                return OrderResult(
                    order_id=client_order_id,
                    request=order,
                    status=OrderStatus.REJECTED,
                    message="Coinbase stop orders are not wired in this adapter yet",
                )
        except Exception as exc:
            return OrderResult(
                order_id=client_order_id,
                request=order,
                status=OrderStatus.REJECTED,
                message=f"Coinbase order rejected: {exc}",
            )

        response = self._as_dict(data)
        success = bool(response.get("success", False))
        order_id = str(response.get("order_id") or response.get("success_response", {}).get("order_id") or client_order_id)
        return OrderResult(
            order_id=order_id,
            request=order,
            status=OrderStatus.NEW if success else OrderStatus.REJECTED,
            message=f"submitted to Coinbase {'sandbox' if self.sandbox else 'live'}" if success else str(response),
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        try:
            accounts_response = self._client().get_accounts()
        except Exception:
            return {}
        data = self._as_dict(accounts_response)
        accounts = data.get("accounts", data if isinstance(data, list) else [])
        positions: dict[str, BrokerPosition] = {}
        for account in accounts:
            account_data = self._as_dict(account)
            currency = account_data.get("currency")
            if currency in {"USD", "USDC"}:
                continue
            available = self._as_dict(account_data.get("available_balance", {}))
            qty = float(available.get("value", 0.0))
            if qty > 0:
                positions[str(currency)] = BrokerPosition(
                    symbol=str(currency),
                    quantity=qty,
                    average_price=0.0,
                    asset_type=AssetType.CRYPTO,
                )
        return positions
