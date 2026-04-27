"""Run the autonomous paper bot from the terminal."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from automation.bot_runner import AutoBotConfig, AutoPaperBot
from automation.runtime_store import RuntimeStore
from config_loader import ConfigLoader
from logger import setup_logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run autonomous Alpaca/Coinbase paper trading")
    parser.add_argument("--broker", default="alpaca", choices=["alpaca", "coinbase", "paper"])
    parser.add_argument("--symbols", default="AAPL,SPY,QQQ")
    parser.add_argument("--strategy", default="momentum", choices=["momentum", "mean_reversion", "breakout", "ai_signal"])
    parser.add_argument("--timeframe", default="1h")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--cycles", type=int, default=0, help="0 means run until stopped")
    parser.add_argument("--preview", action="store_true", help="Generate decisions but do not submit paper orders")
    parser.add_argument("--ignore-market-hours", action="store_true")
    parser.add_argument("--clear-kill-switch", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = ConfigLoader(ROOT_DIR).load()
    config.settings["mode"] = "paper"
    config.settings["live_trading"] = False
    config.settings.setdefault("broker", {})["name"] = args.broker

    store = RuntimeStore(ROOT_DIR)
    if args.clear_kill_switch:
        store.clear_kill_switch()

    symbols = [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
    if not symbols:
        raise ValueError("At least one symbol is required")

    bot_config = AutoBotConfig(
        root_dir=ROOT_DIR,
        settings=config.settings,
        strategies=config.strategies,
        broker_name=args.broker,
        symbols=symbols,
        strategy_name=args.strategy,
        timeframe=args.timeframe,
        limit=args.limit,
        interval_seconds=args.interval,
        submit_orders=not args.preview,
        market_hours_only=not args.ignore_market_hours,
        max_cycles=args.cycles or None,
    )
    logger = setup_logger(ROOT_DIR)
    logger.info(
        "Starting autonomous paper bot broker=%s symbols=%s strategy=%s preview=%s",
        args.broker,
        symbols,
        args.strategy,
        args.preview,
    )
    bot = AutoPaperBot(bot_config, logger)
    bot.run_forever()


if __name__ == "__main__":
    main()

