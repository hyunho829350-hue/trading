"""
Entry point for the automated trading program.

Usage (Windows, Kiwoom OpenAPI+ installed)::

    python -m app.main

Logging is written to stdout and to ``trading.log`` in the current directory.
"""

import logging
import sys

from PyQt5.QtWidgets import QApplication

from .main_window import MainWindow


def _configure_logging() -> None:
    fmt = "%(asctime)s  %(levelname)-8s  %(name)s – %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("trading.log", encoding="utf-8"),
    ]
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


def main() -> None:
    _configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("자동매매 프로그램")
    app.setOrganizationName("TradingApp")

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
