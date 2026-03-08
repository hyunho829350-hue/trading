"""ui/watchlist_panel.py – Real-time Watchlist panel (top-right quadrant).

Shows the list of tickers captured by the condition search with:
  • Current price
  • Change %
  • Bid/Ask quantity ratio (호가 잔량 비)

Updated every tick via signals from the API client.
"""
from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QFontfrom PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.api_client import Tick


def _signed_color(value: float) -> QColor:
    if value > 0:
        return QColor("#ef5350")
    elif value < 0:
        return QColor("#42a5f5")
    return QColor("#e0e0e0")


def _ratio_bar(bid_qty: int, ask_qty: int) -> str:
    total = bid_qty + ask_qty
    if total == 0:
        return "—"
    bid_pct = int(bid_qty / total * 10)
    ask_pct = 10 - bid_pct
    bar = "▮" * bid_pct + "▯" * ask_pct
    return f"매{bid_qty:,} {bar} 도{ask_qty:,}"


_COLS = ["종목코드", "종목명", "현재가", "등락률", "호가 잔량 비 (매수↔매도)"]
_COL_IDX = {name: i for i, name in enumerate(_COLS)}


class WatchlistPanel(QWidget):
    """Top-right quadrant: real-time market watchlist."""

    def __init__(
        self,
        on_buy: Callable[[str, str, int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_buy = on_buy
        self._ticks: dict[str, Tick] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("📡 실시간 감시 레이더 (Watchlist)")
        title.setStyleSheet("font-weight: bold; color: #e0e0e0; font-size: 13px;")
        hdr.addWidget(title)
        hdr.addStretch()
        layout.addLayout(hdr)

        # Table
        self._table = QTableWidget(0, len(_COLS))
        self._table.setHorizontalHeaderLabels(_COLS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(
            "QTableWidget {"
            "  background-color: #1e1e1e;"
            "  color: #e0e0e0;"
            "  gridline-color: #333;"
            "  font-size: 12px;"
            "  border: 1px solid #333;"
            "}"
            "QHeaderView::section {"
            "  background-color: #212121;"
            "  color: #9e9e9e;"
            "  border: none;"
            "  padding: 4px;"
            "  font-size: 11px;"
            "}"
            "QTableWidget::item:alternate { background-color: #252525; }"
            "QTableWidget::item:selected  { background-color: #37474f; }"
        )
        layout.addWidget(self._table)

        # Double-click to buy
        self._table.cellDoubleClicked.connect(self._on_row_double_click)

    # ── public API ────────────────────────────────────────────────────────────

    def update_tick(self, tick: Tick) -> None:
        """Upsert a single ticker row (called from main thread via signal)."""
        self._ticks[tick.ticker] = tick
        # Find or create row
        row = self._find_row(tick.ticker)
        if row == -1:
            row = self._table.rowCount()
            self._table.insertRow(row)

        ratio = _ratio_bar(tick.bid_qty, tick.ask_qty)
        sign = "+" if tick.change_pct >= 0 else ""

        items = [
            tick.ticker,
            tick.name,
            f"{tick.price:,}",
            f"{sign}{tick.change_pct:.2f}%",
            ratio,
        ]
        color = _signed_color(tick.change_pct)
        for col, text in enumerate(items):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            if col in (2, 3):
                item.setForeground(QBrush(color))
            self._table.setItem(row, col, item)

    def _find_row(self, ticker: str) -> int:
        for r in range(self._table.rowCount()):
            it = self._table.item(r, _COL_IDX["종목코드"])
            if it and it.text() == ticker:
                return r
        return -1

    # ── slots ─────────────────────────────────────────────────────────────────

    def _on_row_double_click(self, row: int, _col: int) -> None:
        """Double-click a watchlist row to trigger a buy."""
        ticker_item = self._table.item(row, _COL_IDX["종목코드"])
        name_item = self._table.item(row, _COL_IDX["종목명"])
        price_item = self._table.item(row, _COL_IDX["현재가"])
        if not (ticker_item and price_item):
            return
        ticker = ticker_item.text()
        name = name_item.text() if name_item else ticker
        price = int(price_item.text().replace(",", ""))
        if self._on_buy:
            self._on_buy(ticker, name, price)
