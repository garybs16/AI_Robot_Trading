"""Fidelity broker extension point.

Fidelity does not provide a broadly documented public retail trading API in the
same way Coinbase, Alpaca, Interactive Brokers, or Schwab do. This class exists
so the rest of the system can be wired for Fidelity later through an official,
contracted, or institutionally approved API without relying on scraped or
unofficial endpoints.
"""

from __future__ import annotations

import os

from brokers.base_broker import AccountInfo, BaseBroker, BrokerPosition, OrderRequest, OrderResult, OrderStatus


class FidelityBroker(BaseBroker):
    name = "fidelity"

    def __init__(self) -> None:
        self.api_enabled = os.getenv("FIDELITY_OFFICIAL_API_ENABLED", "false").lower() == "true"

    def validate_credentials(self) -> bool:
        return self.api_enabled

    def get_account(self) -> AccountInfo:
        raise NotImplementedError(
            "Fidelity trading requires an official or contracted API implementation. "
            "Unofficial scraped endpoints are intentionally not supported."
        )

    def get_latest_price(self, symbol: str) -> float:
        raise NotImplementedError("Fidelity market data integration is not configured")

    def submit_order(self, order: OrderRequest) -> OrderResult:
        return OrderResult(
            order_id=self.new_order_id("fidelity"),
            request=order,
            status=OrderStatus.REJECTED,
            message="Fidelity order submission is disabled without an official API implementation",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        return {}

