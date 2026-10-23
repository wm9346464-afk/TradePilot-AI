"""Rate-limit and tool-governance safety tests."""

import pytest

from modules.trustloop.security import InMemoryRateLimiter, RateLimitExceeded


def test_rate_limiter_enforces_window_and_resets():
    now = [100.0]
    limiter = InMemoryRateLimiter(
        max_calls=2,
        window_seconds=60,
        clock=lambda: now[0],
    )

    limiter.check("approve")
    limiter.check("approve")
    with pytest.raises(RateLimitExceeded):
        limiter.check("approve")

    now[0] += 61
    limiter.check("approve")
    assert limiter.remaining("approve") == 1

