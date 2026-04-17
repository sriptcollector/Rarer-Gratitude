import logging
import time
import ccxt
import pandas as pd

log = logging.getLogger("feed")


class DataFeed:
    def __init__(self, exchange_id: str, timeframe: str):
        cls = getattr(ccxt, exchange_id)
        self.ex = cls({"enableRateLimit": True})
        self.timeframe = timeframe
        delay = 5
        while True:
            try:
                self.ex.load_markets()
                break
            except Exception as e:
                log.warning("load_markets failed, retrying in %ds: %s", delay, e)
                time.sleep(delay)
                delay = min(delay * 2, 120)

    def top_symbols(self, quote: str, limit: int, min_vol_usd: float) -> list[str]:
        delay = 5
        while True:
            try:
                tickers = self.ex.fetch_tickers()
                break
            except Exception as e:
                log.warning("fetch_tickers failed, retrying in %ds: %s", delay, e)
                time.sleep(delay)
                delay = min(delay * 2, 120)
        rows = []
        for sym, t in tickers.items():
            if not sym.endswith(f"/{quote}"):
                continue
            m = self.ex.markets.get(sym)
            if not m or not m.get("spot", True) or not m.get("active", True):
                continue
            qv = t.get("quoteVolume") or 0
            if qv < min_vol_usd:
                continue
            rows.append((sym, qv))
        rows.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in rows[:limit]]

    def fetch_ohlcv(self, symbol: str, limit: int = 500) -> pd.DataFrame:
        for attempt in range(3):
            try:
                ohlcv = self.ex.fetch_ohlcv(symbol, timeframe=self.timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
                df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
                return df
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
