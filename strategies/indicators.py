import numpy as np
import pandas as pd

_cache: dict = {}


def clear_cache() -> None:
    _cache.clear()


def _memo(key, factory):
    v = _cache.get(key)
    if v is None:
        v = factory()
        _cache[key] = v
    return v


def sma(s: pd.Series, n: int) -> pd.Series:
    return _memo(("sma", id(s), n), lambda: s.rolling(n).mean())


def ema(s: pd.Series, n: int) -> pd.Series:
    return _memo(("ema", id(s), n),
                 lambda: s.ewm(span=n, adjust=False).mean())


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    def _calc():
        d = s.diff()
        up = d.clip(lower=0).rolling(n).mean()
        dn = (-d.clip(upper=0)).rolling(n).mean()
        rs = up / dn.replace(0, np.nan)
        return 100 - 100 / (1 + rs)
    return _memo(("rsi", id(s), n), _calc)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    def _calc():
        tr = pd.concat([
            df["high"] - df["low"],
            (df["high"] - df["close"].shift()).abs(),
            (df["low"] - df["close"].shift()).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(n).mean()
    return _memo(("atr", id(df), n), _calc)


def bollinger(s: pd.Series, n: int = 20, k: float = 2.0):
    def _calc():
        m = s.rolling(n).mean()
        sd = s.rolling(n).std()
        return m, m + k * sd, m - k * sd
    return _memo(("bol", id(s), n, k), _calc)


def macd(s: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    def _calc():
        line = ema(s, fast) - ema(s, slow)
        signal = ema(line, sig)
        return line, signal, line - signal
    return _memo(("macd", id(s), fast, slow, sig), _calc)


def donchian(df: pd.DataFrame, n: int = 20):
    return _memo(("donc", id(df), n),
                 lambda: (df["high"].rolling(n).max(), df["low"].rolling(n).min()))


def keltner(df: pd.DataFrame, n: int = 20, k: float = 1.5):
    def _calc():
        m = ema(df["close"], n)
        a = atr(df, n)
        return m, m + k * a, m - k * a
    return _memo(("kelt", id(df), n, k), _calc)


def supertrend(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.Series:
    def _calc():
        a = atr(df, n)
        hl2 = (df["high"] + df["low"]) / 2
        upper = (hl2 + mult * a).to_numpy()
        lower = (hl2 - mult * a).to_numpy()
        close = df["close"].to_numpy()
        st = np.empty(len(df))
        st[0] = lower[0]
        trend = 1
        for i in range(1, len(df)):
            if close[i] > st[i - 1]:
                trend = 1
            elif close[i] < st[i - 1]:
                trend = -1
            st[i] = lower[i] if trend == 1 else upper[i]
        return pd.Series(st, index=df.index)
    return _memo(("st", id(df), n, mult), _calc)
