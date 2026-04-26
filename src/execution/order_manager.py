"""Order validation and submission orchestration."""

from __future__ import annotations

import logging

from brokers.base_broker import BaseBroker, OrderRequest, OrderResult, OrderStatus
from risk.risk_manager import MarketContext, PortfolioContext, RiskManager


class OrderManager:
    def __init__(self, broker: BaseBroker, risk_manager: RiskManager, logger: logging.Logger | None = None) -> None:
        self.broker = broker
        self.risk_manager = risk_manager
        self.logger = logger or logging.getLogger(__name__)

    def submit(self, order: OrderRequest, market: MarketContext, portfolio: PortfolioContext) -> OrderResult:
        decision = self.risk_manager.validate_order(order, market, portfolio)
        if not decision.approved:
            self.logger.info("Order rejected by risk manager: %s | %s", order, decision.reason)
            return OrderResult(
                order_id=self.broker.new_order_id("risk"),
                request=order,
                status=OrderStatus.REJECTED,
                message=decision.reason,
            )
        result = self.broker.submit_order(order)
        self.logger.info("Order result: %s", result)
        return result

