"""Adapter for a PayPal MCP tool client.

The concrete MCP transport is injected so the TrustLoop service can use either
the official server or a restricted test client without changing its contract.
"""

from __future__ import annotations

from typing import Protocol

from ..money import Money
from ..models import PaymentResult
from .paypal import CreateInvoiceRequest


class McpToolClient(Protocol):
    def call_tool(self, name: str, arguments: dict) -> dict:
        ...


class McpPayPalGateway:
    backend_name = "MCP"

    def __init__(
        self,
        client: McpToolClient,
        *,
        fallback=None,
        allow_write_fallback: bool = False,
    ) -> None:
        self.client = client
        self.fallback = fallback
        self.allow_write_fallback = allow_write_fallback

    def create_invoice(self, request: CreateInvoiceRequest) -> PaymentResult:
        try:
            raw = self.client.call_tool(
                "create_invoice",
                {
                    "buyer_name": request.buyer_name,
                    "buyer_email": request.buyer_email,
                    "amount": request.amount.to_paypal_string(),
                    "currency": request.amount.currency,
                    "contract_id": request.contract_id,
                    "description": request.description,
                    "idempotency_key": request.idempotency_key,
                },
            )
            return self._to_result(raw, mode="LIVE_SANDBOX")
        except Exception:
            if self.fallback is not None and self.allow_write_fallback:
                return self.fallback.create_invoice(request)
            raise

    def send_invoice(self, invoice_id: str) -> PaymentResult:
        try:
            raw = self.client.call_tool("send_invoice", {"invoice_id": invoice_id})
            return self._to_result(raw, mode="LIVE_SANDBOX")
        except Exception:
            if self.fallback is not None and self.allow_write_fallback:
                return self.fallback.send_invoice(invoice_id)
            raise

    def get_invoice(self, invoice_id: str) -> PaymentResult:
        try:
            raw = self.client.call_tool("get_invoice", {"invoice_id": invoice_id})
            return self._to_result(raw, mode="LIVE_SANDBOX")
        except Exception:
            if self.fallback is not None:
                return self.fallback.get_invoice(invoice_id)
            raise

    def _to_result(self, raw: dict, *, mode: str) -> PaymentResult:
        if not isinstance(raw, dict):
            raise ValueError("MCP PayPal result must be a JSON object")
        amount = raw.get("amount")
        money = None
        if isinstance(amount, dict):
            money = Money(
                amount=str(amount.get("value", "0")),
                currency=amount.get("currency_code", raw.get("currency", "USD")),
            ).quantized()
        return PaymentResult(
            success=bool(raw.get("success", True)),
            backend="MCP",
            mode=mode,
            invoice_id=raw.get("invoice_id") or raw.get("id"),
            invoice_number=raw.get("invoice_number"),
            status=raw.get("status", "UNKNOWN"),
            raw_status=raw.get("status"),
            amount=money,
            payment_url=raw.get("payment_url") or raw.get("recipient_view_url"),
            paid_at=raw.get("paid_at"),
            transaction_id=raw.get("transaction_id"),
            error_code=raw.get("error_code"),
            error_message=raw.get("error"),
            raw_response={
                "invoice_id": raw.get("invoice_id") or raw.get("id"),
                "invoice_number": raw.get("invoice_number"),
                "status": raw.get("status"),
                "currency": (
                    amount.get("currency_code") if isinstance(amount, dict) else None
                ),
                "value": amount.get("value") if isinstance(amount, dict) else None,
                "transaction_id": raw.get("transaction_id"),
            },
        )

