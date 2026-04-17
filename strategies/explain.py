"""Plain-English explanations for why a strategy fired a trade."""
import re


def _parse(name: str) -> tuple[str, dict]:
    """Parse 'EmaCross(fast=5,slow=26)' → ('EmaCross', {'fast':5,'slow':26})."""
    m = re.match(r"([A-Za-z]+)\((.*)\)", name)
    if not m:
        return name, {}
    cls, body = m.group(1), m.group(2)
    params = {}
    for kv in body.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            try: params[k] = float(v) if "." in v else int(v)
            except Exception: params[k] = v
    return cls, params


TEMPLATES = {
    "EmaCross": {
        "buy": "Fast EMA({fast}) crossed above Slow EMA({slow}) — short-term momentum flipped bullish.",
        "sell": "Fast EMA({fast}) crossed back below Slow EMA({slow}) — trend turning down, exit.",
    },
    "RsiMeanReversion": {
        "buy": "RSI({n}) dropped below {lo} — market is oversold, buying the dip.",
        "sell": "RSI({n}) climbed above {hi} — overbought, locking in.",
    },
    "BollingerBreakout": {
        "buy": "Price broke above upper Bollinger band ({n},{k}σ) — strong breakout momentum.",
        "sell": "Price fell below lower band — breakout failed, exit.",
    },
    "BollingerReversion": {
        "buy": "Price stretched below lower Bollinger band ({n},{k}σ) — expecting reversion to the mean.",
        "sell": "Price reverted back to the {n}-period mean — take profit.",
    },
    "DonchianBreakout": {
        "buy": "Price hit a new {n}-bar high — classic trend breakout (Turtle-style).",
        "sell": "Price hit a new {n}-bar low — trend broke, exit.",
    },
    "MacdMomentum": {
        "buy": "MACD({fast},{slow},{sig}) line crossed above signal line, above zero — bullish momentum.",
        "sell": "MACD line crossed back below signal — momentum faded.",
    },
    "KeltnerBreakout": {
        "buy": "Price broke above upper Keltner channel ({n},{k}×ATR) — volatility expansion up.",
        "sell": "Price fell below lower Keltner — exit breakout.",
    },
    "Supertrend": {
        "buy": "SuperTrend({n},{mult}×ATR) flipped to up-trend — entry.",
        "sell": "SuperTrend flipped to down-trend — exit.",
    },
    "MomentumRoc": {
        "buy": "Rate-of-change over {n} bars exceeded {thr} — strong recent momentum.",
        "sell": "Momentum turned negative — exit.",
    },
    "VwapReversion": {
        "buy": "Price fell {z}σ below {n}-bar VWAP — expecting mean reversion back to VWAP.",
        "sell": "Price climbed back above VWAP — exit.",
    },
    "Ichimoku": {
        "buy": "Tenkan crossed Kijun above the Kumo cloud — classic Ichimoku bullish signal.",
        "sell": "Tenkan crossed back below Kijun — bullish setup broken.",
    },
    "Stochastic": {
        "buy": "Stochastic %K({n}) bounced out of oversold (<{lo}) above its signal line — momentum turning up.",
        "sell": "Stochastic pushed into overbought (>{hi}) — take profit.",
    },
    "WilliamsR": {
        "buy": "Williams %R({n}) below {lo} — oversold extreme, expecting bounce.",
        "sell": "Williams %R crossed above {hi} — overbought, exit.",
    },
    "CCI": {
        "buy": "CCI({n}) crossed back up through -{th} — emerging from oversold territory.",
        "sell": "CCI exceeded +{th} — overbought, take profit.",
    },
    "AdxTrend": {
        "buy": "EMA({fast}/{slow}) cross up with ADX > {adx} — trend is both up AND strong.",
        "sell": "EMA lost trend, exit.",
    },
    "Aroon": {
        "buy": "Aroon-Up > 70 and Aroon-Down < 30 — strong fresh uptrend forming.",
        "sell": "Aroon-Down overtook Aroon-Up — uptrend ending.",
    },
    "ParabolicSar": {
        "buy": "Parabolic SAR flipped below price — trend reversal up.",
        "sell": "Parabolic SAR flipped above price — trend reversal down.",
    },
    "HullMaCross": {
        "buy": "Hull MA({fast}) crossed above Hull MA({slow}) — fast-responding trend flip.",
        "sell": "Hull MAs re-crossed — exit.",
    },
    "TemaCross": {
        "buy": "Triple-EMA({fast}) crossed above TEMA({slow}) — low-lag trend confirmation.",
        "sell": "TEMAs re-crossed — exit.",
    },
    "FisherTransform": {
        "buy": "Fisher Transform turned up from negative — sharp oversold reversal.",
        "sell": "Fisher turned down from positive — take profit.",
    },
    "KaufmanAdaptiveMa": {
        "buy": "Price crossed above Kaufman Adaptive MA({n}) — adaptive trend flipped up.",
        "sell": "Price fell below KAMA — trend ended.",
    },
    "HeikinAshiTrend": {
        "buy": "{n} green Heikin-Ashi candles in a row — smoothed uptrend confirmed.",
        "sell": "Two red Heikin-Ashi candles — trend broke.",
    },
    "ZScoreMR": {
        "buy": "{n}-period z-score below -{entry} — price unusually cheap, mean-reversion long.",
        "sell": "Z-score crossed {exit} — back near mean, exit.",
    },
    "ChandeMomentum": {
        "buy": "CMO({n}) crossed up through -{th} — exiting oversold.",
        "sell": "CMO broke above +{th} — overbought, take profit.",
    },
    "ObvDivergence": {
        "buy": "On-Balance Volume hit {n}-bar high as price made new high — volume confirming breakout.",
        "sell": "OBV rolled below its average — volume fading, exit.",
    },
}


def _safe_fmt(tmpl: str, params: dict) -> str:
    class _Safe(dict):
        def __missing__(self, k): return "?"
    return tmpl.format_map(_Safe(params))


def explain_trade(strategy_name: str, side: str, reason: str) -> str:
    """Human-readable 'why did we do this?' summary."""
    cls, params = _parse(strategy_name)
    if reason == "stop":
        return "Stop-loss hit — price dropped to the pre-set ATR-based risk level. Locking the loss."
    if reason == "take":
        return "Take-profit hit — price reached the pre-set target. Banking the win."
    tmpl = TEMPLATES.get(cls, {}).get("buy" if side == "long" or reason == "buy" else "sell")
    if not tmpl:
        return f"{cls}: {reason}"
    return _safe_fmt(tmpl, params)
