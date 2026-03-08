"""core/auto_journal.py – SQLite-based trade auto-journaling.

Records every order event (entry / exit / cancel) with a snapshot of the
order-book state and the account balance at that moment.  After the session
the DB can be queried for win-rate analysis.
"""
from __future__ import annotations

import sqlite3
import threading
import json
from datetime import datetime
from typing import Any

import config


_CREATE_TRADES_TABLE = """
CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp     TEXT    NOT NULL,
    event_type    TEXT    NOT NULL,   -- ENTRY | EXIT | CANCEL | TIMEOUT
    ticker        TEXT    NOT NULL,
    direction     TEXT    NOT NULL,   -- BUY | SELL
    quantity      INTEGER NOT NULL,
    price         REAL    NOT NULL,
    entry_price   REAL,               -- NULL for ENTRY events
    pnl_krw       REAL,               -- realised P&L (NULL until EXIT)
    pnl_pct       REAL,
    orderbook     TEXT,               -- JSON snapshot of bid/ask at execution
    account_cash  REAL,
    note          TEXT
);
"""

_CREATE_TICKS_TABLE = """
CREATE TABLE IF NOT EXISTS tick_snapshots (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp  TEXT NOT NULL,
    ticker     TEXT NOT NULL,
    price      REAL NOT NULL,
    bid        REAL,
    ask        REAL,
    bid_qty    INTEGER,
    ask_qty    INTEGER
);
"""


class AutoJournal:
    """Thread-safe SQLite trade journal."""

    def __init__(self, db_path: str = config.JOURNAL_DB_PATH) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TRADES_TABLE)
            conn.execute(_CREATE_TICKS_TABLE)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, check_same_thread=False)

    # ── public API ────────────────────────────────────────────────────────────

    def record_trade(
        self,
        event_type: str,
        ticker: str,
        direction: str,
        quantity: int,
        price: float,
        entry_price: float | None = None,
        pnl_krw: float | None = None,
        pnl_pct: float | None = None,
        orderbook: dict | None = None,
        account_cash: float | None = None,
        note: str = "",
    ) -> None:
        ts = datetime.now().isoformat(timespec="milliseconds")
        ob_json = json.dumps(orderbook) if orderbook else None
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO trades
                       (timestamp, event_type, ticker, direction, quantity,
                        price, entry_price, pnl_krw, pnl_pct, orderbook,
                        account_cash, note)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ts, event_type, ticker, direction, quantity,
                        price, entry_price, pnl_krw, pnl_pct, ob_json,
                        account_cash, note,
                    ),
                )
                conn.commit()

    def record_tick(
        self,
        ticker: str,
        price: float,
        bid: float | None = None,
        ask: float | None = None,
        bid_qty: int | None = None,
        ask_qty: int | None = None,
    ) -> None:
        ts = datetime.now().isoformat(timespec="milliseconds")
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO tick_snapshots
                       (timestamp, ticker, price, bid, ask, bid_qty, ask_qty)
                       VALUES (?,?,?,?,?,?,?)""",
                    (ts, ticker, price, bid, ask, bid_qty, ask_qty),
                )
                conn.commit()

    def get_daily_summary(self, date: str | None = None) -> list[dict[str, Any]]:
        """Return trade records for a given date (YYYY-MM-DD), default today."""
        date = date or datetime.now().strftime("%Y-%m-%d")
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM trades WHERE timestamp LIKE ? AND event_type='EXIT'",
                (f"{date}%",),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_win_rate(self, date: str | None = None) -> dict[str, Any]:
        """Calculate win rate for exits on a given day."""
        exits = self.get_daily_summary(date)
        if not exits:
            return {"trades": 0, "wins": 0, "losses": 0, "win_rate_pct": 0.0, "total_pnl": 0.0}
        wins = [t for t in exits if (t.get("pnl_krw") or 0) > 0]
        losses = [t for t in exits if (t.get("pnl_krw") or 0) <= 0]
        total_pnl = sum(t.get("pnl_krw") or 0 for t in exits)
        return {
            "trades": len(exits),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": round(len(wins) / len(exits) * 100, 1),
            "total_pnl": total_pnl,
        }
