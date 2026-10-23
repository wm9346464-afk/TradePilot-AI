"""Structured agent proposal and restricted tool governance tests."""

import pytest

from modules.trustloop.agent.tools import (
    ToolRequestDenied,
    build_default_tool_registry,
)
from modules.trustloop.models import ToolRequest
from modules.trustloop.service import build_demo_service, demo_deal_input
from modules.trustloop.agent.planner import RuleBasedPlanner


def test_rule_based_planner_returns_structured_proposal():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, "合同金额：1000元。缺少质量标准和付款条件。")

    proposal = RuleBasedPlanner().propose(run, invoice_currency="USD")

    assert proposal.planner_type == "RULE_BASED"
    assert proposal.recommended_ladder
    assert proposal.needs_human_approval is True
    assert {item.tool_name for item in proposal.requested_tools} == {
        "create_invoice",
        "send_invoice",
    }


def test_tool_registry_denies_unknown_and_unapproved_financial_tools():
    registry = build_default_tool_registry()

    with pytest.raises(ToolRequestDenied, match="unknown tool"):
        registry.get("run_arbitrary_code")

    with pytest.raises(ToolRequestDenied, match="human approval"):
        registry.validate(
            ToolRequest(
                tool_name="create_invoice",
                arguments={"milestone_sequence": 1},
                reason="Create invoice",
            ),
            has_human_approval=False,
        )

    spec = registry.validate(
        ToolRequest(
            tool_name="create_invoice",
            arguments={"milestone_sequence": 1},
            reason="Create invoice",
        ),
        has_human_approval=True,
    )
    assert spec.risk_level.value == "FINANCIAL"


def test_service_persists_agent_proposal_and_audits_it():
    service = build_demo_service()
    run = service.run_full_demo(demo_deal_input())

    assert run.agent_proposal is not None
    assert run.agent_proposal.planner_type == "RULE_BASED"
    assert run.plan is not None
    event_types = [event.event_type for event in service.get_audit_events(run.run_id)]
    assert "AGENT_PROPOSAL_CREATED" in event_types

