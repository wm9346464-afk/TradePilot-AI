"""Deterministic state transitions for a TrustLoop deal run."""

from __future__ import annotations

from datetime import datetime, timezone

from .enums import DealState
from .models import DealRun


class InvalidStateTransition(ValueError):
    pass


TRANSITIONS: dict[DealState, dict[str, DealState]] = {
    DealState.INTAKE: {
        "CASE_SUBMITTED": DealState.CONTRACT_REVIEW,
    },
    DealState.CONTRACT_REVIEW: {
        "REVIEW_COMPLETED": DealState.RISK_ASSESSED,
    },
    DealState.RISK_ASSESSED: {
        "PLAN_CREATED": DealState.PLAN_PROPOSED,
    },
    DealState.PLAN_PROPOSED: {
        "APPROVAL_REQUESTED": DealState.AWAITING_APPROVAL,
    },
    DealState.AWAITING_APPROVAL: {
        "APPROVED": DealState.INVOICE_CREATING,
    },
    DealState.INVOICE_CREATING: {
        "INVOICE_CREATED": DealState.INVOICE_CREATED,
    },
    DealState.INVOICE_CREATED: {
        "INVOICE_SENT": DealState.AWAITING_PAYMENT,
    },
    DealState.AWAITING_PAYMENT: {
        "PAYMENT_CONFIRMED": DealState.PAYMENT_CONFIRMED,
    },
    DealState.PAYMENT_CONFIRMED: {
        "MILESTONE_COMPLETED": DealState.MILESTONE_COMPLETED,
    },
    DealState.MILESTONE_COMPLETED: {
        "PASSPORT_ISSUED": DealState.PASSPORT_ISSUED,
        "NEXT_MILESTONE_REQUESTED": DealState.AWAITING_APPROVAL,
    },
    DealState.FAILED: {},
    DealState.CANCELLED: {},
    DealState.PASSPORT_ISSUED: {},
}

TERMINAL_STATES = {
    DealState.FAILED,
    DealState.CANCELLED,
    DealState.PASSPORT_ISSUED,
}


class DealStateMachine:
    def transition(self, run: DealRun, event_type: str) -> DealRun:
        if event_type == "FAILED" and run.state not in TERMINAL_STATES:
            return run.model_copy(
                update={
                    "state": DealState.FAILED,
                    "updated_at": datetime.now(timezone.utc),
                }
            )
        if event_type == "CANCELLED" and run.state not in TERMINAL_STATES:
            return run.model_copy(
                update={
                    "state": DealState.CANCELLED,
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        next_state = TRANSITIONS.get(run.state, {}).get(event_type)
        if next_state is None:
            raise InvalidStateTransition(
                f"Event {event_type} is not allowed from state {run.state.value}"
            )
        return run.model_copy(
            update={
                "state": next_state,
                "updated_at": datetime.now(timezone.utc),
            }
        )

    def allowed_events(self, state: DealState) -> set[str]:
        if state in TERMINAL_STATES:
            return set()
        return set(TRANSITIONS.get(state, {})) | {"FAILED", "CANCELLED"}

    def can_transition(self, state: DealState, event_type: str) -> bool:
        return event_type in self.allowed_events(state)

