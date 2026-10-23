"""Trust Passport verification helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .audit import AuditEvent, AuditLog
from .models import TrustPassport


class PassportVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    checks: dict[str, bool]
    message: str


def verify_passport(
    passport: TrustPassport,
    events: list[AuditEvent],
) -> PassportVerificationResult:
    checks = {
        "has_audit_events": bool(events),
        "audit_chain_valid": False,
        "head_hash_matches": False,
        "has_paid_settlement": False,
        "approvals_present": bool(passport.approvals),
        "agent_actions_present": bool(passport.agent_actions),
        "amounts_positive": all(item.amount.amount > 0 for item in passport.settlements),
    }
    try:
        audit_log = AuditLog.from_events(passport.run_id, events)
        checks["audit_chain_valid"] = True
        checks["head_hash_matches"] = audit_log.head_hash == passport.audit_head_hash
    except ValueError:
        checks["audit_chain_valid"] = False
    checks["has_paid_settlement"] = any(
        item.status == "PAID" for item in passport.settlements
    )
    valid = all(checks.values())
    message = "Passport integrity verified." if valid else "Passport verification failed."
    return PassportVerificationResult(valid=valid, checks=checks, message=message)
