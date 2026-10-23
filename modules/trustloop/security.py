"""Small in-memory rate limiter for public demo sessions."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable


class RateLimitExceeded(RuntimeError):
    pass


class InMemoryRateLimiter:
    def __init__(
        self,
        *,
        max_calls: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, action: str) -> None:
        now = self.clock()
        events = self._events[action]
        while events and now - events[0] >= self.window_seconds:
            events.popleft()
        if len(events) >= self.max_calls:
            raise RateLimitExceeded(
                f"Rate limit exceeded for {action}: "
                f"max {self.max_calls} calls per {self.window_seconds} seconds"
            )
        events.append(now)

    def remaining(self, action: str) -> int:
        now = self.clock()
        events = self._events[action]
        while events and now - events[0] >= self.window_seconds:
            events.popleft()
        return max(0, self.max_calls - len(events))

