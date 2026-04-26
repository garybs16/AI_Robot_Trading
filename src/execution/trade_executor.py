"""Strategy signal to order conversion."""

from __future__ import annotations

import logging

from brokers.base_broker import AssetType, OrderRequest, OrderSide
from execution.order_manager import OrderManager
from risk.risk_manager import MarketContext, PortfolioContext
from strategies.base_strategy import Signal, SignalAction


class TradeExecutor:
    def __init__(self, order_manager: OrderManager, logger: logging.Logger | None = None) -> None:
        self.order_manager = order_manager
        self.logger = logger or logging.getLogger(__name__)

    def execute_signal(
        self,
        symbol: str,
        asset_type: AssetType,
        signal: Signal,
        quantity: float,
        market: MarketContext,
        portfolio: PortfolioContext,
    ):
        if signal.action == SignalAction.HOLD or quantity <= 0:
            self.logger.info("No order for %s: %s", symbol, signal)
            return None
        side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL
        order = OrderRequest(symbol=symbol, side=side, quantity=quantity, asset_type=asset_type)
        return self.order_manager.submit(order, market, portfolio)

