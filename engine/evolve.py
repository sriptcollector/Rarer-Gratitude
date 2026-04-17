"""Daily evolution: kill bottom performers, mutate top performers."""
import os
import random
import re
import sqlite3
import time
import logging
from dataclasses import dataclass

import config
from engine.broker import PaperAccount


log = logging.getLogger("evolve")
STATE_PATH = os.path.join(os.path.dirname(config.DB_PATH) or ".", "evolve_state.txt")


@dataclass
class EvoConfig:
    period_s: int = 24 * 60 * 60
    kill_frac: float = 0.20
    breed_frac: float = 0.20
    jitter: float = 0.25
    min_trades: int = 5  # require this many trades before eligible for eval


def _parse_name(name: str):
    m = re.match(r"([A-Za-z]+)\((.*)\)", name)
    if not m: return name, {}
    cls, body = m.group(1), m.group(2)
    out = {}
    for kv in body.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            try: out[k] = float(v) if "." in v else int(v)
            except: out[k] = v
    return cls, out


def _mutate(params: dict, jitter: float) -> dict:
    out = {}
    for k, v in params.items():
        if isinstance(v, (int, float)):
            delta = v * jitter * random.uniform(-1, 1)
            nv = v + delta
            if isinstance(v, int):
                nv = max(1, int(round(nv)))
            else:
                nv = max(0.001, round(nv, 3))
            out[k] = nv
        else:
            out[k] = v
    return out


def _instance_from(name: str):
    cls, params = _parse_name(name)
    from strategies import library as lib
    from strategies import extended as ext
    mod = None
    if hasattr(lib, cls): mod = lib
    elif hasattr(ext, cls): mod = ext
    if not mod: return None
    klass = getattr(mod, cls)
    try: return klass(**params)
    except Exception as e:
        log.warning("couldn't instantiate %s(%s): %s", cls, params, e)
        return None


def _last_evo_ts() -> float:
    try:
        with open(STATE_PATH) as f: return float(f.read().strip() or 0)
    except Exception: return 0.0


def _save_evo_ts(ts: float) -> None:
    try:
        with open(STATE_PATH, "w") as f: f.write(str(ts))
    except Exception: pass


def maybe_evolve(strategies, accounts, active_set: set, conn: sqlite3.Connection,
                 cfg: EvoConfig = EvoConfig()) -> bool:
    """Runs if >period_s since last evolution. Returns True if evolved."""
    now = time.time()
    last = _last_evo_ts()
    if last and (now - last) < cfg.period_s:
        return False

    scored = []
    for name in list(active_set):
        acc = accounts.get(name)
        if not acc: continue
        n_trades = len(acc.trades)
        if n_trades < cfg.min_trades:
            continue
        start = acc.equity_curve[0][1] if acc.equity_curve else config.STARTING_CASH
        ret = (acc.equity / start - 1) if start else 0
        scored.append((name, ret, n_trades))

    if len(scored) < 10:
        log.info("evolve: not enough eligible strategies (%d), skipping", len(scored))
        _save_evo_ts(now)
        return False

    scored.sort(key=lambda x: x[1], reverse=True)
    kill_n = max(1, int(len(scored) * cfg.kill_frac))
    breed_n = max(1, int(len(scored) * cfg.breed_frac))

    killed = [n for n, _, _ in scored[-kill_n:]]
    for name in killed:
        active_set.discard(name)

    top = [n for n, _, _ in scored[:breed_n]]
    born = []
    for parent_name in top:
        parent = _instance_from(parent_name)
        if not parent: continue
        cls = parent.__class__
        new_params = _mutate(parent.params, cfg.jitter)
        try:
            child = cls(**new_params)
        except Exception: continue
        gen = 2
        g_match = re.search(r"-g(\d+)$", parent_name)
        if g_match: gen = int(g_match.group(1)) + 1
        child.name = f"{child.name}-g{gen}"
        if child.name in accounts: continue
        strategies.append(child)
        accounts[child.name] = PaperAccount(
            strategy=child.name, cash=config.STARTING_CASH, equity=config.STARTING_CASH,
            fee_bps=config.FEE_BPS, slippage_bps=config.SLIPPAGE_BPS,
        )
        active_set.add(child.name)
        born.append(child.name)

    log.info("evolve: killed %d, bred %d. examples killed=%s born=%s",
             len(killed), len(born), killed[:2], born[:2])
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS evolution
                        (ts REAL, killed TEXT, born TEXT)""")
        conn.execute("INSERT INTO evolution VALUES (?,?,?)",
                     (now, ",".join(killed), ",".join(born)))
        conn.commit()
    except Exception as e:
        log.warning("evolve log failed: %s", e)

    _save_evo_ts(now)
    return True
