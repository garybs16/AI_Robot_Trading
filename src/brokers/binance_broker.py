"""Binance crypto broker adapter using ccxt when credentials are configured."""

from __future__ import annotations

import os

from brokers.base_broker import AccountInfo, AssetType, BaseBroker, BrokerPosition, OrderRequest, OrderResult, OrderStatus


class BinanceBroker(BaseBroker):
    name = "binance"

    def __init__(self, sandbox: bool = True) -> None:
        self.sandbox = sandbox
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY", "")
        self.exchange = None

    def _client(self):
        if self.exchange is None:
            import ccxt

            self.exchange = ccxt.binance(
                {"apiKey": self.api_key, "secret": self.secret_key, "enableRateLimit": True}
            )
            if self.sandbox and hasattr(self.exchange, "set_sandbox_mode"):
                self.exchange.set_sandbox_mode(True)
        return self.exchange

    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def get_account(self) -> AccountInfo:
        if not self.validate_credentials():
            raise PermissionError("Missing Binance credentials")
        balance = self._client().fetch_balance()
        usd = balance.get("USDT", {}) or balance.get("USD", {})
        cash = float(usd.get("free", 0.0))
        total = float(usd.get("total", cash))
        return AccountInfo(cash=cash, equity=total, buying_power=cash, currency="USD")

    def get_latest_price(self, symbol: str) -> float:
        ticker = self._client().fetch_ticker(symbol.replace("/", "/"))
        return float(ticker["last"])

    def submit_order(self, order: OrderRequest) -> OrderResult:
        return OrderResult(
            order_id=self.new_order_id("binance"),
            request=order,
            status=OrderStatus.REJECTED,
            message="Binance live order submission placeholder is disabled by default",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        return {}

