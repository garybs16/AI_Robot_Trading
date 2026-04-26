"""Interactive Brokers placeholder for stocks and options."""

from __future__ import annotations

import os

from brokers.base_broker import AccountInfo, BaseBroker, BrokerPosition, OrderRequest, OrderResult, OrderStatus


class InteractiveBrokersBroker(BaseBroker):
    name = "interactive_brokers"

    def __init__(self) -> None:
        self.host = os.getenv("IB_HOST", "127.0.0.1")
        self.port = int(os.getenv("IB_PORT", "7497"))
        self.client_id = int(os.getenv("IB_CLIENT_ID", "1"))

    def validate_credentials(self) -> bool:
        return bool(self.host and self.port)

    def get_account(self) -> AccountInfo:
        raise NotImplementedError("Interactive Brokers account integration requires ib_insync or official IB API")

    def get_latest_price(self, symbol: str) -> float:
        raise NotImplementedError("Interactive Brokers market data placeholder")

    def submit_order(self, order: OrderRequest) -> OrderResult:
        return OrderResult(
            order_id=self.new_order_id("ib"),
            request=order,
            status=OrderStatus.REJECTED,
            message="Interactive Brokers live order submission placeholder is disabled by default",
        )

    def get_positions(self) -> dict[str, BrokerPosition]:
        return {}

