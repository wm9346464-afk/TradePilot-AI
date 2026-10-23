"""Deterministic in-memory PayPal gateway for v0 and tests."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from ..models import DealRun, PaymentResult
from .paypal import CreateInvoiceRequest, PayPalGatewayError


class FakePayPalGateway:
    backend_name = "FAKE"

    def __init__(self) -> None:
        self._invoices: dict[str, dict] = {}
        self._idempotency: dict[str, str] = {}

    def create_invoice(self, request: CreateInvoiceRequest) -> PaymentResult:
        existing_id = self._idempotency.get(request.idempotency_key)
        if existing_id:
            return self.get_invoice(existing_id)

        invoice_id = f"FAKE-INV-{uuid4().hex[:10].upper()}"
        invoice_number = f"TP-DEMO-{len(self._invoices) + 1:04d}"
        record = {
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "status": "DRAFT",
            "amount": request.amount,
            "buyer_name": request.buyer_name,
            "buyer_email": request.buyer_email,
            "contract_id": request.contract_id,
            "payment_type": request.payment_type,
            "payment_url": f"https://example.invalid/trustloop/{invoice_id}",
            "created_at": datetime.now(timezone.utc),
            "paid_at": None,
            "transaction_id": None,
        }
        self._invoices[invoice_id] = record
        self._idempotency[request.idempotency_key] = invoice_id
        return self._to_result(record)

    def send_invoice(self, invoice_id: str) -> PaymentResult:
        record = self._invoices.get(invoice_id)
        if not record:
            raise PayPalGatewayError("Fake invoice not found", error_code="NOT_FOUND")
        if record["status"] == "PAID":
            return self._to_result(record)
        if record["status"] not in {"DRAFT", "SENT"}:
            raise PayPalGatewayError(
                f"Invoice cannot be sent from status {record['status']}",
                error_code="INVALID_STATUS",
            )
        record["status"] = "SENT"
        return self._to_result(record)

    def get_invoice(self, invoice_id: str) -> PaymentResult:
        record = self._invoices.get(invoice_id)
        if not record:
            raise PayPalGatewayError("Fake invoice not found", error_code="NOT_FOUND")
        return self._to_result(record)

    def simulate_payment(
        self,
        invoice_id: str,
        *,
        amount: Decimal | None = None,
    ) -> PaymentResult:
        record = self._invoices.get(invoice_id)
        if not record:
            raise PayPalGatewayError("Fake invoice not found", error_code="NOT_FOUND")
        if record["status"] == "PAID":
            return self._to_result(record)
        if record["status"] != "SENT":
            raise PayPalGatewayError(
                f"Invoice must be SENT before payment, current={record['status']}",
                error_code="INVALID_STATUS",
            )
        if amount is not None and amount != record["amount"].amount:
            raise PayPalGatewayError(
                "Simulated payment amount does not match invoice",
                error_code="AMOUNT_MISMATCH",
            )
        record["status"] = "PAID"
        record["paid_at"] = datetime.now(timezone.utc)
        record["transaction_id"] = f"FAKE-TXN-{uuid4().hex[:12].upper()}"
        return self._to_result(record)

    def restore_run(self, run: DealRun) -> None:
        """Rebuild deterministic gateway state for a run loaded from storage."""
        milestones = run.plan.milestones if run.plan else []
        for milestone in milestones:
            if not milestone.invoice_id:
                continue
            invoice = next(
                (
                    item
                    for item in reversed(run.invoices)
                    if item.invoice_id == milestone.invoice_id
                ),
                None,
            )
            status_map = {
                "INVOICE_DRAFT": "DRAFT",
                "INVOICE_SENT": "SENT",
                "AWAITING_PAYMENT": "SENT",
                "PAID": "PAID",
                "REFUNDED": "REFUNDED",
                "FAILED": "CANCELLED",
            }
            status = status_map.get(milestone.status.value, "DRAFT")
            self._invoices[milestone.invoice_id] = {
                "invoice_id": milestone.invoice_id,
                "invoice_number": (
                    invoice.invoice_number
                    if invoice and invoice.invoice_number
                    else f"TP-DEMO-{milestone.sequence:04d}"
                ),
                "status": status,
                "amount": invoice.amount if invoice and invoice.amount else milestone.amount,
                "buyer_name": run.deal.buyer.name,
                "buyer_email": run.deal.buyer.email,
                "contract_id": run.deal.deal_id,
                "payment_type": "trust_milestone",
                "payment_url": (
                    invoice.payment_url
                    if invoice and invoice.payment_url
                    else f"https://example.invalid/trustloop/{milestone.invoice_id}"
                ),
                "created_at": invoice.paid_at if invoice and invoice.paid_at else datetime.now(timezone.utc),
                "paid_at": invoice.paid_at if invoice else None,
                "transaction_id": milestone.payment_id,
            }

    def _to_result(self, record: dict) -> PaymentResult:
        return PaymentResult(
            success=True,
            backend="FAKE",
            mode="DEMO",
            invoice_id=record["invoice_id"],
            invoice_number=record["invoice_number"],
            status=record["status"],
            raw_status=record["status"],
            amount=record["amount"],
            payment_url=record["payment_url"],
            paid_at=record["paid_at"],
            transaction_id=record["transaction_id"],
            raw_response={"simulated": True},
        )

