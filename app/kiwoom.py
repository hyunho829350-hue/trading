"""
Kiwoom Securities OpenAPI+ wrapper.

This module wraps the COM-based QAxWidget("KHOPENAPI.KHOpenAPICtrl.1") control
and exposes a clean Python interface for login, real-time data subscription,
condition searches, and order management.

Note: The Kiwoom OpenAPI+ is only available on Windows.  On other platforms the
QAxWidget instantiation will fail at runtime; the rest of the code (UI, logic)
can still be exercised in a mock/test environment.
"""

import logging
from typing import Callable, Dict, List, Optional

from PyQt5.QtAxContainer import QAxWidget
from PyQt5.QtCore import QEventLoop

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kiwoom real-data FIDs (field IDs) used by OnReceiveRealData
# ---------------------------------------------------------------------------
FID_CURRENT_PRICE = "10"   # 현재가
FID_VOLUME = "15"          # 거래량
FID_BEST_ASK1 = "41"       # 매도호가1
FID_BEST_BID1 = "51"       # 매수호가1
FID_OPEN = "16"            # 시가
FID_HIGH = "17"            # 고가
FID_LOW = "18"             # 저가
FID_CHANGE_RATE = "12"     # 등락율

# Default FID list used when subscribing to real-time stock data
REALTIME_FID_LIST = ";".join([
    FID_CURRENT_PRICE, FID_VOLUME, FID_BEST_ASK1, FID_BEST_BID1,
    FID_OPEN, FID_HIGH, FID_LOW, FID_CHANGE_RATE,
])


class KiwoomAPI:
    """Thin wrapper around the Kiwoom QAxWidget COM control.

    Signals emitted by the underlying QAxWidget are forwarded to registered
    Python callbacks so that the rest of the application does not need to
    interact with the COM layer directly.
    """

    def __init__(self) -> None:
        self._ocx: Optional[QAxWidget] = None
        self._login_event_loop: Optional[QEventLoop] = None
        self._last_login_errcode: int = -1

        # Callbacks keyed by event name
        self._on_connect_cb: Optional[Callable[[int], None]] = None
        self._on_real_data_cb: Optional[Callable[[str, str, str], None]] = None
        self._on_chejan_cb: Optional[Callable[[str, int, str], None]] = None
        self._on_receive_tr_cb: Optional[Callable[[str, str, str, str], None]] = None
        self._on_condition_verse_cb: Optional[Callable[[str, str, str, int, int], None]] = None
        self._on_receive_realcondition_cb: Optional[Callable[[str, str, str, str], None]] = None

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize(self) -> "KiwoomAPI":
        """Create the QAxWidget COM object and wire up all event slots."""
        self._ocx = QAxWidget("KHOPENAPI.KHOpenAPICtrl.1")
        self._connect_slots()
        logger.info("Kiwoom QAxWidget initialised.")
        return self

    def _connect_slots(self) -> None:
        ocx = self._ocx
        ocx.OnEventConnect.connect(self._on_event_connect)
        ocx.OnReceiveRealData.connect(self._on_receive_real_data)
        ocx.OnReceiveChejanData.connect(self._on_receive_chejan_data)
        ocx.OnReceiveTrData.connect(self._on_receive_tr_data)
        ocx.OnReceiveConditionVerse.connect(self._on_receive_condition_verse)
        ocx.OnReceiveRealCondition.connect(self._on_receive_real_condition)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self) -> int:
        """Trigger the Kiwoom login dialog and block until the result arrives.

        Returns:
            0  – success
            non-zero – error code from Kiwoom
        """
        if self._ocx is None:
            raise RuntimeError("KiwoomAPI not initialised; call initialize() first.")

        self._login_event_loop = QEventLoop()
        self._ocx.dynamicCall("CommConnect()")
        self._login_event_loop.exec_()
        return self._last_login_errcode

    # ------------------------------------------------------------------
    # Account helpers
    # ------------------------------------------------------------------

    def get_login_info(self, tag: str) -> str:
        """Wrapper for GetLoginInfo(tag).

        Common tags:
            ACCNO      – semicolon-separated account numbers
            USER_ID    – user id
            USER_NAME  – user name
        """
        return self._ocx.dynamicCall("GetLoginInfo(QString)", tag)

    def get_account_list(self) -> List[str]:
        """Return a list of account numbers available after login."""
        raw = self.get_login_info("ACCNO")
        return [a for a in raw.split(";") if a.strip()]

    # ------------------------------------------------------------------
    # Real-time subscription
    # ------------------------------------------------------------------

    def set_real_reg(self, screen_no: str, code_list: str, fid_list: str,
                     opt_type: str = "0") -> None:
        """Register stock codes for real-time data.

        Args:
            screen_no:  Screen number (4-digit string, e.g. "1000").
            code_list:  Semicolon-separated stock codes, e.g. "005930;000660".
            fid_list:   Semicolon-separated FID numbers, e.g. "10;15;41".
            opt_type:   "0" = add to existing registrations, "1" = replace.
        """
        self._ocx.dynamicCall(
            "SetRealReg(QString, QString, QString, QString)",
            screen_no, code_list, fid_list, opt_type,
        )

    def set_real_remove(self, screen_no: str, del_code: str) -> None:
        """Unregister a stock code from real-time data."""
        self._ocx.dynamicCall(
            "SetRealRemove(QString, QString)", screen_no, del_code
        )

    def get_comm_real_data(self, code: str, fid: str) -> str:
        """Read the latest value for *fid* from the real-time data buffer."""
        return self._ocx.dynamicCall(
            "GetCommRealData(QString, int)", code, int(fid)
        )

    # ------------------------------------------------------------------
    # Condition search
    # ------------------------------------------------------------------

    def get_condition_load(self) -> bool:
        """Download condition lists from HTS.

        Must be called before the other condition methods.
        Returns True on success.
        """
        ret = self._ocx.dynamicCall("GetConditionLoad()")
        return ret == 1

    def get_condition_name_list(self) -> Dict[int, str]:
        """Return a dict mapping condition index -> condition name."""
        raw: str = self._ocx.dynamicCall("GetConditionNameList()")
        result: Dict[int, str] = {}
        for item in raw.split(";"):
            item = item.strip()
            if "^" in item:
                idx_str, name = item.split("^", 1)
                try:
                    result[int(idx_str)] = name
                except ValueError:
                    pass
        return result

    def send_condition(self, screen_no: str, cond_name: str,
                       cond_index: int, is_realtime: int = 1) -> bool:
        """Start a condition search.

        Args:
            screen_no:    Screen number.
            cond_name:    Condition name string.
            cond_index:   Condition index.
            is_realtime:  1 = real-time monitoring, 0 = one-shot search.
        Returns:
            True on success.
        """
        ret = self._ocx.dynamicCall(
            "SendCondition(QString, QString, int, int)",
            screen_no, cond_name, cond_index, is_realtime,
        )
        return ret == 1

    def send_condition_stop(self, screen_no: str, cond_name: str,
                            cond_index: int) -> None:
        """Stop real-time condition monitoring."""
        self._ocx.dynamicCall(
            "SendConditionStop(QString, QString, int)",
            screen_no, cond_name, cond_index,
        )

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def send_order(
        self,
        rqname: str,
        screen_no: str,
        account: str,
        order_type: int,
        code: str,
        qty: int,
        price: int,
        hoga_type: str,
        org_order_no: str = "",
    ) -> int:
        """Place or modify/cancel an order.

        order_type:
            1 = 신규매수, 2 = 신규매도, 3 = 매수취소, 4 = 매도취소,
            5 = 매수정정, 6 = 매도정정
        hoga_type:
            "00" = 지정가, "03" = 시장가, "05" = 조건부지정가
        Returns:
            0 on success, negative value on error.
        """
        return self._ocx.dynamicCall(
            "SendOrder(QString, QString, QString, int, QString, int, int, QString, QString)",
            rqname, screen_no, account, order_type,
            code, qty, price, hoga_type, org_order_no,
        )

    def get_chejan_data(self, fid: int) -> str:
        """Read a field from the latest chejan (체결잔고) event data."""
        return self._ocx.dynamicCall("GetChejanData(int)", fid)

    # ------------------------------------------------------------------
    # TR (transaction) query
    # ------------------------------------------------------------------

    def set_input_value(self, id_: str, value: str) -> None:
        self._ocx.dynamicCall("SetInputValue(QString, QString)", id_, value)

    def comm_rq_data(self, rqname: str, trcode: str, prev_next: int,
                     screen_no: str) -> int:
        return self._ocx.dynamicCall(
            "CommRqData(QString, QString, int, QString)",
            rqname, trcode, prev_next, screen_no,
        )

    def get_comm_data(self, trcode: str, record_name: str, index: int,
                      item_name: str) -> str:
        return self._ocx.dynamicCall(
            "GetCommData(QString, QString, int, QString)",
            trcode, record_name, index, item_name,
        )

    def get_repeat_cnt(self, trcode: str, record_name: str) -> int:
        return self._ocx.dynamicCall(
            "GetRepeatCnt(QString, QString)", trcode, record_name
        )

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def register_on_connect(self, cb: Callable[[int], None]) -> None:
        self._on_connect_cb = cb

    def register_on_real_data(
        self, cb: Callable[[str, str, str], None]
    ) -> None:
        self._on_real_data_cb = cb

    def register_on_chejan(
        self, cb: Callable[[str, int, str], None]
    ) -> None:
        self._on_chejan_cb = cb

    def register_on_receive_tr(
        self, cb: Callable[[str, str, str, str], None]
    ) -> None:
        self._on_receive_tr_cb = cb

    def register_on_condition_verse(
        self, cb: Callable[[str, str, str, int, int], None]
    ) -> None:
        self._on_condition_verse_cb = cb

    def register_on_receive_realcondition(
        self, cb: Callable[[str, str, str, str], None]
    ) -> None:
        self._on_receive_realcondition_cb = cb

    # ------------------------------------------------------------------
    # Internal event handlers (forwarded from QAxWidget signals)
    # ------------------------------------------------------------------

    def _on_event_connect(self, err_code: int) -> None:
        self._last_login_errcode = err_code
        if self._login_event_loop and self._login_event_loop.isRunning():
            self._login_event_loop.exit()
        if self._on_connect_cb:
            self._on_connect_cb(err_code)

    def _on_receive_real_data(self, code: str, real_type: str,
                               real_data: str) -> None:
        if self._on_real_data_cb:
            self._on_real_data_cb(code, real_type, real_data)

    def _on_receive_chejan_data(self, gubun: str, item_cnt: int,
                                 fid_list: str) -> None:
        if self._on_chejan_cb:
            self._on_chejan_cb(gubun, item_cnt, fid_list)

    def _on_receive_tr_data(self, screen_no: str, rqname: str, trcode: str,
                             record_name: str, prev_next: str,
                             *_args) -> None:
        if self._on_receive_tr_cb:
            self._on_receive_tr_cb(screen_no, rqname, trcode, prev_next)

    def _on_receive_condition_verse(self, screen_no: str, code_list: str,
                                    cond_name: str, cond_index: int,
                                    next_: int) -> None:
        if self._on_condition_verse_cb:
            self._on_condition_verse_cb(
                screen_no, code_list, cond_name, cond_index, next_
            )

    def _on_receive_real_condition(self, code: str, event_type: str,
                                   cond_name: str,
                                   cond_index: str) -> None:
        if self._on_receive_realcondition_cb:
            self._on_receive_realcondition_cb(
                code, event_type, cond_name, cond_index
            )
