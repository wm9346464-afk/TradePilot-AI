"""Stable payment gateway contract shared by REST, MCP and fake backends."""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..money import Money
from ..models import PaymentResult


class PayPalGatewayError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_code: str = "PAYPAL_ERROR",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable


class CreateInvoiceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    buyer_name: str
    buyer_email: str
    amount: Money
    description: str = "TradePilot TrustLoop demo invoice"
    contract_id: str = ""
    payment_type: str = "trust_milestone"
    idempotency_key: str = Field(min_length=8)


class PayPalGateway(Protocol):
    backend_name: str

    def create_invoice(self, request: CreateInvoiceRequest) -> PaymentResult:
        ...

    def send_invoice(self, invoice_id: str) -> PaymentResult:
        ...

    def get_invoice(self, invoice_id: str) -> PaymentResult:
        ...

