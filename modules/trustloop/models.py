"""Typed domain models for the TrustLoop workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .currency import normalize_currency_code
from .enums import (
    DealState,
    MilestoneStatus,
    RiskDecision,
    RiskSeverity,
    RiskType,
    RunMode,
)
from .fx import FxSnapshot
from .money import Money


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BuyerProfile(StrictModel):
    buyer_id: str = Field(default_factory=lambda: f"BUY-{uuid4().hex[:10].upper()}")
    name: str
    email: str
    country_code: str


class SellerProfile(StrictModel):
    seller_id: str = Field(default_factory=lambda: f"SELL-{uuid4().hex[:10].upper()}")
    name: str
    country_code: str
    supported_currencies: list[str] = Field(default_factory=lambda: ["USD", "EUR"])

    @field_validator("supported_currencies")
    @classmethod
    def normalize_currencies(cls, values: list[str]) -> list[str]:
        return [normalize_currency_code(value) for value in values]


class DealInput(StrictModel):
    buyer_name: str
    buyer_email: str
    buyer_country: str
    seller_name: str = "TradePilot Demo Seller"
    seller_country: str = "CN"
    supported_currencies: list[str] = Field(default_factory=lambda: ["USD", "EUR"])
    product_name: str
    quantity: Decimal
    quantity_unit: str = "t"
    contract_amount: Decimal
    contract_currency: str = "CNY"
    requested_credit_days: int = Field(default=0, ge=0, le=365)
    mode: RunMode = RunMode.DEMO

    @field_validator("quantity", "contract_amount", mode="before")
    @classmethod
    def reject_float_money_inputs(cls, value):
        if isinstance(value, float):
            raise ValueError("Use Decimal or string for quantities and amounts")
        return value

    @field_validator("contract_currency")
    @classmethod
    def normalize_contract_currency(cls, value: str) -> str:
        return normalize_currency_code(value)

    @field_validator("supported_currencies")
    @classmethod
    def normalize_supported_currencies(cls, values: list[str]) -> list[str]:
        return [normalize_currency_code(value) for value in values]


class DealCase(StrictModel):
    deal_id: str = Field(default_factory=lambda: f"DEAL-{uuid4().hex[:12].upper()}")
    buyer: BuyerProfile
    seller: SellerProfile
    product_name: str
    quantity: Decimal
    quantity_unit: str
    contract_value: Money
    requested_credit_days: int
    mode: RunMode
    created_at: datetime = Field(default_factory=utc_now)


class RiskItem(StrictModel):
    type: RiskType
    severity: RiskSeverity
    original: str
    suggestion: str
    description: str
    evidence_quote: str | None = None


class RiskAssessment(StrictModel):
    issues: list[RiskItem] = Field(default_factory=list)
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    decision: RiskDecision = RiskDecision.REVIEW
    contract_hash: str
    mode_code: str = "RULE_ONLY"
    assessed_at: datetime = Field(default_factory=utc_now)


class ProposedMilestone(StrictModel):
    name: str
    purpose: str
    amount: Money
    invoice_currency: str
    unlock_condition: str

    @field_validator("invoice_currency")
    @classmethod
    def normalize_invoice_currency(cls, value: str) -> str:
        return normalize_currency_code(value)


class ToolRequest(StrictModel):
    tool_name: str
    arguments: dict = Field(default_factory=dict)
    reason: str


class AgentProposal(StrictModel):
    decision: Literal["PROCEED", "REVIEW", "BLOCK"]
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    recommended_ladder: list[ProposedMilestone]
    requested_tools: list[ToolRequest] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    needs_human_approval: bool = True
    approval_reason: str = "Financial actions require explicit human approval"
    planner_type: Literal["RULE_BASED", "LLM"] = "RULE_BASED"
    confidence: Decimal = Field(default=Decimal("0.70"), ge=0, le=1)


class SettlementPlan(StrictModel):
    contract_money: Money
    invoice_currency: str
    conversion_required: bool
    fx_snapshot: FxSnapshot | None = None

    @field_validator("invoice_currency")
    @classmethod
    def normalize_invoice_currency(cls, value: str) -> str:
        return normalize_currency_code(value)


class StatusEvent(StrictModel):
    label: str
    at: datetime = Field(default_factory=utc_now)
    detail: str = ""


class TrustMilestone(StrictModel):
    milestone_id: str = Field(default_factory=lambda: f"MS-{uuid4().hex[:10].upper()}")
    sequence: int = Field(ge=1)
    name: str
    purpose: str
    amount: Money
    invoice_currency: str
    unlock_condition: str
    status: MilestoneStatus = MilestoneStatus.LOCKED
    invoice_id: str | None = None
    payment_id: str | None = None
    history: list[StatusEvent] = Field(default_factory=list)

    @field_validator("invoice_currency")
    @classmethod
    def normalize_invoice_currency(cls, value: str) -> str:
        return normalize_currency_code(value)


class ActionPlan(StrictModel):
    plan_id: str = Field(default_factory=lambda: f"PLAN-{uuid4().hex[:10].upper()}")
    proposed_by: Literal["AGENT", "RULE_ENGINE", "HUMAN"] = "RULE_ENGINE"
    settlement_plan: SettlementPlan
    milestones: list[TrustMilestone]
    rationale: str
    risks_addressed: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    approval_reason: str = "Financial action requires explicit human approval"
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalRecord(StrictModel):
    approval_id: str = Field(default_factory=lambda: f"APR-{uuid4().hex[:10].upper()}")
    plan_id: str
    milestone_id: str
    approved_amount: Money
    approved_currency: str
    approved_by: str
    approved_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None


class PaymentResult(StrictModel):
    success: bool
    backend: Literal["REST", "MCP", "FAKE"] = "FAKE"
    mode: Literal["LIVE_SANDBOX", "DEMO", "REPLAY"] = "DEMO"
    invoice_id: str | None = None
    invoice_number: str | None = None
    status: str | None = None
    raw_status: str | None = None
    amount: Money | None = None
    payment_url: str | None = None
    paid_at: datetime | None = None
    transaction_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False
    raw_response: dict | None = None


class SettlementRecord(StrictModel):
    milestone_id: str
    invoice_id: str
    invoice_number: str
    amount: Money
    status: str
    paid_at: datetime | None = None
    transaction_id: str | None = None


class TrustPassport(StrictModel):
    passport_id: str = Field(default_factory=lambda: f"TP-{uuid4().hex[:12].upper()}")
    schema_version: str = "1.0"
    run_id: str
    deal_id: str
    buyer_id: str
    seller_id: str
    contract_hash: str
    risk_summary: RiskAssessment
    ladder: list[TrustMilestone]
    settlements: list[SettlementRecord]
    approvals: list[ApprovalRecord]
    fx_snapshots: list[FxSnapshot] = Field(default_factory=list)
    audit_head_hash: str
    issued_at: datetime = Field(default_factory=utc_now)
    mode: RunMode


class DealRun(StrictModel):
    run_id: str = Field(default_factory=lambda: f"RUN-{uuid4().hex[:12].upper()}")
    state: DealState = DealState.INTAKE
    deal: DealCase
    risk: RiskAssessment | None = None
    agent_proposal: AgentProposal | None = None
    plan: ActionPlan | None = None
    active_milestone_id: str | None = None
    invoices: list[PaymentResult] = Field(default_factory=list)
    approvals: list[ApprovalRecord] = Field(default_factory=list)
    passport: TrustPassport | None = None
    updated_at: datetime = Field(default_factory=utc_now)

