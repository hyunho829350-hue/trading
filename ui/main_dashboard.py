"""
메인 대시보드 (PyQt5)
80만원→1억 소자본 특화 UI
실시간 자본/수익/비용 현황, START/STOP 토글
"""
import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTabWidget, QTextEdit, QSplitter, QFrame,
    QMessageBox, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor


class MainDashboard(QMainWindow):
    """메인 대시보드 창"""

    INITIAL_CAPITAL = 800_000
    TARGET_CAPITAL  = 100_000_000

    def __init__(self, engine=None, trade_book=None, telegram=None):
        super().__init__()
        self.engine     = engine
        self.trade_book = trade_book
        self.telegram   = telegram

        self.setWindowTitle('AI 자동매매 — 80만→1억 (paper 모드)')
        self.setMinimumSize(1200, 800)
        self._setup_ui()
        self._start_timers()

    # ── UI 구성 ──────────────────────────────────────────────────────────
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # 상단 헤더
        main_layout.addWidget(self._build_header())

        # 중간 (좌측 패널 + 우측 탭)
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_tabs())
        splitter.setSizes([220, 980])
        main_layout.addWidget(splitter, stretch=1)

        # 하단 로그
        main_layout.addWidget(self._build_log_panel())

        self._apply_dark_style()

    def _build_header(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_time = QLabel('--:--:--')
        self.lbl_time.setFont(QFont('Consolas', 14, QFont.Bold))

        self.lbl_market_status = QLabel('폐장')
        self.lbl_market_status.setStyleSheet('color: #ff4444; font-weight:bold')

        self.lbl_balance = QLabel('예수금: ---,---원')

        self.btn_start = QPushButton('▶ START')
        self.btn_start.setCheckable(True)
        self.btn_start.clicked.connect(self._toggle_engine)
        self.btn_start.setMinimumWidth(100)

        self.btn_scan = QPushButton('🔍 SCAN')
        self.btn_scan.clicked.connect(self._do_scan)

        self.btn_refresh = QPushButton('💼 잔고조회')
        self.btn_refresh.clicked.connect(self._refresh_balance)

        self.btn_sell_all = QPushButton('🔴 전체매도')
        self.btn_sell_all.clicked.connect(self._confirm_sell_all)
        self.btn_sell_all.setStyleSheet('background:#c62828; color:white; font-weight:bold')

        for w in [self.lbl_time, self.lbl_market_status, QLabel('|'),
                  self.lbl_balance, QLabel('|'),
                  self.btn_start, self.btn_scan, self.btn_refresh, self.btn_sell_all]:
            layout.addWidget(w)
        layout.addStretch()
        return frame

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(4, 4, 4, 4)

        # 자본 현황
        g1 = QGroupBox('💰 자본 현황')
        g1_layout = QVBoxLayout(g1)
        self.lbl_capital   = QLabel('현재: 800,000원')
        self.lbl_pnl_rate  = QLabel('수익: +0.00%')
        self.lbl_target    = QLabel('목표: 100,000,000원')
        self.lbl_achieve   = QLabel('달성: 0.80%')
        for lbl in [self.lbl_capital, self.lbl_pnl_rate, self.lbl_target, self.lbl_achieve]:
            lbl.setFont(QFont('Consolas', 9))
            g1_layout.addWidget(lbl)
        layout.addWidget(g1)

        # 오늘 통계
        g2 = QGroupBox('📊 오늘 통계')
        g2_layout = QVBoxLayout(g2)
        self.lbl_buy_count  = QLabel('매수: 0회')
        self.lbl_sell_count = QLabel('매도: 0회')
        self.lbl_win_rate   = QLabel('승률: 0%')
        self.lbl_pf         = QLabel('손익비: -')
        for lbl in [self.lbl_buy_count, self.lbl_sell_count, self.lbl_win_rate, self.lbl_pf]:
            lbl.setFont(QFont('Consolas', 9))
            g2_layout.addWidget(lbl)
        layout.addWidget(g2)

        # 비용 현황
        g3 = QGroupBox('💸 비용 현황')
        g3_layout = QVBoxLayout(g3)
        self.lbl_fee      = QLabel('수수료: 0원')
        self.lbl_tax      = QLabel('세금:   0원')
        self.lbl_slip     = QLabel('슬리피지: ~0원')
        for lbl in [self.lbl_fee, self.lbl_tax, self.lbl_slip]:
            lbl.setFont(QFont('Consolas', 9))
            g3_layout.addWidget(lbl)
        layout.addWidget(g3)

        layout.addStretch()
        return panel

    def _build_tabs(self) -> QTabWidget:
        self.tabs = QTabWidget()

        # 탭 import는 실행 시점에 처리 (순환 방지)
        try:
            from ui.tab_realtime import TabRealtime
            self.tab_realtime = TabRealtime()
            self.tabs.addTab(self.tab_realtime, '📈 실시간')
        except Exception:
            self.tabs.addTab(QLabel('실시간 탭 로드 실패'), '📈 실시간')

        try:
            from ui.tab_index import TabIndex
            self.tab_index = TabIndex()
            self.tabs.addTab(self.tab_index, '📊 지수')
        except Exception:
            self.tabs.addTab(QLabel('지수 탭 로드 실패'), '📊 지수')

        try:
            from ui.tab_profit import TabProfit
            self.tab_profit = TabProfit(self.trade_book)
            self.tabs.addTab(self.tab_profit, '💰 수익')
        except Exception:
            self.tabs.addTab(QLabel('수익 탭 로드 실패'), '💰 수익')

        try:
            from ui.tab_settings import TabSettings
            self.tab_settings = TabSettings()
            self.tabs.addTab(self.tab_settings, '⚙️ 설정')
        except Exception:
            self.tabs.addTab(QLabel('설정 탭 로드 실패'), '⚙️ 설정')

        try:
            from ui.tab_watchlist import TabWatchlist
            self.tab_watchlist = TabWatchlist()
            self.tabs.addTab(self.tab_watchlist, '🔖 관심')
        except Exception:
            self.tabs.addTab(QLabel('관심 탭 로드 실패'), '🔖 관심')

        try:
            from ui.tab_backtest_ui import TabBacktestUI
            self.tab_backtest = TabBacktestUI()
            self.tabs.addTab(self.tab_backtest, '🧪 백테스트')
        except Exception:
            self.tabs.addTab(QLabel('백테스트 탭 로드 실패'), '🧪 백테스트')

        return self.tabs

    def _build_log_panel(self) -> QWidget:
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setMaximumHeight(160)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(4, 2, 4, 2)

        header = QHBoxLayout()
        header.addWidget(QLabel('📋 로그'))
        for label in ['전체', '신호', '매매', '오류']:
            btn = QPushButton(label)
            btn.setMaximumWidth(50)
            header.addWidget(btn)
        header.addStretch()
        layout.addLayout(header)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont('Consolas', 8))
        self.log_text.setMaximumHeight(120)
        layout.addWidget(self.log_text)
        return frame

    # ── 타이머 ────────────────────────────────────────────────────────────
    def _start_timers(self):
        self.timer_clock = QTimer()
        self.timer_clock.timeout.connect(self._update_clock)
        self.timer_clock.start(1000)

        self.timer_stats = QTimer()
        self.timer_stats.timeout.connect(self._update_stats)
        self.timer_stats.start(3000)

    def _update_clock(self):
        from datetime import datetime
        now = datetime.now()
        self.lbl_time.setText(now.strftime('%H:%M:%S'))
        h = now.hour
        m = now.minute
        if (9 <= h < 15) or (h == 15 and m < 30):
            self.lbl_market_status.setText('개장')
            self.lbl_market_status.setStyleSheet('color: #00ff88; font-weight:bold')
        else:
            self.lbl_market_status.setText('폐장')
            self.lbl_market_status.setStyleSheet('color: #ff4444; font-weight:bold')

    def _update_stats(self):
        if not self.trade_book:
            return
        try:
            daily = self.trade_book.get_daily_summary()
            progress = self.trade_book.get_80만_to_target_progress()
            capital = progress.get('current', self.INITIAL_CAPITAL)
            pnl_rate = progress.get('profit_rate', 0)
            achieve = progress.get('achievement_pct', 0)

            self.lbl_capital.setText(f'현재: {capital:,.0f}원')
            color = '#00ff88' if pnl_rate >= 0 else '#ff4444'
            self.lbl_pnl_rate.setText(f'수익: {pnl_rate:+.2f}%')
            self.lbl_pnl_rate.setStyleSheet(f'color: {color}')
            self.lbl_achieve.setText(f'달성: {achieve:.3f}%')
            self.lbl_buy_count.setText(f'매수: {daily.get("trades", 0)}회')
            self.lbl_win_rate.setText(f'승률: {daily.get("win_rate", 0):.0f}%')
        except Exception:
            pass

    # ── 버튼 액션 ────────────────────────────────────────────────────────
    def _toggle_engine(self, checked: bool):
        if checked:
            self.btn_start.setText('■ STOP')
            self.btn_start.setStyleSheet('background:#c62828; color:white; font-weight:bold')
            if self.engine:
                self.engine.start()
            self.append_log('매매 엔진 START', 'info')
        else:
            self.btn_start.setText('▶ START')
            self.btn_start.setStyleSheet('background:#2e7d32; color:white; font-weight:bold')
            if self.engine:
                self.engine.stop()
            self.append_log('매매 엔진 STOP', 'info')

    def _do_scan(self):
        self.append_log('수동 스캔 시작', 'info')

    def _refresh_balance(self):
        self.append_log('잔고 조회', 'info')

    def _confirm_sell_all(self):
        reply = QMessageBox.question(
            self, '전체매도 확인',
            '보유 종목 전체를 시장가로 매도하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            if self.engine:
                self.engine.sell_all()
            self.append_log('전체 매도 실행', 'sell')

    def append_log(self, msg: str, log_type: str = 'info'):
        colors = {'buy': '#4fc3f7', 'sell': '#ef9a9a',
                  'error': '#fff176', 'info': '#eeeeee'}
        color = colors.get(log_type, '#eeeeee')
        from datetime import datetime
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_text.append(f'<span style="color:{color}">[{ts}] {msg}</span>')
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _apply_dark_style(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background-color: #1a1a2e; color: #eeeeee; }
            QGroupBox { border: 1px solid #444; border-radius: 4px; margin-top: 8px;
                        color: #aaa; font-size: 9pt; }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #aaa; }
            QPushButton { background: #16213e; border: 1px solid #444; border-radius: 4px;
                          padding: 4px 8px; color: #eee; }
            QPushButton:hover { background: #0f3460; }
            QPushButton#btn_start { background: #2e7d32; color: white; font-weight: bold; }
            QTabWidget::pane { border: 1px solid #444; }
            QTabBar::tab { background: #16213e; color: #aaa; padding: 6px 12px; }
            QTabBar::tab:selected { background: #0f3460; color: #fff; }
            QTextEdit { background: #0d1117; color: #ccc; border: 1px solid #333; }
        """)


def launch(engine=None, trade_book=None, telegram=None):
    """앱 실행 진입점"""
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainDashboard(engine=engine, trade_book=trade_book, telegram=telegram)
    window.show()
    return app, window


if __name__ == '__main__':
    app, window = launch()
    sys.exit(app.exec_())
