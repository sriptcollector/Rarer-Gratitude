from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Position:
    symbol: str
    qty: float = 0.0
    entry: float = 0.0
    stop: Optional[float] = None
    take: Optional[float] = None
    legs: int = 0
    entry_ts: float = 0.0

    @property
    def is_open(self) -> bool:
        return self.qty != 0.0


@dataclass
class Trade:
    strategy: str
    symbol: str
    side: str
    entry: float
    exit: float
    qty: float
    pnl: float
    entry_ts: str
    exit_ts: str
    reason: str


@dataclass
class PaperAccount:
    strategy: str
    cash: float
    equity: float
    fee_bps: float
    slippage_bps: float
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[tuple[str, float]] = field(default_factory=list)
    peak: float = 0.0
    max_dd: float = 0.0

    def _cost(self, price: float, side: str) -> float:
        slip = self.slippage_bps / 10_000
        return price * (1 + slip) if side == "buy" else price * (1 - slip)

    def _fee(self, notional: float) -> float:
        return abs(notional) * self.fee_bps / 10_000

    def open_long(self, symbol: str, price: float, qty: float, ts: str,
                  stop: Optional[float] = None, take: Optional[float] = None) -> bool:
        if symbol in self.positions and self.positions[symbol].is_open:
            return False
        p = self._cost(price, "buy")
        cost = p * qty + self._fee(p * qty)
        if cost > self.cash or qty <= 0:
            return False
        self.cash -= cost
        import time as _t
        self.positions[symbol] = Position(
            symbol, qty, p, stop, take, legs=1, entry_ts=_t.time(),
        )
        return True

    def add_long(self, symbol: str, price: float, qty: float, ts: str,
                 max_legs: int = 3) -> bool:
        pos = self.positions.get(symbol)
        if not pos or not pos.is_open:
            return False
        if pos.legs >= max_legs or qty <= 0:
            return False
        p = self._cost(price, "buy")
        cost = p * qty + self._fee(p * qty)
        if cost > self.cash:
            return False
        self.cash -= cost
        new_qty = pos.qty + qty
        pos.entry = (pos.entry * pos.qty + p * qty) / new_qty
        pos.qty = new_qty
        pos.legs += 1
        return True

    def close(self, symbol: str, price: float, ts: str, reason: str = "signal") -> Optional[Trade]:
        pos = self.positions.get(symbol)
        if not pos or not pos.is_open:
            return None
        p = self._cost(price, "sell")
        proceeds = p * pos.qty - self._fee(p * pos.qty)
        self.cash += proceeds
        pnl = (p - pos.entry) * pos.qty - self._fee(p * pos.qty) - self._fee(pos.entry * pos.qty)
        trade = Trade(self.strategy, symbol, "long", pos.entry, p, pos.qty, pnl,
                      entry_ts="", exit_ts=ts, reason=reason)
        self.trades.append(trade)
        pos.qty = 0.0
        return trade

    def mark(self, prices: dict[str, float], ts: str) -> None:
        eq = self.cash
        for sym, pos in self.positions.items():
            if pos.is_open and sym in prices:
                eq += pos.qty * prices[sym]
        self.equity = eq
        self.equity_curve.append((ts, eq))
        if eq > self.peak:
            self.peak = eq
        if self.peak > 0:
            dd = (self.peak - eq) / self.peak
            if dd > self.max_dd:
                self.max_dd = dd

    def check_stops(self, symbol: str, high: float, low: float, ts: str) -> Optional[Trade]:
        pos = self.positions.get(symbol)
        if not pos or not pos.is_open:
            return None
        if pos.stop is not None and low <= pos.stop:
            return self.close(symbol, pos.stop, ts, reason="stop")
        if pos.take is not None and high >= pos.take:
            return self.close(symbol, pos.take, ts, reason="take")
        return None
