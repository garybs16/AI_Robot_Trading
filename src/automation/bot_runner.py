"""Autonomous paper-trading runner used by the dashboard and CLI extensions."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from automation.runtime_store import RuntimeStore
from brokers.base_broker import AssetType, BaseBroker, OrderRequest, OrderSide
from brokers.broker_factory import BrokerFactory
from data.market_data import MarketDataProvider
from execution.order_manager import OrderManager
from risk.position_sizer import PositionSizer
from risk.risk_manager import MarketContext, PortfolioContext, RiskManager
from strategies.ai_signal_strategy import AISignalStrategy
from strategies.base_strategy import SignalAction
from strategies.breakout_strategy import BreakoutStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.options_strategy import OptionsStrategy
from utils.validators import infer_asset_type


STRATEGY_CLASSES = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "options": OptionsStrategy,
    "ai_signal": AISignalStrategy,
}


@dataclass
class AutoBotConfig:
    root_dir: Path
    settings: dict[str, Any]
    strategies: dict[str, Any]
    broker_name: str
    symbols: list[str]
    strategy_name: str
    timeframe: str = "1h"
    limit: int = 500
    interval_seconds: int = 60
    submit_orders: bool = True
    market_hours_only: bool = True
    max_cycles: int | None = None


def is_market_open(symbol: str, now: datetime | None = None) -> bool:
    """Return True for crypto always, and for stocks during regular US hours."""

    if "/" in symbol:
        return True
    eastern = ZoneInfo("America/New_York")
    current = (now or datetime.now(tz=eastern)).astimezone(eastern)
    if current.weekday() >= 5:
        return False
    return dt_time(9, 30) <= current.time() <= dt_time(16, 0)


def symbol_has_position(positions: dict[str, Any], symbol: str) -> bool:
    possible_symbols = {symbol, symbol.replace("/", ""), symbol.split("/")[0]}
    return any(candidate in positions for candidate in possible_symbols)


class AutoPaperBot:
    """Runs a multi-symbol paper trading loop with guardrails."""

    def __init__(
        self,
        config: AutoBotConfig,
        logger: logging.Logger,
        stop_event: threading.Event | None = None,
        state: dict[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.logger = logger
        self.stop_event = stop_event or threading.Event()
        self.state = state if state is not None else {}
        self.store = RuntimeStore(config.root_dir)
        self.broker = self._build_broker()
        self.provider = self._build_market_data_provider()
        self.initial_equity: float | None = None
        self.peak_equity: float | None = None
        self.cycle_count = 0

    def _build_broker(self) -> BaseBroker:
        settings = dict(self.config.settings)
        settings["mode"] = "paper"
        settings.setdefault("broker", {})["name"] = self.config.broker_name
        return BrokerFactory.create(settings, force_paper=self.config.broker_name == "paper")

    def _build_market_data_provider(self) -> MarketDataProvider:
        market_cfg = self.config.settings.get("market_data", {})
        crypto_exchange = str(market_cfg.get("crypto_exchange") or self.config.broker_name or "coinbase")
        if crypto_exchange == "coinbase_advanced_trade":
            crypto_exchange = "coinbase"
        return MarketDataProvider(logger=self.logger, crypto_exchange=crypto_exchange)

    def _strategy(self):
        params = self.config.strategies.get(self.config.strategy_name, {})
        return STRATEGY_CLASSES[self.config.strategy_name](params)

    def _risk_locked(self, account_equity: float) -> str | None:
        risk_cfg = self.config.settings.get("risk", {})
        max_daily_loss = float(risk_cfg.get("max_daily_loss", 0.03))
        max_drawdown = float(risk_cfg.get("max_drawdown", 0.10))
        if self.initial_equity is None:
            self.initial_equity = account_equity
        if self.peak_equity is None:
            self.peak_equity = account_equity
        self.peak_equity = max(self.peak_equity, account_equity)
        daily_pnl_fraction = account_equity / self.initial_equity - 1 if self.initial_equity else 0.0
        drawdown = account_equity / self.peak_equity - 1 if self.peak_equity else 0.0
        if daily_pnl_fraction <= -abs(max_daily_loss):
            self.store.activate_kill_switch("daily loss lockout")
            return f"Daily loss lockout hit: {daily_pnl_fraction:.2%}"
        if drawdown <= -abs(max_drawdown):
            self.store.activate_kill_switch("drawdown lockout")
            return f"Drawdown lockout hit: {drawdown:.2%}"
        return None

    def _event(self, symbol: str, signal: str, status: str, message: str, **extra: Any) -> dict[str, Any]:
        event = {
            "timestamp": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
            "broker": self.config.broker_name,
            "symbol": symbol,
            "strategy": self.config.strategy_name,
            "signal": signal,
            "status": status,
            "message": message,
            **extra,
        }
        self.store.append_event(event)
        self.logger.info("Auto event: %s", event)
        return event

    def run_once(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        if self.store.kill_switch_active():
            reason = self.store.kill_switch_reason()
            return [self._event("", "", "blocked", f"Kill switch active: {reason}")]

        if not self.broker.validate_credentials() and self.broker.name != "paper":
            return [self._event("", "", "blocked", f"{self.broker.name} credentials are missing in .env")]

        account = self.broker.get_account()
        lockout = self._risk_locked(account.equity)
        if lockout:
            return [self._event("", "", "blocked", lockout)]

        for symbol in self.config.symbols:
            if self.stop_event.is_set():
                break
            if self.config.market_hours_only and not is_market_open(symbol):
                events.append(self._event(symbol, "", "skipped", "Outside regular market hours"))
                continue
            try:
                events.append(self._scan_symbol(symbol))
            except Exception as exc:
                events.append(self._event(symbol, "", "error", str(exc)))
        self.cycle_count += 1
        return events

    def _scan_symbol(self, symbol: str) -> dict[str, Any]:
        asset_type_name = infer_asset_type(symbol)
        data = self.provider.get_history(symbol, asset_type_name, self.config.timeframe, self.config.limit)
        latest_price = float(data["close"].iloc[-1])
        if hasattr(self.broker, "set_price"):
            self.broker.set_price(symbol, latest_price)

        strategy = self._strategy()
        signal = strategy.generate_signal(data)
        account = self.broker.get_account()
        positions = self.broker.get_positions()

        if signal.action == SignalAction.HOLD:
            return self._event(
                symbol,
                signal.action.value,
                "no_order",
                signal.reason,
                price=latest_price,
                quantity=0,
            )
        if signal.action == SignalAction.BUY and symbol_has_position(positions, symbol):
            return self._event(
                symbol,
                signal.action.value,
                "skipped",
                "Buy skipped because a position already exists",
                price=latest_price,
                quantity=0,
            )
        if signal.action == SignalAction.SELL and not symbol_has_position(positions, symbol):
            return self._event(
                symbol,
                signal.action.value,
                "skipped",
                "Sell skipped because no long position exists",
                price=latest_price,
                quantity=0,
            )

        quantity = self._position_size(account.equity, latest_price)
        if quantity <= 0:
            return self._event(symbol, signal.action.value, "blocked", "Calculated quantity is zero", price=latest_price)

        if not self.config.submit_orders:
            return self._event(
                symbol,
                signal.action.value,
                "preview",
                "Signal generated, order submission disabled",
                price=latest_price,
                quantity=quantity,
            )

        return self._submit_order(symbol, asset_type_name, signal.action, quantity, latest_price, data, account.equity)

    def _position_size(self, equity: float, latest_price: float) -> float:
        risk_cfg = self.config.settings.get("risk", {})
        sizer = PositionSizer(
            max_position_fraction=float(risk_cfg.get("max_position_size", 0.20)),
            default_risk_fraction=float(risk_cfg.get("risk_per_trade", 0.01)),
        )
        return sizer.percent_of_portfolio(equity, latest_price)

    def _submit_order(
        self,
        symbol: str,
        asset_type_name: str,
        action: SignalAction,
        quantity: float,
        latest_price: float,
        data: pd.DataFrame,
        equity: float,
    ) -> dict[str, Any]:
        risk_manager = RiskManager(self.config.settings.get("risk", {}))
        order_manager = OrderManager(self.broker, risk_manager, self.logger)
        side = OrderSide.BUY if action == SignalAction.BUY else OrderSide.SELL
        order = OrderRequest(symbol=symbol, side=side, quantity=quantity, asset_type=AssetType(asset_type_name))
        volatility_raw = data["close"].pct_change().rolling(20).std().iloc[-1]
        volatility = float(0.0 if pd.isna(volatility_raw) else volatility_raw)
        market = MarketContext(
            price=latest_price,
            slippage=float(self.config.settings.get("execution", {}).get("slippage_rate", 0.0005)),
            volatility=volatility,
        )
        portfolio = PortfolioContext(equity=equity, open_trades=len(self.broker.get_positions()))
        result = order_manager.submit(order, market, portfolio)
        return self._event(
            symbol,
            action.value,
            result.status.value,
            result.message,
            price=latest_price,
            quantity=quantity,
            order_id=result.order_id,
        )

    def run_forever(self) -> None:
        self.state.update(
            {
                "running": True,
                "started_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
                "last_message": "Bot started",
                "cycle_count": 0,
            }
        )
        try:
            while not self.stop_event.is_set():
                events = self.run_once()
                self.state["last_events"] = events
                self.state["last_message"] = events[-1]["message"] if events else "Cycle completed"
                self.state["cycle_count"] = self.cycle_count
                self.state["last_run_at"] = datetime.now(tz=ZoneInfo("UTC")).isoformat()
                if self.config.max_cycles is not None and self.cycle_count >= self.config.max_cycles:
                    break
                self.stop_event.wait(max(self.config.interval_seconds, 1))
        except Exception as exc:
            self.state["last_message"] = f"Bot stopped on error: {exc}"
            self.logger.exception("Auto bot stopped on error")
        finally:
            self.state["running"] = False
            self.state["stopped_at"] = datetime.now(tz=ZoneInfo("UTC")).isoformat()

