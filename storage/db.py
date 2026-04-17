import os
import sqlite3
from contextlib import contextmanager


SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy TEXT, symbol TEXT, side TEXT,
  entry REAL, exit REAL, qty REAL, pnl REAL,
  entry_ts TEXT, exit_ts TEXT, reason TEXT,
  explanation TEXT
);
CREATE TABLE IF NOT EXISTS metrics (
  ts TEXT, strategy TEXT, trades INT, win_rate REAL,
  expectancy REAL, profit_factor REAL, equity REAL,
  max_dd REAL, return_pct REAL,
  PRIMARY KEY (ts, strategy)
);
CREATE TABLE IF NOT EXISTS news (
  id INTEGER PRIMARY KEY,
  ts INTEGER, title TEXT, url TEXT, source TEXT,
  sentiment INTEGER, symbols TEXT, traded INTEGER
);
CREATE INDEX IF NOT EXISTS idx_news_ts ON news(ts DESC);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
CREATE INDEX IF NOT EXISTS idx_trades_id_desc ON trades(id DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_strategy ON metrics(strategy);
CREATE INDEX IF NOT EXISTS idx_metrics_ts ON metrics(ts);
"""


def init(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(trades)").fetchall()}
    if "explanation" not in cols:
        conn.execute("ALTER TABLE trades ADD COLUMN explanation TEXT")
    conn.commit()
    return conn


def insert_trade(conn, t, explanation: str = "") -> None:
    conn.execute(
        "INSERT INTO trades(strategy,symbol,side,entry,exit,qty,pnl,entry_ts,exit_ts,reason,explanation)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (t.strategy, t.symbol, t.side, t.entry, t.exit, t.qty, t.pnl,
         t.entry_ts, t.exit_ts, t.reason, explanation),
    )


def upsert_metrics_batch(conn, ts: str, metrics: list) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO metrics(ts,strategy,trades,win_rate,expectancy,"
        "profit_factor,equity,max_dd,return_pct) VALUES (?,?,?,?,?,?,?,?,?)",
        [(ts, m["strategy"], m["trades"], m["win_rate"], m["expectancy"],
          m["profit_factor"], m["equity"], m["max_dd"], m["return_pct"])
         for m in metrics],
    )


def upsert_metrics(conn, ts: str, m: dict) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO metrics(ts,strategy,trades,win_rate,expectancy,"
        "profit_factor,equity,max_dd,return_pct) VALUES (?,?,?,?,?,?,?,?,?)",
        (ts, m["strategy"], m["trades"], m["win_rate"], m["expectancy"],
         m["profit_factor"], m["equity"], m["max_dd"], m["return_pct"]),
    )
