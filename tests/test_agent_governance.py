"""Structured agent proposal and restricted tool governance tests."""

import pytest

from modules.trustloop.agent.tools import (
    ToolRequestDenied,
    build_default_tool_registry,
)
from modules.trustloop.models import ToolRequest
from modules.trustloop.service import build_demo_service, demo_deal_input
from modules.trustloop.agent.planner import RuleBasedPlanner
from modules.trustloop.agent.negotiation import negotiate
from modules.trustloop.agent.executor import AgentToolExecutionError, AgentToolExecutor
from modules.trustloop.enums import DealState
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


def test_agent_executor_runs_requested_invoice_tools_in_order():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    run = service.approve_plan(run.run_id)

    run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)

    assert run.state == DealState.AWAITING_PAYMENT
    assert run.plan.milestones[0].invoice_id is not None


def test_agent_executor_rejects_missing_send_tool():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    run.agent_proposal.requested_tools = [
        item for item in run.agent_proposal.requested_tools if item.tool_name != "send_invoice"
    ]
    service._runs[run.run_id] = run
    run = service.approve_plan(run.run_id)

    with pytest.raises(AgentToolExecutionError, match="send_invoice"):
        AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)


def test_service_enforces_required_tools_when_planner_omits_them():
    class NoToolsPlanner:
        def propose(self, run, **kwargs):
            proposal = RuleBasedPlanner().propose(run, **kwargs)
            return proposal.model_copy(
                update={"requested_tools": [], "warnings": []}
            )

    service = build_demo_service()
    service.agent_planner = NoToolsPlanner()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")

    assert [item.tool_name for item in run.agent_proposal.requested_tools] == [
        "create_invoice",
        "send_invoice",
    ]
    assert any("enforced" in warning for warning in run.agent_proposal.warnings)


def test_buyer_seller_negotiation_reaches_milestone_agreement():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")

    result = negotiate(run)

    assert result.agreed is True
    assert result.final_initial_payment is not None
    assert result.final_credit_days == 0
    assert len(result.turns) >= 3
    assert result.turns[-1].accepted is True


def test_buyer_seller_negotiation_rejects_no_overlap():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")

    result = negotiate(run, buyer_max_initial_payment=100)

    assert result.agreed is False
    assert result.final_initial_payment is None
    assert "No agreement" in result.summary


def test_service_audits_negotiation_result():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")

    result = service.simulate_negotiation(run.run_id)

    assert result.agreed is True
    assert service.get_negotiation(run.run_id) == result
    assert any(
        event.event_type == "NEGOTIATION_COMPLETED"
        for event in service.get_audit_events(run.run_id)
    )

