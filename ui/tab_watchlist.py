"""
관심 종목 탭 — 종목 추가/삭제/저장 + 실시간 현재가
"""
import json
import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QPushButton, QHeaderView, QMessageBox, QLabel
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

WATCHLIST_PATH = r'C:\trading\config\watchlist.json'


class TabWatchlist(QWidget):
    def __init__(self, api_handler=None):
        super().__init__()
        self.api = api_handler
        self._watchlist: list = []   # [{code, name}, ...]
        self._prices: dict   = {}    # {code: {price, change_rate}}
        self._setup_ui()
        self._load_watchlist()
        self._start_timer()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 테이블
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['종목코드', '종목명', '현재가', '등락률', '거래량', '삭제'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)

        # 추가 영역
        add_layout = QHBoxLayout()
        add_layout.addWidget(QLabel('종목코드:'))
        self.edit_code = QLineEdit()
        self.edit_code.setPlaceholderText('예: 005930')
        self.edit_code.setMaximumWidth(120)
        add_layout.addWidget(self.edit_code)

        btn_add  = QPushButton('추가')
        btn_save = QPushButton('저장')
        btn_add.clicked.connect(self._add_stock)
        btn_save.clicked.connect(self._save_watchlist)
        add_layout.addWidget(btn_add)
        add_layout.addWidget(btn_save)
        add_layout.addStretch()
        layout.addLayout(add_layout)

    def _start_timer(self):
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh_prices)
        self.timer.start(3000)

    def _load_watchlist(self):
        try:
            path = WATCHLIST_PATH
            if not os.path.exists(path):
                path = 'watchlist.json'
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    self._watchlist = json.load(f)
        except Exception:
            self._watchlist = []
        self._rebuild_table()

    def _save_watchlist(self):
        try:
            path = WATCHLIST_PATH
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._watchlist, f, ensure_ascii=False, indent=2)
        except Exception:
            try:
                with open('watchlist.json', 'w', encoding='utf-8') as f:
                    json.dump(self._watchlist, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
        QMessageBox.information(self, '저장', '관심 종목이 저장되었습니다.')

    def _rebuild_table(self):
        self.table.setRowCount(len(self._watchlist))
        for row, item in enumerate(self._watchlist):
            code = item.get('code', '')
            name = item.get('name', '')
            price_info = self._prices.get(code, {})
            price  = price_info.get('price', 0)
            change = price_info.get('change_rate', 0)
            vol    = price_info.get('volume', 0)

            values = [code, name,
                      f'{price:,}' if price else '-',
                      f'{change:+.2f}%' if price else '-',
                      f'{vol:,}' if vol else '-',
                      '[X]']

            fg_color = QColor('#00ff88') if change >= 0 else QColor('#ff4444')
            for col, val in enumerate(values):
                cell = QTableWidgetItem(str(val))
                if col in (2, 3, 4) and price:
                    cell.setForeground(fg_color)
                self.table.setItem(row, col, cell)

    def _add_stock(self):
        code = self.edit_code.text().strip()
        if not code or not code.isdigit() or len(code) != 6:
            QMessageBox.warning(self, '오류', '6자리 종목코드를 입력하세요.')
            return

        if any(s['code'] == code for s in self._watchlist):
            QMessageBox.information(self, '안내', '이미 추가된 종목입니다.')
            return

        name = code  # API 연결 시 종목명 조회
        if self.api:
            try:
                name = self.api.get_stock_name(code) or code
            except Exception:
                pass

        self._watchlist.append({'code': code, 'name': name})
        self._rebuild_table()
        self.edit_code.clear()

    def _on_double_click(self, row: int, col: int):
        if row < len(self._watchlist):
            code = self._watchlist[row]['code']
            self._watchlist.pop(row)
            self._rebuild_table()

    def _refresh_prices(self):
        self._rebuild_table()

    def update_price(self, code: str, price: int, change_rate: float, volume: int = 0):
        """외부에서 실시간 가격 업데이트"""
        self._prices[code] = {'price': price, 'change_rate': change_rate, 'volume': volume}
