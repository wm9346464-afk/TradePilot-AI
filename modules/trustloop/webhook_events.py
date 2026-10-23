"""Authoritative processing of verified PayPal webhook events."""

from __future__ import annotations

from dataclasses import dataclass

from .enums import DealState


@dataclass(frozen=True)
class WebhookProcessResult:
    status: str
    processed: bool
    message: str
    run_id: str | None = None
    state: str | None = None


def process_verified_paypal_event(event: dict, service) -> WebhookProcessResult:
    """Process an already-verified event without trusting its payment claims."""
    if not isinstance(event, dict):
        return WebhookProcessResult("invalid_event", False, "Webhook body must be a JSON object")

    event_type = str(event.get("event_type", ""))
    if event_type != "INVOICING.INVOICE.PAID":
        return WebhookProcessResult(
            "ignored_event",
            False,
            f"Event type {event_type or '<missing>'} does not advance a TrustLoop run",
        )

    resource = event.get("resource")
    if not isinstance(resource, dict):
        return WebhookProcessResult(
            "invalid_event", False, "Paid invoice event is missing a resource object"
        )
    invoice_id = str(resource.get("id", "")).strip()
    if not invoice_id:
        return WebhookProcessResult(
            "invalid_event", False, "Paid invoice event is missing resource.id"
        )

    run = service.find_run_by_invoice(invoice_id)
    if run is None:
        return WebhookProcessResult(
            "run_not_found",
            False,
            "Invoice does not belong to a stored TrustLoop run",
        )
    if run.state not in {
        DealState.AWAITING_PAYMENT,
        DealState.PAYMENT_CONFIRMED,
        DealState.MILESTONE_COMPLETED,
    }:
        if run.state in {DealState.AWAITING_APPROVAL, DealState.PASSPORT_ISSUED}:
            return WebhookProcessResult(
                "already_processed",
                False,
                "Payment was already processed",
                run.run_id,
                run.state.value,
            )
        return WebhookProcessResult(
            "ignored_state",
            False,
            f"Run state {run.state.value} cannot accept a payment event",
            run.run_id,
            run.state.value,
        )

    refreshed = run
    if run.state == DealState.AWAITING_PAYMENT:
        refreshed = service.refresh_payment(run.run_id)
        if refreshed.state != DealState.PAYMENT_CONFIRMED:
            return WebhookProcessResult(
                "payment_pending",
                False,
                "PayPal has not yet confirmed PAID status",
                refreshed.run_id,
                refreshed.state.value,
            )

    advanced = service.advance_after_payment(refreshed.run_id)
    return WebhookProcessResult(
        "processed",
        True,
        "PayPal PAID status confirmed and the TrustLoop run advanced",
        advanced.run_id,
        advanced.state.value,
    )
