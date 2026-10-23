"""TrustLoop orchestration service for the deterministic v0 workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import os

from modules.contract_checker import SAMPLE_CONTRACT

from .agent.planner import RuleBasedPlanner
from .agent.llm_planner import LLMPlanner
from .agent.tools import ToolRegistry, build_default_tool_registry
from .audit import AuditEvent, AuditLog
from .currency import CurrencyPolicy
from .enums import DealState, MilestoneStatus, RunMode
from .fx import build_fx_provider
from .models import (
    ActionPlan,
    ApprovalRecord,
    BuyerProfile,
    DealCase,
    DealInput,
    DealRun,
    PaymentResult,
    SellerProfile,
    SettlementPlan,
    SettlementRecord,
    StatusEvent,
    TrustMilestone,
    TrustPassport,
)
from .money import Money, money
from .policy import PolicyEngine, PolicyViolation
from .state_machine import DealStateMachine


class TrustLoopService:
    def __init__(
        self,
        *,
        contract_gateway,
        paypal_gateway,
        fx_provider,
        policy_engine: PolicyEngine,
        currency_policy: CurrencyPolicy | None = None,
        state_machine: DealStateMachine | None = None,
        agent_planner=None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.contract_gateway = contract_gateway
        self.paypal_gateway = paypal_gateway
        self.fx_provider = fx_provider
        self.policy_engine = policy_engine
        self.currency_policy = currency_policy or CurrencyPolicy()
        self.state_machine = state_machine or DealStateMachine()
        self.agent_planner = agent_planner or RuleBasedPlanner()
        self.tool_registry = tool_registry or build_default_tool_registry()
        self._runs: dict[str, DealRun] = {}
        self._audits: dict[str, AuditLog] = {}

    def start_case(self, deal_input: DealInput) -> DealRun:
        deal = DealCase(
            buyer=BuyerProfile(
                name=deal_input.buyer_name,
                email=deal_input.buyer_email,
                country_code=deal_input.buyer_country,
            ),
            seller=SellerProfile(
                name=deal_input.seller_name,
                country_code=deal_input.seller_country,
                supported_currencies=deal_input.supported_currencies,
            ),
            product_name=deal_input.product_name,
            quantity=deal_input.quantity,
            quantity_unit=deal_input.quantity_unit,
            contract_value=money(
                deal_input.contract_amount,
                deal_input.contract_currency,
            ),
            requested_credit_days=deal_input.requested_credit_days,
            mode=deal_input.mode,
        )
        run = DealRun(deal=deal)
        self._runs[run.run_id] = run
        self._audits[run.run_id] = AuditLog(run.run_id)
        self._audit(
            run.run_id,
            "CASE_CREATED",
            "SYSTEM",
            "TrustLoopService",
            {
                "deal_id": deal.deal_id,
                "contract_value": deal.contract_value.model_dump(mode="json"),
                "mode": deal.mode.value,
            },
        )
        run = self.state_machine.transition(run, "CASE_SUBMITTED")
        self._save(run)
        return run

    def review_contract(
        self,
        run_id: str,
        contract_text: str,
        *,
        use_ai: bool = False,
        force_demo: bool = False,
        lang: str = "zh",
    ) -> DealRun:
        run = self._require_run(run_id, DealState.CONTRACT_REVIEW)
        risk = self.contract_gateway.review(
            contract_text,
            use_ai=use_ai,
            force_demo=force_demo,
            lang=lang,
        )
        run = run.model_copy(update={"risk": risk})
        run = self.state_machine.transition(run, "REVIEW_COMPLETED")
        self._audit(
            run_id,
            "CONTRACT_REVIEWED",
            "SYSTEM",
            "ContractReviewGateway",
            {
                "contract_hash": risk.contract_hash,
                "decision": risk.decision.value,
                "high_count": risk.high_count,
                "medium_count": risk.medium_count,
                "low_count": risk.low_count,
                "mode_code": risk.mode_code,
            },
        )
        self._save(run)
        return run

    def propose_plan(
        self,
        run_id: str,
        *,
        invoice_currency: str = "USD",
        sample_amount: Decimal | int | str = "500",
        trial_amount: Decimal | int | str = "5000",
        deposit_amount: Decimal | int | str = "10000",
    ) -> DealRun:
        run = self._require_run(run_id, DealState.RISK_ASSESSED)
        decision = self.currency_policy.validate_invoice_currency(
            invoice_currency,
            run.deal.seller.supported_currencies,
            run.deal.seller.country_code,
            run.deal.buyer.country_code,
        )
        if decision.status in {"UNSUPPORTED", "INVALID_CURRENCY"}:
            raise PolicyViolation(decision.reason)
        selected_currency = decision.invoice_currency or invoice_currency

        fx_snapshot = None
        conversion_required = selected_currency != run.deal.contract_value.currency
        if conversion_required:
            fx_snapshot = self.fx_provider.get_rate(
                run.deal.contract_value.currency,
                selected_currency,
            )

        proposal = self.agent_planner.propose(
            run,
            invoice_currency=selected_currency,
            sample_amount=sample_amount,
            trial_amount=trial_amount,
            deposit_amount=deposit_amount,
        )
        self.policy_engine.validate_agent_proposal(proposal)
        self.tool_registry.validate_proposal(
            proposal.requested_tools,
            needs_human_approval=proposal.needs_human_approval,
        )
        milestones = [
            TrustMilestone(
                sequence=index,
                name=item.name,
                purpose=item.purpose,
                amount=item.amount,
                invoice_currency=item.invoice_currency,
                unlock_condition=item.unlock_condition,
            )
            for index, item in enumerate(proposal.recommended_ladder, start=1)
        ]
        milestones[0] = milestones[0].model_copy(update={"status": MilestoneStatus.READY})

        plan = ActionPlan(
            proposed_by="AGENT" if proposal.planner_type == "LLM" else "RULE_ENGINE",
            settlement_plan=SettlementPlan(
                contract_money=run.deal.contract_value,
                invoice_currency=selected_currency,
                conversion_required=conversion_required,
                fx_snapshot=fx_snapshot,
            ),
            milestones=milestones,
            rationale=proposal.rationale,
            risks_addressed=[
                issue.description for issue in (run.risk.issues if run.risk else [])
            ],
            evidence_refs=[
                issue.evidence_quote
                for issue in (run.risk.issues if run.risk else [])
                if issue.evidence_quote
            ],
            requires_human_approval=True,
        )
        self.policy_engine.validate_plan(plan)
        run = run.model_copy(
            update={
                "agent_proposal": proposal,
                "plan": plan,
                "active_milestone_id": milestones[0].milestone_id,
            }
        )
        run = self.state_machine.transition(run, "PLAN_CREATED")
        run = self.state_machine.transition(run, "APPROVAL_REQUESTED")
        self._audit(
            run_id,
            "AGENT_PROPOSAL_CREATED",
            "AGENT",
            "RuleBasedPlanner",
            {
                "decision": proposal.decision,
                "planner_type": proposal.planner_type,
                "confidence": str(proposal.confidence),
                "tools": [item.tool_name for item in proposal.requested_tools],
                "evidence_refs": proposal.evidence_refs,
                "warnings": proposal.warnings,
            },
        )
        self._audit(
            run_id,
            "PLAN_PROPOSED",
            "SYSTEM",
            "RuleBasedPlanner",
            {
                "plan_id": plan.plan_id,
                "contract_currency": run.deal.contract_value.currency,
                "invoice_currency": selected_currency,
                "currency_status": decision.status,
                "fx_mode": fx_snapshot.mode if fx_snapshot else None,
                "milestones": [
                    {
                        "milestone_id": item.milestone_id,
                        "amount": item.amount.model_dump(mode="json"),
                    }
                    for item in milestones
                ],
            },
        )
        self._save(run)
        return run

    def approve_plan(
        self,
        run_id: str,
        *,
        milestone_id: str | None = None,
        approved_by: str = "Seller Operator",
    ) -> DealRun:
        run = self._require_run(run_id, DealState.AWAITING_APPROVAL)
        if not run.plan:
            raise PolicyViolation("No plan is available for approval")
        milestone = self._find_milestone(run, milestone_id)
        approval = ApprovalRecord(
            plan_id=run.plan.plan_id,
            milestone_id=milestone.milestone_id,
            approved_amount=milestone.amount,
            approved_currency=milestone.invoice_currency,
            approved_by=approved_by,
        )
        self.policy_engine.validate_approval(run, milestone, approval)
        run = run.model_copy(update={"approvals": [*run.approvals, approval]})
        run = self.state_machine.transition(run, "APPROVED")
        self._audit(
            run_id,
            "PLAN_APPROVED",
            "HUMAN",
            approved_by,
            {
                "approval_id": approval.approval_id,
                "plan_id": approval.plan_id,
                "milestone_id": approval.milestone_id,
                "amount": approval.approved_amount.model_dump(mode="json"),
            },
        )
        self._save(run)
        return run

    def create_invoice(
        self,
        run_id: str,
        *,
        milestone_id: str | None = None,
    ) -> DealRun:
        run = self._require_run(run_id, DealState.INVOICE_CREATING)
        milestone = self._find_milestone(run, milestone_id)
        self.policy_engine.ensure_can_create_invoice(run, milestone)
        from .gateways.paypal import CreateInvoiceRequest

        request = CreateInvoiceRequest(
            buyer_name=run.deal.buyer.name,
            buyer_email=run.deal.buyer.email,
            amount=milestone.amount,
            description=f"{milestone.name}: {milestone.purpose}",
            contract_id=run.deal.deal_id,
            payment_type="trust_milestone",
            idempotency_key=f"{run_id}:{milestone.milestone_id}:invoice",
        )
        invoice = self.paypal_gateway.create_invoice(request)
        if not invoice.success:
            raise PolicyViolation(invoice.error_message or "Invoice creation failed")

        milestone.status = MilestoneStatus.INVOICE_DRAFT
        milestone.invoice_id = invoice.invoice_id
        milestone.history.append(StatusEvent(label="INVOICE_CREATED", detail=invoice.invoice_id or ""))
        run = run.model_copy(update={"invoices": [*run.invoices, invoice]})
        run = self.state_machine.transition(run, "INVOICE_CREATED")
        self._audit(
            run_id,
            "INVOICE_CREATED",
            "PAYPAL",
            self.paypal_gateway.backend_name,
            {
                "invoice_id": invoice.invoice_id,
                "amount": milestone.amount.model_dump(mode="json"),
                "status": invoice.status,
            },
        )
        self._save(run)
        return run

    def send_invoice(
        self,
        run_id: str,
        *,
        milestone_id: str | None = None,
    ) -> DealRun:
        run = self._require_run(run_id, DealState.INVOICE_CREATED)
        milestone = self._find_milestone(run, milestone_id)
        if not milestone.invoice_id:
            raise PolicyViolation("Milestone has no invoice_id")
        invoice = self.paypal_gateway.send_invoice(milestone.invoice_id)
        if not invoice.success:
            raise PolicyViolation(invoice.error_message or "Invoice send failed")
        milestone.status = MilestoneStatus.AWAITING_PAYMENT
        milestone.history.append(
            StatusEvent(label="INVOICE_SENT", detail=invoice.status or "")
        )
        run = self.state_machine.transition(run, "INVOICE_SENT")
        self._audit(
            run_id,
            "INVOICE_SENT",
            "PAYPAL",
            self.paypal_gateway.backend_name,
            {"invoice_id": milestone.invoice_id, "status": invoice.status},
        )
        self._save(run)
        return run

    def simulate_payment(
        self,
        run_id: str,
        *,
        milestone_id: str | None = None,
    ) -> DealRun:
        run = self._require_run(run_id, DealState.AWAITING_PAYMENT)
        milestone = self._find_milestone(run, milestone_id)
        if not milestone.invoice_id:
            raise PolicyViolation("Milestone has no invoice_id")
        simulator = getattr(self.paypal_gateway, "simulate_payment", None)
        if not callable(simulator):
            raise PolicyViolation("The configured PayPal gateway cannot simulate payment")
        invoice = simulator(milestone.invoice_id)
        if not invoice.success or invoice.status != "PAID":
            raise PolicyViolation(invoice.error_message or "Simulated payment failed")
        milestone.status = MilestoneStatus.PAID
        milestone.payment_id = invoice.transaction_id
        milestone.history.append(
            StatusEvent(label="PAID", detail=invoice.transaction_id or "")
        )
        run = self.state_machine.transition(run, "PAYMENT_CONFIRMED")
        self._audit(
            run_id,
            "PAYMENT_CONFIRMED",
            "PAYPAL",
            self.paypal_gateway.backend_name,
            {
                "invoice_id": milestone.invoice_id,
                "transaction_id": invoice.transaction_id,
                "amount": milestone.amount.model_dump(mode="json"),
                "simulated": True,
            },
        )
        self._save(run)
        return run

    def refresh_payment(
        self,
        run_id: str,
        *,
        milestone_id: str | None = None,
    ) -> DealRun:
        """Refresh the active invoice and advance only on a verified PAID status."""
        run = self._require_run(run_id, DealState.AWAITING_PAYMENT)
        milestone = self._find_milestone(run, milestone_id)
        if not milestone.invoice_id:
            raise PolicyViolation("Milestone has no invoice_id")

        invoice = self.paypal_gateway.get_invoice(milestone.invoice_id)
        if not invoice.success:
            raise PolicyViolation(
                invoice.error_message or "PayPal payment status lookup failed"
            )

        updated_invoices = list(run.invoices)
        for index, item in enumerate(updated_invoices):
            if item.invoice_id == milestone.invoice_id:
                updated_invoices[index] = invoice
                break
        else:
            updated_invoices.append(invoice)
        run = run.model_copy(update={"invoices": updated_invoices})

        if invoice.status == "PAID":
            milestone.status = MilestoneStatus.PAID
            milestone.payment_id = invoice.transaction_id
            milestone.history.append(
                StatusEvent(label="PAID", detail=invoice.transaction_id or "")
            )
            run = self.state_machine.transition(run, "PAYMENT_CONFIRMED")
            self._audit(
                run_id,
                "PAYMENT_CONFIRMED",
                "PAYPAL",
                self.paypal_gateway.backend_name,
                {
                    "invoice_id": milestone.invoice_id,
                    "transaction_id": invoice.transaction_id,
                    "amount": milestone.amount.model_dump(mode="json"),
                    "raw_status": invoice.raw_status,
                },
            )
        else:
            self._audit(
                run_id,
                "PAYMENT_STATUS_CHECKED",
                "PAYPAL",
                self.paypal_gateway.backend_name,
                {
                    "invoice_id": milestone.invoice_id,
                    "status": invoice.status,
                    "raw_status": invoice.raw_status,
                },
            )

        self._save(run)
        return run

    def complete_milestone(
        self,
        run_id: str,
        *,
        milestone_id: str | None = None,
    ) -> DealRun:
        run = self._require_run(run_id, DealState.PAYMENT_CONFIRMED)
        milestone = self._find_milestone(run, milestone_id)
        self.policy_engine.ensure_payment_can_complete(milestone)
        run = self.state_machine.transition(run, "MILESTONE_COMPLETED")
        next_sequence = milestone.sequence + 1
        next_ready_id = None
        for item in run.plan.milestones if run.plan else []:
            if item.sequence == next_sequence and item.status == MilestoneStatus.LOCKED:
                item.status = MilestoneStatus.READY
                next_ready_id = item.milestone_id
                break
        run = run.model_copy(update={"active_milestone_id": next_ready_id})
        self._audit(
            run_id,
            "MILESTONE_COMPLETED",
            "SYSTEM",
            "TrustLoopService",
            {
                "milestone_id": milestone.milestone_id,
                "next_milestone_unlocked": next_sequence,
            },
        )
        self._save(run)
        return run

    def request_next_milestone(self, run_id: str) -> DealRun:
        """Return to approval for the next READY milestone."""
        run = self._require_run(run_id, DealState.MILESTONE_COMPLETED)
        next_milestone = next(
            (
                item
                for item in (run.plan.milestones if run.plan else [])
                if item.status == MilestoneStatus.READY
            ),
            None,
        )
        if next_milestone is None:
            raise PolicyViolation("No READY milestone remains; issue the passport instead")
        run = run.model_copy(update={"active_milestone_id": next_milestone.milestone_id})
        run = self.state_machine.transition(run, "NEXT_MILESTONE_REQUESTED")
        self._audit(
            run_id,
            "NEXT_MILESTONE_REQUESTED",
            "SYSTEM",
            "TrustLoopService",
            {
                "milestone_id": next_milestone.milestone_id,
                "sequence": next_milestone.sequence,
                "amount": next_milestone.amount.model_dump(mode="json"),
            },
        )
        self._save(run)
        return run

    def issue_passport(self, run_id: str) -> TrustPassport:
        run = self._require_run(run_id, DealState.MILESTONE_COMPLETED)
        if not run.risk or not run.plan:
            raise PolicyViolation("Risk assessment and plan are required for a passport")
        settlements = []
        for milestone in run.plan.milestones:
            if milestone.invoice_id and milestone.status == MilestoneStatus.PAID:
                invoice = next(
                    (item for item in run.invoices if item.invoice_id == milestone.invoice_id),
                    None,
                )
                settlements.append(
                    SettlementRecord(
                        milestone_id=milestone.milestone_id,
                        invoice_id=milestone.invoice_id,
                        invoice_number=invoice.invoice_number if invoice and invoice.invoice_number else "",
                        amount=milestone.amount,
                        status="PAID",
                        paid_at=invoice.paid_at if invoice else None,
                        transaction_id=milestone.payment_id,
                    )
                )
        if not settlements:
            raise PolicyViolation("No paid settlement is available for a passport")
        fx_snapshots = (
            [run.plan.settlement_plan.fx_snapshot]
            if run.plan.settlement_plan.fx_snapshot
            else []
        )
        passport = TrustPassport(
            deal_id=run.deal.deal_id,
            buyer_id=run.deal.buyer.buyer_id,
            seller_id=run.deal.seller.seller_id,
            contract_hash=run.risk.contract_hash,
            risk_summary=run.risk,
            ladder=run.plan.milestones,
            settlements=settlements,
            approvals=run.approvals,
            fx_snapshots=fx_snapshots,
            audit_head_hash=self._audits[run_id].head_hash,
            mode=run.deal.mode,
        )
        run = run.model_copy(update={"passport": passport})
        run = self.state_machine.transition(run, "PASSPORT_ISSUED")
        run = run.model_copy(update={"active_milestone_id": None})
        self._audit(
            run_id,
            "PASSPORT_ISSUED",
            "SYSTEM",
            "TrustPassportService",
            {
                "passport_id": passport.passport_id,
                "audit_head_hash": passport.audit_head_hash,
            },
        )
        passport = passport.model_copy(
            update={"audit_head_hash": self._audits[run_id].head_hash}
        )
        run = run.model_copy(update={"passport": passport})
        self._save(run)
        return passport

    def run_full_demo(self, deal_input: DealInput) -> DealRun:
        run = self.start_case(deal_input)
        run = self.review_contract(run.run_id, SAMPLE_CONTRACT, use_ai=False)
        run = self.propose_plan(run.run_id, invoice_currency="USD")
        while run.plan and any(
            item.status != MilestoneStatus.PAID for item in run.plan.milestones
        ):
            run = self.approve_plan(run.run_id)
            run = self.create_invoice(run.run_id)
            run = self.send_invoice(run.run_id)
            run = self.simulate_payment(run.run_id)
            run = self.complete_milestone(run.run_id)
            if run.plan and any(
                item.status != MilestoneStatus.PAID for item in run.plan.milestones
            ):
                run = self.request_next_milestone(run.run_id)
        self.issue_passport(run.run_id)
        return self._runs[run.run_id]

    def get_run(self, run_id: str) -> DealRun:
        if run_id not in self._runs:
            raise KeyError(f"Unknown run_id: {run_id}")
        return self._runs[run_id]

    def get_audit_events(self, run_id: str) -> list[AuditEvent]:
        if run_id not in self._audits:
            raise KeyError(f"Unknown run_id: {run_id}")
        return list(self._audits[run_id].events)

    def verify_audit_chain(self, run_id: str) -> bool:
        return self._audits[run_id].verify_chain()

    def _new_milestone(
        self,
        sequence: int,
        name: str,
        purpose: str,
        amount: Decimal | int | str,
        currency: str,
        unlock_condition: str,
    ) -> TrustMilestone:
        return TrustMilestone(
            sequence=sequence,
            name=name,
            purpose=purpose,
            amount=money(amount, currency),
            invoice_currency=currency,
            unlock_condition=unlock_condition,
        )

    def _find_milestone(
        self,
        run: DealRun,
        milestone_id: str | None,
    ) -> TrustMilestone:
        if not run.plan or not run.plan.milestones:
            raise PolicyViolation("No milestones are available")
        if milestone_id:
            for item in run.plan.milestones:
                if item.milestone_id == milestone_id:
                    return item
            raise PolicyViolation(f"Unknown milestone: {milestone_id}")
        if run.active_milestone_id:
            for item in run.plan.milestones:
                if item.milestone_id == run.active_milestone_id:
                    return item
            raise PolicyViolation(f"Unknown active milestone: {run.active_milestone_id}")
        ready = [item for item in run.plan.milestones if item.status == MilestoneStatus.READY]
        if ready:
            return ready[0]
        return run.plan.milestones[0]

    def _require_run(self, run_id: str, expected_state: DealState) -> DealRun:
        run = self.get_run(run_id)
        if run.state != expected_state:
            raise PolicyViolation(
                f"Run {run_id} is in {run.state.value}, expected {expected_state.value}"
            )
        return run

    def _audit(
        self,
        run_id: str,
        event_type: str,
        actor_type: str,
        actor_id: str,
        payload: dict,
    ) -> None:
        self._audits[run_id].append(event_type, actor_type, actor_id, payload)

    def _save(self, run: DealRun) -> None:
        run = run.model_copy(update={"updated_at": datetime.now(timezone.utc)})
        self._runs[run.run_id] = run


def demo_deal_input() -> DealInput:
    return DealInput(
        buyer_name="Northbridge Infrastructure Pte. Ltd.",
        buyer_email=os.getenv("PAYPAL_SANDBOX_BUYER_EMAIL", "buyer@example.com"),
        buyer_country="SG",
        seller_name="TradePilot Demo Steel Seller",
        seller_country="CN",
        supported_currencies=["USD", "EUR"],
        product_name="HRB400E rebar",
        quantity=Decimal("500"),
        quantity_unit="t",
        contract_amount=Decimal("1825000"),
        contract_currency="CNY",
        requested_credit_days=30,
        mode=RunMode.DEMO,
    )


def build_demo_service() -> TrustLoopService:
    return build_runtime_service(paypal_backend="fake", use_llm=False)


def build_runtime_service(
    *,
    paypal_backend: str = "fake",
    use_llm: bool = True,
) -> TrustLoopService:
    from .gateways.contracts import ExistingContractReviewGateway
    from .gateways.factory import build_paypal_gateway
    from .policy import PolicyConfig

    fx_provider = build_fx_provider()
    policy = PolicyEngine(PolicyConfig(), fx_provider)
    planner = LLMPlanner() if use_llm else RuleBasedPlanner()
    return TrustLoopService(
        contract_gateway=ExistingContractReviewGateway(),
        paypal_gateway=build_paypal_gateway(paypal_backend),
        fx_provider=fx_provider,
        policy_engine=policy,
        currency_policy=CurrencyPolicy(fallback_currency="USD"),
        agent_planner=planner,
    )

