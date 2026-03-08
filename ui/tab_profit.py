"""
수익 탭 — 수익 현황 + 목표 달성률 + 비용 현황
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor


class ProfitCard(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMinimumWidth(140)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        self.lbl_title  = QLabel(title)
        self.lbl_title.setAlignment(Qt.AlignCenter)

        self.lbl_amount = QLabel('+0원')
        self.lbl_amount.setAlignment(Qt.AlignCenter)
        self.lbl_amount.setFont(QFont('Consolas', 12, QFont.Bold))

        self.lbl_rate   = QLabel('+0.00%')
        self.lbl_rate.setAlignment(Qt.AlignCenter)
        self.lbl_rate.setFont(QFont('Arial', 10))

        for w in [self.lbl_title, self.lbl_amount, self.lbl_rate]:
            layout.addWidget(w)

    def update(self, amount: float, rate: float):
        color = '#00ff88' if amount >= 0 else '#ff4444'
        bg    = '#1b3a2a' if amount >= 0 else '#3a1b1b'
        self.lbl_amount.setText(f'{amount:+,.0f}원')
        self.lbl_rate.setText(f'{rate:+.2f}%')
        self.lbl_amount.setStyleSheet(f'color: {color}')
        self.lbl_rate.setStyleSheet(f'color: {color}')
        self.setStyleSheet(f'background: {bg}; border: 1px solid #444; border-radius: 8px;')


class TabProfit(QWidget):
    INITIAL_CAPITAL = 800_000
    TARGET_CAPITAL  = 100_000_000

    def __init__(self, trade_book=None):
        super().__init__()
        self.trade_book = trade_book
        self._setup_ui()
        self._start_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 수익 카드
        cards = QHBoxLayout()
        self.card_daily   = ProfitCard('오늘')
        self.card_weekly  = ProfitCard('이번 주')
        self.card_monthly = ProfitCard('이번 달')
        self.card_total   = ProfitCard('누적')
        for c in [self.card_daily, self.card_weekly, self.card_monthly, self.card_total]:
            cards.addWidget(c)
        layout.addLayout(cards)

        # 목표 달성 프로그레스
        prog_frame = QFrame()
        prog_frame.setFrameShape(QFrame.StyledPanel)
        prog_layout = QVBoxLayout(prog_frame)

        self.lbl_progress_title = QLabel('🎯 80만 → 1억 목표 달성률')
        self.lbl_progress_title.setFont(QFont('Arial', 11, QFont.Bold))
        prog_layout.addWidget(self.lbl_progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 10000)  # 0.01% 단위
        self.progress_bar.setValue(80)
        self.progress_bar.setFormat('%v / 10000 (0.01%단위)')
        self.progress_bar.setStyleSheet(
            'QProgressBar { border: 1px solid #444; border-radius: 4px; text-align: center; }'
            'QProgressBar::chunk { background: #00ff88; }'
        )
        prog_layout.addWidget(self.progress_bar)

        self.lbl_progress_detail = QLabel('현재: 800,000원 / 목표: 100,000,000원')
        prog_layout.addWidget(self.lbl_progress_detail)
        layout.addWidget(prog_frame)

        # 비용 현황 테이블
        layout.addWidget(QLabel('💸 비용 현황'))
        self.cost_table = QTableWidget(3, 4)
        self.cost_table.setHorizontalHeaderLabels(['구분', '오늘', '이번달', '누적'])
        self.cost_table.setVerticalHeaderLabels(['수수료', '세금', '슬리피지(추정)'])
        self.cost_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.cost_table.setMaximumHeight(120)
        self.cost_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.cost_table)

        layout.addStretch()

    def _start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(5000)
        self._refresh()

    def _refresh(self):
        if not self.trade_book:
            return
        try:
            daily   = self.trade_book.get_daily_summary()
            weekly  = self.trade_book.get_weekly_summary()
            monthly = self.trade_book.get_monthly_summary()
            cumul   = self.trade_book.get_cumulative()
            progress = self.trade_book.get_80만_to_target_progress()

            ic = self.INITIAL_CAPITAL

            self.card_daily.update(daily.get('pnl', 0),   daily.get('pnl', 0) / ic * 100)
            self.card_weekly.update(weekly.get('pnl', 0),  weekly.get('pnl', 0) / ic * 100)
            self.card_monthly.update(monthly.get('pnl', 0), monthly.get('pnl', 0) / ic * 100)
            self.card_total.update(cumul.get('cumulative_pnl', 0),
                                   cumul.get('cumulative_pnl', 0) / ic * 100)

            ach_pct = progress.get('achievement_pct', 0.8)
            self.progress_bar.setValue(int(ach_pct * 100))
            self.progress_bar.setFormat(f'{ach_pct:.3f}% 달성')
            cap = progress.get('current', ic)
            self.lbl_progress_detail.setText(
                f'현재: {cap:,.0f}원 / 목표: {self.TARGET_CAPITAL:,}원'
            )
        except Exception:
            pass
