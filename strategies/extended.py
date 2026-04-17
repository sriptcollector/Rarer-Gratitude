import numpy as np
import pandas as pd
from .base import Strategy, Signal
from . import indicators as ind


def _atr_stops(df, px, sl_mult=2.0, tp_mult=3.0):
    a = ind.atr(df, 14).iloc[-1]
    if not np.isfinite(a) or a <= 0:
        return None, None
    return px - sl_mult * a, px + tp_mult * a


class Ichimoku(Strategy):
    def min_bars(self): return 60

    def generate(self, df, in_position):
        hi = df["high"]; lo = df["low"]; cl = df["close"]
        tenkan = (hi.rolling(9).max() + lo.rolling(9).min()) / 2
        kijun = (hi.rolling(26).max() + lo.rolling(26).min()) / 2
        span_a = ((tenkan + kijun) / 2).shift(26)
        span_b = ((hi.rolling(52).max() + lo.rolling(52).min()) / 2).shift(26)
        if span_b.isna().iloc[-1]: return Signal("hold")
        px = cl.iloc[-1]
        above_cloud = px > max(span_a.iloc[-1], span_b.iloc[-1])
        cross_up = tenkan.iloc[-2] <= kijun.iloc[-2] and tenkan.iloc[-1] > kijun.iloc[-1]
        if not in_position and cross_up and above_cloud:
            s, t = _atr_stops(df, px, 2.0, 4.0)
            return Signal("buy", stop=s, take=t)
        cross_dn = tenkan.iloc[-2] >= kijun.iloc[-2] and tenkan.iloc[-1] < kijun.iloc[-1]
        if in_position and cross_dn:
            return Signal("sell")
        return Signal("hold")


class Stochastic(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        low_n = df["low"].rolling(n).min()
        high_n = df["high"].rolling(n).max()
        k = 100 * (df["close"] - low_n) / (high_n - low_n)
        d = k.rolling(3).mean()
        if d.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        lo, hi = self.params["lo"], self.params["hi"]
        if not in_position and k.iloc[-2] <= lo and k.iloc[-1] > lo and k.iloc[-1] > d.iloc[-1]:
            s, t = _atr_stops(df, px, 1.5, 2.5)
            return Signal("buy", stop=s, take=t)
        if in_position and k.iloc[-1] > hi:
            return Signal("sell")
        return Signal("hold")


class WilliamsR(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        hh = df["high"].rolling(n).max()
        ll = df["low"].rolling(n).min()
        wr = -100 * (hh - df["close"]) / (hh - ll)
        if wr.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and wr.iloc[-1] < self.params["lo"]:
            s, t = _atr_stops(df, px, 1.5, 2.5)
            return Signal("buy", stop=s, take=t)
        if in_position and wr.iloc[-1] > self.params["hi"]:
            return Signal("sell")
        return Signal("hold")


class CCI(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        tp = (df["high"] + df["low"] + df["close"]) / 3
        m = tp.rolling(n).mean()
        md = (tp - m).abs().rolling(n).mean()
        cci = (tp - m) / (0.015 * md)
        if cci.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and cci.iloc[-2] < -self.params["th"] and cci.iloc[-1] > -self.params["th"]:
            s, t = _atr_stops(df, px, 1.5, 3.0)
            return Signal("buy", stop=s, take=t)
        if in_position and cci.iloc[-1] > self.params["th"]:
            return Signal("sell")
        return Signal("hold")


class AdxTrend(Strategy):
    """EMA cross filtered by ADX > threshold (trend strength gate)."""
    def min_bars(self): return max(self.params["slow"], 30) + 5

    def generate(self, df, in_position):
        high, low, close = df["high"], df["low"], df["close"]
        up = high.diff(); dn = -low.diff()
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = ind.atr(df, 14)
        plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(14).mean() / tr
        minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(14).mean() / tr
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        if adx.isna().iloc[-1]: return Signal("hold")
        f = ind.ema(close, self.params["fast"])
        s = ind.ema(close, self.params["slow"])
        strong = adx.iloc[-1] > self.params["adx"]
        px = close.iloc[-1]
        if not in_position and f.iloc[-1] > s.iloc[-1] and strong:
            sl, tp = _atr_stops(df, px, 2.0, 4.0)
            return Signal("buy", stop=sl, take=tp)
        if in_position and f.iloc[-1] < s.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class Aroon(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        up = 100 * (n - df["high"].rolling(n + 1).apply(lambda x: n - x.argmax(), raw=True)) / n
        dn = 100 * (n - df["low"].rolling(n + 1).apply(lambda x: n - x.argmin(), raw=True)) / n
        if up.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and up.iloc[-1] > 70 and dn.iloc[-1] < 30:
            s, t = _atr_stops(df, px, 2.0, 3.5)
            return Signal("buy", stop=s, take=t)
        if in_position and dn.iloc[-1] > up.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class ParabolicSar(Strategy):
    def min_bars(self): return 30

    def generate(self, df, in_position):
        af0, af_step, af_max = self.params["af0"], self.params["step"], self.params["max_af"]
        high, low = df["high"].values, df["low"].values
        n = len(df)
        sar = np.zeros(n); bull = True
        af = af0; ep = high[0]; sar[0] = low[0]
        for i in range(1, n):
            sar[i] = sar[i-1] + af * (ep - sar[i-1])
            if bull:
                if low[i] < sar[i]:
                    bull = False; sar[i] = ep; ep = low[i]; af = af0
                else:
                    if high[i] > ep: ep = high[i]; af = min(af + af_step, af_max)
            else:
                if high[i] > sar[i]:
                    bull = True; sar[i] = ep; ep = high[i]; af = af0
                else:
                    if low[i] < ep: ep = low[i]; af = min(af + af_step, af_max)
        px = df["close"].iloc[-1]
        if not in_position and bull and not (df["close"].iloc[-2] > sar[-2]):
            sl, tp = _atr_stops(df, px, 2.0, 3.5)
            return Signal("buy", stop=sl, take=tp)
        if in_position and not bull:
            return Signal("sell")
        return Signal("hold")


class HullMaCross(Strategy):
    def min_bars(self): return max(self.params["slow"], 40) + 5

    def generate(self, df, in_position):
        def hma(s, n):
            half = n // 2
            wma = lambda x, k: x.rolling(k).apply(lambda v: np.dot(v, np.arange(1, k+1)) / (k*(k+1)/2), raw=True)
            diff = 2 * wma(s, half) - wma(s, n)
            return wma(diff, int(np.sqrt(n)))
        f = hma(df["close"], self.params["fast"])
        s = hma(df["close"], self.params["slow"])
        if s.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and f.iloc[-1] > s.iloc[-1]:
            sl, tp = _atr_stops(df, px, 2.0, 3.5)
            return Signal("buy", stop=sl, take=tp)
        if in_position and f.iloc[-1] < s.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class TemaCross(Strategy):
    def min_bars(self): return max(self.params["slow"], 30) * 3 + 5

    def generate(self, df, in_position):
        def tema(s, n):
            e1 = ind.ema(s, n); e2 = ind.ema(e1, n); e3 = ind.ema(e2, n)
            return 3 * e1 - 3 * e2 + e3
        f = tema(df["close"], self.params["fast"])
        s = tema(df["close"], self.params["slow"])
        if s.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and f.iloc[-1] > s.iloc[-1]:
            sl, tp = _atr_stops(df, px, 2.0, 4.0)
            return Signal("buy", stop=sl, take=tp)
        if in_position and f.iloc[-1] < s.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class FisherTransform(Strategy):
    def min_bars(self): return self.params["n"] + 10

    def generate(self, df, in_position):
        n = self.params["n"]
        hl = (df["high"] + df["low"]) / 2
        mn = hl.rolling(n).min(); mx = hl.rolling(n).max()
        val = 2 * ((hl - mn) / (mx - mn) - 0.5)
        val = val.clip(-0.999, 0.999).ffill().fillna(0)
        fish = np.zeros(len(df))
        for i in range(1, len(df)):
            fish[i] = 0.5 * (np.log((1 + val.iloc[i]) / (1 - val.iloc[i])) + fish[i-1])
        fish_s = pd.Series(fish, index=df.index)
        trig = fish_s.shift(1)
        px = df["close"].iloc[-1]
        if not in_position and fish_s.iloc[-2] <= trig.iloc[-2] and fish_s.iloc[-1] > trig.iloc[-1] and fish_s.iloc[-1] < 0:
            sl, tp = _atr_stops(df, px, 1.5, 2.5)
            return Signal("buy", stop=sl, take=tp)
        if in_position and fish_s.iloc[-1] < trig.iloc[-1] and fish_s.iloc[-1] > 0:
            return Signal("sell")
        return Signal("hold")


class KaufmanAdaptiveMa(Strategy):
    def min_bars(self): return self.params["n"] + 10

    def generate(self, df, in_position):
        n = self.params["n"]
        change = (df["close"] - df["close"].shift(n)).abs()
        volatility = df["close"].diff().abs().rolling(n).sum()
        er = (change / volatility).fillna(0)
        sc = (er * (2 / 3 - 2 / 31) + 2 / 31) ** 2
        kama = df["close"].copy()
        for i in range(1, len(df)):
            kama.iloc[i] = kama.iloc[i-1] + sc.iloc[i] * (df["close"].iloc[i] - kama.iloc[i-1])
        px = df["close"].iloc[-1]
        if not in_position and df["close"].iloc[-1] > kama.iloc[-1]:
            sl, tp = _atr_stops(df, px, 2.0, 3.0)
            return Signal("buy", stop=sl, take=tp)
        if in_position and df["close"].iloc[-1] < kama.iloc[-1]:
            return Signal("sell")
        return Signal("hold")


class HeikinAshiTrend(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        ha_close = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
        ha_open = ha_close.copy()
        for i in range(1, len(df)):
            ha_open.iloc[i] = (ha_open.iloc[i-1] + ha_close.iloc[i-1]) / 2
        green = ha_close > ha_open
        n = self.params["n"]
        px = df["close"].iloc[-1]
        if not in_position and green.iloc[-n:].sum() == n and not green.iloc[-n-1]:
            sl, tp = _atr_stops(df, px, 2.0, 3.5)
            return Signal("buy", stop=sl, take=tp)
        if in_position and not green.iloc[-1] and not green.iloc[-2]:
            return Signal("sell")
        return Signal("hold")


class ZScoreMR(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        m = df["close"].rolling(n).mean()
        sd = df["close"].rolling(n).std()
        z = (df["close"] - m) / sd
        if sd.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and z.iloc[-1] < -self.params["entry"]:
            sl, tp = _atr_stops(df, px, 1.5, 2.0)
            return Signal("buy", stop=sl, take=m.iloc[-1])
        if in_position and z.iloc[-1] > self.params["exit"]:
            return Signal("sell")
        return Signal("hold")


class ChandeMomentum(Strategy):
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        n = self.params["n"]
        diff = df["close"].diff()
        up = diff.clip(lower=0).rolling(n).sum()
        dn = (-diff.clip(upper=0)).rolling(n).sum()
        cmo = 100 * (up - dn) / (up + dn)
        if cmo.isna().iloc[-1]: return Signal("hold")
        px = df["close"].iloc[-1]
        if not in_position and cmo.iloc[-2] < -self.params["th"] and cmo.iloc[-1] > -self.params["th"]:
            sl, tp = _atr_stops(df, px, 1.8, 2.8)
            return Signal("buy", stop=sl, take=tp)
        if in_position and cmo.iloc[-1] > self.params["th"]:
            return Signal("sell")
        return Signal("hold")


class ObvDivergence(Strategy):
    """On-balance volume breakout to new highs."""
    def min_bars(self): return self.params["n"] + 5

    def generate(self, df, in_position):
        sign = np.sign(df["close"].diff().fillna(0))
        obv = (sign * df["volume"]).cumsum()
        n = self.params["n"]
        obv_hi = obv.rolling(n).max()
        px_hi = df["close"].rolling(n).max()
        px = df["close"].iloc[-1]
        if not in_position and obv.iloc[-1] >= obv_hi.iloc[-1] and px >= px_hi.iloc[-1]:
            sl, tp = _atr_stops(df, px, 2.0, 4.0)
            return Signal("buy", stop=sl, take=tp)
        if in_position and obv.iloc[-1] < obv.rolling(n).mean().iloc[-1]:
            return Signal("sell")
        return Signal("hold")
