"""tests/test_throttle_manager.py – Unit tests for ThrottleManager."""
from __future__ import annotations

import time
import threading
import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.throttle_manager import ThrottleManager


class TestThrottleManager:
    def test_acquire_within_limit(self) -> None:
        """Should allow up to max_orders_per_sec acquisitions without delay."""
        tm = ThrottleManager(max_orders_per_sec=3, max_queries_per_sec=3, delay_sec=0.05)
        for _ in range(3):
            tm.acquire_order_slot()
        assert tm.order_count_last_second == 3

    def test_query_count_tracking(self) -> None:
        tm = ThrottleManager(max_orders_per_sec=5, max_queries_per_sec=5, delay_sec=0.01)
        for _ in range(4):
            tm.acquire_query_slot()
        assert tm.query_count_last_second == 4

    def test_rate_limit_delays(self) -> None:
        """Acquiring beyond limit should block until capacity is available."""
        tm = ThrottleManager(max_orders_per_sec=2, max_queries_per_sec=5, delay_sec=0.05)
        # Fill up the limit
        tm.acquire_order_slot()
        tm.acquire_order_slot()
        # Third slot must wait; we run it in a thread with a timeout
        done = threading.Event()

        def _try() -> None:
            tm.acquire_order_slot()
            done.set()

        t = threading.Thread(target=_try, daemon=True)
        t.start()
        # Expect it to eventually succeed (within 2 seconds)
        finished = done.wait(timeout=2.0)
        assert finished, "acquire_order_slot timed out waiting for capacity"

    def test_counts_reset_after_one_second(self) -> None:
        """Counts should drop back to 0 after the 1-second window expires."""
        tm = ThrottleManager(max_orders_per_sec=5, max_queries_per_sec=5, delay_sec=0.01)
        tm.acquire_order_slot()
        tm.acquire_order_slot()
        assert tm.order_count_last_second == 2
        time.sleep(1.1)
        assert tm.order_count_last_second == 0

    def test_log_callback_called_on_limit(self) -> None:
        """Log callback should be invoked when limit is approached."""
        messages: list[str] = []
        tm = ThrottleManager(
            max_orders_per_sec=1, max_queries_per_sec=5,
            delay_sec=0.05,
            log_callback=messages.append,
        )
        # Fill up
        tm.acquire_order_slot()
        # Now try to get another – should trigger log before succeeding
        done = threading.Event()

        def _acquire() -> None:
            tm.acquire_order_slot()
            done.set()

        t = threading.Thread(target=_acquire, daemon=True)
        t.start()
        done.wait(timeout=2.0)
        assert any("Throttle" in m for m in messages), "Expected throttle log message"
