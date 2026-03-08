"""ui/positions_panel.py – Active Positions panel (bottom-left quadrant).

Shows every open position with:
  • Entry price, current price, real-time P&L (%)
  • Stop-loss / take-profit target lines
  • Individual "청산" (liquidate) button per position
"""
from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush, QColor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.trading_engine import Position


def _signed_color(value: float) -> QColor:
    if value > 0:
        return QColor("#ef5350")
    elif value < 0:
        return QColor("#42a5f5")
    return QColor("#e0e0e0")


_COLS = ["종목코드", "종목명", "매입가", "현재가", "수익률", "평가손익", "손절가", "익절가", "청산"]
_IDX = {n: i for i, n in enumerate(_COLS)}


class PositionsPanel(QWidget):
    """Bottom-left quadrant: active positions with per-row liquidation."""

    def __init__(
        self,
        on_liquidate: Callable[[str], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_liquidate = on_liquidate
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        title = QLabel("📊 보유 종목 & 주문 제어 (Active Positions)")
        title.setStyleSheet("font-weight: bold; color: #e0e0e0; font-size: 13px;")
        layout.addWidget(title)

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

    # ── public API ────────────────────────────────────────────────────────────

    def refresh_positions(self, positions: dict[str, Position]) -> None:
        """Rebuild the table from the current position dict."""
        # Remove rows that no longer exist
        existing_tickers: set[str] = set()
        rows_to_remove: list[int] = []
        for row in range(self._table.rowCount()):
            it = self._table.item(row, _IDX["종목코드"])
            if it:
                t = it.text()
                if t not in positions:
                    rows_to_remove.append(row)
                else:
                    existing_tickers.add(t)
        for row in reversed(rows_to_remove):
            self._table.removeRow(row)

        # Update or add rows
        for ticker, pos in positions.items():
            if ticker not in existing_tickers:
                self._insert_row(pos)
            else:
                self._update_row(pos)

    def _find_row(self, ticker: str) -> int:
        for r in range(self._table.rowCount()):
            it = self._table.item(r, _IDX["종목코드"])
            if it and it.text() == ticker:
                return r
        return -1

    def _insert_row(self, pos: Position) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._write_row(row, pos)
        self._add_liquidate_button(row, pos.ticker)

    def _update_row(self, pos: Position) -> None:
        row = self._find_row(pos.ticker)
        if row == -1:
            return
        self._write_row(row, pos)

    def _write_row(self, row: int, pos: Position) -> None:
        sign = "+" if pos.pnl_pct >= 0 else ""
        color = _signed_color(pos.pnl_pct)

        values = [
            (pos.ticker,               "#e0e0e0"),
            (pos.name,                 "#e0e0e0"),
            (f"{pos.entry_price:,}",   "#e0e0e0"),
            (f"{pos.current_price:,}", _signed_color(pos.pnl_pct).name()),
            (f"{sign}{pos.pnl_pct:.2f}%", color.name()),
            (f"₩{pos.pnl_krw:+,.0f}", color.name()),
            (f"{pos.stop_loss:,}",     "#42a5f5"),
            (f"{pos.take_profit:,}",   "#ef5350"),
        ]
        for col, (text, col_hex) in enumerate(values):
            item = QTableWidgetItem(text)
            item.setTextAlignment(Qt.AlignCenter)
            item.setForeground(QBrush(QColor(col_hex)))
            self._table.setItem(row, col, item)

    def _add_liquidate_button(self, row: int, ticker: str) -> None:
        btn = QPushButton("청산")
        btn.setFixedHeight(28)
        btn.setStyleSheet(
            "QPushButton { background:#b71c1c; color:#fff; border-radius:3px; font-weight:bold; }"
            "QPushButton:hover { background:#d32f2f; }"
        )
        btn.clicked.connect(lambda _checked=False, t=ticker: self._liquidate(t))
        self._table.setCellWidget(row, _IDX["청산"], btn)

    def _liquidate(self, ticker: str) -> None:
        if self._on_liquidate:
            self._on_liquidate(ticker)
