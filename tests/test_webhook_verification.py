"""PayPal webhook signature verification tests with mocked HTTP."""

import json

from modules.webhook_handler import WebhookHandler


class FakeResponse:
    def __init__(self, status):
        self.status = status

    def raise_for_status(self):
        return None

    def json(self):
        return {"verification_status": self.status}


def _headers():
    return {
        "Paypal-Transmission-Id": "transmission-1",
        "Paypal-Transmission-Time": "2026-10-23T00:00:00Z",
        "Paypal-Transmission-Sig": "signature",
        "Paypal-Cert-Url": "https://example.com/cert",
        "Paypal-Auth-Algo": "SHA256withRSA",
    }


def test_webhook_verification_uses_paypal_api(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "modules.paypal_payment.get_paypal_access_token",
        lambda: "token",
    )

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse("SUCCESS")

    monkeypatch.setattr("modules.webhook_handler.requests.post", fake_post)
    handler = WebhookHandler(webhook_id="WH-1", demo_mode=False)
    body = json.dumps({"event_type": "INVOICING.INVOICE.PAID"})

    assert handler.verify_signature(_headers(), body) is True
    assert captured["url"].endswith("/verify-webhook-signature")
    assert captured["json"]["webhook_id"] == "WH-1"


def test_webhook_verification_rejects_failure_and_missing_headers(monkeypatch):
    monkeypatch.setattr(
        "modules.paypal_payment.get_paypal_access_token",
        lambda: "token",
    )
    monkeypatch.setattr(
        "modules.webhook_handler.requests.post",
        lambda *args, **kwargs: FakeResponse("FAILURE"),
    )
    handler = WebhookHandler(webhook_id="WH-1", demo_mode=False)
    body = json.dumps({"event_type": "INVOICING.INVOICE.PAID"})

    assert handler.verify_signature(_headers(), body) is False
    assert handler.verify_signature({}, body) is False

