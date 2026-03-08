"""core/api_client.py – Kiwoom API wrapper with built-in mock/simulation mode.

In production (API_MOCK_MODE = False) this module wraps the real Kiwoom
OpenAPI+ COM object via win32com.  In mock mode it generates realistic
synthetic tick data so the rest of the system can be developed and tested
on any platform.
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import config

# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------

@dataclass
class Tick:
    ticker: str
    name: str
    price: int
    change_pct: float
    bid: int
    ask: int
    bid_qty: int
    ask_qty: int
    volume: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="milliseconds"))


@dataclass
class OrderResult:
    order_id: str
    ticker: str
    direction: str     # "BUY" | "SELL"
    quantity: int
    price: int
    status: str        # "FILLED" | "PENDING" | "CANCELLED" | "FAILED"
    filled_price: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="milliseconds"))


@dataclass
class AccountInfo:
    account_no: str
    total_assets: float
    cash: float
    daily_pnl: float
    daily_pnl_pct: float


# ---------------------------------------------------------------------------
# Mock data helpers
# ---------------------------------------------------------------------------

_MOCK_STOCKS: list[dict] = [
    {"ticker": "005930", "name": "삼성전자",   "base_price": 72_000},
    {"ticker": "000660", "name": "SK하이닉스", "base_price": 198_000},
    {"ticker": "035420", "name": "NAVER",      "base_price": 215_000},
    {"ticker": "051910", "name": "LG화학",     "base_price": 410_000},
    {"ticker": "006400", "name": "삼성SDI",    "base_price": 330_000},
]


class _MockMarket:
    """Generates synthetic tick data for simulation mode."""

    def __init__(self) -> None:
        self._prices: dict[str, float] = {
            s["ticker"]: float(s["base_price"]) for s in _MOCK_STOCKS
        }
        self._lock = threading.Lock()

    def next_tick(self, ticker: str, name: str, base_price: int) -> Tick:
        with self._lock:
            prev = self._prices[ticker]
            # Random walk: ±0.3 % per tick
            change = prev * random.uniform(-0.003, 0.003)
            price = max(1, int(round(prev + change)))
            self._prices[ticker] = price
            spread = max(100, int(price * 0.001))
            bid = price - spread // 2
            ask = price + spread // 2
            change_pct = (price - base_price) / base_price * 100
            return Tick(
                ticker=ticker,
                name=name,
                price=price,
                change_pct=round(change_pct, 2),
                bid=bid,
                ask=ask,
                bid_qty=random.randint(100, 5_000),
                ask_qty=random.randint(100, 5_000),
                volume=random.randint(1_000, 100_000),
            )

    def get_price(self, ticker: str) -> int:
        with self._lock:
            return int(self._prices.get(ticker, 0))


# ---------------------------------------------------------------------------
# API Client
# ---------------------------------------------------------------------------

class APIClient:
    """Unified interface for Kiwoom API (real or mock)."""

    def __init__(
        self,
        mock_mode: bool = config.API_MOCK_MODE,
        account_no: str = config.KIWOOM_ACCOUNT,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._mock = mock_mode
        self._account_no = account_no
        self._log = log_callback or (lambda _: None)
        self._connected = False

        self._mock_market = _MockMarket() if mock_mode else None
        self._mock_cash = 10_000_000.0    # ₩10 million starting cash
        self._mock_daily_pnl = 0.0
        self._order_counter = 0
        self._lock = threading.Lock()

        # Tick subscribers: ticker -> list of callbacks
        self._tick_handlers: dict[str, list[Callable[[Tick], None]]] = {}
        self._subscribed: set[str] = set()
        self._tick_thread: threading.Thread | None = None

    # ── connection ────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        if self._mock:
            self._connected = True
            self._log("[API] Mock mode – connected (simulation).")
            return True
        try:
            # Real Kiwoom connection would go here (Windows only)
            import win32com.client  # type: ignore[import]
            self._ocx = win32com.client.Dispatch("KHOPENAPI.KHOpenAPICtrl.1")
            self._connected = True
            self._log("[API] Connected to Kiwoom OpenAPI+.")
            return True
        except Exception as exc:
            self._log(f"[API] Connection failed: {exc}")
            return False

    def disconnect(self) -> None:
        self._connected = False
        self._subscribed.clear()
        self._log("[API] Disconnected.")

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── watchlist subscription ────────────────────────────────────────────────

    def subscribe_ticks(self, ticker: str, callback: Callable[[Tick], None]) -> None:
        """Subscribe to real-time ticks for a ticker."""
        if ticker not in self._tick_handlers:
            self._tick_handlers[ticker] = []
        self._tick_handlers[ticker].append(callback)
        self._subscribed.add(ticker)
        if self._mock and (self._tick_thread is None or not self._tick_thread.is_alive()):
            self._start_mock_ticker()

    def unsubscribe_ticks(self, ticker: str) -> None:
        self._subscribed.discard(ticker)
        self._tick_handlers.pop(ticker, None)

    def get_watchlist(self) -> list[Tick]:
        """Return current tick for every mock stock (initial population)."""
        if self._mock:
            return [
                self._mock_market.next_tick(s["ticker"], s["name"], s["base_price"])
                for s in _MOCK_STOCKS
            ]
        return []  # Real implementation would query Kiwoom

    def _start_mock_ticker(self) -> None:
        def _run() -> None:
            stock_map = {s["ticker"]: s for s in _MOCK_STOCKS}
            while self._connected:
                for ticker in list(self._subscribed):
                    s = stock_map.get(ticker)
                    if s is None:
                        continue
                    tick = self._mock_market.next_tick(
                        ticker, s["name"], s["base_price"]
                    )
                    for cb in list(self._tick_handlers.get(ticker, [])):
                        try:
                            cb(tick)
                        except Exception:
                            pass
                time.sleep(0.5)

        self._tick_thread = threading.Thread(target=_run, daemon=True)
        self._tick_thread.start()

    # ── orders ────────────────────────────────────────────────────────────────

    def send_order(
        self,
        ticker: str,
        direction: str,
        quantity: int,
        price: int,
        order_type: str = "LIMIT",
    ) -> OrderResult:
        """Submit an order.  Returns an OrderResult (may be PENDING)."""
        with self._lock:
            self._order_counter += 1
            order_id = f"ORD{self._order_counter:06d}"

        if self._mock:
            return self._mock_fill(order_id, ticker, direction, quantity, price)

        # Real Kiwoom order submission would go here
        raise NotImplementedError("Real Kiwoom orders not implemented in this environment.")

    def cancel_order(self, order_id: str) -> bool:
        if self._mock:
            self._log(f"[API] Mock cancel order {order_id}")
            return True
        raise NotImplementedError

    def _mock_fill(
        self,
        order_id: str,
        ticker: str,
        direction: str,
        quantity: int,
        price: int,
    ) -> OrderResult:
        market_price = self._mock_market.get_price(ticker) if self._mock_market else price
        # 80 % chance of immediate fill within ±1 tick
        if random.random() < 0.8:
            slippage = random.randint(-1, 1) * 100
            filled_price = max(1, market_price + slippage)
            cost = filled_price * quantity
            with self._lock:
                if direction == "BUY":
                    self._mock_cash -= cost
                else:
                    self._mock_cash += cost
            return OrderResult(
                order_id=order_id,
                ticker=ticker,
                direction=direction,
                quantity=quantity,
                price=price,
                status="FILLED",
                filled_price=filled_price,
            )
        # 20 % chance of PENDING (will be handled by trading_engine timeout)
        return OrderResult(
            order_id=order_id,
            ticker=ticker,
            direction=direction,
            quantity=quantity,
            price=price,
            status="PENDING",
        )

    # ── account ───────────────────────────────────────────────────────────────

    def get_account_info(self) -> AccountInfo:
        if self._mock:
            initial_capital = 10_000_000.0
            return AccountInfo(
                account_no=self._account_no,
                total_assets=self._mock_cash + initial_capital,
                cash=self._mock_cash,
                daily_pnl=self._mock_daily_pnl,
                daily_pnl_pct=round(self._mock_daily_pnl / initial_capital * 100, 2),
            )
        raise NotImplementedError

    def add_mock_pnl(self, pnl: float) -> None:
        """Used by trading_engine to reflect realised P&L in the mock account."""
        if self._mock:
            with self._lock:
                self._mock_daily_pnl += pnl
