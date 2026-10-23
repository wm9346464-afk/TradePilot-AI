"""Rate-limit and tool-governance safety tests."""

import os

import pytest

from modules.config import _apply_secret_mapping
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


def test_streamlit_secrets_map_to_env_without_overriding(monkeypatch):
    monkeypatch.delenv("TRUSTLOOP_TEST_SECRET", raising=False)
    monkeypatch.setenv("TRUSTLOOP_EXISTING_SECRET", "environment-value")

    _apply_secret_mapping(
        {
            "TRUSTLOOP_TEST_SECRET": "secret-value",
            "TRUSTLOOP_EXISTING_SECRET": "secret-must-not-win",
            "NESTED_SECRET": {"ignored": "nested"},
        }
    )

    assert os.environ["TRUSTLOOP_TEST_SECRET"] == "secret-value"
    assert os.environ["TRUSTLOOP_EXISTING_SECRET"] == "environment-value"

