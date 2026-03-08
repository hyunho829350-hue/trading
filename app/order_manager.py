"""
Order manager – safe buy/sell logic with slippage, unfilled-order cancellation,
and stop-loss / take-profit monitoring.

Architecture
------------
* ``OrderManager`` holds a dict of open positions keyed by stock code.
* When a buy order is placed the position is tracked as ``PENDING``.
* On chejan event (체결잔고) the state transitions to ``FILLED``.
* A ``QTimer`` fires every second to:
  - Cancel or correct unfilled orders that are older than ``CANCEL_TIMEOUT_SEC``.
  - Check stop-loss / take-profit targets for filled positions.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable, Dict, Optional

from PyQt5.QtCore import QTimer

from .kiwoom import KiwoomAPI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants (can be overridden via constructor kwargs)
# ---------------------------------------------------------------------------
DEFAULT_CANCEL_TIMEOUT_SEC: int = 5       # cancel unfilled order after this many seconds
DEFAULT_TAKE_PROFIT_RATE: float = 0.05    # 5 % gain → sell
DEFAULT_STOP_LOSS_RATE: float = 0.03      # 3 % loss → sell
DEFAULT_SLIPPAGE_TICKS: int = 2           # buy at current_price + N ticks above
MONITOR_INTERVAL_MS: int = 1_000          # position-monitor polling interval

# Kiwoom chejan FIDs
CHEJAN_FID_ORDER_NO = 9203       # 주문번호
CHEJAN_FID_CODE = 9001           # 종목코드
CHEJAN_FID_ORDER_STATE = 913     # 주문상태
CHEJAN_FID_FILLED_QTY = 911      # 체결수량
CHEJAN_FID_FILLED_PRICE = 910    # 체결가
CHEJAN_FID_UNFILLED_QTY = 902    # 미체결수량

# Order types
ORDER_BUY = 1
ORDER_SELL = 2
ORDER_CANCEL_BUY = 3
ORDER_CANCEL_SELL = 4
ORDER_CORRECT_BUY = 5
ORDER_CORRECT_SELL = 6

HOGA_LIMIT = "00"    # 지정가
HOGA_MARKET = "03"   # 시장가


class PositionState(Enum):
    PENDING = auto()   # order sent, not yet filled
    FILLED = auto()    # fully filled
    CLOSED = auto()    # position closed (profit / loss taken)


@dataclass
class Position:
    """Tracks a single open or pending position."""
    code: str
    order_no: str
    qty: int
    order_price: int
    filled_price: int = 0
    filled_qty: int = 0
    state: PositionState = PositionState.PENDING
    order_time: float = field(default_factory=time.time)
    target_price: int = 0    # 익절가
    stop_price: int = 0      # 손절가


class OrderManager:
    """Manages the full order lifecycle for the automated trading program.

    Parameters
    ----------
    kiwoom:
        Initialised and logged-in ``KiwoomAPI`` instance.
    account:
        Account number string to trade on.
    cancel_timeout_sec:
        Seconds to wait for a fill before cancelling the order.
    take_profit_rate:
        Fractional gain at which to take profit (e.g. ``0.05`` for 5 %).
    stop_loss_rate:
        Fractional loss at which to stop-loss (e.g. ``0.03`` for 3 %).
    slippage_ticks:
        Number of ticks above current price used for limit buy orders.
    on_log:
        Optional callback ``(str) -> None`` to forward log messages to the UI.
    """

    def __init__(
        self,
        kiwoom: KiwoomAPI,
        account: str,
        cancel_timeout_sec: int = DEFAULT_CANCEL_TIMEOUT_SEC,
        take_profit_rate: float = DEFAULT_TAKE_PROFIT_RATE,
        stop_loss_rate: float = DEFAULT_STOP_LOSS_RATE,
        slippage_ticks: int = DEFAULT_SLIPPAGE_TICKS,
        on_log: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._kiwoom = kiwoom
        self._account = account
        self._cancel_timeout_sec = cancel_timeout_sec
        self._take_profit_rate = take_profit_rate
        self._stop_loss_rate = stop_loss_rate
        self._slippage_ticks = slippage_ticks
        self._on_log = on_log

        # code -> Position
        self._positions: Dict[str, Position] = {}
        # order_no -> code  (reverse lookup for chejan events)
        self._order_to_code: Dict[str, str] = {}

        # Current real-time prices – updated by trading engine
        self._current_prices: Dict[str, int] = {}
        # Tick size cache – populated lazily
        self._tick_sizes: Dict[str, int] = {}

        kiwoom.register_on_chejan(self._on_chejan)

        self._monitor_timer = QTimer()
        self._monitor_timer.setInterval(MONITOR_INTERVAL_MS)
        self._monitor_timer.timeout.connect(self._monitor_positions)
        self._monitor_timer.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_price(self, code: str, price: int) -> None:
        """Called by the trading engine whenever a new price arrives."""
        self._current_prices[code] = price

    def buy(self, code: str, qty: int, current_price: int,
            screen_no: str = "2000") -> bool:
        """Place a limit buy order with slippage adjustment.

        The order price is ``current_price + slippage_ticks * tick_size``.

        Returns True if the order was sent successfully.
        """
        if code in self._positions:
            self._log(f"[매수 거부] {code} 이미 포지션 존재")
            return False

        tick = self._get_tick_size(current_price)
        order_price = current_price + self._slippage_ticks * tick

        ret = self._kiwoom.send_order(
            rqname=f"매수_{code}",
            screen_no=screen_no,
            account=self._account,
            order_type=ORDER_BUY,
            code=code,
            qty=qty,
            price=order_price,
            hoga_type=HOGA_LIMIT,
        )

        if ret != 0:
            self._log(f"[매수 실패] {code} 오류코드={ret}")
            return False

        pos = Position(code=code, order_no="", qty=qty, order_price=order_price)
        self._positions[code] = pos
        self._log(
            f"[매수 주문] {code} {qty}주 @ {order_price:,}원 "
            f"(현재가 {current_price:,} + {self._slippage_ticks}틱)"
        )
        return True

    def sell_market(self, code: str, qty: int, reason: str = "매도",
                    screen_no: str = "2001") -> bool:
        """Place a market sell order for *code*."""
        ret = self._kiwoom.send_order(
            rqname=f"{reason}_{code}",
            screen_no=screen_no,
            account=self._account,
            order_type=ORDER_SELL,
            code=code,
            qty=qty,
            price=0,
            hoga_type=HOGA_MARKET,
        )
        if ret != 0:
            self._log(f"[{reason} 실패] {code} 오류코드={ret}")
            return False
        self._log(f"[{reason}] {code} {qty}주 시장가 매도 주문")
        return True

    def cancel_order(self, code: str, screen_no: str = "2002") -> bool:
        """Cancel the pending buy order for *code*."""
        pos = self._positions.get(code)
        if pos is None or pos.state != PositionState.PENDING:
            return False
        if not pos.order_no:
            return False

        ret = self._kiwoom.send_order(
            rqname=f"취소_{code}",
            screen_no=screen_no,
            account=self._account,
            order_type=ORDER_CANCEL_BUY,
            code=code,
            qty=pos.qty,
            price=0,
            hoga_type=HOGA_LIMIT,
            org_order_no=pos.order_no,
        )
        if ret != 0:
            self._log(f"[취소 실패] {code} 오류코드={ret}")
            return False

        self._log(f"[주문 취소] {code} 주문번호={pos.order_no}")
        del self._positions[code]
        if pos.order_no:
            self._order_to_code.pop(pos.order_no, None)
        return True

    def correct_order(self, code: str, new_price: int,
                      screen_no: str = "2003") -> bool:
        """Correct the order price of a pending buy order for *code*."""
        pos = self._positions.get(code)
        if pos is None or pos.state != PositionState.PENDING:
            return False
        if not pos.order_no:
            return False

        ret = self._kiwoom.send_order(
            rqname=f"정정_{code}",
            screen_no=screen_no,
            account=self._account,
            order_type=ORDER_CORRECT_BUY,
            code=code,
            qty=pos.qty - pos.filled_qty,
            price=new_price,
            hoga_type=HOGA_LIMIT,
            org_order_no=pos.order_no,
        )
        if ret != 0:
            self._log(f"[정정 실패] {code} 오류코드={ret}")
            return False

        pos.order_price = new_price
        self._log(f"[주문 정정] {code} → {new_price:,}원")
        return True

    @property
    def positions(self) -> Dict[str, Position]:
        return dict(self._positions)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _monitor_positions(self) -> None:
        """Periodic routine – cancel stale orders and check profit/loss."""
        now = time.time()
        for code, pos in list(self._positions.items()):
            if pos.state == PositionState.PENDING:
                elapsed = now - pos.order_time
                if elapsed >= self._cancel_timeout_sec:
                    self._log(
                        f"[미체결 취소] {code} {elapsed:.0f}초 경과 → 주문 취소"
                    )
                    self.cancel_order(code)

            elif pos.state == PositionState.FILLED:
                price = self._current_prices.get(code)
                if price is None:
                    continue
                if pos.target_price and price >= pos.target_price:
                    self._log(
                        f"[익절] {code} 현재가={price:,} >= 목표가={pos.target_price:,}"
                    )
                    if self.sell_market(code, pos.filled_qty, reason="익절"):
                        pos.state = PositionState.CLOSED
                elif pos.stop_price and price <= pos.stop_price:
                    self._log(
                        f"[손절] {code} 현재가={price:,} <= 손절가={pos.stop_price:,}"
                    )
                    if self.sell_market(code, pos.filled_qty, reason="손절"):
                        pos.state = PositionState.CLOSED

    def _on_chejan(self, gubun: str, _item_cnt: int, _fid_list: str) -> None:
        """Handle chejan (체결잔고) events from the Kiwoom API."""
        if gubun != "0":  # 0 = 주문체결, 1 = 잔고
            return

        raw_code: str = self._kiwoom.get_chejan_data(CHEJAN_FID_CODE).strip()
        code = raw_code.lstrip("A")  # Kiwoom prefixes KOSDAQ codes with "A"
        order_no: str = self._kiwoom.get_chejan_data(CHEJAN_FID_ORDER_NO).strip()
        filled_qty_str: str = self._kiwoom.get_chejan_data(CHEJAN_FID_FILLED_QTY).strip()
        filled_price_str: str = self._kiwoom.get_chejan_data(CHEJAN_FID_FILLED_PRICE).strip()

        if not code:
            return

        # Register order_no -> code on first event
        if order_no and order_no not in self._order_to_code:
            self._order_to_code[order_no] = code

        pos = self._positions.get(code)
        if pos is None:
            return

        # Update order number if not yet known
        if not pos.order_no and order_no:
            pos.order_no = order_no

        try:
            filled_qty = int(filled_qty_str) if filled_qty_str else 0
            filled_price = int(filled_price_str) if filled_price_str else 0
        except ValueError:
            return

        if filled_qty > 0 and filled_price > 0:
            pos.filled_qty += filled_qty
            pos.filled_price = filled_price

            if pos.filled_qty >= pos.qty:
                pos.state = PositionState.FILLED
                pos.target_price = int(filled_price * (1 + self._take_profit_rate))
                pos.stop_price = int(filled_price * (1 - self._stop_loss_rate))
                self._log(
                    f"[체결 완료] {code} {pos.filled_qty}주 @ {filled_price:,}원  "
                    f"목표가={pos.target_price:,}  손절가={pos.stop_price:,}"
                )

    @staticmethod
    def _get_tick_size(price: int) -> int:
        """Return the minimum price tick for the given stock price.

        Based on KRX rules (KOSPI/KOSDAQ unified from 2023-01-02):
            price < 2,000          →    1
            2,000 ≤ price < 5,000  →    5
            5,000 ≤ price < 20,000 →   10
            20,000 ≤ price < 50,000 →  50
            50,000 ≤ price < 200,000 → 100
            200,000 ≤ price < 500,000 → 500
            500,000 ≤                 → 1,000
        """
        if price < 2_000:
            return 1
        if price < 5_000:
            return 5
        if price < 20_000:
            return 10
        if price < 50_000:
            return 50
        if price < 200_000:
            return 100
        if price < 500_000:
            return 500
        return 1_000

    def _log(self, message: str) -> None:
        logger.info(message)
        if self._on_log:
            self._on_log(message)
