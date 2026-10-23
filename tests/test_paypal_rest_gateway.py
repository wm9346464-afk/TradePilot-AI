"""Mocked tests for the TrustLoop PayPal REST adapter."""

from modules.trustloop.gateways.paypal import CreateInvoiceRequest
from modules.trustloop.gateways.paypal_rest import PayPalRestGateway
from modules.trustloop.money import money


def _request() -> CreateInvoiceRequest:
    return CreateInvoiceRequest(
        buyer_name="Buyer",
        buyer_email="buyer@example.com",
        amount=money("500", "USD"),
        contract_id="DEAL-1",
        idempotency_key="invoice-request-0001",
    )


def test_rest_gateway_maps_create_send_and_paid_status(monkeypatch):
    gateway = PayPalRestGateway(configured_check=lambda: True)
    captured = {}

    def fake_create(**kwargs):
        captured.update(kwargs)
        return {
            "success": True,
            "invoice_id": "INV-1",
            "invoice_number": "TP-1",
            "status": "DRAFT",
            "total": 500.0,
            "currency": "USD",
            "payment_url": "https://sandbox.paypal.com/invoice/INV-1",
        }

    monkeypatch.setattr(
        "modules.trustloop.gateways.paypal_rest.create_invoice_api",
        fake_create,
    )
    created = gateway.create_invoice(_request())

    assert created.success is True
    assert created.invoice_id == "INV-1"
    assert created.amount.format() == "USD 500.00"
    assert captured["idempotency_key"] == "invoice-request-0001"
    assert captured["currency"] == "USD"

    monkeypatch.setattr(
        "modules.trustloop.gateways.paypal_rest.send_invoice_api",
        lambda invoice_id, idempotency_key="": {"success": True},
    )
    sent = gateway.send_invoice("INV-1")
    assert sent.success is True
    assert sent.status == "SENT"

    monkeypatch.setattr(
        "modules.trustloop.gateways.paypal_rest.get_invoice_status_api",
        lambda invoice_id: {
            "success": True,
            "status": "PAID",
            "amount": "500.00",
            "currency": "USD",
            "invoice_number": "TP-1",
            "recipient_view_url": "https://sandbox.paypal.com/invoice/INV-1",
            "paid_at": "2026-10-23T10:30:00Z",
            "transaction_id": "PAY-1",
        },
    )
    paid = gateway.get_invoice("INV-1")

    assert paid.success is True
    assert paid.status == "PAID"
    assert paid.amount.format() == "USD 500.00"
    assert paid.transaction_id == "PAY-1"
    assert paid.paid_at is not None


def test_rest_gateway_maps_retryable_errors(monkeypatch):
    gateway = PayPalRestGateway(configured_check=lambda: True)
    monkeypatch.setattr(
        "modules.trustloop.gateways.paypal_rest.create_invoice_api",
        lambda **kwargs: {
            "success": False,
            "error": "PayPal API HTTP错误: 429 Too Many Requests",
        },
    )
    result = gateway.create_invoice(_request())

    assert result.success is False
    assert result.error_code == "RATE_LIMITED"
    assert result.retryable is True


def test_rest_gateway_does_not_call_api_without_config(monkeypatch):
    gateway = PayPalRestGateway(configured_check=lambda: False)
    monkeypatch.setattr(
        "modules.trustloop.gateways.paypal_rest.create_invoice_api",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("network path called")),
    )
    result = gateway.create_invoice(_request())

    assert result.success is False
    assert result.error_code == "NOT_CONFIGURED"

