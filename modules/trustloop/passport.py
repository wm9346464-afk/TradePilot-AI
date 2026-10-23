"""Trust Passport verification helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .audit import AuditEvent, AuditLog
from .models import TrustPassport
from .passport_signature import verify_passport_signature


class PassportVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    checks: dict[str, bool]
    message: str


def verify_passport(
    passport: TrustPassport,
    events: list[AuditEvent],
    *,
    signing_key: str | None = None,
) -> PassportVerificationResult:
    checks = {
        "has_audit_events": bool(events),
        "audit_chain_valid": False,
        "head_hash_matches": False,
        "contract_hash_matches": False,
        "passport_issue_event_matches": False,
        "settlement_invoices_match": False,
        "risk_summary_hash_matches": (
            passport.risk_summary.contract_hash == passport.contract_hash
        ),
        "approvals_match_audit": False,
        "settlements_match_audit": False,
        "has_paid_settlement": False,
        "approvals_present": bool(passport.approvals),
        "agent_actions_present": bool(passport.agent_actions),
        "amounts_positive": all(item.amount.amount > 0 for item in passport.settlements),
    }
    try:
        AuditLog.from_events(passport.run_id, events)
        checks["audit_chain_valid"] = True
        checks["head_hash_matches"] = any(
            event.event_hash == passport.audit_head_hash for event in events
        )
        checks["contract_hash_matches"] = any(
            event.event_type == "CONTRACT_REVIEWED"
            and event.payload.get("contract_hash") == passport.contract_hash
            for event in events
        )
        checks["passport_issue_event_matches"] = any(
            event.event_type == "PASSPORT_ISSUED"
            and event.payload.get("passport_id") == passport.passport_id
            for event in events
        )
        checks["settlement_invoices_match"] = all(
            any(
                event.event_type == "INVOICE_CREATED"
                and event.payload.get("invoice_id") == settlement.invoice_id
                for event in events
            )
            for settlement in passport.settlements
        )
        checks["approvals_match_audit"] = all(
            any(
                event.event_type == "PLAN_APPROVED"
                and event.payload.get("approval_id") == approval.approval_id
                and event.payload.get("milestone_id") == approval.milestone_id
                and event.payload.get("amount")
                == approval.approved_amount.model_dump(mode="json")
                for event in events
            )
            for approval in passport.approvals
        )
        checks["settlements_match_audit"] = all(
            any(
                event.event_type == "PAYMENT_CONFIRMED"
                and event.payload.get("invoice_id") == settlement.invoice_id
                and event.payload.get("transaction_id") == settlement.transaction_id
                and event.payload.get("amount")
                == settlement.amount.model_dump(mode="json")
                for event in events
            )
            for settlement in passport.settlements
        )
    except ValueError:
        checks["audit_chain_valid"] = False
    checks["has_paid_settlement"] = any(
        item.status == "PAID" for item in passport.settlements
    )
    if signing_key is not None or passport.signature is not None:
        checks["issuer_signature_valid"] = bool(
            signing_key and verify_passport_signature(passport, signing_key)
        )
    valid = all(checks.values())
    if valid and "issuer_signature_valid" in checks:
        message = "Passport integrity and issuer signature verified."
    elif valid:
        message = "Passport integrity verified; issuer signature is not configured."
    else:
        message = "Passport verification failed."
    return PassportVerificationResult(valid=valid, checks=checks, message=message)
