"""Tabular evidence projections for the AG Grid console.

The console renders the run's own domain objects: milestones joined to their
approvals and PayPal invoices, plus the audit hash chain. No new business logic
lives here, so every number can be traced back to the audit trail.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

MILESTONE_COLUMNS = {
    "stage": "#",
    "status": "Status",
    "milestone": "Milestone",
    "amount": "Amount",
    "approved": "Approved",
    "approved_by": "Approved by",
    "invoice": "PayPal invoice",
    "transaction": "Transaction",
    "unlock_condition": "Unlock condition",
}

EVENT_COLUMNS = {
    "sequence": "#",
    "event_type": "Event",
    "actor": "Actor",
    "detail": "Payload",
    "hash": "Event hash",
    "at": "At (UTC)",
}


def _money(value) -> str:
    return value.format() if value is not None else ""


def milestone_rows(run) -> list[dict]:
    """One row per trust-ladder milestone, joined to its approval and invoice."""

    milestones = run.plan.milestones if run.plan else []
    rows: list[dict] = []
    for milestone in milestones:
        approval = next(
            (item for item in run.approvals if item.milestone_id == milestone.milestone_id),
            None,
        )
        invoice = next(
            (
                item
                for item in reversed(run.invoices)
                if milestone.invoice_id and item.invoice_id == milestone.invoice_id
            ),
            None,
        )
        rows.append(
            {
                "stage": milestone.sequence,
                "status": milestone.status.value,
                "milestone": milestone.name,
                "amount": _money(milestone.amount),
                "approved": _money(approval.approved_amount) if approval else "",
                "approved_by": approval.approved_by if approval else "",
                "invoice": (
                    (invoice.invoice_number or invoice.invoice_id) if invoice else ""
                ),
                "transaction": (invoice.transaction_id or "") if invoice else "",
                "unlock_condition": milestone.unlock_condition,
            }
        )
    return rows


def exposure_summary(run) -> dict:
    """Planned, approved and settled exposure in the invoice currency."""

    milestones = run.plan.milestones if run.plan else []
    currency = milestones[0].invoice_currency if milestones else ""
    planned = sum((item.amount.amount for item in milestones), Decimal("0"))
    settled = sum(
        (item.amount.amount for item in milestones if item.status.value == "PAID"),
        Decimal("0"),
    )
    approved = sum(
        (
            item.approved_amount.amount
            for item in run.approvals
            if item.approved_amount.currency == currency
        ),
        Decimal("0"),
    )
    return {
        "currency": currency,
        "planned": str(planned),
        "approved": str(approved),
        "settled": str(settled),
        "outstanding": str(planned - settled),
        "planned_label": f"{currency} {planned:,.2f}",
        "approved_label": f"{currency} {approved:,.2f}",
        "settled_label": f"{currency} {settled:,.2f}",
        "outstanding_label": f"{currency} {planned - settled:,.2f}",
    }


def _payload_hint(payload: dict) -> str:
    if not payload:
        return ""
    parts = []
    for key, value in list(payload.items())[:3]:
        if isinstance(value, (list, dict)):
            continue
        parts.append(f"{key}={str(value)[:40]}")
    return " · ".join(parts)


def event_rows(events) -> list[dict]:
    """One row per audit event, with the chain hash exposed for verification."""

    return [
        {
            "sequence": event.sequence,
            "event_type": event.event_type,
            "actor": f"{event.actor_type} / {event.actor_id}",
            "detail": _payload_hint(event.payload),
            "hash": event.event_hash[:16],
            "at": event.created_at.strftime("%Y-%m-%d %H:%M:%SZ"),
        }
        for event in events
    ]


def to_frame(rows: list[dict], columns: dict[str, str]) -> pd.DataFrame:
    """Build an ordered DataFrame; an empty run still yields the right columns."""

    frame = pd.DataFrame(rows)
    if frame.empty:
        return pd.DataFrame(columns=list(columns))
    return frame[list(columns)]


def exposure_bar_html(exposure: dict) -> str:
    """Stacked bar showing settled / approved-unpaid / not-yet-approved exposure."""

    planned = Decimal(exposure["planned"] or "0")
    if planned <= 0:
        return ""
    settled = Decimal(exposure["settled"] or "0")
    approved = Decimal(exposure["approved"] or "0")
    settled_pct = float(settled / planned * 100)
    approved_pct = float(max(approved - settled, Decimal("0")) / planned * 100)
    open_pct = max(0.0, 100.0 - settled_pct - approved_pct)
    return (
        '<div class="tp-exp-bar">'
        f'<span class="tp-exp-seg tp-exp-settled" style="width:{settled_pct:.1f}%"></span>'
        f'<span class="tp-exp-seg tp-exp-approved" style="width:{approved_pct:.1f}%"></span>'
        f'<span class="tp-exp-seg tp-exp-open" style="width:{open_pct:.1f}%"></span>'
        "</div>"
        '<div class="tp-exp-legend">'
        f'<span><i class="tp-exp-dot tp-exp-settled"></i>{exposure["settled_label"]} settled</span>'
        f'<span><i class="tp-exp-dot tp-exp-approved"></i>{exposure["approved_label"]} approved, unpaid</span>'
        f'<span><i class="tp-exp-dot tp-exp-open"></i>{exposure["outstanding_label"]} not approved</span>'
        "</div>"
    )
