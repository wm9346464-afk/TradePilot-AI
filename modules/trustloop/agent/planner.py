"""Deterministic agent planner used before the live LLM planner is enabled."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from ..enums import RiskDecision
from ..models import (
    AgentProposal,
    DealRun,
    ProposedMilestone,
    ToolRequest,
)
from ..money import money


class AgentPlanner(Protocol):
    def propose(
        self,
        run: DealRun,
        *,
        invoice_currency: str,
        sample_amount: Decimal | int | str = "500",
        trial_amount: Decimal | int | str = "5000",
        deposit_amount: Decimal | int | str = "10000",
    ) -> AgentProposal:
        ...


class RuleBasedPlanner:
    def propose(
        self,
        run: DealRun,
        *,
        invoice_currency: str,
        sample_amount: Decimal | int | str = "500",
        trial_amount: Decimal | int | str = "5000",
        deposit_amount: Decimal | int | str = "10000",
    ) -> AgentProposal:
        if not run.risk:
            raise ValueError("Cannot propose a plan before contract review")

        warnings: list[str] = []
        if run.risk.decision == RiskDecision.BLOCK:
            decision = "BLOCK"
            warnings.append("Contract has blocking risks; direct unsecured credit is not allowed.")
        elif run.risk.decision == RiskDecision.REVIEW:
            decision = "REVIEW"
            warnings.append("Contract risks require human approval before payment.")
        else:
            decision = "PROCEED"

        if invoice_currency != run.deal.contract_value.currency:
            warnings.append(
                f"Contract currency {run.deal.contract_value.currency} differs from "
                f"invoice currency {invoice_currency}; an FX snapshot is required."
            )

        milestones = [
            ProposedMilestone(
                name="Sample fee",
                purpose="Verify payment capability and intent before a larger trial order.",
                amount=money(sample_amount, invoice_currency),
                invoice_currency=invoice_currency,
                unlock_condition="Buyer accepts the evidence-backed review and approves the plan.",
            ),
            ProposedMilestone(
                name="Small trial order",
                purpose="Validate fulfilment and acceptance with limited exposure.",
                amount=money(trial_amount, invoice_currency),
                invoice_currency=invoice_currency,
                unlock_condition="Sample-fee payment is confirmed by PayPal.",
            ),
            ProposedMilestone(
                name="Commodity deposit",
                purpose="Reduce unsecured exposure before a larger shipment or credit terms.",
                amount=money(deposit_amount, invoice_currency),
                invoice_currency=invoice_currency,
                unlock_condition="Trial order payment and acceptance are complete.",
            ),
        ]

        evidence_refs = [
            issue.evidence_quote
            for issue in run.risk.issues
            if issue.evidence_quote
        ]
        return AgentProposal(
            decision=decision,
            rationale=(
                f"The buyer requested {run.deal.requested_credit_days} days of credit. "
                f"The contract review found {run.risk.high_count} high-risk issue(s). "
                "A staged trust ladder limits exposure while creating verifiable payment evidence."
            ),
            evidence_refs=evidence_refs,
            recommended_ladder=milestones,
            requested_tools=[
                ToolRequest(
                    tool_name="create_invoice",
                    arguments={"milestone_sequence": 1},
                    reason="Create the first approved milestone invoice.",
                ),
                ToolRequest(
                    tool_name="send_invoice",
                    arguments={"milestone_sequence": 1},
                    reason="Send the invoice only after human approval.",
                ),
            ],
            warnings=warnings,
            needs_human_approval=True,
            approval_reason="Financial actions and amount/currency changes require human approval.",
            planner_type="RULE_BASED",
            confidence=Decimal("0.82") if decision == "PROCEED" else Decimal("0.70"),
        )

