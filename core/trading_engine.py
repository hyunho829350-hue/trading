"""core/trading_engine.py – Smart execution engine.

Features:
  • Slippage-controlled limit orders (price ± N ticks from current market).
  • Pending order tracker with automatic cancel-and-resubmit after timeout.
  • Position timeout liquidation (force-close after MAX minutes).
  • Integration with ThrottleManager, RiskManager, and AutoJournal.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import config
from core.api_client import APIClient, OrderResult, Tick
from core.auto_journal import AutoJournal
from core.risk_manager import RiskManager, KillSwitchError
from core.throttle_manager import ThrottleManager


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Position:
    ticker: str
    name: str
    entry_price: int
    quantity: int
    stop_loss: int
    take_profit: int
    opened_at: float = field(default_factory=time.monotonic)
    current_price: int = 0

    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * 100

    @property
    def pnl_krw(self) -> float:
        return (self.current_price - self.entry_price) * self.quantity

    @property
    def age_seconds(self) -> float:
        return time.monotonic() - self.opened_at


@dataclass
class PendingOrder:
    order_result: OrderResult
    ticker: str
    name: str
    direction: str
    quantity: int
    target_price: int
    submitted_at: float = field(default_factory=time.monotonic)
    retry_count: int = 0


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class TradingEngine:
    """Orchestrates order submission, position management, and risk checks."""

    def __init__(
        self,
        api: APIClient,
        throttle: ThrottleManager,
        risk: RiskManager,
        journal: AutoJournal,
        order_timeout_sec: float = config.ORDER_TIMEOUT_SEC,
        position_timeout_min: float = config.POSITION_TIMEOUT_MIN,
        slippage_ticks: int = config.SLIPPAGE_TICKS,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._api = api
        self._throttle = throttle
        self._risk = risk
        self._journal = journal
        self._order_timeout = order_timeout_sec
        self._position_timeout = position_timeout_min * 60
        self._slippage_ticks = slippage_ticks
        self._log = log_callback or (lambda _: None)

        self._lock = threading.Lock()
        self._positions: dict[str, Position] = {}       # ticker -> Position
        self._pending_orders: dict[str, PendingOrder] = {}  # order_id -> PendingOrder

        # Callbacks so UI can refresh
        self.on_position_update: Callable[[], None] | None = None
        self.on_order_update: Callable[[OrderResult], None] | None = None

        self._running = False
        self._monitor_thread: threading.Thread | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="engine-monitor"
        )
        self._monitor_thread.start()
        self._log("[Engine] Started.")

    def stop(self) -> None:
        self._running = False
        self._log("[Engine] Stopped.")

    # ── order submission ──────────────────────────────────────────────────────

    def buy(self, ticker: str, name: str, quantity: int, current_price: int) -> None:
        """Submit a slippage-controlled buy order."""
        try:
            self._risk.assert_trading_allowed()
        except KillSwitchError as e:
            self._log(f"[Engine] BUY blocked – {e}")
            return

        with self._lock:
            pos_count = len(self._positions)
        if not self._risk.can_open_position(pos_count):
            self._log(f"[Engine] BUY blocked – max positions reached ({pos_count}).")
            return

        # Slippage: place limit order slightly above current price (eager fill)
        tick_size = self._tick_size(current_price)
        limit_price = current_price + tick_size * self._slippage_ticks

        self._throttle.acquire_order_slot()
        result = self._api.send_order(ticker, "BUY", quantity, limit_price)
        self._log(
            f"[Order] BUY {ticker} qty={quantity} price={limit_price:,} → {result.status}"
        )

        if result.status == "FILLED":
            self._open_position(result, ticker, name, result.filled_price, quantity)
        else:
            with self._lock:
                self._pending_orders[result.order_id] = PendingOrder(
                    order_result=result,
                    ticker=ticker,
                    name=name,
                    direction="BUY",
                    quantity=quantity,
                    target_price=limit_price,
                )

        if self.on_order_update:
            self.on_order_update(result)

    def sell(self, ticker: str, quantity: int, reason: str = "Manual") -> None:
        """Close an existing position."""
        with self._lock:
            pos = self._positions.get(ticker)
        if pos is None:
            self._log(f"[Engine] SELL {ticker} – no open position.")
            return

        self._throttle.acquire_order_slot()
        tick_size = self._tick_size(pos.current_price or pos.entry_price)
        limit_price = (pos.current_price or pos.entry_price) - tick_size * self._slippage_ticks
        result = self._api.send_order(ticker, "SELL", quantity, limit_price)

        if result.status in ("FILLED", "PENDING"):
            pnl_krw = (result.filled_price - pos.entry_price) * quantity if result.status == "FILLED" else 0
            pnl_pct = pnl_krw / (pos.entry_price * quantity) * 100 if pos.entry_price else 0

            self._log(
                f"[Order] SELL {ticker} qty={quantity} price={result.filled_price:,} "
                f"P&L=₩{pnl_krw:+,.0f} ({pnl_pct:+.2f}%) reason={reason}"
            )
            if result.status == "FILLED":
                self._risk.record_pnl(pnl_krw)
                self._api.add_mock_pnl(pnl_krw)
                self._journal.record_trade(
                    event_type="EXIT",
                    ticker=ticker,
                    direction="SELL",
                    quantity=quantity,
                    price=result.filled_price,
                    entry_price=pos.entry_price,
                    pnl_krw=pnl_krw,
                    pnl_pct=round(pnl_pct, 3),
                    note=reason,
                )
                with self._lock:
                    self._positions.pop(ticker, None)
                if self.on_position_update:
                    self.on_position_update()

        if self.on_order_update:
            self.on_order_update(result)

    def liquidate_all(self, reason: str = "Kill-Switch") -> None:
        """Force-close all positions (kill-switch)."""
        self._log(f"[Engine] LIQUIDATE ALL – reason: {reason}")
        with self._lock:
            tickers = list(self._positions.keys())
        for ticker in tickers:
            with self._lock:
                pos = self._positions.get(ticker)
            if pos:
                self.sell(ticker, pos.quantity, reason=reason)

    # ── tick update ───────────────────────────────────────────────────────────

    def on_tick(self, tick: Tick) -> None:
        """Called by the API client for every incoming market tick."""
        with self._lock:
            pos = self._positions.get(tick.ticker)
        if pos is None:
            return

        pos.current_price = tick.price
        self._journal.record_tick(
            tick.ticker, tick.price, tick.bid, tick.ask, tick.bid_qty, tick.ask_qty
        )

        # Check stop-loss / take-profit
        if tick.price <= pos.stop_loss:
            self._log(f"[Engine] Stop-loss hit for {tick.ticker} @ {tick.price:,}")
            self.sell(tick.ticker, pos.quantity, reason="Stop-Loss")
        elif tick.price >= pos.take_profit:
            self._log(f"[Engine] Take-profit hit for {tick.ticker} @ {tick.price:,}")
            self.sell(tick.ticker, pos.quantity, reason="Take-Profit")

        if self.on_position_update:
            self.on_position_update()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _open_position(
        self,
        result: OrderResult,
        ticker: str,
        name: str,
        filled_price: int,
        quantity: int,
    ) -> None:
        pos = Position(
            ticker=ticker,
            name=name,
            entry_price=filled_price,
            quantity=quantity,
            stop_loss=self._risk.stop_loss_price(filled_price),
            take_profit=self._risk.take_profit_price(filled_price),
            current_price=filled_price,
        )
        with self._lock:
            self._positions[ticker] = pos
        self._log(
            f"[Engine] Position opened: {ticker} entry={filled_price:,} "
            f"SL={pos.stop_loss:,} TP={pos.take_profit:,}"
        )
        self._journal.record_trade(
            event_type="ENTRY",
            ticker=ticker,
            direction="BUY",
            quantity=quantity,
            price=filled_price,
        )
        if self.on_position_update:
            self.on_position_update()

    def _monitor_loop(self) -> None:
        """Background thread: handle pending order timeouts and position timeouts."""
        while self._running:
            now = time.monotonic()

            # Pending order timeout → cancel + resubmit
            with self._lock:
                pending_ids = list(self._pending_orders.keys())
            for oid in pending_ids:
                with self._lock:
                    po = self._pending_orders.get(oid)
                if po is None:
                    continue
                if now - po.submitted_at > self._order_timeout:
                    self._api.cancel_order(oid)
                    self._log(
                        f"[Engine] Order {oid} timed out – resubmitting "
                        f"(attempt {po.retry_count + 1})"
                    )
                    with self._lock:
                        self._pending_orders.pop(oid, None)
                    # Resubmit on next tick (avoid infinite retry storm)
                    if po.retry_count < 3:
                        self._throttle.acquire_order_slot()
                        new_result = self._api.send_order(
                            po.ticker, po.direction, po.quantity, po.target_price
                        )
                        if new_result.status == "FILLED" and po.direction == "BUY":
                            self._open_position(
                                new_result, po.ticker, po.name,
                                new_result.filled_price, po.quantity
                            )
                        elif new_result.status == "PENDING":
                            po.order_result = new_result
                            po.submitted_at = now
                            po.retry_count += 1
                            with self._lock:
                                self._pending_orders[new_result.order_id] = po

            # Position timeout liquidation
            with self._lock:
                pos_list = list(self._positions.values())
            for pos in pos_list:
                if pos.age_seconds > self._position_timeout:
                    self._log(
                        f"[Engine] Position timeout for {pos.ticker} "
                        f"(held {pos.age_seconds/60:.1f} min) – liquidating."
                    )
                    self.sell(pos.ticker, pos.quantity, reason="Timeout")

            time.sleep(1)

    # ── accessors (for UI) ────────────────────────────────────────────────────

    @property
    def positions(self) -> dict[str, Position]:
        with self._lock:
            return dict(self._positions)

    @staticmethod
    def _tick_size(price: int) -> int:
        """Korean market tick size rules (simplified)."""
        if price < 2_000:
            return 1
        elif price < 5_000:
            return 5
        elif price < 20_000:
            return 10
        elif price < 50_000:
            return 50
        elif price < 200_000:
            return 100
        elif price < 500_000:
            return 500
        else:
            return 1_000
