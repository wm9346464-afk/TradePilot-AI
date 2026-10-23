"""Deterministic financial and approval guardrails."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from .enums import MilestoneStatus
from .fx import FxRateProvider
from .models import (
    ActionPlan,
    AgentProposal,
    ApprovalRecord,
    DealRun,
    Money,
    TrustMilestone,
)


class PolicyViolation(ValueError):
    pass


class PolicyConfig(BaseModel):
    max_invoice_amount_usd: Decimal = Decimal("10000")
    max_milestones: int = Field(default=5, ge=1, le=20)
    allowed_currencies: list[str] = Field(
        default_factory=lambda: ["USD", "EUR", "GBP", "JPY", "CNY"]
    )
    require_human_approval: bool = True


class PolicyEngine:
    def __init__(self, config: PolicyConfig, fx_provider: FxRateProvider) -> None:
        self.config = config
        self.fx_provider = fx_provider

    def _usd_value(self, amount: Money) -> Decimal:
        if amount.currency == "USD":
            return amount.amount
        snapshot = self.fx_provider.get_rate(amount.currency, "USD")
        return snapshot.convert(amount).amount

    def validate_milestone(self, milestone: TrustMilestone) -> None:
        if milestone.amount.amount <= 0:
            raise PolicyViolation("Milestone amount must be positive")
        if milestone.invoice_currency not in self.config.allowed_currencies:
            raise PolicyViolation(
                f"Invoice currency {milestone.invoice_currency} is not allowed"
            )
        if milestone.amount.currency != milestone.invoice_currency:
            raise PolicyViolation("Milestone amount currency must match invoice currency")
        if self._usd_value(milestone.amount) > self.config.max_invoice_amount_usd:
            raise PolicyViolation(
                f"Milestone exceeds max invoice amount: {milestone.amount.format()}"
            )

    def validate_plan(self, plan: ActionPlan) -> None:
        if len(plan.milestones) > self.config.max_milestones:
            raise PolicyViolation(
                f"Plan has {len(plan.milestones)} milestones; maximum is "
                f"{self.config.max_milestones}"
            )
        sequences = [item.sequence for item in plan.milestones]
        if sequences != list(range(1, len(plan.milestones) + 1)):
            raise PolicyViolation("Milestone sequence must be contiguous and start at 1")
        for milestone in plan.milestones:
            self.validate_milestone(milestone)
        total_usd = sum(
            (self._usd_value(milestone.amount) for milestone in plan.milestones),
            Decimal("0"),
        )
        contract_usd = self._usd_value(plan.settlement_plan.contract_money)
        if total_usd > contract_usd:
            raise PolicyViolation(
                "Trust Ladder total exceeds the contract value"
            )

    def validate_agent_proposal(self, proposal: AgentProposal) -> None:
        if proposal.decision == "BLOCK":
            raise PolicyViolation("Agent blocked the deal; financial execution is disabled")
        if not proposal.recommended_ladder:
            raise PolicyViolation("Agent proposal must include at least one milestone")
        if len(proposal.recommended_ladder) > self.config.max_milestones:
            raise PolicyViolation(
                f"Agent proposed {len(proposal.recommended_ladder)} milestones; "
                f"maximum is {self.config.max_milestones}"
            )
        if any(
            request.tool_name in {"create_invoice", "send_invoice"}
            for request in proposal.requested_tools
        ) and not proposal.needs_human_approval:
            raise PolicyViolation("Financial tool requests must require human approval")
        for milestone in proposal.recommended_ladder:
            if milestone.amount.amount <= 0:
                raise PolicyViolation("Proposed milestone amount must be positive")
            if milestone.invoice_currency not in self.config.allowed_currencies:
                raise PolicyViolation(
                    f"Invoice currency {milestone.invoice_currency} is not allowed"
                )
            if milestone.amount.currency != milestone.invoice_currency:
                raise PolicyViolation("Proposed milestone currency mismatch")
            if self._usd_value(milestone.amount) > self.config.max_invoice_amount_usd:
                raise PolicyViolation(
                    f"Proposed milestone exceeds max amount: {milestone.amount.format()}"
                )

    def validate_approval(
        self,
        run: DealRun,
        milestone: TrustMilestone,
        approval: ApprovalRecord,
    ) -> None:
        if not run.plan:
            raise PolicyViolation("Deal run has no action plan")
        if approval.plan_id != run.plan.plan_id:
            raise PolicyViolation("Approval does not belong to the current plan")
        if approval.milestone_id != milestone.milestone_id:
            raise PolicyViolation("Approval does not belong to the milestone")
        if approval.approved_amount != milestone.amount:
            raise PolicyViolation("Approved amount does not match milestone amount")
        if approval.approved_currency != milestone.invoice_currency:
            raise PolicyViolation("Approved currency does not match milestone currency")

    def ensure_can_create_invoice(
        self,
        run: DealRun,
        milestone: TrustMilestone,
    ) -> None:
        if not any(item.milestone_id == milestone.milestone_id for item in run.approvals):
            raise PolicyViolation("Invoice creation requires a matching human approval")
        self.validate_milestone(milestone)
        if milestone.status != MilestoneStatus.READY:
            raise PolicyViolation(
                f"Milestone status {milestone.status.value} cannot create an invoice"
            )

    def ensure_payment_can_complete(
        self,
        milestone: TrustMilestone,
    ) -> None:
        if milestone.status != MilestoneStatus.PAID:
            raise PolicyViolation("Only a PAID milestone can be completed")

