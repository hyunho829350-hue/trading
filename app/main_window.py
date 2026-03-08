"""
Main window – Stage 1.

Layout
------
┌─────────────────────────────────────────────┐
│  [로그인]  상태: 미접속   계좌: [────────▼]  │  ← Toolbar area
├──────────────────┬──────────────────────────┤
│  조건검색        │  실시간 체결 로그         │
│  [조건식 ▼]      │  (QListWidget)            │
│  [시작] [중지]   │                           │
├──────────────────┴──────────────────────────┤
│  계좌 잔고 현황 (QTableWidget)               │
└─────────────────────────────────────────────┘
"""

import logging
from typing import Dict, Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .kiwoom import KiwoomAPI
from .order_manager import OrderManager, PositionState
from .trading_engine import TradingEngine

logger = logging.getLogger(__name__)

MAX_LOG_ITEMS = 500   # keep the list widget bounded


class MainWindow(QMainWindow):
    """Top-level application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("자동매매 프로그램 – Kiwoom OpenAPI+")
        self.resize(1_100, 700)

        self._kiwoom: Optional[KiwoomAPI] = None
        self._order_manager: Optional[OrderManager] = None
        self._trading_engine: Optional[TradingEngine] = None
        self._conditions: Dict[int, str] = {}

        self._init_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 8, 8, 8)

        # ── Top bar ─────────────────────────────────────────────────────
        top_bar = self._build_top_bar()
        root_layout.addLayout(top_bar)

        # ── Middle splitter (condition panel | log) ──────────────────────
        splitter = QSplitter(Qt.Horizontal)

        left_panel = self._build_condition_panel()
        splitter.addWidget(left_panel)

        log_group = self._build_log_panel()
        splitter.addWidget(log_group)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        root_layout.addWidget(splitter, stretch=3)

        # ── Bottom: balance table ────────────────────────────────────────
        balance_group = self._build_balance_panel()
        root_layout.addWidget(balance_group, stretch=2)

    def _build_top_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()

        self.btn_login = QPushButton("로그인")
        self.btn_login.setFixedWidth(80)
        self.btn_login.clicked.connect(self._on_login_clicked)
        layout.addWidget(self.btn_login)

        self.lbl_status = QLabel("상태: 미접속")
        self.lbl_status.setMinimumWidth(160)
        layout.addWidget(self.lbl_status)

        layout.addWidget(QLabel("계좌:"))
        self.combo_account = QComboBox()
        self.combo_account.setMinimumWidth(180)
        layout.addWidget(self.combo_account)

        layout.addStretch()
        return layout

    def _build_condition_panel(self) -> QGroupBox:
        group = QGroupBox("조건검색")
        layout = QVBoxLayout(group)

        self.combo_condition = QComboBox()
        layout.addWidget(self.combo_condition)

        btn_row = QHBoxLayout()
        self.btn_cond_start = QPushButton("시작")
        self.btn_cond_start.setEnabled(False)
        self.btn_cond_start.clicked.connect(self._on_cond_start)
        btn_row.addWidget(self.btn_cond_start)

        self.btn_cond_stop = QPushButton("중지")
        self.btn_cond_stop.setEnabled(False)
        self.btn_cond_stop.clicked.connect(self._on_cond_stop)
        btn_row.addWidget(self.btn_cond_stop)
        layout.addLayout(btn_row)

        layout.addWidget(QLabel("포착 종목"))
        self.list_condition_stocks = QListWidget()
        layout.addWidget(self.list_condition_stocks)

        return group

    def _build_log_panel(self) -> QGroupBox:
        group = QGroupBox("실시간 체결 로그")
        layout = QVBoxLayout(group)
        self.list_log = QListWidget()
        font = QFont("Courier New", 9)
        self.list_log.setFont(font)
        layout.addWidget(self.list_log)
        return group

    def _build_balance_panel(self) -> QGroupBox:
        group = QGroupBox("계좌 잔고 현황")
        layout = QVBoxLayout(group)

        headers = ["종목코드", "상태", "주문가", "체결가", "수량", "목표가", "손절가"]
        self.table_balance = QTableWidget(0, len(headers))
        self.table_balance.setHorizontalHeaderLabels(headers)
        self.table_balance.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.table_balance.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table_balance.setAlternatingRowColors(True)
        layout.addWidget(self.table_balance)

        return group

    # ------------------------------------------------------------------
    # Login flow
    # ------------------------------------------------------------------

    def _on_login_clicked(self) -> None:
        self.btn_login.setEnabled(False)
        self.lbl_status.setText("상태: 로그인 중…")

        try:
            self._kiwoom = KiwoomAPI()
            self._kiwoom.initialize()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "초기화 실패",
                f"Kiwoom QAxWidget을 초기화할 수 없습니다.\n\n{exc}\n\n"
                "Kiwoom OpenAPI+가 설치된 Windows 환경에서 실행해 주세요.",
            )
            self.lbl_status.setText("상태: 초기화 실패")
            self.btn_login.setEnabled(True)
            return

        self._kiwoom.register_on_connect(self._on_kiwoom_connect)
        err = self._kiwoom.login()
        # _on_kiwoom_connect will be called before login() returns

    def _on_kiwoom_connect(self, err_code: int) -> None:
        if err_code == 0:
            user_name = self._kiwoom.get_login_info("USER_NAME")
            accounts = self._kiwoom.get_account_list()
            self.lbl_status.setText(f"상태: 접속중 ({user_name})")
            self.lbl_status.setStyleSheet("color: green; font-weight: bold;")

            self.combo_account.clear()
            for acc in accounts:
                self.combo_account.addItem(acc)

            self._log(f"로그인 성공 – 사용자: {user_name}  계좌수: {len(accounts)}")

            self._setup_trading_components()
        else:
            self.lbl_status.setText(f"상태: 로그인 실패 (오류={err_code})")
            self.lbl_status.setStyleSheet("color: red;")
            self.btn_login.setEnabled(True)
            self._log(f"로그인 실패 – 오류코드: {err_code}")

    def _setup_trading_components(self) -> None:
        account = self.combo_account.currentText()
        if not account:
            return

        self._order_manager = OrderManager(
            kiwoom=self._kiwoom,
            account=account,
            on_log=self._log,
        )

        self._trading_engine = TradingEngine(
            kiwoom=self._kiwoom,
            order_manager=self._order_manager,
            parent=self,
        )
        self._trading_engine.log_message.connect(self._log)
        self._trading_engine.condition_stocks_updated.connect(
            self._on_condition_stocks_updated
        )
        self._trading_engine.buy_signal.connect(self._on_buy_signal)

        # Load conditions
        self._conditions = self._trading_engine.get_conditions()
        self.combo_condition.clear()
        for idx, name in self._conditions.items():
            self.combo_condition.addItem(f"[{idx}] {name}", userData=idx)
        if self._conditions:
            self.btn_cond_start.setEnabled(True)

        # Start balance refresh timer
        self._balance_timer = QTimer(self)
        self._balance_timer.setInterval(3_000)
        self._balance_timer.timeout.connect(self._refresh_balance_table)
        self._balance_timer.start()

    # ------------------------------------------------------------------
    # Condition search callbacks
    # ------------------------------------------------------------------

    def _on_cond_start(self) -> None:
        if self._trading_engine is None:
            return
        idx = self.combo_condition.currentData()
        if idx is None:
            return
        name = self._conditions.get(idx, "")
        ok = self._trading_engine.start_condition(idx, name)
        if ok:
            self.btn_cond_start.setEnabled(False)
            self.btn_cond_stop.setEnabled(True)

    def _on_cond_stop(self) -> None:
        if self._trading_engine:
            self._trading_engine.stop_condition()
        self.btn_cond_start.setEnabled(True)
        self.btn_cond_stop.setEnabled(False)
        self.list_condition_stocks.clear()

    def _on_condition_stocks_updated(self, codes: list) -> None:
        self.list_condition_stocks.clear()
        for code in codes:
            self.list_condition_stocks.addItem(code)

    def _on_buy_signal(self, code: str, price: int) -> None:
        self._log(f"★ 매수신호 {code} @ {price:,}원")

    # ------------------------------------------------------------------
    # Balance table
    # ------------------------------------------------------------------

    def _refresh_balance_table(self) -> None:
        if self._order_manager is None:
            return
        positions = self._order_manager.positions
        self.table_balance.setRowCount(len(positions))

        for row, (code, pos) in enumerate(positions.items()):
            state_text = {
                PositionState.PENDING: "대기",
                PositionState.FILLED: "보유",
                PositionState.CLOSED: "청산",
            }.get(pos.state, "?")

            values = [
                code,
                state_text,
                f"{pos.order_price:,}",
                f"{pos.filled_price:,}" if pos.filled_price else "-",
                str(pos.filled_qty),
                f"{pos.target_price:,}" if pos.target_price else "-",
                f"{pos.stop_price:,}" if pos.stop_price else "-",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                if pos.state == PositionState.CLOSED:
                    item.setForeground(QColor("gray"))
                elif pos.state == PositionState.FILLED:
                    item.setForeground(QColor("darkblue"))
                self.table_balance.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Log helper
    # ------------------------------------------------------------------

    def _log(self, message: str) -> None:
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        item = QListWidgetItem(f"[{ts}]  {message}")

        # Colour-code by message type
        msg_lower = message.lower()
        if "매수" in message or "signal" in msg_lower:
            item.setForeground(QColor("darkred"))
        elif "익절" in message:
            item.setForeground(QColor("blue"))
        elif "손절" in message or "실패" in message:
            item.setForeground(QColor("red"))
        elif "취소" in message or "정정" in message:
            item.setForeground(QColor("darkorange"))

        self.list_log.insertItem(0, item)

        # Bound the list to avoid memory growth
        while self.list_log.count() > MAX_LOG_ITEMS:
            self.list_log.takeItem(self.list_log.count() - 1)

        logger.info(message)
