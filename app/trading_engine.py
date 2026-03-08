"""
Real-time trading engine – Stage 2.

Responsibilities
----------------
* Load condition lists from Kiwoom HTS and start the selected condition.
* Register detected stocks for real-time quotes via ``SetRealReg``.
* Parse ``OnReceiveRealData`` events and detect buy signals.
* Delegate order placement to ``OrderManager``.

Buy signal criteria (adjustable via constructor kwargs)
-------------------------------------------------------
* Current volume > 0  (non-zero activity)
* Price within ``max_gap_from_open`` % of the day's open (not a run-away gap)
* Stock is in the active condition result and has no existing position

Note: A full average-volume comparison (``volume_surge_ratio``) requires
historical data which would need a separate TR request; the parameter is
reserved for a future enhancement.
"""

import logging
from typing import Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal

from .kiwoom import KiwoomAPI, REALTIME_FID_LIST
from .kiwoom import (
    FID_CURRENT_PRICE, FID_VOLUME, FID_BEST_ASK1,
    FID_OPEN, FID_HIGH, FID_LOW, FID_CHANGE_RATE,
)
from .order_manager import OrderManager

logger = logging.getLogger(__name__)

CONDITION_SCREEN_NO = "5000"
REALTIME_SCREEN_NO = "1000"

# Default buy-signal parameters
DEFAULT_VOLUME_SURGE_RATIO: float = 2.0   # reserved for future average-volume comparison
DEFAULT_MAX_GAP_FROM_OPEN: float = 0.03   # 시가 대비 최대 허용 갭 비율
DEFAULT_ORDER_QTY: int = 1                # 1주 (실사용 시 자금 관리 로직으로 교체)


class TradingEngine(QObject):
    """Wires together Kiwoom events, signal detection, and order dispatch.

    Signals (Qt)
    ------------
    condition_stocks_updated(list):
        Emitted when the condition search result changes.
    buy_signal(str, int):
        Emitted when a buy signal is detected for (code, price).
    log_message(str):
        General log line for the UI.
    """

    condition_stocks_updated = pyqtSignal(list)
    buy_signal = pyqtSignal(str, int)
    log_message = pyqtSignal(str)

    def __init__(
        self,
        kiwoom: KiwoomAPI,
        order_manager: OrderManager,
        volume_surge_ratio: float = DEFAULT_VOLUME_SURGE_RATIO,
        max_gap_from_open: float = DEFAULT_MAX_GAP_FROM_OPEN,
        order_qty: int = DEFAULT_ORDER_QTY,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._kiwoom = kiwoom
        self._order_manager = order_manager
        self._volume_surge_ratio = volume_surge_ratio
        self._max_gap_from_open = max_gap_from_open
        self._order_qty = order_qty

        # condition index -> name for currently active condition
        self._active_condition: Optional[tuple] = None  # (index, name)

        # code -> snapshot of latest real-time data
        self._rt_data: Dict[str, Dict[str, int]] = {}
        # Codes currently in the condition result
        self._condition_codes: List[str] = []

        kiwoom.register_on_real_data(self._on_real_data)
        kiwoom.register_on_receive_realcondition(self._on_receive_real_condition)
        kiwoom.register_on_condition_verse(self._on_condition_verse)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_conditions(self) -> Dict[int, str]:
        """Load and return condition list from HTS."""
        if not self._kiwoom.get_condition_load():
            logger.warning("GetConditionLoad() returned failure.")
        conditions = self._kiwoom.get_condition_name_list()
        logger.info("Loaded %d conditions: %s", len(conditions), conditions)
        return conditions

    def start_condition(self, index: int, name: str) -> bool:
        """Activate real-time condition monitoring for the given condition."""
        if self._active_condition:
            self.stop_condition()

        ok = self._kiwoom.send_condition(
            screen_no=CONDITION_SCREEN_NO,
            cond_name=name,
            cond_index=index,
            is_realtime=1,
        )
        if ok:
            self._active_condition = (index, name)
            msg = f"[조건검색 시작] [{index}] {name}"
            logger.info(msg)
            self.log_message.emit(msg)
        else:
            logger.warning("SendCondition failed for %s(%d)", name, index)
        return ok

    def stop_condition(self) -> None:
        """Stop the currently active condition."""
        if not self._active_condition:
            return
        index, name = self._active_condition
        self._kiwoom.send_condition_stop(CONDITION_SCREEN_NO, name, index)
        self._active_condition = None
        logger.info("Condition %s(%d) stopped.", name, index)

    # ------------------------------------------------------------------
    # Kiwoom event callbacks
    # ------------------------------------------------------------------

    def _on_condition_verse(self, screen_no: str, code_list: str,
                            cond_name: str, cond_index: int,
                            next_: int) -> None:
        """Initial result set for the activated condition."""
        codes = [c for c in code_list.split(";") if c.strip()]
        self._update_condition_codes(codes)
        msg = f"[조건검색 결과] {cond_name}: {len(codes)}종목"
        logger.info(msg)
        self.log_message.emit(msg)
        self.condition_stocks_updated.emit(codes)

    def _on_receive_real_condition(self, code: str, event_type: str,
                                   cond_name: str, cond_index: str) -> None:
        """Real-time add/remove notifications for condition result."""
        if event_type == "I":  # 편입
            if code not in self._condition_codes:
                self._condition_codes.append(code)
                self._register_realtime(code)
                msg = f"[조건 편입] {code} ({cond_name})"
                logger.info(msg)
                self.log_message.emit(msg)
                self.condition_stocks_updated.emit(list(self._condition_codes))
        elif event_type == "D":  # 이탈
            if code in self._condition_codes:
                self._condition_codes.remove(code)
                self._kiwoom.set_real_remove(REALTIME_SCREEN_NO, code)
                msg = f"[조건 이탈] {code} ({cond_name})"
                logger.info(msg)
                self.log_message.emit(msg)
                self.condition_stocks_updated.emit(list(self._condition_codes))

    def _on_real_data(self, code: str, real_type: str, _real_data: str) -> None:
        """Parse incoming real-time tick and evaluate buy signal."""
        if real_type != "주식체결":
            return

        def _parse(fid: str) -> int:
            raw = self._kiwoom.get_comm_real_data(code, fid).strip()
            try:
                return abs(int(raw))
            except ValueError:
                return 0

        current_price = _parse(FID_CURRENT_PRICE)
        volume = _parse(FID_VOLUME)
        open_price = _parse(FID_OPEN)
        best_ask = _parse(FID_BEST_ASK1)

        if current_price == 0:
            return

        snapshot = {
            "price": current_price,
            "volume": volume,
            "open": open_price,
            "best_ask": best_ask,
        }
        self._rt_data[code] = snapshot

        # Forward price to order manager for stop-loss/take-profit checks
        self._order_manager.update_price(code, current_price)

        # Evaluate buy signal
        if self._is_buy_signal(code, snapshot):
            msg = f"[매수 신호] {code} @ {current_price:,}원"
            logger.info(msg)
            self.log_message.emit(msg)
            self.buy_signal.emit(code, current_price)
            self._order_manager.buy(code, self._order_qty, current_price)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_condition_codes(self, codes: List[str]) -> None:
        new_set = set(codes)
        old_set = set(self._condition_codes)

        for code in new_set - old_set:
            self._register_realtime(code)
        for code in old_set - new_set:
            self._kiwoom.set_real_remove(REALTIME_SCREEN_NO, code)

        self._condition_codes = codes

    def _register_realtime(self, code: str) -> None:
        self._kiwoom.set_real_reg(
            screen_no=REALTIME_SCREEN_NO,
            code_list=code,
            fid_list=REALTIME_FID_LIST,
            opt_type="0",
        )

    def _is_buy_signal(self, code: str, snap: Dict[str, int]) -> bool:
        """Return True when the snapshot satisfies buy conditions.

        Rules:
        1. The stock must be in the active condition result.
        2. The current price must not be more than ``max_gap_from_open`` above
           the open price (avoid chasing gap-up opens).
        3. Volume surge: current cumulative volume ≥ some minimum threshold
           (simple check; a full implementation would compare against a moving
           average which requires historical data not available without a TR).
        4. The code must not already have an open position.
        """
        if code not in self._condition_codes:
            return False

        if code in self._order_manager.positions:
            return False

        price = snap["price"]
        open_price = snap.get("open", 0)

        if open_price and open_price > 0:
            gap = (price - open_price) / open_price
            if gap > self._max_gap_from_open:
                return False

        volume = snap.get("volume", 0)
        if volume < 1:
            return False

        return True
