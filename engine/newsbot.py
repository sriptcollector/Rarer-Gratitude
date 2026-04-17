import hashlib
import logging
import time
import urllib.request
import xml.etree.ElementTree as ET
from calendar import timegm
from datetime import datetime, timezone
from email.utils import parsedate_tz, mktime_tz

import config
from engine.broker import PaperAccount, Trade
from storage import db as dbm


log = logging.getLogger("newsbot")

RSS_FEEDS = [
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("CoinTelegraph", "https://cointelegraph.com/rss"),
    ("Decrypt", "https://decrypt.co/feed"),
    ("TheBlock", "https://www.theblock.co/rss.xml"),
]

SYMBOL_KEYWORDS = {
    "BTC/USDT": ["bitcoin", "btc "],
    "ETH/USDT": ["ethereum", "ether ", "eth "],
    "SOL/USDT": ["solana", "sol "],
    "XRP/USDT": ["xrp", "ripple"],
    "ALGO/USDT": ["algorand", "algo "],
    "CRV/USDT": ["curve finance", "crv "],
    "GRT/USDT": ["the graph", "grt "],
    "BAT/USDT": ["basic attention", "bat "],
}

POSITIVE = ["partnership", "approval", "approved", "launch", "etf",
            "bullish", "rally", "upgrade", "soar", "surge", "all-time high",
            "adoption", "integration", "expand", "gain", "breakthrough",
            "fund", "raise", "record", "beat", "win", "institutional"]
NEGATIVE = ["hack", "hacked", "exploit", "lawsuit", "crash", "dump",
            "delist", "ban", "banned", "fraud", "scam", "collapse",
            "bearish", "plunge", "drop", "decline", "warning", "fear",
            "investigation", "seize", "liquidation", "bankruptcy", "fail"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _score(text: str) -> int:
    t = text.lower()
    return sum(1 for w in POSITIVE if w in t) - sum(1 for w in NEGATIVE if w in t)


def _match_symbols(text: str, active: set[str]) -> list[str]:
    t = " " + text.lower() + " "
    out = []
    for sym, kws in SYMBOL_KEYWORDS.items():
        if sym not in active:
            continue
        if any(k in t for k in kws):
            out.append(sym)
    return out


class NewsBot:
    NAME = "NewsBot"

    def __init__(self, conn, prices_ref: dict, active_symbols: set[str]):
        self.conn = conn
        self.prices = prices_ref
        self.active = active_symbols
        self.seen: set[int] = set()
        self.account = PaperAccount(
            strategy=self.NAME,
            cash=config.STARTING_CASH,
            equity=config.STARTING_CASH,
            fee_bps=config.FEE_BPS,
            slippage_bps=config.SLIPPAGE_BPS,
        )
        self._rehydrate()

    def _rehydrate(self) -> None:
        rows = self.conn.execute(
            "SELECT entry,exit,qty,pnl,entry_ts,exit_ts,reason,symbol "
            "FROM trades WHERE strategy=? ORDER BY id", (self.NAME,),
        ).fetchall()
        eq = config.STARTING_CASH
        peak = eq
        for entry, exit_px, qty, pnl, ets, xts, reason, symbol in rows:
            self.account.trades.append(Trade(
                strategy=self.NAME, symbol=symbol, side="long",
                entry=entry, exit=exit_px, qty=qty, pnl=pnl,
                entry_ts=ets or "", exit_ts=xts or "", reason=reason or "news",
            ))
            eq += pnl
            if eq > peak:
                peak = eq
            if peak > 0:
                dd = (peak - eq) / peak
                if dd > self.account.max_dd:
                    self.account.max_dd = dd
        self.account.cash = max(0.0, eq)
        self.account.equity = self.account.cash
        self.account.peak = peak
        self.account.equity_curve.append((_now_iso(), config.STARTING_CASH))
        self.account.equity_curve.append((_now_iso(), self.account.equity))
        try:
            ids = self.conn.execute(
                "SELECT id FROM news ORDER BY id DESC LIMIT 1000").fetchall()
            self.seen = {r[0] for r in ids}
        except Exception:
            pass

    def _fetch_feed(self, source: str, url: str) -> list:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 RareGratitude/1.0"})
            with urllib.request.urlopen(req, timeout=8) as r:
                raw = r.read()
            root = ET.fromstring(raw)
            items = []
            for it in root.iter("item"):
                title = (it.findtext("title") or "").strip()
                link = (it.findtext("link") or "").strip()
                desc = (it.findtext("description") or "").strip()
                pub = it.findtext("pubDate") or ""
                try:
                    ts = mktime_tz(parsedate_tz(pub)) if pub else int(time.time())
                except Exception:
                    ts = int(time.time())
                nid = int(hashlib.md5(link.encode()).hexdigest()[:12], 16) if link \
                    else int(hashlib.md5(title.encode()).hexdigest()[:12], 16)
                items.append({
                    "id": nid,
                    "title": title,
                    "body": desc,
                    "url": link,
                    "source": source,
                    "published_on": int(ts),
                })
            return items
        except Exception as e:
            log.debug("feed %s: %s", source, e)
            return []

    def _fetch(self) -> list:
        all_items = []
        for source, url in RSS_FEEDS:
            all_items.extend(self._fetch_feed(source, url))
        return all_items

    def _store(self, item, sentiment: int, matched: list[str], traded: bool) -> None:
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO news(id,ts,title,url,source,sentiment,symbols,traded) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (int(item.get("id") or 0),
                 int(item.get("published_on") or 0),
                 (item.get("title") or "")[:300],
                 (item.get("url") or "")[:500],
                 (item.get("source") or "")[:80],
                 sentiment,
                 ",".join(matched),
                 1 if traded else 0),
            )
            self.conn.commit()
        except Exception as e:
            log.debug("news store: %s", e)

    def _open(self, sym: str, px: float, ts: str, headline: str) -> bool:
        risk = config.RISK_PCT * 2.0
        qty = (self.account.cash * risk) / px
        if qty <= 0:
            return False
        ok = self.account.open_long(sym, px, qty, ts,
                                    stop=px * 0.96, take=px * 1.06)
        if ok:
            log.info("NewsBot BUY %s @ %.6f qty=%.4f :: %s", sym, px, qty, headline[:80])
        return ok

    def _close(self, sym: str, px: float, ts: str, why: str) -> None:
        t = self.account.close(sym, px, ts, reason="news")
        if t:
            t.entry_ts = ts
            dbm.insert_trade(self.conn, t, why[:200])
            self.conn.commit()
            log.info("NewsBot SELL %s @ %.6f pnl=%.2f", sym, px, t.pnl)

    def _check_exits(self, prices: dict, ts: str) -> None:
        for sym, pos in list(self.account.positions.items()):
            if not pos.is_open or sym not in prices:
                continue
            px = prices[sym]
            if pos.stop is not None and px <= pos.stop:
                t = self.account.close(sym, pos.stop, ts, reason="stop")
                if t:
                    t.entry_ts = ts
                    dbm.insert_trade(self.conn, t, "Stop hit")
                    self.conn.commit()
            elif pos.take is not None and px >= pos.take:
                t = self.account.close(sym, pos.take, ts, reason="take")
                if t:
                    t.entry_ts = ts
                    dbm.insert_trade(self.conn, t, "Take-profit hit")
                    self.conn.commit()

    def step(self) -> None:
        items = self._fetch()
        ts = _now_iso()
        prices = dict(self.prices)
        self._check_exits(prices, ts)
        new_items = [i for i in items if int(i.get("id") or 0) not in self.seen]
        new_items.sort(key=lambda x: int(x.get("published_on") or 0))
        for item in new_items:
            nid = int(item.get("id") or 0)
            if not nid:
                continue
            self.seen.add(nid)
            text = (item.get("title") or "") + " \n" + (item.get("body") or "")
            matched = _match_symbols(text, self.active)
            if not matched:
                self._store(item, 0, [], False)
                continue
            score = _score(text)
            traded = False
            for sym in matched:
                px = prices.get(sym)
                if not px:
                    continue
                pos = self.account.positions.get(sym)
                in_pos = bool(pos and pos.is_open)
                if score >= 2 and not in_pos:
                    if self._open(sym, px, ts, item.get("title") or ""):
                        traded = True
                elif score <= -2 and in_pos:
                    self._close(sym, px, ts, "bearish news: " + (item.get("title") or "")[:160])
                    traded = True
            self._store(item, score, matched, traded)
        self.account.mark(prices, ts)

    def run(self, interval: int = 60) -> None:
        log.info("NewsBot online, polling every %ds", interval)
        while True:
            try:
                self.step()
            except Exception as e:
                log.warning("NewsBot step: %s", e)
            time.sleep(interval)
