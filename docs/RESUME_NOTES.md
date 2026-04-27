# Resume Notes

## Suggested Resume Bullet

Built a Python automated trading platform with broker-agnostic execution, Alpaca paper trading integration, Coinbase sandbox support, risk-managed autonomous trading, backtesting, AI signal generation, Streamlit dashboard, SQLite audit history, Docker packaging, and GitHub Actions CI.

## Technical Highlights

- Python, pandas, scikit-learn, Streamlit, SQLite, Docker, GitHub Actions
- Broker abstraction for Alpaca, Coinbase, Binance, Interactive Brokers, Fidelity placeholder, and custom adapters
- Risk controls: per-trade risk, daily loss lockout, drawdown lockout, max position size, slippage/volatility filters
- Backtesting metrics: total return, CAGR, Sharpe, Sortino, max drawdown, win rate, profit factor
- Autonomous paper trading worker with market-hours guard, kill switch, and decision history

## Demo Checklist

1. Show dashboard connected to Alpaca paper account.
2. Show quote chart and signal generation.
3. Run a backtest and show metrics.
4. Start autonomous paper worker in preview mode.
5. Show SQLite-backed trade/decision history.
6. Show GitHub Actions passing.
7. Explain live-trading guardrails.

