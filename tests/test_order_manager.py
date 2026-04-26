from brokers.base_broker import AssetType, OrderRequest, OrderSide, OrderStatus
from brokers.paper_broker import PaperBroker
from execution.order_manager import OrderManager
from risk.risk_manager import MarketContext, PortfolioContext, RiskManager


def test_order_manager_blocks_risky_order_before_broker_submit():
    broker = PaperBroker(starting_cash=100_000, prices={"AAPL": 100})
    manager = OrderManager(broker, RiskManager({"max_position_size": 0.01}))
    order = OrderRequest("AAPL", OrderSide.BUY, 1000, AssetType.STOCK)
    result = manager.submit(order, MarketContext(price=100), PortfolioContext(equity=100_000))
    assert result.status == OrderStatus.REJECTED
    assert broker.orders == []


def test_order_manager_submits_approved_order():
    broker = PaperBroker(starting_cash=100_000, prices={"AAPL": 100}, fee_rate=0, slippage_rate=0)
    manager = OrderManager(broker, RiskManager({"max_position_size": 0.2, "risk_per_trade": 0.05}))
    order = OrderRequest("AAPL", OrderSide.BUY, 10, AssetType.STOCK, metadata={"max_loss": 100})
    result = manager.submit(order, MarketContext(price=100), PortfolioContext(equity=100_000))
    assert result.status == OrderStatus.FILLED
    assert broker.get_positions()["AAPL"].quantity == 10

