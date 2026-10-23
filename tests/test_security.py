"""Rate-limit and tool-governance safety tests."""

import os

import pytest

from modules.config import _apply_secret_mapping, _is_secure_service_url
from modules.trustloop.security import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    is_safe_paypal_payment_url,
)


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


def test_payment_url_must_be_https_paypal_domain():
    assert is_safe_paypal_payment_url(
        "https://www.sandbox.paypal.com/invoice/INV-1"
    ) is True
    assert is_safe_paypal_payment_url("https://paypal.com/invoice/INV-1") is True
    assert is_safe_paypal_payment_url("javascript:alert(1)") is False
    assert is_safe_paypal_payment_url("http://www.paypal.com/invoice/INV-1") is False
    assert is_safe_paypal_payment_url("https://paypal.com.attacker.example/") is False


def test_api_key_endpoints_require_https_except_local_development():
    assert _is_secure_service_url("https://api.example.com/v1") is True
    assert _is_secure_service_url("http://localhost:8080/v1") is True
    assert _is_secure_service_url("http://127.0.0.1:8080/v1") is True
    assert _is_secure_service_url("http://api.example.com/v1") is False
    assert _is_secure_service_url("file:///etc/passwd") is False

