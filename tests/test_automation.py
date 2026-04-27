from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from automation.bot_runner import is_market_open, symbol_has_position
from automation.runtime_store import RuntimeStore
from brokers.base_broker import AssetType, BrokerPosition


def test_market_hours_crypto_is_always_open():
    saturday = datetime(2026, 4, 25, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open("BTC/USD", saturday)


def test_market_hours_stock_regular_session_only():
    open_time = datetime(2026, 4, 27, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    closed_time = datetime(2026, 4, 27, 18, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open("AAPL", open_time)
    assert not is_market_open("AAPL", closed_time)


def test_symbol_has_position_handles_crypto_and_alpaca_formats():
    positions = {
        "BTC": BrokerPosition("BTC", 0.1, 0, AssetType.CRYPTO),
        "AAPL": BrokerPosition("AAPL", 1, 100, AssetType.STOCK),
    }
    assert symbol_has_position(positions, "BTC/USD")
    assert symbol_has_position(positions, "AAPL")


def test_runtime_store_kill_switch_and_history(tmp_path: Path):
    store = RuntimeStore(tmp_path)
    store.append_event({"symbol": "AAPL", "status": "preview", "message": "test"})
    assert store.read_events()[0]["symbol"] == "AAPL"
    store.activate_kill_switch("test")
    assert store.kill_switch_active()
    assert "test" in store.kill_switch_reason()
    store.clear_kill_switch()
    assert not store.kill_switch_active()

