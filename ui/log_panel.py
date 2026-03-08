"""ui/log_panel.py – System Log panel (bottom-right quadrant).

Displays API connection state, order fill confirmations, errors, and other
system messages in a scrolling, time-stamped text area.
"""
from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QLabel,
)

import config


_LEVEL_COLORS: dict[str, str] = {
    "INFO":    "#e0e0e0",
    "OK":      "#66bb6a",
    "WARN":    "#ffa726",
    "ERROR":   "#ef5350",
    "KILL":    "#ff1744",
    "ORDER":   "#42a5f5",
    "Engine":  "#ab47bc",
    "Throttle":"#26c6da",
    "API":     "#80cbc4",
}


def _classify(text: str) -> str:
    for key in _LEVEL_COLORS:
        if f"[{key}]" in text or f"[{key.upper()}]" in text:
            return key
    return "INFO"


class LogPanel(QWidget):
    """Scrolling system log with colour-coded severity."""

    # Signal so other threads can safely append text
    append_signal: pyqtSignal = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._max_lines = config.LOG_MAX_LINES
        self._setup_ui()
        self.append_signal.connect(self._on_append)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Text area (created first so the clear button can reference it)
        self._text_area = QTextEdit()
        self._text_area.setReadOnly(True)
        self._text_area.setStyleSheet(
            "QTextEdit {"
            "  background-color: #121212;"
            "  color: #e0e0e0;"
            "  font-family: 'Consolas', 'D2Coding', monospace;"
            "  font-size: 11px;"
            "  border: 1px solid #333;"
            "  border-radius: 4px;"
            "}"
        )

        # Header (after _text_area so the clear button can safely connect)
        header = QHBoxLayout()
        title = QLabel("📋 시스템 로그")
        title.setStyleSheet("font-weight: bold; color: #e0e0e0; font-size: 13px;")
        header.addWidget(title)
        header.addStretch()
        clear_btn = QPushButton("지우기")
        clear_btn.setFixedWidth(60)
        clear_btn.setStyleSheet(
            "QPushButton { background: #424242; color: #bbb; border-radius: 4px; padding: 2px 6px; }"
            "QPushButton:hover { background: #616161; }"
        )
        clear_btn.clicked.connect(self._text_area.clear)
        header.addWidget(clear_btn)
        layout.addLayout(header)

        layout.addWidget(self._text_area)

    # ── public API ────────────────────────────────────────────────────────────

    def log(self, message: str) -> None:
        """Thread-safe log append."""
        self.append_signal.emit(message)

    def _on_append(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        full = f"[{ts}] {message}"
        level = _classify(message)
        color = _LEVEL_COLORS.get(level, "#e0e0e0")

        cursor = self._text_area.textCursor()
        cursor.movePosition(QTextCursor.End)

        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(full + "\n")

        # Trim to max lines
        doc = self._text_area.document()
        while doc.blockCount() > self._max_lines:
            cursor2 = QTextCursor(doc.begin())
            cursor2.select(QTextCursor.BlockUnderCursor)
            cursor2.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            cursor2.removeSelectedText()

        self._text_area.ensureCursorVisible()
