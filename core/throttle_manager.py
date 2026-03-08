"""core/throttle_manager.py – API rate-limit controller.

Tracks how many orders and queries have been issued in the current second
and injects a configurable delay when the limits are approached so that
the Kiwoom API never shuts the connection down.
"""
from __future__ import annotations

import time
import threading
from collections import deque
from typing import Callable

import config


class ThrottleManager:
    """Thread-safe rate limiter for Kiwoom API calls."""

    def __init__(
        self,
        max_orders_per_sec: int = config.MAX_ORDERS_PER_SECOND,
        max_queries_per_sec: int = config.MAX_QUERIES_PER_SECOND,
        delay_sec: float = config.THROTTLE_DELAY_SEC,
        log_callback: Callable[[str], None] | None = None,
    ) -> None:
        self._max_orders = max_orders_per_sec
        self._max_queries = max_queries_per_sec
        self._delay = delay_sec
        self._log = log_callback or (lambda _: None)

        self._lock = threading.Lock()
        # Each deque stores the timestamp (float) of recent calls.
        self._order_times: deque[float] = deque()
        self._query_times: deque[float] = deque()

    # ── internal helpers ──────────────────────────────────────────────────────

    def _prune(self, times: deque[float]) -> None:
        """Remove timestamps older than 1 second."""
        now = time.monotonic()
        while times and now - times[0] > 1.0:
            times.popleft()

    def _wait_if_needed(self, times: deque[float], limit: int, label: str) -> None:
        """Block (with short sleep) until there is capacity."""
        while True:
            with self._lock:
                self._prune(times)
                if len(times) < limit:
                    times.append(time.monotonic())
                    return
            # Approaching limit – wait before retrying.
            self._log(
                f"[Throttle] {label} rate limit approached "
                f"({len(times)}/{limit}/s). Delaying {self._delay}s."
            )
            time.sleep(self._delay)

    # ── public API ────────────────────────────────────────────────────────────

    def acquire_order_slot(self) -> None:
        """Block until an order slot is available, then consume it."""
        self._wait_if_needed(self._order_times, self._max_orders, "ORDER")

    def acquire_query_slot(self) -> None:
        """Block until a query slot is available, then consume it."""
        self._wait_if_needed(self._query_times, self._max_queries, "QUERY")

    @property
    def order_count_last_second(self) -> int:
        with self._lock:
            self._prune(self._order_times)
            return len(self._order_times)

    @property
    def query_count_last_second(self) -> int:
        with self._lock:
            self._prune(self._query_times)
            return len(self._query_times)
