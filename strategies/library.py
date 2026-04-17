import pandas as pd
from .base import Strategy, Signal
from . import indicators as ind


class EmaCross(Strategy):
    def min_bars(self): return max(self.params["slow"], 50) + 5

    def generate(self, df, in_position):
        f = ind.ema(df["close"], self.params["fast"])
        s = ind.ema(df["close"], self.params["slow"])
        if len(df) < self.min_bars(): return Signal("hold")
        bull = f.iloc[-1] > s.iloc[-1]
        if not in_position and bull:
            a = ind.atr(df, 14).iloc[-1]
            px = df["close"].iloc[-1]
            return Signal("buy", stop=px - 2 * a, take=px + 4 * a)
        if in_position and not bull:
            return Signal("sell")
        return Signal("hold")


class RsiMeanReversion(Strategy):
    def min_bars(self): return self.params["n"] + 10

    def generate(self, df, in_position):
        r = ind.rsi(df["close"], self.params["n"])
        if r.isna().iloc[-1]: return Signal("hold")
        lo, hi = self.params["lo"], self.params["hi"]
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and r.iloc[-1] < lo:
            return Signal("buy", stop=px - 1.5 * a, take=px + 2 * a)
        if in_position and r.iloc[-1] > hi:
            return Signal("sell")
        return Signal("hold")


class BollingerBreakout(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        _, up, lo = ind.bollinger(df["close"], self.params["n"], self.params["k"])
        if up.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and px > up.iloc[-1]:
            return Signal("buy", stop=px - 2 * a, take=px + 3 * a)
        if in_position and px < lo.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class BollingerReversion(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        mid, up, lo = ind.bollinger(df["close"], self.params["n"], self.params["k"])
        if lo.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and px < lo.iloc[-1]:
            return Signal("buy", stop=px - 1.5 * a, take=mid.iloc[-1])
        if in_position and px > mid.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class DonchianBreakout(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        hi, lo = ind.donchian(df, self.params["n"])
        if hi.isna().iloc[-2]: return Signal("hold")
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and px >= hi.iloc[-2]:
            return Signal("buy", stop=px - 2 * a, take=px + 4 * a)
        if in_position and px <= lo.iloc[-2]:
            return Signal("sell")
        return Signal("hold")


class MacdMomentum(Strategy):
    def min_bars(self): return self.params["slow"] + self.params["sig"] + 5

    def generate(self, df, in_position):
        line, sig, _ = ind.macd(df["close"], self.params["fast"], self.params["slow"], self.params["sig"])
        if sig.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        bull = line.iloc[-1] > sig.iloc[-1]
        if not in_position and bull and line.iloc[-1] > 0:
            return Signal("buy", stop=px - 2 * a, take=px + 3 * a)
        if in_position and not bull:
            return Signal("sell")
        return Signal("hold")


class KeltnerBreakout(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        _, up, lo = ind.keltner(df, self.params["n"], self.params["k"])
        if up.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and px > up.iloc[-1]:
            return Signal("buy", stop=px - 2 * a, take=px + 3 * a)
        if in_position and px < lo.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class Supertrend(Strategy):
    def min_bars(self): return self.params["n"] + 10

    def generate(self, df, in_position):
        st = ind.supertrend(df, self.params["n"], self.params["mult"])
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and px > st.iloc[-1] and df["close"].iloc[-2] <= st.iloc[-2]:
            return Signal("buy", stop=px - 2 * a, take=px + 4 * a)
        if in_position and px < st.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class MomentumRoc(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        roc = df["close"].pct_change(n)
        thr = self.params["thr"]
        px = df["close"].iloc[-1]
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and roc.iloc[-1] > thr:
            return Signal("buy", stop=px - 2 * a, take=px + 3 * a)
        if in_position and roc.iloc[-1] < 0:
            return Signal("sell")
        return Signal("hold")


class VwapReversion(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        tp = (df["high"] + df["low"] + df["close"]) / 3
        v = df["volume"]
        vwap = (tp * v).rolling(n).sum() / v.rolling(n).sum()
        std = (tp - vwap).rolling(n).std()
        if std.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        z = (px - vwap.iloc[-1]) / std.iloc[-1] if std.iloc[-1] else 0
        a = ind.atr(df, 14).iloc[-1]
        if not in_position and z < -self.params["z"]:
            return Signal("buy", stop=px - 1.5 * a, take=vwap.iloc[-1])
        if in_position and px > vwap.iloc[-1]:
            return Signal("sell")
        return Signal("hold")
