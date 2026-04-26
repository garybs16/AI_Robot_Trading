"""Pre-trade risk validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from brokers.base_broker import AssetType, OrderRequest


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


@dataclass(frozen=True)
class MarketContext:
    price: float
    spread: float = 0.0
    slippage: float = 0.0
    volatility: float = 0.0
    is_earnings_window: bool = False


@dataclass(frozen=True)
class PortfolioContext:
    equity: float
    daily_pnl: float = 0.0
    drawdown: float = 0.0
    open_trades: int = 0
    current_asset_exposure: float = 0.0


class RiskManager:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        cfg = config or {}
        self.risk_per_trade = float(cfg.get("risk_per_trade", 0.01))
        self.max_daily_loss = float(cfg.get("max_daily_loss", 0.03))
        self.max_drawdown = float(cfg.get("max_drawdown", 0.10))
        self.max_position_size = float(cfg.get("max_position_size", 0.20))
        self.max_open_trades = int(cfg.get("max_open_trades", 5))
        self.max_slippage = float(cfg.get("max_slippage", 0.0025))
        self.max_spread = float(cfg.get("max_spread", 0.005))
        self.max_volatility = float(cfg.get("max_volatility", 0.08))
        self.allow_earnings_trades = bool(cfg.get("allow_earnings_trades", False))
        self.require_defined_options_risk = bool(cfg.get("require_defined_options_risk", True))

    def validate_order(
        self,
        order: OrderRequest,
        market: MarketContext,
        portfolio: PortfolioContext,
    ) -> RiskDecision:
        if order.quantity <= 0:
            return RiskDecision(False, "quantity must be positive")
        if market.price <= 0:
            return RiskDecision(False, "market price must be positive")
        if portfolio.equity <= 0:
            return RiskDecision(False, "portfolio equity must be positive")
        if portfolio.daily_pnl / portfolio.equity <= -self.max_daily_loss:
            return RiskDecision(False, "max daily loss exceeded")
        if portfolio.drawdown <= -self.max_drawdown:
            return RiskDecision(False, "max drawdown exceeded")
        if portfolio.open_trades >= self.max_open_trades:
            return RiskDecision(False, "max open trades reached")
        if market.spread > self.max_spread:
            return RiskDecision(False, "spread too high")
        if market.slippage > self.max_slippage:
            return RiskDecision(False, "slippage too high")
        if market.volatility > self.max_volatility:
            return RiskDecision(False, "volatility too high")
        if market.is_earnings_window and not self.allow_earnings_trades:
            return RiskDecision(False, "earnings window trading disabled")

        notional = order.quantity * market.price
        if notional / portfolio.equity > self.max_position_size:
            return RiskDecision(False, "position size exceeds max_position_size")

        projected_risk = float(order.metadata.get("max_loss", notional * self.risk_per_trade))
        if projected_risk / portfolio.equity > self.risk_per_trade:
            return RiskDecision(False, "trade risk exceeds risk_per_trade")

        if order.asset_type == AssetType.OPTION and self.require_defined_options_risk:
            max_loss = order.metadata.get("max_loss")
            if max_loss is None or float(max_loss) <= 0:
                return RiskDecision(False, "options trade rejected because max_loss is undefined")

        return RiskDecision(True, "approved")

