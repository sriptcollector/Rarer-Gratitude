from dataclasses import dataclass
from typing import Optional
import pandas as pd


@dataclass
class Signal:
    action: str  # "buy", "sell", "hold"
    stop: Optional[float] = None
    take: Optional[float] = None


class Strategy:
    name: str = "base"

    def __init__(self, **params):
        self.params = params
        self.name = f"{self.__class__.__name__}(" + ",".join(f"{k}={v}" for k, v in params.items()) + ")"

    def min_bars(self) -> int:
        return 50

    def generate(self, df: pd.DataFrame, in_position: bool) -> Signal:
        raise NotImplementedError
