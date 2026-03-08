"""
Tests for kiwoom.py, order_manager.py, and trading_engine.py.

These tests use unittest.mock so they do NOT require a real Kiwoom
OpenAPI+ installation (Windows-only COM component).
"""

import sys
import unittest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Stub out PyQt5.QtAxContainer before importing app modules so that tests
# can run on non-Windows / without the Kiwoom COM component.
# ---------------------------------------------------------------------------
ax_stub = MagicMock()
sys.modules.setdefault("PyQt5.QtAxContainer", ax_stub)
ax_stub.QAxWidget = ax_stub.QAxWidget  # keep the same mock object


class TestKiwoomGetConditionNameList(unittest.TestCase):
    """Unit tests for KiwoomAPI.get_condition_name_list()."""

    def _make_api(self, raw_response: str):
        from app.kiwoom import KiwoomAPI
        api = KiwoomAPI.__new__(KiwoomAPI)
        api._ocx = MagicMock()
        api._ocx.dynamicCall.return_value = raw_response
        api._login_event_loop = None
        api._last_login_errcode = -1
        for attr in (
            "_on_connect_cb", "_on_real_data_cb", "_on_chejan_cb",
            "_on_receive_tr_cb", "_on_condition_verse_cb",
            "_on_receive_realcondition_cb",
        ):
            setattr(api, attr, None)
        return api

    def test_parses_multiple_conditions(self):
        api = self._make_api("0^급등주포착;1^눌림목;2^거래량급증;")
        result = api.get_condition_name_list()
        self.assertEqual(result, {0: "급등주포착", 1: "눌림목", 2: "거래량급증"})

    def test_empty_string_returns_empty_dict(self):
        api = self._make_api("")
        result = api.get_condition_name_list()
        self.assertEqual(result, {})

    def test_ignores_malformed_items(self):
        api = self._make_api("0^valid;bad_item;1^also_valid")
        result = api.get_condition_name_list()
        self.assertEqual(result, {0: "valid", 1: "also_valid"})


class TestKiwoomAccountList(unittest.TestCase):
    """Unit tests for KiwoomAPI.get_account_list()."""

    def _make_api(self):
        from app.kiwoom import KiwoomAPI
        api = KiwoomAPI.__new__(KiwoomAPI)
        api._ocx = MagicMock()
        api._login_event_loop = None
        api._last_login_errcode = -1
        for attr in (
            "_on_connect_cb", "_on_real_data_cb", "_on_chejan_cb",
            "_on_receive_tr_cb", "_on_condition_verse_cb",
            "_on_receive_realcondition_cb",
        ):
            setattr(api, attr, None)
        return api

    def test_get_account_list_multiple(self):
        api = self._make_api()
        api._ocx.dynamicCall.return_value = "1234567890;0987654321;"
        result = api.get_account_list()
        self.assertEqual(result, ["1234567890", "0987654321"])

    def test_get_account_list_single(self):
        api = self._make_api()
        api._ocx.dynamicCall.return_value = "9999999999"
        result = api.get_account_list()
        self.assertEqual(result, ["9999999999"])


class TestTickSize(unittest.TestCase):
    """Verify KRX tick size rules."""

    def _tick(self, price: int) -> int:
        from app.order_manager import OrderManager
        return OrderManager._get_tick_size(price)

    def test_below_2000(self):
        self.assertEqual(self._tick(1_999), 1)
        self.assertEqual(self._tick(1), 1)

    def test_2000_to_4999(self):
        self.assertEqual(self._tick(2_000), 5)
        self.assertEqual(self._tick(4_999), 5)

    def test_5000_to_19999(self):
        self.assertEqual(self._tick(5_000), 10)
        self.assertEqual(self._tick(19_999), 10)

    def test_20000_to_49999(self):
        self.assertEqual(self._tick(20_000), 50)
        self.assertEqual(self._tick(49_999), 50)

    def test_50000_to_199999(self):
        self.assertEqual(self._tick(50_000), 100)
        self.assertEqual(self._tick(199_999), 100)

    def test_200000_to_499999(self):
        self.assertEqual(self._tick(200_000), 500)
        self.assertEqual(self._tick(499_999), 500)

    def test_500000_and_above(self):
        self.assertEqual(self._tick(500_000), 1_000)
        self.assertEqual(self._tick(1_000_000), 1_000)


class TestOrderManagerBuy(unittest.TestCase):
    """Tests for OrderManager buy / cancel logic (no real Kiwoom needed)."""

    def _make_manager(self):
        from app.order_manager import OrderManager

        kiwoom = MagicMock()
        kiwoom.send_order.return_value = 0
        kiwoom.register_on_chejan = MagicMock()

        logs = []
        with patch("app.order_manager.QTimer") as mock_timer_cls:
            mock_timer = MagicMock()
            mock_timer_cls.return_value = mock_timer
            mgr = OrderManager(
                kiwoom=kiwoom,
                account="1234567890",
                on_log=logs.append,
            )
        return mgr, kiwoom, logs

    def test_buy_places_order_with_slippage(self):
        """Buy at 10,000 → tick=10 → 2 ticks slippage → order price 10,020."""
        mgr, kiwoom, logs = self._make_manager()
        result = mgr.buy("005930", qty=10, current_price=10_000)
        self.assertTrue(result)
        kiwoom.send_order.assert_called_once()
        # Inspect 'price' keyword arg
        call_kwargs = kiwoom.send_order.call_args.kwargs
        self.assertEqual(call_kwargs["price"], 10_020)

    def test_buy_rejected_when_position_exists(self):
        mgr, kiwoom, logs = self._make_manager()
        mgr.buy("005930", qty=5, current_price=10_000)
        result = mgr.buy("005930", qty=5, current_price=10_000)
        self.assertFalse(result)
        self.assertEqual(kiwoom.send_order.call_count, 1)

    def test_buy_returns_false_on_kiwoom_error(self):
        mgr, kiwoom, logs = self._make_manager()
        kiwoom.send_order.return_value = -100
        result = mgr.buy("000660", qty=1, current_price=5_000)
        self.assertFalse(result)
        self.assertNotIn("000660", mgr.positions)

    def test_cancel_order_removes_position(self):
        mgr, kiwoom, logs = self._make_manager()
        mgr.buy("005930", qty=1, current_price=10_000)
        pos = mgr.positions["005930"]
        pos.order_no = "ORD001"

        result = mgr.cancel_order("005930")
        self.assertTrue(result)
        self.assertNotIn("005930", mgr.positions)

    def test_sell_market_calls_send_order(self):
        mgr, kiwoom, logs = self._make_manager()
        result = mgr.sell_market("005930", qty=3, reason="익절")
        self.assertTrue(result)
        self.assertEqual(kiwoom.send_order.call_count, 1)


class TestOrderManagerChejan(unittest.TestCase):
    """Tests for chejan event handling – position state transitions."""

    def _make_manager(self):
        from app.order_manager import OrderManager

        kiwoom = MagicMock()
        kiwoom.send_order.return_value = 0
        kiwoom.register_on_chejan = MagicMock()

        with patch("app.order_manager.QTimer") as mock_timer_cls:
            mock_timer_cls.return_value = MagicMock()
            mgr = OrderManager(
                kiwoom=kiwoom,
                account="1234567890",
                take_profit_rate=0.05,
                stop_loss_rate=0.03,
            )
        return mgr, kiwoom

    def test_chejan_transitions_to_filled(self):
        from app.order_manager import PositionState
        mgr, kiwoom = self._make_manager()
        mgr.buy("005930", qty=2, current_price=10_000)
        pos = mgr.positions["005930"]
        pos.order_no = "ORD001"

        chejan_data = {
            9001: "005930",
            9203: "ORD001",
            911: "2",       # filled qty
            910: "10020",   # filled price
        }
        kiwoom.get_chejan_data.side_effect = lambda fid: str(chejan_data.get(fid, ""))
        mgr._on_chejan("0", 4, "")

        self.assertEqual(pos.state, PositionState.FILLED)
        self.assertEqual(pos.filled_price, 10_020)
        self.assertEqual(pos.target_price, int(10_020 * 1.05))
        self.assertEqual(pos.stop_price, int(10_020 * 0.97))

    def test_chejan_ignores_gubun_1(self):
        from app.order_manager import PositionState
        mgr, kiwoom = self._make_manager()
        mgr.buy("005930", qty=1, current_price=5_000)
        mgr._on_chejan("1", 0, "")  # gubun=1 = balance update, ignore
        pos = mgr.positions["005930"]
        self.assertEqual(pos.state, PositionState.PENDING)


class TestTradingEngineBuySignal(unittest.TestCase):
    """Tests for TradingEngine._is_buy_signal()."""

    def _make_engine(self):
        from app.trading_engine import TradingEngine

        kiwoom = MagicMock()
        order_mgr = MagicMock()
        order_mgr.positions = {}

        engine = TradingEngine.__new__(TradingEngine)
        engine._kiwoom = kiwoom
        engine._order_manager = order_mgr
        engine._volume_surge_ratio = 2.0
        engine._max_gap_from_open = 0.03
        engine._order_qty = 1
        engine._active_condition = None
        engine._rt_data = {}
        engine._condition_codes = ["005930"]

        return engine, kiwoom, order_mgr

    def test_buy_signal_normal_conditions(self):
        engine, _, __ = self._make_engine()
        snap = {"price": 10_000, "volume": 100, "open": 9_800, "best_ask": 10_010}
        self.assertTrue(engine._is_buy_signal("005930", snap))

    def test_buy_signal_rejected_gap_too_large(self):
        """Price 5% above open exceeds max_gap_from_open (3%)."""
        engine, _, __ = self._make_engine()
        snap = {"price": 10_500, "volume": 200, "open": 10_000, "best_ask": 10_510}
        self.assertFalse(engine._is_buy_signal("005930", snap))

    def test_buy_signal_accepted_at_gap_boundary(self):
        """Price exactly 3% above open is still acceptable."""
        engine, _, __ = self._make_engine()
        snap = {"price": 10_300, "volume": 100, "open": 10_000, "best_ask": 10_310}
        self.assertTrue(engine._is_buy_signal("005930", snap))

    def test_buy_signal_rejected_no_volume(self):
        engine, _, __ = self._make_engine()
        snap = {"price": 10_000, "volume": 0, "open": 9_900, "best_ask": 10_010}
        self.assertFalse(engine._is_buy_signal("005930", snap))

    def test_buy_signal_rejected_code_not_in_condition(self):
        engine, _, __ = self._make_engine()
        snap = {"price": 10_000, "volume": 100, "open": 9_800, "best_ask": 10_010}
        self.assertFalse(engine._is_buy_signal("999999", snap))

    def test_buy_signal_rejected_existing_position(self):
        engine, _, order_mgr = self._make_engine()
        order_mgr.positions = {"005930": MagicMock()}
        snap = {"price": 10_000, "volume": 100, "open": 9_800, "best_ask": 10_010}
        self.assertFalse(engine._is_buy_signal("005930", snap))


if __name__ == "__main__":
    unittest.main()
