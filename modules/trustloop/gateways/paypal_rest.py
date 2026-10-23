"""PayPal REST adapter behind the TrustLoop gateway contract."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from modules.paypal_payment import (
    create_invoice_api,
    get_invoice_status_api,
    is_paypal_configured,
    send_invoice_api,
)

from ..money import Money
from ..models import PaymentResult
from .paypal import CreateInvoiceRequest


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _map_error(message: str) -> tuple[str, bool]:
    text = str(message or "").lower()
    if "429" in text or "rate" in text:
        return "RATE_LIMITED", True
    if "timeout" in text or "timed out" in text or "connection" in text:
        return "NETWORK_ERROR", True
    if "401" in text or "unauthorized" in text or "未授权" in text:
        return "UNAUTHORIZED", False
    if "403" in text or "permission" in text or "权限" in text:
        return "FORBIDDEN", False
    if "422" in text or "currency" in text or "calculation" in text:
        return "VALIDATION_ERROR", False
    return "PAYPAL_API_ERROR", False


class PayPalRestGateway:
    backend_name = "REST"

    def __init__(self, *, configured_check=is_paypal_configured) -> None:
        self._configured_check = configured_check

    @property
    def is_configured(self) -> bool:
        return bool(self._configured_check())

    def create_invoice(self, request: CreateInvoiceRequest) -> PaymentResult:
        if not self.is_configured:
            return PaymentResult(
                success=False,
                backend="REST",
                mode="LIVE_SANDBOX",
                error_code="NOT_CONFIGURED",
                error_message="PayPal REST Sandbox is not configured",
                retryable=False,
            )
        raw = create_invoice_api(
            buyer_email=request.buyer_email,
            buyer_name=request.buyer_name,
            items=[
                {
                    "name": "Trust milestone",
                    "description": request.description,
                    "quantity": "1",
                    "unit_price": request.amount.to_paypal_string(),
                }
            ],
            note=request.description,
            currency=request.amount.currency,
            contract_id=request.contract_id,
            payment_type=request.payment_type,
            idempotency_key=request.idempotency_key,
        )
        if not raw.get("success"):
            code, retryable = _map_error(str(raw.get("error", "")))
            return PaymentResult(
                success=False,
                backend="REST",
                mode="LIVE_SANDBOX",
                error_code=code,
                error_message=str(raw.get("error", "PayPal invoice creation failed")),
                retryable=retryable,
            )
        safe_response = {
            "invoice_id": raw.get("invoice_id"),
            "invoice_number": raw.get("invoice_number"),
            "status": raw.get("status"),
            "total": str(raw.get("total", request.amount.amount)),
            "currency": raw.get("currency", request.amount.currency),
        }
        return PaymentResult(
            success=True,
            backend="REST",
            mode="LIVE_SANDBOX",
            invoice_id=raw.get("invoice_id"),
            invoice_number=raw.get("invoice_number"),
            status=raw.get("status", "DRAFT"),
            raw_status=raw.get("status"),
            amount=Money(
                amount=Decimal(str(raw.get("total", request.amount.amount))),
                currency=raw.get("currency", request.amount.currency),
            ).quantized(),
            payment_url=raw.get("payment_url") or raw.get("recipient_view_url"),
            raw_response=safe_response,
        )

    def send_invoice(self, invoice_id: str) -> PaymentResult:
        if not self.is_configured:
            return PaymentResult(
                success=False,
                backend="REST",
                mode="LIVE_SANDBOX",
                invoice_id=invoice_id,
                error_code="NOT_CONFIGURED",
                error_message="PayPal REST Sandbox is not configured",
            )
        raw = send_invoice_api(
            invoice_id,
            idempotency_key=f"trustloop-send-{invoice_id}",
        )
        if not raw.get("success"):
            code, retryable = _map_error(str(raw.get("error", "")))
            return PaymentResult(
                success=False,
                backend="REST",
                mode="LIVE_SANDBOX",
                invoice_id=invoice_id,
                error_code=code,
                error_message=str(raw.get("error", "PayPal invoice send failed")),
                retryable=retryable,
            )
        return PaymentResult(
            success=True,
            backend="REST",
            mode="LIVE_SANDBOX",
            invoice_id=invoice_id,
            status="SENT",
            raw_status="SENT",
            raw_response={"success": True, "status": "SENT"},
        )

    def get_invoice(self, invoice_id: str) -> PaymentResult:
        if not self.is_configured:
            return PaymentResult(
                success=False,
                backend="REST",
                mode="LIVE_SANDBOX",
                invoice_id=invoice_id,
                error_code="NOT_CONFIGURED",
                error_message="PayPal REST Sandbox is not configured",
            )
        raw = get_invoice_status_api(invoice_id)
        if not raw.get("success"):
            code, retryable = _map_error(str(raw.get("error", "")))
            return PaymentResult(
                success=False,
                backend="REST",
                mode="LIVE_SANDBOX",
                invoice_id=invoice_id,
                error_code=code,
                error_message=str(raw.get("error", "PayPal invoice lookup failed")),
                retryable=retryable,
            )
        currency = str(raw.get("currency", "USD"))
        amount_value = raw.get("total", raw.get("amount", "0"))
        return PaymentResult(
            success=True,
            backend="REST",
            mode="LIVE_SANDBOX",
            invoice_id=invoice_id,
            invoice_number=raw.get("invoice_number"),
            status=raw.get("status", "UNKNOWN"),
            raw_status=raw.get("status"),
            amount=Money(
                amount=Decimal(str(amount_value or "0")),
                currency=currency,
            ).quantized(),
            payment_url=raw.get("recipient_view_url"),
            paid_at=_parse_datetime(raw.get("paid_at")),
            transaction_id=raw.get("transaction_id") or None,
            raw_response={
                "invoice_id": invoice_id,
                "invoice_number": raw.get("invoice_number"),
                "status": raw.get("status"),
                "total": str(amount_value or "0"),
                "currency": currency,
                "transaction_id": raw.get("transaction_id"),
            },
        )

