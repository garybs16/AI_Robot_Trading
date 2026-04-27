"""FastAPI service exposing trading platform status and controls."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from automation.runtime_store import RuntimeStore
from brokers.broker_factory import BrokerFactory
from config_loader import ConfigLoader
from data.market_data import MarketDataProvider
from logger import setup_logger
from strategies.ai_signal_strategy import AISignalStrategy
from strategies.base_strategy import SignalAction
from strategies.breakout_strategy import BreakoutStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.options_strategy import OptionsStrategy
from utils.validators import infer_asset_type


STRATEGIES = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "options": OptionsStrategy,
    "ai_signal": AISignalStrategy,
}


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: str
    live_trading_enabled: bool
    kill_switch_active: bool


class AccountResponse(BaseModel):
    broker: str
    cash: float
    equity: float
    buying_power: float
    currency: str
    positions: int


class QuoteResponse(BaseModel):
    symbol: str
    timeframe: str
    timestamp: str
    close: float
    volume: float


class SignalResponse(BaseModel):
    symbol: str
    strategy: str
    signal: str
    confidence: float
    reason: str
    latest_price: float


class KillSwitchRequest(BaseModel):
    reason: str = Field(default="api request", min_length=1, max_length=200)


def load_config():
    config = ConfigLoader(ROOT_DIR).load()
    config.settings["mode"] = "paper"
    config.settings["live_trading"] = False
    return config


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Robot Trading API",
        version="1.0.0",
        description="Operational API for paper trading status, market data, signals, and safety controls.",
    )
    logger = setup_logger(ROOT_DIR)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        config = load_config()
        store = RuntimeStore(ROOT_DIR)
        return HealthResponse(
            status="ok",
            service="ai-robot-trading",
            timestamp=datetime.now(timezone.utc).isoformat(),
            live_trading_enabled=bool(config.settings.get("live_trading", False)),
            kill_switch_active=store.kill_switch_active(),
        )

    @app.get("/account", response_model=AccountResponse)
    def account(broker: str = Query(default="alpaca")) -> AccountResponse:
        config = load_config()
        config.settings.setdefault("broker", {})["name"] = broker
        broker_adapter = BrokerFactory.create(config.settings, force_paper=broker == "paper")
        if not broker_adapter.validate_credentials() and broker_adapter.name != "paper":
            raise HTTPException(status_code=401, detail=f"{broker_adapter.name} credentials are missing")
        info = broker_adapter.get_account()
        positions = broker_adapter.get_positions()
        return AccountResponse(
            broker=broker_adapter.name,
            cash=info.cash,
            equity=info.equity,
            buying_power=info.buying_power,
            currency=info.currency,
            positions=len(positions),
        )

    @app.get("/quote", response_model=QuoteResponse)
    def quote(
        symbol: str = Query(default="AAPL"),
        timeframe: str = Query(default="1h"),
        broker: str = Query(default="alpaca"),
    ) -> QuoteResponse:
        config = load_config()
        config.settings.setdefault("broker", {})["name"] = broker
        market_cfg = config.settings.get("market_data", {})
        crypto_exchange = str(market_cfg.get("crypto_exchange") or broker or "coinbase")
        provider = MarketDataProvider(logger=logger, crypto_exchange=crypto_exchange)
        data = provider.get_history(symbol, infer_asset_type(symbol), timeframe, 5, min_rows=1)
        latest = data.iloc[-1]
        return QuoteResponse(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(data.index[-1]),
            close=float(latest["close"]),
            volume=float(latest["volume"]),
        )

    @app.get("/signal", response_model=SignalResponse)
    def signal(
        symbol: str = Query(default="AAPL"),
        strategy: str = Query(default="momentum"),
        timeframe: str = Query(default="1h"),
        broker: str = Query(default="alpaca"),
        limit: int = Query(default=500, ge=80, le=2000),
    ) -> SignalResponse:
        if strategy not in STRATEGIES:
            raise HTTPException(status_code=400, detail=f"Unsupported strategy: {strategy}")
        config = load_config()
        market_cfg = config.settings.get("market_data", {})
        crypto_exchange = str(market_cfg.get("crypto_exchange") or broker or "coinbase")
        provider = MarketDataProvider(logger=logger, crypto_exchange=crypto_exchange)
        data = provider.get_history(symbol, infer_asset_type(symbol), timeframe, limit)
        strategy_obj = STRATEGIES[strategy](config.strategies.get(strategy, {}))
        signal_result = strategy_obj.generate_signal(data)
        return SignalResponse(
            symbol=symbol,
            strategy=strategy,
            signal=signal_result.action.value if isinstance(signal_result.action, SignalAction) else str(signal_result.action),
            confidence=signal_result.confidence,
            reason=signal_result.reason,
            latest_price=float(data["close"].iloc[-1]),
        )

    @app.get("/events")
    def events(limit: int = Query(default=100, ge=1, le=1000)) -> dict[str, Any]:
        return {"events": RuntimeStore(ROOT_DIR).read_events(limit)}

    @app.post("/kill-switch")
    def activate_kill_switch(payload: KillSwitchRequest) -> dict[str, str]:
        RuntimeStore(ROOT_DIR).activate_kill_switch(payload.reason)
        return {"status": "activated", "reason": payload.reason}

    @app.delete("/kill-switch")
    def clear_kill_switch() -> dict[str, str]:
        RuntimeStore(ROOT_DIR).clear_kill_switch()
        return {"status": "cleared"}

    return app


app = create_app()

