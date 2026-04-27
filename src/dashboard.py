"""Streamlit dashboard for the trading bot."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = Path(__file__).resolve().parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from backtesting.backtest_engine import BacktestEngine
from automation.bot_runner import AutoBotConfig, AutoPaperBot
from automation.runtime_store import RuntimeStore
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


STRATEGIES = {
    "momentum": MomentumStrategy,
    "mean_reversion": MeanReversionStrategy,
    "breakout": BreakoutStrategy,
    "options": OptionsStrategy,
    "ai_signal": AISignalStrategy,
}

SYMBOL_PRESETS = {
    "Stocks": ["AAPL", "SPY", "QQQ", "NVDA", "TSLA"],
    "Crypto": ["BTC/USD", "ETH/USD", "SOL/USD"],
}


def load_config() -> Any:
    config = ConfigLoader(ROOT_DIR).load()
    config.settings["mode"] = "paper"
    config.settings["live_trading"] = False
    return config


def runtime_store() -> RuntimeStore:
    return RuntimeStore(ROOT_DIR)


def build_strategy(name: str, params: dict[str, Any]):
    return STRATEGIES[name](params)


def broker_for(config: Any, broker_name: str, latest_price: float | None = None, symbol: str | None = None):
    config.settings.setdefault("broker", {})["name"] = broker_name
    prices = {symbol: latest_price} if symbol and latest_price is not None else None
    return BrokerFactory.create(config.settings, prices=prices, force_paper=broker_name == "paper")


def market_data_for(config: Any, broker_name: str, logger) -> MarketDataProvider:
    market_cfg = config.settings.get("market_data", {})
    crypto_exchange = str(market_cfg.get("crypto_exchange") or broker_name or "coinbase")
    if crypto_exchange == "coinbase_advanced_trade":
        crypto_exchange = "coinbase"
    return MarketDataProvider(logger=logger, crypto_exchange=crypto_exchange)


def format_money(value: float | None) -> str:
    if value is None:
        return "-"
    return f"${value:,.2f}"


def status_badge(label: str, state: str) -> str:
    colors = {
        "ok": ("#0f766e", "#e6fffb"),
        "warn": ("#a16207", "#fff7d6"),
        "bad": ("#b91c1c", "#fee2e2"),
        "neutral": ("#334155", "#f1f5f9"),
    }
    fg, bg = colors[state]
    return f"<span class='status' style='color:{fg};background:{bg}'>{label}</span>"


def apply_theme() -> None:
    st.set_page_config(page_title="AI Robot Trading", page_icon=None, layout="wide")
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.25rem; max-width: 1500px; }
        h1, h2, h3 { letter-spacing: 0; }
        .hero {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            padding: 18px 20px;
            background: #ffffff;
            margin-bottom: 14px;
        }
        .hero-title { font-size: 28px; font-weight: 750; color: #111827; margin: 0; }
        .hero-subtitle { color: #475569; margin-top: 6px; font-size: 15px; }
        .status {
            display: inline-block;
            border-radius: 999px;
            padding: 4px 10px;
            font-size: 13px;
            font-weight: 650;
            margin-right: 6px;
            margin-top: 8px;
        }
        .section {
            border: 1px solid #d8dee8;
            border-radius: 8px;
            background: #ffffff;
            padding: 14px 16px;
            margin-bottom: 14px;
        }
        .section-title {
            font-size: 16px;
            font-weight: 750;
            margin-bottom: 10px;
            color: #111827;
        }
        .small-muted { color: #64748b; font-size: 13px; }
        div[data-testid="stMetric"] {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 10px 12px;
            background: #fbfdff;
        }
        .stButton > button {
            border-radius: 6px;
            min-height: 42px;
            font-weight: 700;
        }
        .stDataFrame { border: 1px solid #e2e8f0; border-radius: 8px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(broker_name: str, account_ok: bool, live_trading: bool) -> None:
    mode_state = "bad" if live_trading else "ok"
    account_state = "ok" if account_ok else "warn"
    st.markdown(
        f"""
        <div class='hero'>
          <div class='hero-title'>AI Robot Trading Dashboard</div>
          <div class='hero-subtitle'>Paper trading control center for quotes, signals, account checks, backtests, and broker demo orders.</div>
          {status_badge("Paper mode active" if not live_trading else "Live mode flag detected", mode_state)}
          {status_badge(f"Broker: {broker_name}", "neutral")}
          {status_badge("Account connected" if account_ok else "Account not checked", account_state)}
          {status_badge("Autonomous worker available", "neutral")}
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_account_snapshot(config: Any, broker_name: str) -> tuple[dict[str, Any], bool]:
    try:
        broker = broker_for(config, broker_name)
        if not broker.validate_credentials() and broker.name != "paper":
            return {"error": f"{broker.name} credentials are missing in .env"}, False
        account = broker.get_account()
        positions = broker.get_positions()
        return {
            "cash": account.cash,
            "equity": account.equity,
            "buying_power": account.buying_power,
            "currency": account.currency,
            "positions": positions,
        }, True
    except Exception as exc:
        return {"error": str(exc)}, False


def render_account(account: dict[str, Any], account_ok: bool) -> None:
    st.markdown("<div class='section-title'>Account</div>", unsafe_allow_html=True)
    if not account_ok:
        st.warning(account.get("error", "Account is not connected."))
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Equity", format_money(account["equity"]))
    col2.metric("Cash", format_money(account["cash"]))
    col3.metric("Buying Power", format_money(account["buying_power"]))
    col4.metric("Open Positions", len(account["positions"]))


def render_positions(account: dict[str, Any], account_ok: bool) -> None:
    st.markdown("<div class='section-title'>Positions</div>", unsafe_allow_html=True)
    if not account_ok:
        st.info("Connect a broker account to view positions.")
        return
    positions = account["positions"]
    if not positions:
        st.info("No open positions.")
        return
    rows = [
        {
            "Symbol": pos.symbol,
            "Quantity": pos.quantity,
            "Average Price": pos.average_price,
            "Asset Type": pos.asset_type.value,
        }
        for pos in positions.values()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_market_and_signal(config: Any, logger, broker_name: str, symbol: str, strategy_name: str, timeframe: str, limit: int):
    provider = market_data_for(config, broker_name, logger)
    asset_type = infer_asset_type(symbol)
    data = provider.get_history(symbol, asset_type, timeframe, limit)
    strategy = build_strategy(strategy_name, config.strategies.get(strategy_name, {}))
    signal = strategy.generate_signal(data)
    latest_price = float(data["close"].iloc[-1])

    st.markdown("<div class='section-title'>Market And Signal</div>", unsafe_allow_html=True)
    price_col, signal_col, confidence_col, rows_col = st.columns(4)
    price_col.metric("Last Price", format_money(latest_price))
    signal_col.metric("Signal", signal.action.value)
    confidence_col.metric("Confidence", f"{signal.confidence:.0%}")
    rows_col.metric("Bars Loaded", len(data))

    chart_data = data[["close"]].rename(columns={"close": "Close"})
    st.line_chart(chart_data, height=290)
    st.caption(signal.reason)
    return data, signal, latest_price


def run_backtest(config: Any, data: pd.DataFrame, strategy_name: str) -> Any:
    execution_cfg = config.settings.get("execution", {})
    engine = BacktestEngine(
        starting_cash=float(config.settings.get("starting_cash", 100000)),
        fee_rate=float(execution_cfg.get("fee_rate", 0.001)),
        slippage_rate=float(execution_cfg.get("slippage_rate", 0.0005)),
        allocation_fraction=float(config.settings.get("risk", {}).get("max_position_size", 0.20)),
    )
    strategy = build_strategy(strategy_name, config.strategies.get(strategy_name, {}))
    return engine.run(data, strategy)


def render_backtest(config: Any, data: pd.DataFrame, strategy_name: str) -> None:
    st.markdown("<div class='section-title'>Backtest</div>", unsafe_allow_html=True)
    if st.button("Run Backtest", use_container_width=True):
        with st.spinner("Running backtest..."):
            result = run_backtest(config, data, strategy_name)
        metrics = result.metrics
        cols = st.columns(5)
        cols[0].metric("Total Return", f"{metrics.get('total_return', 0):.2%}")
        cols[1].metric("Sharpe", f"{metrics.get('sharpe_ratio', 0):.2f}")
        cols[2].metric("Max Drawdown", f"{metrics.get('max_drawdown', 0):.2%}")
        cols[3].metric("Win Rate", f"{metrics.get('win_rate', 0):.2%}")
        cols[4].metric("Trades", f"{int(metrics.get('number_of_trades', 0))}")
        st.line_chart(result.equity_curve.rename("Equity"), height=250)
        if not result.trades.empty:
            st.dataframe(result.trades, use_container_width=True, hide_index=True)


def run_paper_cycle(
    config: Any,
    broker_name: str,
    symbol: str,
    data: pd.DataFrame,
    signal,
    latest_price: float,
    submit_order: bool,
) -> dict[str, Any]:
    broker = broker_for(config, broker_name, latest_price=latest_price, symbol=symbol)
    if not broker.validate_credentials() and broker.name != "paper":
        return {"status": "blocked", "message": f"{broker.name} credentials are missing in .env"}

    if hasattr(broker, "set_price"):
        broker.set_price(symbol, latest_price)

    account = broker.get_account()
    positions = broker.get_positions()
    volatility_raw = data["close"].pct_change().rolling(20).std().iloc[-1]
    volatility = float(0.0 if pd.isna(volatility_raw) else volatility_raw)
    sizer = PositionSizer(
        max_position_fraction=float(config.settings.get("risk", {}).get("max_position_size", 0.20)),
        default_risk_fraction=float(config.settings.get("risk", {}).get("risk_per_trade", 0.01)),
    )
    quantity = sizer.percent_of_portfolio(account.equity, latest_price)

    if signal.action == SignalAction.HOLD:
        return {"status": "no_order", "message": "Strategy is HOLD. No order was submitted."}
    if signal.action == SignalAction.SELL:
        possible_symbols = {symbol, symbol.replace("/", ""), symbol.split("/")[0]}
        if not any(candidate in positions for candidate in possible_symbols):
            return {"status": "no_order", "message": "Sell signal ignored because there is no open long position."}
    if not submit_order:
        return {
            "status": "preview",
            "message": f"Preview only: {signal.action.value} {quantity:.6f} {symbol} at about {latest_price:.2f}",
        }

    risk_manager = RiskManager(config.settings.get("risk", {}))
    order_manager = OrderManager(broker, risk_manager, setup_logger(ROOT_DIR))
    side = OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL
    order = OrderRequest(symbol=symbol, side=side, quantity=quantity, asset_type=AssetType(infer_asset_type(symbol)))
    market = MarketContext(
        price=latest_price,
        slippage=float(config.settings.get("execution", {}).get("slippage_rate", 0.0005)),
        volatility=volatility,
    )
    portfolio = PortfolioContext(equity=account.equity, open_trades=len(positions))
    result = order_manager.submit(order, market, portfolio)
    return {
        "status": result.status.value,
        "message": result.message,
        "order_id": result.order_id,
        "filled_quantity": result.filled_quantity,
        "average_price": result.average_price,
    }


def render_paper_action(config: Any, broker_name: str, symbol: str, data: pd.DataFrame, signal, latest_price: float) -> None:
    st.markdown("<div class='section-title'>Paper Trade Action</div>", unsafe_allow_html=True)
    submit_order = st.checkbox("Submit approved paper order when signal is BUY or SELL", value=False)
    if st.button("Run One Paper Cycle", use_container_width=True):
        with st.spinner("Checking risk and paper execution..."):
            result = run_paper_cycle(config, broker_name, symbol, data, signal, latest_price, submit_order)
        if result["status"] in {"filled", "new"}:
            st.success(result)
        elif result["status"] == "preview":
            st.info(result["message"])
        elif result["status"] == "no_order":
            st.info(result["message"])
        else:
            st.warning(result)


def bot_is_running() -> bool:
    thread = st.session_state.get("bot_thread")
    return bool(thread and thread.is_alive())


def start_bot(
    config: Any,
    broker_name: str,
    symbols: list[str],
    strategy_name: str,
    timeframe: str,
    limit: int,
    interval_seconds: int,
    submit_orders: bool,
    market_hours_only: bool,
) -> None:
    if bot_is_running():
        return
    stop_event = threading.Event()
    state: dict[str, Any] = {}
    auto_config = AutoBotConfig(
        root_dir=ROOT_DIR,
        settings=config.settings,
        strategies=config.strategies,
        broker_name=broker_name,
        symbols=symbols,
        strategy_name=strategy_name,
        timeframe=timeframe,
        limit=limit,
        interval_seconds=interval_seconds,
        submit_orders=submit_orders,
        market_hours_only=market_hours_only,
        max_cycles=None,
    )
    bot = AutoPaperBot(auto_config, setup_logger(ROOT_DIR), stop_event=stop_event, state=state)
    thread = threading.Thread(target=bot.run_forever, name="auto-paper-bot", daemon=True)
    st.session_state["bot_stop_event"] = stop_event
    st.session_state["bot_state"] = state
    st.session_state["bot_thread"] = thread
    thread.start()


def stop_bot() -> None:
    stop_event = st.session_state.get("bot_stop_event")
    if stop_event:
        stop_event.set()


def render_autonomous_control(
    config: Any,
    broker_name: str,
    selected_symbol: str,
    strategy_name: str,
    timeframe: str,
    limit: int,
) -> None:
    store = runtime_store()
    st.markdown("<div class='section-title'>Autonomous Paper Bot</div>", unsafe_allow_html=True)
    running = bot_is_running()
    state = st.session_state.get("bot_state", {})

    status_cols = st.columns(4)
    status_cols[0].metric("Worker", "Running" if running else "Stopped")
    status_cols[1].metric("Cycles", state.get("cycle_count", 0))
    status_cols[2].metric("Last Run", state.get("last_run_at", "-"))
    status_cols[3].metric("Kill Switch", "ON" if store.kill_switch_active() else "OFF")

    symbol_text = st.text_input("Symbols To Scan", value=selected_symbol, help="Comma-separated, for example AAPL, SPY, QQQ")
    symbols = [item.strip().upper() for item in symbol_text.split(",") if item.strip()]
    if not symbols:
        symbols = [selected_symbol]
    interval_seconds = st.number_input("Loop Interval Seconds", min_value=15, max_value=3600, value=60, step=15)
    submit_orders = st.checkbox("Allow automatic paper order submission", value=True)
    market_hours_only = st.checkbox("Trade stocks only during regular market hours", value=True)

    col1, col2, col3 = st.columns(3)
    if col1.button("Start Autonomous Bot", disabled=running, use_container_width=True):
        start_bot(
            config,
            broker_name,
            symbols,
            strategy_name,
            timeframe,
            limit,
            int(interval_seconds),
            bool(submit_orders),
            bool(market_hours_only),
        )
        st.rerun()
    if col2.button("Stop Bot", disabled=not running, use_container_width=True):
        stop_bot()
        st.rerun()
    if col3.button("Emergency Kill Switch", use_container_width=True):
        stop_bot()
        store.activate_kill_switch("manual dashboard kill switch")
        st.rerun()

    if store.kill_switch_active():
        st.error(f"Kill switch active: {store.kill_switch_reason()}")
        if st.button("Clear Kill Switch", use_container_width=True):
            store.clear_kill_switch()
            st.rerun()

    last_message = state.get("last_message", "No autonomous run yet.")
    st.caption(last_message)
    if running:
        st.info("Leave this Streamlit server running. Closing the terminal stops the bot.")


def render_logs() -> None:
    st.markdown("<div class='section-title'>Recent Logs</div>", unsafe_allow_html=True)
    log_path = ROOT_DIR / "logs" / "trading_bot.log"
    if not log_path.exists():
        st.info("No logs yet.")
        return
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()[-80:]
    st.code("\n".join(lines), language="text")


def render_trade_history() -> None:
    st.markdown("<div class='section-title'>Trade And Decision History</div>", unsafe_allow_html=True)
    rows = runtime_store().read_events(limit=200)
    if not rows:
        st.info("No autonomous decisions recorded yet.")
        return
    frame = pd.DataFrame(rows)
    st.dataframe(frame, use_container_width=True, hide_index=True)


def sidebar_controls(config: Any) -> tuple[str, str, str, str, int]:
    st.sidebar.title("Controls")
    broker_name = st.sidebar.selectbox("Broker", ["alpaca", "paper", "coinbase"], index=0)
    preset_group = st.sidebar.radio("Asset Group", list(SYMBOL_PRESETS), horizontal=True)
    default_symbol = SYMBOL_PRESETS[preset_group][0]
    symbol = st.sidebar.selectbox("Symbol", SYMBOL_PRESETS[preset_group], index=0)
    custom_symbol = st.sidebar.text_input("Custom Symbol", value="")
    if custom_symbol.strip():
        symbol = custom_symbol.strip().upper()
    strategy_name = st.sidebar.selectbox("Strategy", list(STRATEGIES), index=0)
    timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "1d"], index=3)
    limit = st.sidebar.slider("Historical Bars", min_value=80, max_value=1000, value=int(config.settings.get("data_lookback_bars", 500)), step=20)
    st.sidebar.caption(f"Default symbol: {default_symbol}")
    st.sidebar.divider()
    st.sidebar.write("Safety")
    st.sidebar.write("Live trading is off.")
    st.sidebar.write("Paper account or local simulator only.")
    return broker_name, symbol, strategy_name, timeframe, limit


def main() -> None:
    apply_theme()
    config = load_config()
    logger = setup_logger(ROOT_DIR)
    broker_name, symbol, strategy_name, timeframe, limit = sidebar_controls(config)

    account, account_ok = get_account_snapshot(config, broker_name)
    render_header(broker_name, account_ok, bool(config.settings.get("live_trading", False)))

    account_col, positions_col = st.columns([1.2, 1])
    with account_col:
        render_account(account, account_ok)
    with positions_col:
        render_positions(account, account_ok)

    try:
        data, signal, latest_price = render_market_and_signal(config, logger, broker_name, symbol, strategy_name, timeframe, limit)
    except Exception as exc:
        st.error(f"Market data or signal failed: {exc}")
        return

    action_col, backtest_col = st.columns([0.9, 1.1])
    with action_col:
        render_autonomous_control(config, broker_name, symbol, strategy_name, timeframe, limit)
        render_paper_action(config, broker_name, symbol, data, signal, latest_price)
    with backtest_col:
        render_backtest(config, data, strategy_name)

    render_trade_history()
    render_logs()


if __name__ == "__main__":
    main()
