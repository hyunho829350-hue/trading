"""ui/main_window.py – 4-Quadrant Main Window.

Layout
──────
┌──────────────────────┬──────────────────────┐
│  AccountPanel (TL)   │  WatchlistPanel (TR)  │
├──────────────────────┼──────────────────────┤
│  PositionsPanel (BL) │  LogPanel (BR)        │
└──────────────────────┴──────────────────────┘

All updates from background threads are marshalled back to the Qt main
thread through Qt signals so that no worker thread touches widgets directly.
"""
from __future__ import annotations

from PyQt5.QtCore import QTimer, pyqtSignal, QObject
from PyQt5.QtWidgets import (
    QMainWindow,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
    QLabel,
)
from PyQt5.QtCore import Qt

import config
from core.api_client import APIClient, AccountInfo, Tick
from core.auto_journal import AutoJournal
from core.risk_manager import RiskManager
from core.throttle_manager import ThrottleManager
from core.trading_engine import TradingEngine, Position
from ui.account_panel import AccountPanel
from ui.log_panel import LogPanel
from ui.positions_panel import PositionsPanel
from ui.watchlist_panel import WatchlistPanel


class _Signals(QObject):
    """Carrier for cross-thread Qt signals."""
    tick_received    = pyqtSignal(object)    # Tick
    account_updated  = pyqtSignal(object)    # AccountInfo
    positions_changed = pyqtSignal(object)   # dict[str, Position]
    log_message      = pyqtSignal(str)


class MainWindow(QMainWindow):
    """The trading system control-room window."""

    def __init__(self) -> None:
        super().__init__()
        self._signals = _Signals()
        self._setup_core()
        self._setup_ui()
        self._connect_signals()
        self._start_timers()
        self.setWindowTitle("🖥️  스캘핑 자동매매 시스템 v1.0")
        self.resize(1400, 900)
        self._log("[API] 시스템 초기화 완료.")
        self._api.connect()

    # ── core setup ────────────────────────────────────────────────────────────

    def _setup_core(self) -> None:
        self._journal  = AutoJournal()
        self._throttle = ThrottleManager(log_callback=self._log)
        self._risk     = RiskManager(
            on_kill_switch=self._on_kill_switch_triggered,
            log_callback=self._log,
        )
        self._api = APIClient(log_callback=self._log)
        self._engine = TradingEngine(
            api=self._api,
            throttle=self._throttle,
            risk=self._risk,
            journal=self._journal,
            log_callback=self._log,
        )
        self._engine.on_position_update = self._request_position_update
        self._engine.on_order_update = lambda r: self._log(
            f"[ORDER] {r.direction} {r.ticker} {r.status} @ {r.filled_price:,}"
        )

        # Subscribe ticks for all mock stocks
        from core.api_client import _MOCK_STOCKS
        for s in _MOCK_STOCKS:
            self._api.subscribe_ticks(
                s["ticker"],
                lambda tick: self._signals.tick_received.emit(tick),
            )
        self._engine.start()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # Outer vertical splitter (top row | bottom row)
        v_split = QSplitter(Qt.Vertical)

        # Top row: horizontal splitter
        top_split = QSplitter(Qt.Horizontal)
        self._account_panel = AccountPanel(on_kill_switch=self._kill_switch)
        self._watchlist_panel = WatchlistPanel(on_buy=self._on_buy_request)
        top_split.addWidget(self._account_panel)
        top_split.addWidget(self._watchlist_panel)
        top_split.setStretchFactor(0, 1)
        top_split.setStretchFactor(1, 2)

        # Bottom row: horizontal splitter
        bot_split = QSplitter(Qt.Horizontal)
        self._positions_panel = PositionsPanel(on_liquidate=self._on_liquidate)
        self._log_panel = LogPanel()
        bot_split.addWidget(self._positions_panel)
        bot_split.addWidget(self._log_panel)
        bot_split.setStretchFactor(0, 2)
        bot_split.setStretchFactor(1, 1)

        v_split.addWidget(top_split)
        v_split.addWidget(bot_split)
        v_split.setStretchFactor(0, 1)
        v_split.setStretchFactor(1, 1)
        main_layout.addWidget(v_split)

        # Status bar
        self._status_label = QLabel("● 시뮬레이션 모드" if config.API_MOCK_MODE else "● 실시간 연결")
        self._status_label.setStyleSheet("color: #66bb6a; padding: 0 8px;")
        self.statusBar().addPermanentWidget(self._status_label)

        # Dark theme for whole window
        self.setStyleSheet(
            "QMainWindow, QWidget { background-color: #1a1a1a; color: #e0e0e0; }"
            "QSplitter::handle { background: #333; }"
            "QStatusBar { background: #212121; color: #9e9e9e; font-size: 11px; }"
        )

    # ── signals ───────────────────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._signals.tick_received.connect(self._on_tick_received)
        self._signals.account_updated.connect(self._on_account_updated)
        self._signals.positions_changed.connect(self._on_positions_changed)
        self._signals.log_message.connect(self._log_panel.log)

    # ── timers ────────────────────────────────────────────────────────────────

    def _start_timers(self) -> None:
        # Account refresh
        self._account_timer = QTimer(self)
        self._account_timer.timeout.connect(self._refresh_account)
        self._account_timer.start(config.UI_TICK_INTERVAL_MS * 2)

        # Watchlist initial population
        QTimer.singleShot(500, self._init_watchlist)

    def _init_watchlist(self) -> None:
        for tick in self._api.get_watchlist():
            self._watchlist_panel.update_tick(tick)
            self._engine.on_tick(tick)

    def _refresh_account(self) -> None:
        try:
            info = self._api.get_account_info()
            self._signals.account_updated.emit(info)
        except Exception as e:
            self._log(f"[ERROR] 계좌 조회 실패: {e}")

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_tick_received(self, tick: object) -> None:
        tick: Tick = tick  # type: ignore[assignment]
        self._watchlist_panel.update_tick(tick)
        self._engine.on_tick(tick)

    def _on_account_updated(self, info: object) -> None:
        info: AccountInfo = info  # type: ignore[assignment]
        self._account_panel.update_account(info)

    def _on_positions_changed(self, positions: object) -> None:
        positions: dict = positions  # type: ignore[assignment]
        self._positions_panel.refresh_positions(positions)

    def _request_position_update(self) -> None:
        self._signals.positions_changed.emit(self._engine.positions)

    def _on_buy_request(self, ticker: str, name: str, price: int) -> None:
        self._log(f"[UI] 매수 요청: {name}({ticker}) @ {price:,}")
        self._engine.buy(ticker, name, quantity=1, current_price=price)

    def _on_liquidate(self, ticker: str) -> None:
        pos = self._engine.positions.get(ticker)
        if pos:
            self._log(f"[UI] 수동 청산: {pos.name}({ticker})")
            self._engine.sell(ticker, pos.quantity, reason="Manual")

    def _kill_switch(self) -> None:
        self._log("[KILL] Kill-Switch 발동 – 전체 청산 및 API 연결 해제")
        self._risk.activate_kill_switch("UI Button")
        self._engine.liquidate_all(reason="Kill-Switch")
        self._api.disconnect()
        self._account_timer.stop()
        self._status_label.setText("● 연결 해제됨")
        self._status_label.setStyleSheet("color: #ef5350; padding: 0 8px;")

    def _on_kill_switch_triggered(self) -> None:
        """Called by RiskManager when daily loss limit is breached."""
        self._log("[KILL] 일일 손실 한도 초과 – 자동 Kill-Switch 발동")
        self._engine.liquidate_all(reason="Daily Loss Limit")
        self._api.disconnect()

    def _log(self, message: str) -> None:
        self._signals.log_message.emit(message)

    # ── window close ─────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._engine.stop()
        self._api.disconnect()
        super().closeEvent(event)
