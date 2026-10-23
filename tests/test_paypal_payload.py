"""Regression tests for the PayPal invoice request payload."""

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import modules.paypal_payment as paypal_payment


class FakeResponse:
    content = json.dumps({"id": "INV-1"}).encode("utf-8")

    def json(self):
        return {"id": "INV-1", "detail": {"invoice_number": "TP-1"}}


def test_invoice_payload_does_not_send_unverified_merchant_email(monkeypatch):
    captured = {}

    monkeypatch.setattr(paypal_payment, "get_paypal_access_token", lambda: "token")
    monkeypatch.setattr(
        paypal_payment,
        "get_merchant_email",
        lambda: "sb-test@business.example.com",
    )
    monkeypatch.setattr(paypal_payment, "get_merchant_name", lambda: "TradePilot AI")

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(paypal_payment, "_request_with_retry", fake_request)
    result = paypal_payment.create_invoice_api(
        buyer_email="buyer@example.com",
        buyer_name="Buyer",
        items=[{"name": "Sample", "quantity": "1", "unit_price": "1.00"}],
        currency="USD",
        idempotency_key="payload-test-0001",
    )

    assert result["success"] is True
    assert captured["headers"]["PayPal-Request-Id"] == "payload-test-0001"
    assert captured["json"]["invoicer"] == {
        "name": {"full_name": "TradePilot AI"}
    }
    assert "email_address" not in captured["json"]["invoicer"]

