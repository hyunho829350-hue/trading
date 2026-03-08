"""ui/account_panel.py – Account & Risk Summary panel (top-left quadrant).

Displays:
  • Total assets, available cash, daily realised P&L
  • Kill-Switch button (large, red) – liquidates everything and disconnects

The Kill-Switch is wired to TradingEngine.liquidate_all() + APIClient.disconnect()
via the callbacks passed at construction time.
"""
from __future__ import annotations

from typing import Callable

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QMessageBox,
)

from core.api_client import AccountInfo


def _fmt_krw(value: float) -> str:
    return f"₩{value:>+,.0f}" if value != 0 else "₩0"


def _signed_color(value: float) -> str:
    if value > 0:
        return "#ef5350"   # Korean convention: red = up
    elif value < 0:
        return "#42a5f5"   # blue = down
    return "#e0e0e0"


class AccountPanel(QWidget):
    """Top-left quadrant: account summary + kill-switch."""

    def __init__(
        self,
        on_kill_switch: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_kill_switch = on_kill_switch
        self._setup_ui()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # Title
        title = QLabel("🏦 계좌 & 리스크 요약")
        title.setStyleSheet("font-weight: bold; color: #e0e0e0; font-size: 13px;")
        root.addWidget(title)

        # Metrics grid
        grid = QGridLayout()
        grid.setSpacing(6)

        def _label(text: str, align: Qt.AlignmentFlag = Qt.AlignLeft) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #9e9e9e; font-size: 11px;")
            lbl.setAlignment(align)
            return lbl

        def _value(text: str = "–") -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet("color: #e0e0e0; font-size: 13px; font-weight: bold;")
            lbl.setAlignment(Qt.AlignRight)
            return lbl

        grid.addWidget(_label("총 자산"),       0, 0)
        self._total_assets = _value()
        grid.addWidget(self._total_assets,       0, 1)

        grid.addWidget(_label("예수금"),         1, 0)
        self._cash = _value()
        grid.addWidget(self._cash,               1, 1)

        grid.addWidget(_label("당일 실현 손익"), 2, 0)
        self._daily_pnl = _value()
        grid.addWidget(self._daily_pnl,          2, 1)

        grid.addWidget(_label("당일 손익률"),    3, 0)
        self._daily_pnl_pct = _value()
        grid.addWidget(self._daily_pnl_pct,      3, 1)

        root.addLayout(grid)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #424242;")
        root.addWidget(sep)

        # Kill-Switch button
        self._kill_btn = QPushButton("⛔  전체 포지션 청산 (Kill-Switch)")
        self._kill_btn.setMinimumHeight(56)
        self._kill_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #b71c1c;"
            "  color: #ffffff;"
            "  font-size: 16px;"
            "  font-weight: bold;"
            "  border-radius: 6px;"
            "  border: 2px solid #ef5350;"
            "}"
            "QPushButton:hover {"
            "  background-color: #d32f2f;"
            "}"
            "QPushButton:pressed {"
            "  background-color: #7f0000;"
            "}"
        )
        self._kill_btn.clicked.connect(self._confirm_kill)
        root.addWidget(self._kill_btn)

        root.addStretch()

    # ── slots ─────────────────────────────────────────────────────────────────

    def _confirm_kill(self) -> None:
        reply = QMessageBox.warning(
            self,
            "Kill-Switch 확인",
            "⚠️  모든 포지션을 시장가로 청산하고 API 연결을 끊습니다.\n계속하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._on_kill_switch()
            self._kill_btn.setText("⛔  Kill-Switch 발동됨")
            self._kill_btn.setEnabled(False)
            self._kill_btn.setStyleSheet(
                "QPushButton { background-color: #424242; color: #9e9e9e; "
                "font-size: 16px; font-weight: bold; border-radius: 6px; }"
            )

    def update_account(self, info: AccountInfo) -> None:
        """Refresh displayed values."""
        self._total_assets.setText(f"₩{info.total_assets:>,.0f}")
        self._cash.setText(f"₩{info.cash:>,.0f}")

        color = _signed_color(info.daily_pnl)
        self._daily_pnl.setText(
            f"<span style='color:{color}'>{_fmt_krw(info.daily_pnl)}</span>"
        )
        self._daily_pnl.setTextFormat(Qt.RichText)

        color2 = _signed_color(info.daily_pnl_pct)
        sign = "+" if info.daily_pnl_pct >= 0 else ""
        self._daily_pnl_pct.setText(
            f"<span style='color:{color2}'>{sign}{info.daily_pnl_pct:.2f}%</span>"
        )
        self._daily_pnl_pct.setTextFormat(Qt.RichText)
