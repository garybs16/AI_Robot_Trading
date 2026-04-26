"""Local simulated broker for paper trading and tests."""

from __future__ import annotations

from collections.abc import Mapping

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


class PaperBroker(BaseBroker):
    name = "paper"

    def __init__(
        self,
        starting_cash: float = 100_000.0,
        prices: Mapping[str, float] | None = None,
        fee_rate: float = 0.001,
        slippage_rate: float = 0.0005,
    ) -> None:
        self.cash = float(starting_cash)
        self.prices: dict[str, float] = {k: float(v) for k, v in (prices or {}).items()}
        self.positions: dict[str, BrokerPosition] = {}
        self.fee_rate = float(fee_rate)
        self.slippage_rate = float(slippage_rate)
        self.orders: list[OrderResult] = []

    def set_price(self, symbol: str, price: float) -> None:
        if price <= 0:
            raise ValueError("price must be positive")
        self.prices[symbol] = float(price)

    def update_prices(self, prices: Mapping[str, float]) -> None:
        for symbol, price in prices.items():
            self.set_price(symbol, price)

    def get_account(self) -> AccountInfo:
        equity = self.cash
        for position in self.positions.values():
            equity += position.quantity * self.get_latest_price(position.symbol)
        return AccountInfo(cash=self.cash, equity=equity, buying_power=self.cash)

    def get_latest_price(self, symbol: str) -> float:
        try:
            return self.prices[symbol]
        except KeyError as exc:
            raise ValueError(f"No paper price available for {symbol}") from exc

    def submit_order(self, order: OrderRequest) -> OrderResult:
        if order.quantity <= 0:
            result = OrderResult(
                order_id=self.new_order_id("paper"),
                request=order,
                status=OrderStatus.REJECTED,
                message="quantity must be positive",
            )
            self.orders.append(result)
            return result

        market_price = self.get_latest_price(order.symbol)
        if order.order_type == OrderType.LIMIT and order.limit_price is None:
            return self._reject(order, "limit_price required for limit order")

        if order.order_type == OrderType.LIMIT:
            if order.side == OrderSide.BUY and market_price > float(order.limit_price):
                return self._reject(order, "buy limit not marketable")
            if order.side == OrderSide.SELL and market_price < float(order.limit_price):
                return self._reject(order, "sell limit not marketable")

        fill_price = market_price * (1 + self.slippage_rate if order.side == OrderSide.BUY else 1 - self.slippage_rate)
        notional = fill_price * order.quantity
        fee = abs(notional) * self.fee_rate

        if order.side == OrderSide.BUY:
            total_cost = notional + fee
            if total_cost > self.cash:
                return self._reject(order, "insufficient buying power")
            self.cash -= total_cost
            existing = self.positions.get(order.symbol)
            if existing:
                new_qty = existing.quantity + order.quantity
                existing.average_price = ((existing.average_price * existing.quantity) + notional) / new_qty
                existing.quantity = new_qty
            else:
                self.positions[order.symbol] = BrokerPosition(
                    symbol=order.symbol,
                    quantity=order.quantity,
                    average_price=fill_price,
                    asset_type=order.asset_type,
                )
        else:
            existing = self.positions.get(order.symbol)
            if not existing or existing.quantity < order.quantity:
                return self._reject(order, "cannot sell more than current position")
            self.cash += notional - fee
            existing.quantity -= order.quantity
            if existing.quantity <= 1e-12:
                self.positions.pop(order.symbol, None)

        result = OrderResult(
            order_id=self.new_order_id("paper"),
            request=order,
            status=OrderStatus.FILLED,
            filled_quantity=order.quantity,
            average_price=fill_price,
            message="filled by paper broker",
        )
        self.orders.append(result)
        return result

    def _reject(self, order: OrderRequest, message: str) -> OrderResult:
        result = OrderResult(
            order_id=self.new_order_id("paper"),
            request=order,
            status=OrderStatus.REJECTED,
            message=message,
        )
        self.orders.append(result)
        return result

    def get_positions(self) -> dict[str, BrokerPosition]:
        return dict(self.positions)

    def validate_credentials(self) -> bool:
        return True

