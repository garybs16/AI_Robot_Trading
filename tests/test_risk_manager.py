from brokers.base_broker import AssetType, OrderRequest, OrderSide
from risk.risk_manager import MarketContext, PortfolioContext, RiskManager


def test_risk_manager_rejects_oversized_position():
    manager = RiskManager({"max_position_size": 0.1})
    order = OrderRequest("AAPL", OrderSide.BUY, quantity=200, asset_type=AssetType.STOCK)
    decision = manager.validate_order(order, MarketContext(price=100), PortfolioContext(equity=100_000))
    assert not decision.approved
    assert "position size" in decision.reason


def test_risk_manager_rejects_option_without_defined_max_loss():
    manager = RiskManager({"require_defined_options_risk": True})
    order = OrderRequest("SPY_CALL", OrderSide.BUY, quantity=1, asset_type=AssetType.OPTION)
    decision = manager.validate_order(order, MarketContext(price=2), PortfolioContext(equity=100_000))
    assert not decision.approved
    assert "max_loss" in decision.reason


def test_risk_manager_approves_defined_risk_order():
    manager = RiskManager({"risk_per_trade": 0.01, "max_position_size": 0.2})
    order = OrderRequest(
        "AAPL",
        OrderSide.BUY,
        quantity=10,
        asset_type=AssetType.STOCK,
        metadata={"max_loss": 100},
    )
    decision = manager.validate_order(order, MarketContext(price=100), PortfolioContext(equity=100_000))
    assert decision.approved

