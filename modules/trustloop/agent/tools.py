"""Restricted tool registry for agentic actions."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict

from ..models import ToolRequest


class ToolRisk(str, Enum):
    READ = "READ"
    WRITE = "WRITE"
    FINANCIAL = "FINANCIAL"


class ToolSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    risk_level: ToolRisk
    requires_approval: bool
    required_arguments: tuple[str, ...] = ()


class ToolRequestDenied(ValueError):
    pass


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        spec = self._specs.get(name)
        if not spec:
            raise ToolRequestDenied(f"Agent requested an unknown tool: {name}")
        return spec

    def validate(self, request: ToolRequest, *, has_human_approval: bool = False) -> ToolSpec:
        spec = self.get(request.tool_name)
        missing = [key for key in spec.required_arguments if key not in request.arguments]
        if missing:
            raise ToolRequestDenied(
                f"Tool {spec.name} missing required arguments: {missing}"
            )
        if spec.requires_approval and not has_human_approval:
            raise ToolRequestDenied(
                f"Tool {spec.name} requires explicit human approval before execution"
            )
        return spec

    def validate_proposal(
        self,
        requests: list[ToolRequest],
        *,
        needs_human_approval: bool,
    ) -> list[ToolSpec]:
        validated: list[ToolSpec] = []
        for request in requests:
            spec = self.get(request.tool_name)
            missing = [key for key in spec.required_arguments if key not in request.arguments]
            if missing:
                raise ToolRequestDenied(
                    f"Tool {spec.name} missing required arguments: {missing}"
                )
            if spec.requires_approval and not needs_human_approval:
                raise ToolRequestDenied(
                    f"Tool {spec.name} requires the proposal to request human approval"
                )
            validated.append(spec)
        return validated

    def list_tools(self) -> list[ToolSpec]:
        return sorted(self._specs.values(), key=lambda item: item.name)


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="get_deal_context",
            description="Read the current deal, risk and currency context.",
            risk_level=ToolRisk.READ,
            requires_approval=False,
        )
    )
    registry.register(
        ToolSpec(
            name="review_contract",
            description="Review contract text and return evidence-backed risks.",
            risk_level=ToolRisk.READ,
            requires_approval=False,
            required_arguments=("contract_text",),
        )
    )
    registry.register(
        ToolSpec(
            name="validate_currency",
            description="Validate a currency against PayPal and merchant constraints.",
            risk_level=ToolRisk.READ,
            requires_approval=False,
            required_arguments=("currency",),
        )
    )
    registry.register(
        ToolSpec(
            name="get_fx_snapshot",
            description="Read a timestamped FX snapshot for a currency pair.",
            risk_level=ToolRisk.READ,
            requires_approval=False,
            required_arguments=("base_currency", "quote_currency"),
        )
    )
    registry.register(
        ToolSpec(
            name="propose_trust_ladder",
            description="Build a staged trust payment plan.",
            risk_level=ToolRisk.READ,
            requires_approval=False,
        )
    )
    registry.register(
        ToolSpec(
            name="create_invoice",
            description="Create a draft invoice with the selected payment backend.",
            risk_level=ToolRisk.FINANCIAL,
            requires_approval=True,
            required_arguments=("milestone_sequence",),
        )
    )
    registry.register(
        ToolSpec(
            name="send_invoice",
            description="Send an approved draft invoice.",
            risk_level=ToolRisk.FINANCIAL,
            requires_approval=True,
            required_arguments=("milestone_sequence",),
        )
    )
    registry.register(
        ToolSpec(
            name="check_payment",
            description="Read the current payment status for an invoice.",
            risk_level=ToolRisk.READ,
            requires_approval=False,
            required_arguments=("invoice_id",),
        )
    )
    registry.register(
        ToolSpec(
            name="issue_passport",
            description="Issue a trust passport from verified transaction evidence.",
            risk_level=ToolRisk.WRITE,
            requires_approval=False,
        )
    )
    return registry

