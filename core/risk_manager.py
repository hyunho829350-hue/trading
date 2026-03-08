"""core/risk_manager.py – Risk management and kill-switch logic.

Responsibilities:
  • Track daily realised P&L and fire the kill-switch when the daily loss
    limit is breached.
  • Enforce maximum simultaneous position count.
  • Compute per-trade stop-loss and take-profit price levels.
  • Expose a ``KillSwitchError`` that trading_engine raises when the kill
    switch is active so that all order submissions are blocked.
"""
from __future__ import annotations

import threading
from typing import Callable

import config


class KillSwitchError(RuntimeError):
    """Raised when the kill-switch has been activated."""


class RiskManager:
    """Central risk gatekeeper for the trading session."""

    def __init__(
        self,
        daily_loss_limit: float = config.DAILY_LOSS_LIMIT_KRW,
        max_positions: int = config.MAX_POSITION_COUNT,
        stop_loss_pct: float = config.MAX_LOSS_PER_TRADE_PCT,
        take_profit_pct: float = config.TAKE_PROFIT_PCT,
        on_kill_switch: Callable[[], None] | None = None,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._daily_loss_limit = daily_loss_limit
        self._max_positions = max_positions
        self._stop_loss_pct = stop_loss_pct / 100.0
        self._take_profit_pct = take_profit_pct / 100.0
        self._on_kill_switch = on_kill_switch or (lambda: None)
        self._log = log_callback or (lambda _: None)

        self._lock = threading.Lock()
        self._daily_pnl: float = 0.0
        self._kill_switch_active: bool = False

    # ── kill-switch ───────────────────────────────────────────────────────────

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_switch_active

    def activate_kill_switch(self, reason: str = "Manual") -> None:
        """Manually or automatically activate the kill-switch."""
        with self._lock:
            if self._kill_switch_active:
                return
            self._kill_switch_active = True
        self._log(f"[KILL SWITCH] Activated – reason: {reason}")
        self._on_kill_switch()

    def deactivate_kill_switch(self) -> None:
        """Reset the kill-switch (use with caution)."""
        with self._lock:
            self._kill_switch_active = False
        self._log("[KILL SWITCH] Deactivated.")

    def assert_trading_allowed(self) -> None:
        """Raise KillSwitchError if the kill-switch is active."""
        if self._kill_switch_active:
            raise KillSwitchError("Kill-switch is active – all trading blocked.")

    # ── daily P&L tracking ────────────────────────────────────────────────────

    def record_pnl(self, pnl_krw: float) -> None:
        """Update cumulative daily P&L and auto-trigger kill-switch if needed."""
        with self._lock:
            self._daily_pnl += pnl_krw
            current = self._daily_pnl
        if current <= -abs(self._daily_loss_limit):
            self.activate_kill_switch(
                f"Daily loss limit breached (₩{current:,.0f})"
            )

    def reset_daily_pnl(self) -> None:
        with self._lock:
            self._daily_pnl = 0.0

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    # ── position count guard ──────────────────────────────────────────────────

    def can_open_position(self, current_count: int) -> bool:
        return current_count < self._max_positions and not self._kill_switch_active

    # ── price levels ──────────────────────────────────────────────────────────

    def stop_loss_price(self, entry_price: float) -> float:
        return round(entry_price * (1.0 - self._stop_loss_pct))

    def take_profit_price(self, entry_price: float) -> float:
        return round(entry_price * (1.0 + self._take_profit_pct))
