# Trading Bot Framework

Production-oriented Python framework for backtesting and paper trading crypto, stocks, and defined-risk options strategies.

## Critical Risk Warning

This software is not financial advice. Trading stocks, crypto, and options can lose money quickly, including more than expected in volatile markets or with implementation/configuration errors. Live trading is disabled by default and should only be enabled after independent review, paper-trading validation, broker permission checks, and explicit user confirmation.

The default mode is `paper`. The system refuses live mode unless all of these are true:

- `LIVE_TRADING=true` is set in `.env`
- `config/settings.yaml` has `mode: live`
- `live_trading: true`
- `user_confirm_live: true`
- `broker.allow_live: true`
- pre-trade risk checks approve every order

Live broker order submission adapters are placeholders by design. Extend them deliberately and keep the risk manager in the execution path.

## Project Layout

```text
trading_bot/
  config/              YAML settings, symbols, and strategy parameters
  src/                 Application code
  tests/               Deterministic pytest suite
  logs/                Runtime logs, created automatically
  backtest_results/    Backtest exports, created automatically
```

## VS Code Setup

Open the `trading_bot` folder in VS Code.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Select `.venv` as the Python interpreter in VS Code.

## Configuration

Edit these files:

- `config/settings.yaml`: mode, broker settings, risk limits, fees, slippage, cash
- `config/symbols.yaml`: crypto pairs, stocks, and option contract templates
- `config/strategies.yaml`: strategy parameters
- `.env`: API credentials only; never hardcode secrets in source

Safe default settings:

```yaml
mode: paper
live_trading: false
starting_cash: 100000
default_timeframe: "1h"
risk:
  risk_per_trade: 0.01
  max_daily_loss: 0.03
  max_drawdown: 0.10
```

## Run Backtests

From the `trading_bot` directory:

```powershell
python src/main.py --mode backtest --strategy momentum --asset BTC/USD
python src/main.py --mode backtest --strategy mean_reversion --asset SPY
python src/main.py --mode backtest --strategy breakout --asset ETH/USD
```

Backtests export:

- `equity_curve.csv`
- `trades.csv`
- `metrics.csv`
- `equity_curve.png`

Network data uses `yfinance` for stocks and `ccxt` for crypto. If a data provider fails during a smoke run, the framework falls back to deterministic synthetic data and logs the reason.

Crypto market data defaults to Coinbase in `config/settings.yaml`:

```yaml
market_data:
  crypto_exchange: coinbase
```

## Run Paper Trading

```powershell
python src/main.py --mode paper --strategy ai_signal --asset AAPL
python src/main.py --mode paper --strategy breakout --asset ETH/USD
```

Paper mode uses `PaperBroker`, simulated fills, fees, slippage, position tracking, risk validation, and logs every signal/order decision to `logs/trading_bot.log`.

## Dashboard UI

For a non-technical operator view, run the Streamlit dashboard:

```powershell
cd C:\Users\Admin\Documents\Trading_Robot\trading_bot
streamlit run src/dashboard.py
```

The dashboard shows:

- paper account cash, equity, buying power, and positions
- broker connection status
- quote chart and latest strategy signal
- one-click backtest metrics
- a guarded paper-trading action button
- autonomous Start/Stop controls
- multi-symbol scanning
- market-hours-only stock execution
- emergency kill switch
- persistent trade and decision history
- recent logs

Paper order submission from the dashboard requires enabling the paper order checkbox. Live trading remains disabled by config.

### Autonomous Paper Mode

Open the dashboard, choose:

- Broker: `alpaca`
- Symbols: for example `AAPL, SPY, QQQ`
- Strategy: `momentum`, `mean_reversion`, `breakout`, or `ai_signal`
- Loop interval: at least 15 seconds

Then click **Start Autonomous Bot**. The worker will keep scanning while the Streamlit server is running. Click **Stop Bot** to stop normal automation, or **Emergency Kill Switch** to block future automation until the kill switch is cleared.

Automation guardrails:

- paper mode only
- `LIVE_TRADING=false`
- daily loss lockout
- max drawdown lockout
- no duplicate buy if a position already exists
- no sell if no long position exists
- stock market-hours filter
- all orders still pass through `RiskManager`

### Broker-Hosted Demo Money

For a real trading app with demo money, use a broker's official paper/sandbox environment.

Alpaca is the recommended first integration for stocks and options paper trading:

1. Create an Alpaca Trading API account.
2. Switch to the Paper Trading account in Alpaca.
3. Generate paper API keys.
4. Put them in `.env`:

```text
LIVE_TRADING=false
ALPACA_API_KEY=your_paper_key
ALPACA_SECRET_KEY=your_paper_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

Then verify account connectivity:

```powershell
python src/main.py --mode account --broker alpaca --strategy momentum --asset AAPL
```

Then run automated broker-hosted paper trading:

```powershell
python src/main.py --mode paper --broker alpaca --strategy momentum --asset AAPL
```

With `--broker alpaca`, paper mode submits approved orders to Alpaca's paper account. With no broker override, paper mode stays local and uses `PaperBroker`.

Coinbase crypto sandbox is also supported for market and GTC limit crypto orders. Create Coinbase sandbox API credentials, then set:

```text
COINBASE_KEY_FILE=C:\path\to\coinbase_sandbox_key.json
```

or:

```text
COINBASE_API_KEY=organizations/...
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----...
```

Then run:

```powershell
python src/main.py --mode account --broker coinbase --strategy momentum --asset BTC/USD
python src/main.py --mode paper --broker coinbase --strategy momentum --asset BTC/USD
```

Coinbase config defaults to `api-sandbox.coinbase.com`. To point Coinbase at live trading later, you must change the config and pass the live trading guardrails.

## Real Broker Connectivity

Use `quote` mode for real public market data without account credentials:

```powershell
python src/main.py --mode quote --broker coinbase --strategy momentum --asset BTC/USD --limit 5
```

Use `account` mode to verify authenticated broker connectivity. For Coinbase, first add keys to `.env`:

```text
COINBASE_API_KEY=organizations/...
COINBASE_API_SECRET=-----BEGIN EC PRIVATE KEY-----...
```

Or use a Coinbase key-file path:

```text
COINBASE_KEY_FILE=C:\Users\Admin\Documents\Trading_Robot\coinbase_key.json
```

Then run:

```powershell
python src/main.py --mode account --broker coinbase --strategy momentum --asset BTC/USD
```

`account` mode reads account information but does not place trades. Fidelity account/trading connectivity remains disabled unless you provide an official or contracted API implementation.

## Strategies

Implemented:

- `momentum`: short/long moving-average crossover
- `mean_reversion`: RSI plus Bollinger Bands
- `breakout`: range breakout with volume confirmation
- `options`: long call, long put, and vertical spread risk profile framework
- `ai_signal`: scikit-learn classifier with engineered price/volume/volatility/trend features, chronological train/test split, walk-forward generation, and confidence threshold

## Brokers

Implemented interfaces:

- `PaperBroker`: local simulation
- `AlpacaBroker`: account adapter and safe disabled order placeholder
- `BinanceBroker`: ccxt-backed account/price adapter and safe disabled order placeholder
- `CoinbaseBroker`: Coinbase Advanced Trade adapter shell using the official Python SDK, with live order submission disabled until reviewed
- `InteractiveBrokersBroker`: placeholder for IB account, stock, and options extension
- `FidelityBroker`: safe extension point only; refuses trading unless backed by an official or contracted API implementation
- `custom`: dynamic class-path loader for any broker/exchange adapter that inherits from `BaseBroker`

Select a broker in `config/settings.yaml`:

```yaml
broker:
  name: coinbase
```

Or override it from the CLI:

```powershell
python src/main.py --mode paper --broker coinbase --strategy momentum --asset BTC/USD
```

Paper mode still uses `PaperBroker` for execution by default, even if you pass `--broker coinbase`, so strategy testing does not touch a real account. Live mode requires explicit live settings and still refuses order submission until the broker adapter is completed and reviewed.

Broker API keys are read from environment variables:

```text
ALPACA_API_KEY
ALPACA_SECRET_KEY
BINANCE_API_KEY
BINANCE_SECRET_KEY
COINBASE_API_KEY
COINBASE_API_SECRET
IB_HOST
IB_PORT
IB_CLIENT_ID
```

For additional brokers, implement a class that inherits from `brokers.base_broker.BaseBroker`, then configure:

```yaml
broker:
  name: custom
  custom:
    class_path: "my_brokers.schwab_adapter:SchwabBroker"
    kwargs:
      account_id: "..."
```

Do not connect brokers through browser automation, scraped endpoints, or stored website passwords. That is brittle and unsafe for automated trading.

## Risk Management

The `RiskManager` runs before every submitted order and checks:

- max risk per trade
- max daily loss
- max drawdown
- max position size
- max open trades
- spread, slippage, and volatility limits
- earnings window block for stocks unless allowed
- options max loss requirement

The default posture is conservative. Options trades without defined `max_loss` are rejected.

## Tests

```powershell
pytest -q
```

The suite covers risk management, position sizing, order validation, strategy signals, and backtesting metrics.

## Extending Toward Live Trading

Keep live trading behind explicit configuration and a terminal confirmation step. Before adding broker order submission, implement:

- account buying-power validation
- symbol permission validation
- market-hours/session checks
- broker-side order status reconciliation
- idempotent order IDs
- kill switch and daily loss lockout persistence
- integration tests against broker paper environments

Never bypass `OrderManager` or `RiskManager` for any broker.
