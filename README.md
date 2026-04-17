# Crypto Paper-Trading Bot

Live paper-trades ~95 strategies (10 base patterns × parameter sweeps) across the top N liquid spot pairs on an exchange via `ccxt`. Ranks strategies by expectancy, win rate, profit factor, and drawdown. Persists trades + rolling metrics to SQLite.

## Strategies included

- EMA crossover (trend)
- RSI mean reversion
- Bollinger breakout / reversion
- Donchian breakout
- MACD momentum
- Keltner breakout
- Supertrend
- Momentum (ROC threshold)
- VWAP reversion (z-score)

Each is instantiated across a parameter grid (~95 total configs).

## Local run

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Logs the top 10 by expectancy every `LOG_EVERY` ticks. Trades + metrics land in `data/bot.db` (SQLite).

## Deploy to Railway

1. Push this folder to a GitHub repo.
2. `railway init` → link to the repo (or use the web UI: New Project → Deploy from GitHub).
3. In the Railway project, set env vars from `.env.example` (all optional, defaults work).
4. Deploy. The `Procfile` runs `python main.py` as a worker.
5. Add a Railway volume mounted at `/app/data` if you want `bot.db` to persist across deploys.

## Important notes

- **Ranked by % return** on the simulated account, with win rate as tiebreaker. Expectancy, profit factor, and max drawdown are still tracked and written to SQLite so you can re-rank however you want.
- **Realistic costs**: 10 bps fee + 5 bps slippage are modeled per side by default. Real exchange rates may be lower, but this catches strategies that only work at zero cost.
- **Paper only**: there is no order-submission code to a live account. Positions are simulated at next-tick close price with slippage.
- **Rate limits**: fetching 50 symbols every 60s is well within Binance's public limits. Raise `POLL_SECONDS` or lower `MAX_SYMBOLS` if you see 418/429.
- **Warm-up**: strategies return "hold" until they have enough bars. Expect the first few ticks to produce no trades.

## Inspecting results

```bash
sqlite3 data/bot.db "SELECT strategy, trades, win_rate, expectancy, return_pct FROM metrics \
  WHERE ts = (SELECT MAX(ts) FROM metrics) ORDER BY expectancy DESC LIMIT 20;"
```

## Extending

- Add a strategy: subclass `Strategy` in `strategies/library.py`, implement `generate(df, in_position)`, add param combos to `strategies/registry.py`.
- Swap exchange: set `EXCHANGE=kraken` (or any ccxt-supported exchange). For multi-exchange, instantiate multiple `DataFeed`s.
- Forex: ccxt does not cover forex; wire in `oandapyV20` as a second feed if you want FX pairs.
