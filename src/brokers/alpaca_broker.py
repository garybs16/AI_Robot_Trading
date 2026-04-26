"""Alpaca broker adapter for paper trading and guarded live trading."""

from __future__ import annotations

import os
from typing import Any

import requests

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


class AlpacaBroker(BaseBroker):
    """Alpaca Trading API adapter.

    The default base URL is Alpaca's paper API. Live trading must be enabled by
    config guardrails before this class should ever be pointed at a live URL.
    """

    name = "alpaca"

    def __init__(self, base_url: str | None = None, paper: bool = True) -> None:
        self.api_key = os.getenv("ALPACA_API_KEY", "")
        self.secret_key = os.getenv("ALPACA_SECRET_KEY", "")
        default_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.base_url = (base_url or os.getenv("ALPACA_BASE_URL", default_url)).rstrip("/")
        self.paper = "paper-api" in self.base_url

    def validate_credentials(self) -> bool:
        return bool(self.api_key and self.secret_key)

    def _headers(self) -> dict[str, str]:
        return {"APCA-API-KEY-ID": self.api_key, "APCA-API-SECRET-KEY": self.secret_key}

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        if not self.validate_credentials():
            raise PermissionError("Missing Alpaca credentials")
        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=self._headers(),
            timeout=15,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def get_account(self) -> AccountInfo:
        data = self._request("GET", "/v2/account")
        return AccountInfo(
            cash=float(data["cash"]),
            equity=float(data["equity"]),
            buying_power=float(data["buying_power"]),
            currency=data.get("currency", "USD"),
        )

    def get_latest_price(self, symbol: str) -> float:
        raise NotImplementedError("Use MarketDataProvider for Alpaca market data integration")

    def submit_order(self, order: OrderRequest) -> OrderResult:
        if not self.paper and os.getenv("LIVE_TRADING", "false").lower() != "true":
            return OrderResult(
                order_id=self.new_order_id("alpaca"),
                request=order,
                status=OrderStatus.REJECTED,
                message="Alpaca live URL refused because LIVE_TRADING is not true",
            )

        payload: dict[str, Any] = {
            "symbol": order.symbol.replace("/", ""),
            "qty": str(order.quantity),
            "side": order.side.value,
            "type": order.order_type.value,
            "time_in_force": str(order.metadata.get("time_in_force", "day")),
        }
        if order.asset_type == AssetType.CRYPTO:
            payload["symbol"] = order.symbol
            payload["time_in_force"] = str(order.metadata.get("time_in_force", "gtc"))
        if order.order_type == OrderType.LIMIT:
            payload["limit_price"] = order.limit_price
        if order.order_type == OrderType.STOP:
            payload["stop_price"] = order.stop_price
        if "client_order_id" in order.metadata:
            payload["client_order_id"] = str(order.metadata["client_order_id"])

        try:
            data = self._request("POST", "/v2/orders", json=payload)
        except Exception as exc:
            return OrderResult(
                order_id=self.new_order_id("alpaca"),
                request=order,
                status=OrderStatus.REJECTED,
                message=f"Alpaca order rejected: {exc}",
            )

        status_text = str(data.get("status", "new")).lower()
        status = OrderStatus.FILLED if status_text == "filled" else OrderStatus.NEW
        filled_quantity = float(data.get("filled_qty") or 0.0)
        avg_price_raw = data.get("filled_avg_price")
        return OrderResult(
            order_id=str(data.get("id", self.new_order_id("alpaca"))),
            request=order,
            status=status,
            filled_quantity=filled_quantity,
            average_price=float(avg_price_raw) if avg_price_raw else None,
            message=f"submitted to Alpaca {'paper' if self.paper else 'live'} account: {status_text}",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        try:
            rows = self._request("GET", "/v2/positions")
        except Exception:
            return {}
        positions: dict[str, BrokerPosition] = {}
        for row in rows:
            symbol = str(row["symbol"])
            asset_class = str(row.get("asset_class", "us_equity"))
            if asset_class == "crypto":
                asset_type = AssetType.CRYPTO
            elif asset_class == "option":
                asset_type = AssetType.OPTION
            else:
                asset_type = AssetType.STOCK
            positions[symbol] = BrokerPosition(
                symbol=symbol,
                quantity=float(row["qty"]),
                average_price=float(row.get("avg_entry_price") or 0.0),
                asset_type=asset_type,
            )
        return positions
