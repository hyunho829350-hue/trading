"""
실시간 탭 — 보유 종목 + 매매 이력
"""
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QLabel, QSplitter, QPushButton, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont


class TabRealtime(QWidget):
    def __init__(self, engine=None, trade_book=None):
        super().__init__()
        self.engine     = engine
        self.trade_book = trade_book
        self._setup_ui()
        self._start_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('📌 보유 종목'))

        # 보유 종목 테이블
        self.holdings_table = QTableWidget(0, 7)
        self.holdings_table.setHorizontalHeaderLabels([
            '종목명', '보유수', '매수가', '현재가', '손익금', '수익률', '손익분기점'
        ])
        self.holdings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.holdings_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.holdings_table.cellClicked.connect(self._on_holding_click)
        self.holdings_table.setFont(QFont('Consolas', 9))
        layout.addWidget(self.holdings_table, stretch=1)

        layout.addWidget(QLabel('📋 매매 이력 (오늘)'))

        # 매매 이력 테이블
        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels([
            '시간', '종목명', '구분', '체결가', '수량', '순수익', '조건명'
        ])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setFont(QFont('Consolas', 9))
        layout.addWidget(self.history_table, stretch=1)

    def _start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(1000)

    def _refresh(self):
        self._update_holdings()
        self._update_history()

    def _update_holdings(self):
        if not self.engine:
            return
        positions = self.engine.position_mgr.get_all_positions()
        self.holdings_table.setRowCount(len(positions))

        BEP_COST = 1.00261  # 수수료+세금
        for row, (code, pos) in enumerate(positions.items()):
            buy_p = pos['buy_price']
            cur_p = pos.get('current_price', buy_p)
            qty   = pos['quantity']
            pnl   = (cur_p - buy_p) * qty - (buy_p * qty * 0.00015 + cur_p * qty * 0.00245)
            rate  = (cur_p - buy_p) / buy_p * 100
            bep   = buy_p * BEP_COST

            items = [
                code, str(qty), f'{buy_p:,}', f'{cur_p:,}',
                f'{pnl:+,.0f}원', f'{rate:+.2f}%', f'{bep:,.0f}원'
            ]
            bg_color = QColor('#1b5e20') if pnl >= 0 else QColor('#b71c1c')
            if rate <= -1.5:
                bg_color = QColor('#c62828')

            for col, val in enumerate(items):
                item = QTableWidgetItem(val)
                item.setBackground(bg_color)
                self.holdings_table.setItem(row, col, item)

    def _update_history(self):
        if not self.trade_book:
            return
        import csv, os
        path = self.trade_book.csv_path if self.trade_book else 'trade_book.csv'
        if not os.path.exists(path):
            return

        from datetime import date
        today = date.today().strftime('%Y-%m-%d')

        rows = []
        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                for r in csv.DictReader(f):
                    if r.get('date') == today:
                        rows.append(r)
        except Exception:
            return

        self.history_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            direction = r.get('direction', '')
            net = r.get('net_profit', '')
            items = [
                r.get('time', ''), r.get('stock_name', r.get('stock_code', '')),
                direction, r.get('price', ''), r.get('quantity', ''),
                f'{float(net):+,.0f}원' if net else '-',
                r.get('strategy', ''),
            ]
            fg = QColor('#4fc3f7') if direction == 'BUY' else QColor('#ef9a9a')
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setForeground(fg)
                self.history_table.setItem(i, col, item)

    def _on_holding_click(self, row: int, col: int):
        code_item = self.holdings_table.item(row, 0)
        if not code_item:
            return
        code = code_item.text()
        reply = QMessageBox.question(
            self, '즉시 매도',
            f'{code} 즉시 매도하시겠습니까?',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes and self.engine:
            pos = self.engine.position_mgr.get_position(code)
            if pos:
                cur = pos.get('current_price', pos['buy_price'])
                self.engine._execute_sell(code, cur, '수동매도')
