"""tests/test_auto_journal.py – Unit tests for AutoJournal."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime

import pytest
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.auto_journal import AutoJournal


@pytest.fixture()
def journal(tmp_path):
    db = str(tmp_path / "test_trades.db")
    return AutoJournal(db_path=db)


class TestAutoJournal:
    def test_record_and_retrieve_entry(self, journal: AutoJournal) -> None:
        journal.record_trade(
            event_type="ENTRY",
            ticker="005930",
            direction="BUY",
            quantity=10,
            price=72_000,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        # No EXIT yet – daily summary should be empty
        summary = journal.get_daily_summary(today)
        assert summary == []

    def test_record_exit_appears_in_summary(self, journal: AutoJournal) -> None:
        journal.record_trade(
            event_type="EXIT",
            ticker="005930",
            direction="SELL",
            quantity=10,
            price=73_000,
            entry_price=72_000,
            pnl_krw=10_000.0,
            pnl_pct=1.39,
        )
        today = datetime.now().strftime("%Y-%m-%d")
        summary = journal.get_daily_summary(today)
        assert len(summary) == 1
        assert summary[0]["ticker"] == "005930"
        assert summary[0]["pnl_krw"] == 10_000.0

    def test_win_rate_calculation(self, journal: AutoJournal) -> None:
        # 2 wins, 1 loss
        for pnl in [5_000, 3_000, -2_000]:
            journal.record_trade(
                event_type="EXIT",
                ticker="000660",
                direction="SELL",
                quantity=1,
                price=200_000,
                pnl_krw=float(pnl),
            )
        stats = journal.get_win_rate()
        assert stats["trades"] == 3
        assert stats["wins"] == 2
        assert stats["losses"] == 1
        assert abs(stats["win_rate_pct"] - 66.7) < 0.1
        assert stats["total_pnl"] == 6_000.0

    def test_record_tick(self, journal: AutoJournal) -> None:
        journal.record_tick("005930", 72_000, bid=71_950, ask=72_050, bid_qty=500, ask_qty=300)
        # Just ensure no exception is raised and DB is consistent
        import sqlite3
        conn = sqlite3.connect(journal._db_path)
        rows = conn.execute("SELECT * FROM tick_snapshots").fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][2] == "005930"

    def test_win_rate_no_trades(self, journal: AutoJournal) -> None:
        stats = journal.get_win_rate()
        assert stats["trades"] == 0
        assert stats["win_rate_pct"] == 0.0
