from brokers.broker_factory import BrokerFactory
from brokers.alpaca_broker import AlpacaBroker
from brokers.coinbase_broker import CoinbaseBroker
from brokers.fidelity_broker import FidelityBroker
from brokers.paper_broker import PaperBroker


def test_broker_factory_forces_paper_in_paper_mode():
    settings = {"starting_cash": 1000, "broker": {"name": "coinbase"}, "execution": {}}
    broker = BrokerFactory.create(settings, prices={"BTC/USD": 100}, force_paper=True)
    assert isinstance(broker, PaperBroker)
    assert broker.get_latest_price("BTC/USD") == 100


def test_broker_factory_builds_alpaca_paper_adapter():
    settings = {
        "broker": {"name": "alpaca", "alpaca": {"base_url": "https://paper-api.alpaca.markets", "paper": True}},
        "execution": {},
    }
    broker = BrokerFactory.create(settings)
    assert isinstance(broker, AlpacaBroker)
    assert broker.paper


def test_broker_factory_builds_coinbase_adapter():
    settings = {"broker": {"name": "coinbase", "coinbase": {}}, "execution": {}}
    broker = BrokerFactory.create(settings)
    assert isinstance(broker, CoinbaseBroker)
    assert broker.sandbox


def test_coinbase_adapter_accepts_key_file_env(monkeypatch):
    monkeypatch.setenv("TEST_COINBASE_KEY_FILE", "C:\\keys\\coinbase.json")
    broker = CoinbaseBroker(api_key_env="NO_KEY", api_secret_env="NO_SECRET", key_file_env="TEST_COINBASE_KEY_FILE")
    assert broker.validate_credentials()


def test_broker_factory_builds_fidelity_safe_adapter():
    settings = {"broker": {"name": "fidelity"}, "execution": {}}
    broker = BrokerFactory.create(settings)
    assert isinstance(broker, FidelityBroker)
    assert not broker.validate_credentials()
