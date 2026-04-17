from itertools import product
from .library import (
    EmaCross, RsiMeanReversion, BollingerBreakout, BollingerReversion,
    DonchianBreakout, MacdMomentum, KeltnerBreakout, Supertrend,
    MomentumRoc, VwapReversion,
)
from .extended import (
    Ichimoku, Stochastic, WilliamsR, CCI, AdxTrend, Aroon, ParabolicSar,
    HullMaCross, TemaCross, FisherTransform, KaufmanAdaptiveMa,
    HeikinAshiTrend, ZScoreMR, ChandeMomentum, ObvDivergence,
)


def build_all():
    strategies = []

    for fast, slow in product([3, 5, 8, 12, 20, 34], [26, 50, 100, 200]):
        if fast >= slow: continue
        strategies.append(EmaCross(fast=fast, slow=slow))

    for n, lo, hi in product([5, 7, 14, 21, 28], [20, 25, 30], [65, 70, 75, 80]):
        strategies.append(RsiMeanReversion(n=n, lo=lo, hi=hi))

    for n, k in product([14, 20, 30, 50, 80], [1.8, 2.0, 2.5, 3.0]):
        strategies.append(BollingerBreakout(n=n, k=k))

    for n, k in product([14, 20, 30, 50], [1.5, 1.8, 2.0, 2.5]):
        strategies.append(BollingerReversion(n=n, k=k))

    for n in [10, 20, 30, 55, 100, 150, 200]:
        strategies.append(DonchianBreakout(n=n))

    for fast, slow, sig in [(12, 26, 9), (8, 21, 5), (5, 35, 5), (10, 30, 9),
                             (16, 40, 9), (6, 19, 6), (7, 25, 8)]:
        strategies.append(MacdMomentum(fast=fast, slow=slow, sig=sig))

    for n, k in product([10, 14, 20, 30, 50], [1.0, 1.5, 2.0, 2.5, 3.0]):
        strategies.append(KeltnerBreakout(n=n, k=k))

    for n, mult in product([5, 7, 10, 14, 20, 30], [1.5, 2.0, 3.0, 4.0]):
        strategies.append(Supertrend(n=n, mult=mult))

    for n, thr in product([3, 5, 10, 15, 20, 30], [0.003, 0.005, 0.01, 0.02, 0.03, 0.05]):
        strategies.append(MomentumRoc(n=n, thr=thr))

    for n, z in product([20, 30, 50, 80], [1.5, 2.0, 2.5, 3.0]):
        strategies.append(VwapReversion(n=n, z=z))

    # extended
    strategies.append(Ichimoku())

    for n, lo, hi in product([9, 14, 21], [15, 20, 25], [75, 80, 85]):
        strategies.append(Stochastic(n=n, lo=lo, hi=hi))

    for n, lo, hi in product([9, 14, 21, 30], [-85, -80, -75], [-25, -20, -15]):
        strategies.append(WilliamsR(n=n, lo=lo, hi=hi))

    for n, th in product([14, 20, 30], [100, 150, 200]):
        strategies.append(CCI(n=n, th=th))

    for fast, slow, adx in product([5, 8, 12], [26, 50], [20, 25, 30]):
        strategies.append(AdxTrend(fast=fast, slow=slow, adx=adx))

    for n in [14, 20, 25, 30, 50]:
        strategies.append(Aroon(n=n))

    for af0, step, mx in [(0.02, 0.02, 0.2), (0.01, 0.01, 0.1), (0.03, 0.03, 0.3)]:
        strategies.append(ParabolicSar(af0=af0, step=step, max_af=mx))

    for fast, slow in product([9, 14, 21], [34, 55, 89]):
        if fast < slow:
            strategies.append(HullMaCross(fast=fast, slow=slow))

    for fast, slow in product([9, 12, 21], [26, 50]):
        if fast < slow:
            strategies.append(TemaCross(fast=fast, slow=slow))

    for n in [9, 14, 21, 30]:
        strategies.append(FisherTransform(n=n))

    for n in [10, 14, 20, 30, 50]:
        strategies.append(KaufmanAdaptiveMa(n=n))

    for n in [2, 3, 4, 5]:
        strategies.append(HeikinAshiTrend(n=n))

    for n, entry, exit_ in product([20, 30, 50, 100], [1.5, 2.0, 2.5, 3.0], [0.0, 0.5, 1.0]):
        strategies.append(ZScoreMR(n=n, entry=entry, exit=exit_))

    for n, th in product([9, 14, 21, 30], [30, 50, 70]):
        strategies.append(ChandeMomentum(n=n, th=th))

    for n in [10, 20, 50, 100]:
        strategies.append(ObvDivergence(n=n))

    return strategies
