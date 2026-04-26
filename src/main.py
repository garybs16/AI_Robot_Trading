"""Command-line entry point for backtesting, broker checks, and safe paper trading."""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtesting.backtest_engine import BacktestEngine
from brokers.base_broker import AssetType, OrderRequest, OrderSide
from brokers.broker_factory import BrokerFactory
from config_loader import ConfigLoader
from data.market_data import MarketDataProvider
from execution.order_manager import OrderManager
from logger import setup_logger
from risk.position_sizer import PositionSizer
from risk.risk_manager import MarketContext, PortfolioContext, RiskManager
from strategies.ai_signal_strategy import AISignalStrategy
from strategies.base_strategy import SignalAction
from strategies.breakout_strategy import BreakoutStrategy
from strategies.mean_reversion_strategy import MeanReversionStrategy
from strategies.momentum_strategy import MomentumStrategy
from strategies.options_strategy import OptionsStrategy
from utils.validators import infer_asset_type


def build_market_data_provider(config: Any, logger: logging.Logger) -> MarketDataProvider:
    market_data_cfg = config.settings.get("market_data", {})
    broker_name = str(config.settings.get("broker", {}).get("name", "")).lower()
    crypto_exchange = str(market_data_cfg.get("crypto_exchange") or broker_name or "coinbase")
    if crypto_exchange == "coinbase_advanced_trade":
        crypto_exchange = "coinbase"
    return MarketDataProvider(logger=logger, crypto_exchange=crypto_exchange)


def build_strategy(name: str, params: dict) -> object:
    mapping = {
        "momentum": MomentumStrategy,
        "mean_reversion": MeanReversionStrategy,
        "breakout": BreakoutStrategy,
        "options": OptionsStrategy,
        "ai_signal": AISignalStrategy,
    }
    try:
        return mapping[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown strategy: {name}") from exc


def build_broker(config: Any, prices: dict[str, float] | None = None):
    broker_name = str(config.settings.get("broker", {}).get("name", "paper")).lower()
    force_paper = str(config.settings.get("mode", "paper")).lower() == "paper" and broker_name == "paper"
    return BrokerFactory.create(config.settings, prices=prices, force_paper=force_paper)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production-oriented trading bot framework")
    parser.add_argument("--mode", choices=["backtest", "paper", "quote", "account", "live"], default=None)
    parser.add_argument("--strategy", required=True, choices=["momentum", "mean_reversion", "breakout", "options", "ai_signal"])
    parser.add_argument("--asset", required=True)
    parser.add_argument("--broker", default=None, help="Override broker config, e.g. paper, coinbase, alpaca, fidelity, custom")
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output-dir", default="backtest_results")
    return parser.parse_args()


def run_quote(args: argparse.Namespace, config, logger: logging.Logger) -> None:
    asset_type = infer_asset_type(args.asset)
    timeframe = args.timeframe or config.settings.get("default_timeframe", "1h")
    limit = args.limit or 5
    data = build_market_data_provider(config, logger).get_history(args.asset, asset_type, timeframe, limit, min_rows=1)
    latest = data.iloc[-1]
    print(
        {
            "symbol": args.asset,
            "timeframe": timeframe,
            "timestamp": str(data.index[-1]),
            "open": float(latest["open"]),
            "high": float(latest["high"]),
            "low": float(latest["low"]),
            "close": float(latest["close"]),
            "volume": float(latest["volume"]),
        }
    )


def run_account_check(args: argparse.Namespace, config, logger: logging.Logger) -> None:
    broker = BrokerFactory.create(config.settings, force_paper=False)
    if not broker.validate_credentials():
        raise PermissionError(
            f"{broker.name} credentials are not configured. Add the broker API keys to .env and rerun account mode."
        )
    account = broker.get_account()
    positions = broker.get_positions()
    logger.info("Broker account check succeeded for %s", broker.name)
    print(
        {
            "broker": broker.name,
            "cash": account.cash,
            "equity": account.equity,
            "buying_power": account.buying_power,
            "currency": account.currency,
            "positions": len(positions),
        }
    )


def run_backtest(args: argparse.Namespace, config, logger: logging.Logger) -> None:
    asset_type = infer_asset_type(args.asset)
    timeframe = args.timeframe or config.settings.get("default_timeframe", "1h")
    limit = args.limit or int(config.settings.get("data_lookback_bars", 500))
    data = build_market_data_provider(config, logger).get_history(args.asset, asset_type, timeframe, limit)
    strategy = build_strategy(args.strategy, config.strategies.get(args.strategy, {}))
    execution_cfg = config.settings.get("execution", {})
    engine = BacktestEngine(
        starting_cash=float(config.settings.get("starting_cash", 100000)),
        fee_rate=float(execution_cfg.get("fee_rate", 0.001)),
        slippage_rate=float(execution_cfg.get("slippage_rate", 0.0005)),
        allocation_fraction=float(config.settings.get("risk", {}).get("max_position_size", 0.20)),
    )
    result = engine.run(data, strategy)
    output = config.root_dir / args.output_dir / args.strategy / args.asset.replace("/", "_")
    engine.export(result, output)
    logger.info("Backtest metrics for %s %s: %s", args.asset, args.strategy, result.metrics)
    print(result.metrics)
    print(f"Exported results to {output}")


def run_paper(args: argparse.Namespace, config, logger: logging.Logger) -> None:
    asset_type_name = infer_asset_type(args.asset)
    asset_type = AssetType(asset_type_name)
    timeframe = args.timeframe or config.settings.get("default_timeframe", "1h")
    limit = args.limit or int(config.settings.get("data_lookback_bars", 500))
    data_provider = build_market_data_provider(config, logger)
    data = data_provider.get_history(args.asset, asset_type_name, timeframe, limit)
    latest_price = float(data["close"].iloc[-1])

    execution_cfg = config.settings.get("execution", {})
    broker = build_broker(config, prices={args.asset: latest_price})
    if not broker.validate_credentials() and broker.name != "paper":
        raise PermissionError(f"{broker.name} paper trading requires API credentials in .env")
    risk_manager = RiskManager(config.settings.get("risk", {}))
    order_manager = OrderManager(broker, risk_manager, logger)
    sizer = PositionSizer(
        max_position_fraction=float(config.settings.get("risk", {}).get("max_position_size", 0.20)),
        default_risk_fraction=float(config.settings.get("risk", {}).get("risk_per_trade", 0.01)),
    )
    strategy = build_strategy(args.strategy, config.strategies.get(args.strategy, {}))

    iterations = int(config.settings.get("paper_max_iterations", 1))
    interval = int(config.settings.get("paper_loop_interval_seconds", 60))
    for iteration in range(iterations):
        data = data_provider.get_history(args.asset, asset_type_name, timeframe, limit)
        latest_price = float(data["close"].iloc[-1])
        if hasattr(broker, "set_price"):
            broker.set_price(args.asset, latest_price)
        signal = strategy.generate_signal(data)
        account = broker.get_account()
        volatility = float(data["close"].pct_change().rolling(20).std().iloc[-1] or 0.0)
        quantity = sizer.percent_of_portfolio(account.equity, latest_price)
        market = MarketContext(price=latest_price, slippage=float(execution_cfg.get("slippage_rate", 0.0005)), volatility=volatility)
        portfolio = PortfolioContext(equity=account.equity, open_trades=len(broker.get_positions()))
        logger.info("Paper iteration %s signal=%s price=%s equity=%s", iteration + 1, signal, latest_price, account.equity)
        if signal.action in {SignalAction.BUY, SignalAction.SELL}:
            if signal.action == SignalAction.SELL:
                positions = broker.get_positions()
                possible_symbols = {
                    args.asset,
                    args.asset.replace("/", ""),
                    args.asset.split("/")[0],
                }
                if not any(symbol in positions for symbol in possible_symbols):
                    logger.info("Skipping sell signal for %s because no long position exists", args.asset)
                    continue
            side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL
            order = OrderRequest(symbol=args.asset, side=side, quantity=quantity, asset_type=asset_type)
            result = order_manager.submit(order, market, portfolio)
            print(result)
        if iteration < iterations - 1:
            time.sleep(interval)


def run_live_guardrails(args: argparse.Namespace, config, logger: logging.Logger) -> None:
    broker_cfg = config.settings.get("broker", {})
    broker_name = str(broker_cfg.get("name", "paper")).lower()
    if broker_name == "paper":
        raise PermissionError("Live mode cannot use PaperBroker. Configure alpaca, binance, or interactive_brokers.")

    print("LIVE TRADING PRE-CHECK")
    for key in sorted(config.settings):
        value = config.settings[key]
        if "key" in key.lower() or "secret" in key.lower():
            value = "***"
        print(f"{key}: {value}")

    if os.getenv("LIVE_TRADING", "false").lower() != "true":
        raise PermissionError("LIVE_TRADING=true is required in the environment.")

    broker = build_broker(config)
    if not broker.validate_credentials():
        raise PermissionError(f"{broker_name} credentials are missing or invalid.")

    account = broker.get_account()
    if account.buying_power <= 0:
        raise PermissionError("Account buying power must be positive.")

    risk_cfg = config.settings.get("risk", {})
    if float(risk_cfg.get("risk_per_trade", 1.0)) > 0.02:
        raise PermissionError("risk_per_trade above 2% is refused for live mode.")

    confirmation = input(f"Type LIVE TRADE {args.asset} to enable live trading checks: ")
    if confirmation != f"LIVE TRADE {args.asset}":
        raise PermissionError("Live trading confirmation did not match.")

    logger.critical("Live pre-checks passed for %s using %s, but order submission remains adapter-controlled.", args.asset, broker_name)
    raise NotImplementedError("Live order execution adapters are intentionally disabled until implemented and reviewed.")


def main() -> None:
    args = parse_args()
    config = ConfigLoader(ROOT_DIR).load()
    if args.mode:
        config.settings["mode"] = args.mode
    if args.broker:
        config.settings.setdefault("broker", {})["name"] = args.broker
    if args.mode or args.broker:
        ConfigLoader.validate_safety(config)
    logger = setup_logger(config.root_dir)

    if config.settings.get("mode") == "live":
        run_live_guardrails(args, config, logger)
    elif config.settings.get("mode") == "account":
        run_account_check(args, config, logger)
    elif config.settings.get("mode") == "quote":
        run_quote(args, config, logger)
    elif config.settings.get("mode") == "backtest":
        run_backtest(args, config, logger)
    else:
        run_paper(args, config, logger)


if __name__ == "__main__":
    main()
