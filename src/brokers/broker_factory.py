"""Broker registry and dynamic adapter loading."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from brokers.alpaca_broker import AlpacaBroker
from brokers.base_broker import BaseBroker
from brokers.binance_broker import BinanceBroker
from brokers.coinbase_broker import CoinbaseBroker
from brokers.fidelity_broker import FidelityBroker
from brokers.interactive_brokers import InteractiveBrokersBroker
from brokers.paper_broker import PaperBroker


class BrokerFactory:
    """Creates broker adapters from config.

    Built-ins cover common brokers. The `custom` config supports other brokers
    without modifying core execution/risk code:

    broker:
      name: custom
      custom:
        class_path: "my_package.my_broker:MyBroker"
        kwargs:
          base_url: "https://example"
    """

    BUILT_INS = {
        "alpaca": AlpacaBroker,
        "binance": BinanceBroker,
        "coinbase": CoinbaseBroker,
        "coinbase_advanced_trade": CoinbaseBroker,
        "fidelity": FidelityBroker,
        "interactive_brokers": InteractiveBrokersBroker,
        "ib": InteractiveBrokersBroker,
        "paper": PaperBroker,
    }

    @classmethod
    def create(
        cls,
        settings: dict[str, Any],
        prices: dict[str, float] | None = None,
        force_paper: bool = False,
    ) -> BaseBroker:
        broker_cfg = settings.get("broker", {})
        name = str(broker_cfg.get("name", "paper")).lower()
        execution_cfg = settings.get("execution", {})

        if force_paper or name == "paper":
            return PaperBroker(
                starting_cash=float(settings.get("starting_cash", 100000)),
                prices=prices or {},
                fee_rate=float(execution_cfg.get("fee_rate", 0.001)),
                slippage_rate=float(execution_cfg.get("slippage_rate", 0.0005)),
            )

        if name == "custom":
            custom_cfg = broker_cfg.get("custom", {})
            return cls._create_custom(custom_cfg)

        if name == "alpaca":
            return AlpacaBroker(base_url=broker_cfg.get("alpaca", {}).get("base_url"))
        if name == "binance":
            return BinanceBroker(sandbox=bool(broker_cfg.get("binance", {}).get("sandbox", True)))
        if name in {"coinbase", "coinbase_advanced_trade"}:
            coinbase_cfg = broker_cfg.get("coinbase", {})
            return CoinbaseBroker(
                api_key_env=str(coinbase_cfg.get("api_key_env", "COINBASE_API_KEY")),
                api_secret_env=str(coinbase_cfg.get("api_secret_env", "COINBASE_API_SECRET")),
                key_file_env=str(coinbase_cfg.get("key_file_env", "COINBASE_KEY_FILE")),
            )
        if name in {"interactive_brokers", "ib"}:
            return InteractiveBrokersBroker()
        if name == "fidelity":
            return FidelityBroker()

        supported = ", ".join(sorted(set(cls.BUILT_INS) | {"custom"}))
        raise ValueError(f"Unsupported broker '{name}'. Supported brokers: {supported}")

    @staticmethod
    def _create_custom(custom_cfg: dict[str, Any]) -> BaseBroker:
        class_path = str(custom_cfg.get("class_path", ""))
        if ":" not in class_path:
            raise ValueError("broker.custom.class_path must use 'module.path:ClassName'")
        module_name, class_name = class_path.split(":", 1)
        module = import_module(module_name)
        broker_cls = getattr(module, class_name)
        kwargs = custom_cfg.get("kwargs", {})
        broker = broker_cls(**kwargs)
        if not isinstance(broker, BaseBroker):
            raise TypeError("Custom broker must inherit from BaseBroker")
        return broker
