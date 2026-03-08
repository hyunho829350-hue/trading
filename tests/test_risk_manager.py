"""tests/test_risk_manager.py – Unit tests for RiskManager."""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from core.risk_manager import RiskManager, KillSwitchError


class TestRiskManager:
    def _make(self, **kwargs) -> RiskManager:
        defaults = dict(
            daily_loss_limit=100_000,
            max_positions=3,
            stop_loss_pct=0.5,
            take_profit_pct=1.0,
        )
        defaults.update(kwargs)
        return RiskManager(**defaults)

    def test_kill_switch_initially_inactive(self) -> None:
        rm = self._make()
        assert not rm.kill_switch_active

    def test_manual_kill_switch(self) -> None:
        triggered = []
        rm = self._make(on_kill_switch=lambda: triggered.append(True))
        rm.activate_kill_switch("Test")
        assert rm.kill_switch_active
        assert triggered == [True]

    def test_double_activate_only_fires_once(self) -> None:
        triggered = []
        rm = self._make(on_kill_switch=lambda: triggered.append(True))
        rm.activate_kill_switch("First")
        rm.activate_kill_switch("Second")
        assert len(triggered) == 1

    def test_deactivate_kill_switch(self) -> None:
        rm = self._make()
        rm.activate_kill_switch()
        rm.deactivate_kill_switch()
        assert not rm.kill_switch_active

    def test_assert_trading_allowed_raises_when_active(self) -> None:
        rm = self._make()
        rm.activate_kill_switch()
        with pytest.raises(KillSwitchError):
            rm.assert_trading_allowed()

    def test_assert_trading_allowed_passes_when_inactive(self) -> None:
        rm = self._make()
        rm.assert_trading_allowed()  # Should not raise

    def test_daily_loss_limit_triggers_kill_switch(self) -> None:
        triggered = []
        rm = self._make(
            daily_loss_limit=100_000,
            on_kill_switch=lambda: triggered.append(True),
        )
        rm.record_pnl(-50_000)
        assert not rm.kill_switch_active
        rm.record_pnl(-60_000)   # total = -110_000 → breaches limit
        assert rm.kill_switch_active
        assert triggered

    def test_daily_pnl_accumulates(self) -> None:
        rm = self._make()
        rm.record_pnl(10_000)
        rm.record_pnl(-5_000)
        assert rm.daily_pnl == 5_000

    def test_reset_daily_pnl(self) -> None:
        rm = self._make()
        rm.record_pnl(20_000)
        rm.reset_daily_pnl()
        assert rm.daily_pnl == 0.0

    def test_can_open_position_within_limit(self) -> None:
        rm = self._make(max_positions=3)
        assert rm.can_open_position(2) is True
        assert rm.can_open_position(3) is False

    def test_can_open_position_blocked_by_kill_switch(self) -> None:
        rm = self._make()
        rm.activate_kill_switch()
        assert rm.can_open_position(0) is False

    def test_stop_loss_price(self) -> None:
        rm = self._make(stop_loss_pct=0.5)
        sl = rm.stop_loss_price(100_000)
        assert sl == 99_500

    def test_take_profit_price(self) -> None:
        rm = self._make(take_profit_pct=1.0)
        tp = rm.take_profit_price(100_000)
        assert tp == 101_000
