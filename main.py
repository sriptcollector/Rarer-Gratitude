import os
import re
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

import config
from engine.data_feed import DataFeed
from engine.broker import PaperAccount, Trade
from engine.metrics import summarize
from engine.newsbot import NewsBot
from engine.state import state as shared_state
from strategies.registry import build_all
from strategies.explain import explain_trade
from strategies import indicators as ind_mod
from engine.evolve import maybe_evolve, EvoConfig
from storage import db


_fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
_root = logging.getLogger()
_root.setLevel(logging.INFO)
if not _root.handlers:
    _stream = logging.StreamHandler()
    _stream.setFormatter(_fmt)
    _root.addHandler(_stream)
    try:
        os.makedirs("logs", exist_ok=True)
        _rot = RotatingFileHandler("logs/bot.rotated.log",
                                   maxBytes=10 * 1024 * 1024, backupCount=5)
        _rot.setFormatter(_fmt)
        _root.addHandler(_rot)
    except Exception:
        pass
log = logging.getLogger("bot")


def position_qty(cash: float, price: float, risk_pct: float, stop: float | None) -> float:
    if not stop or stop >= price:
        return (cash * risk_pct) / price
    risk_per_unit = price - stop
    budget = cash * risk_pct
    return max(0.0, budget / risk_per_unit)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def main():
    log.info("Booting paper bot on %s %s (quote=%s min_vol=%s)",
             config.EXCHANGE, config.TIMEFRAME, config.QUOTE, config.MIN_VOL_USD)
    conn = db.init(config.DB_PATH)
    feed = DataFeed(config.EXCHANGE, config.TIMEFRAME)

    symbols = feed.top_symbols(config.QUOTE, config.MAX_SYMBOLS, config.MIN_VOL_USD)
    if not symbols:
        for alt_quote in ("USD", "USDC", "USDT"):
            if alt_quote == config.QUOTE:
                continue
            symbols = feed.top_symbols(alt_quote, config.MAX_SYMBOLS, config.MIN_VOL_USD)
            if symbols:
                log.info("Fell back to quote=%s (original %s returned nothing)",
                         alt_quote, config.QUOTE)
                break
    log.info("Trading %d symbols: %s", len(symbols),
             ", ".join(symbols[:10]) + ("..." if len(symbols) > 10 else ""))
    shared_state["symbols"] = symbols

    strategies = build_all()
    log.info("Loaded %d strategies", len(strategies))
    active: set[str] = {s.name for s in strategies}

    accounts: dict[str, PaperAccount] = {
        s.name: PaperAccount(
            strategy=s.name,
            cash=config.STARTING_CASH,
            equity=config.STARTING_CASH,
            fee_bps=config.FEE_BPS,
            slippage_bps=config.SLIPPAGE_BPS,
        )
        for s in strategies
    }

    # Rehydrate accounts from historical trades so stats survive restarts
    rehydrated = 0
    for name, acc in accounts.items():
        rows = conn.execute(
            "SELECT entry, exit, qty, pnl, entry_ts, exit_ts, reason, symbol "
            "FROM trades WHERE strategy=? ORDER BY id", (name,),
        ).fetchall()
        if not rows:
            continue
        equity = config.STARTING_CASH
        peak = equity
        for entry, exit_px, qty, pnl, ets, xts, reason, symbol in rows:
            acc.trades.append(Trade(
                strategy=name, symbol=symbol, side="long",
                entry=entry, exit=exit_px, qty=qty, pnl=pnl,
                entry_ts=ets or "", exit_ts=xts or "", reason=reason or "signal",
            ))
            equity += pnl
            if equity > peak:
                peak = equity
            if peak > 0:
                dd = (peak - equity) / peak
                if dd > acc.max_dd:
                    acc.max_dd = dd
        acc.cash = max(0.0, equity)
        acc.equity = acc.cash
        acc.peak = peak
        acc.equity_curve.append((now_iso(), config.STARTING_CASH))
        acc.equity_curve.append((now_iso(), acc.equity))
        rehydrated += 1
    log.info("Rehydrated %d accounts from trade history", rehydrated)

    # NewsBot runs in its own thread; shares a price snapshot with the main loop.
    shared_prices: dict[str, float] = {}
    active_syms = set(symbols)
    newsbot = NewsBot(conn, shared_prices, active_syms)
    accounts[NewsBot.NAME] = newsbot.account
    threading.Thread(
        target=newsbot.run, kwargs={"interval": int(os.getenv("NEWS_INTERVAL_S", "60"))},
        daemon=True, name="newsbot",
    ).start()

    tick = 0
    fetch_pool = ThreadPoolExecutor(max_workers=min(8, len(symbols) or 1))
    while True:
        t0 = time.time()
        tick += 1
        prices: dict[str, float] = {}
        bars: dict[str, object] = {}
        ind_mod.clear_cache()

        def _fetch(sym):
            try:
                df = feed.fetch_ohlcv(sym, limit=config.WARMUP_BARS + 5)
                return sym, df
            except Exception as e:
                log.warning("fetch %s failed: %s", sym, e)
                return sym, None

        for sym, df in fetch_pool.map(_fetch, symbols):
            if df is None or len(df) < 50:
                continue
            bars[sym] = df
            prices[sym] = float(df["close"].iloc[-1])
        shared_prices.clear()
        shared_prices.update(prices)

        ts = now_iso()

        for strat in strategies:
            if strat.name not in active:
                continue
            acc = accounts[strat.name]

            for sym, df in bars.items():
                pos = acc.positions.get(sym)
                hi = float(df["high"].iloc[-1])
                lo = float(df["low"].iloc[-1])
                closed = acc.check_stops(sym, hi, lo, ts)
                if closed:
                    closed.entry_ts = ts
                    db.insert_trade(conn, closed, explain_trade(strat.name, closed.side, closed.reason))

                in_pos = bool(pos and pos.is_open)
                try:
                    sig = strat.generate(df, in_pos)
                except Exception as e:
                    log.debug("strat %s err %s: %s", strat.name, sym, e)
                    continue

                px = float(df["close"].iloc[-1])
                if sig.action == "buy" and not in_pos:
                    qty = position_qty(acc.cash, px, config.RISK_PCT, sig.stop)
                    if qty > 0:
                        acc.open_long(sym, px, qty, ts, sig.stop, sig.take)
                elif sig.action == "buy" and in_pos:
                    qty = position_qty(acc.cash, px, config.RISK_PCT, sig.stop)
                    if qty > 0:
                        acc.add_long(sym, px, qty, ts, max_legs=config.MAX_LEGS)
                elif sig.action == "sell" and in_pos:
                    t = acc.close(sym, px, ts, reason="signal")
                    if t:
                        t.entry_ts = ts
                        db.insert_trade(conn, t, explain_trade(strat.name, "sell", "sell"))

            acc.mark(prices, ts)

        open_count = sum(1 for a in accounts.values() for p in a.positions.values() if p.is_open)
        try:
            with open(os.path.join(os.path.dirname(config.DB_PATH) or ".", "open_positions.txt"), "w") as f:
                f.write(str(open_count))
        except Exception:
            pass

        ranked = sorted(
            (summarize(a) for a in accounts.values()),
            key=lambda m: (m["return_pct"], m["win_rate"]),
            reverse=True,
        )
        db.upsert_metrics_batch(conn, ts, ranked)
        conn.commit()

        if tick % config.LOG_EVERY == 0:
            log.info("=== Top 10 by return %% (tick %d) ===", tick)
            for m in ranked[:10]:
                log.info(
                    "%-55s trades=%-4d return=%+.3f%% win=%.2f pf=%.2f dd=%.2f%%",
                    m["strategy"][:55], m["trades"], m["return_pct"],
                    m["win_rate"], m["profit_factor"], m["max_dd"] * 100,
                )

        try:
            maybe_evolve(strategies, accounts, active, conn, EvoConfig(
                period_s=int(os.getenv("EVO_PERIOD_S", str(24*60*60))),
            ))
        except Exception as e:
            log.warning("evolve error: %s", e)

        elapsed = time.time() - t0
        shared_state["last_tick_ts"] = ts
        shared_state["last_tick_ms"] = int(elapsed * 1000)
        shared_state["open_positions"] = open_count
        sleep_s = max(1.0, config.POLL_SECONDS - elapsed)
        log.debug("tick %d done in %.1fs, sleeping %.1fs", tick, elapsed, sleep_s)
        time.sleep(sleep_s)


def _supervised():
    backoff = 10
    while True:
        try:
            main()
        except KeyboardInterrupt:
            log.info("Shutdown requested")
            return
        except Exception as e:
            log.exception("Bot crashed: %s — restarting in %ds", e, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
        else:
            return


if __name__ == "__main__":
    _supervised()
