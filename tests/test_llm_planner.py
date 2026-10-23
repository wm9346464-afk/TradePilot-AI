"""Structured LLM planner validation and fallback tests."""

import json

from modules.contract_checker import SAMPLE_CONTRACT
from modules.trustloop.agent.llm_planner import LLMPlanner
from modules.trustloop.service import build_demo_service, demo_deal_input


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _risk_ready_run():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    return service.review_contract(run.run_id, SAMPLE_CONTRACT)


def _llm_payload(content):
    return {
        "choices": [
            {"message": {"content": json.dumps(content, ensure_ascii=False)}}
        ]
    }


def test_llm_planner_returns_valid_structured_proposal(monkeypatch):
    run = _risk_ready_run()
    evidence = next(
        item.evidence_quote for item in run.risk.issues if item.evidence_quote
    )
    payload = _llm_payload(
        {
            "decision": "REVIEW",
            "rationale": "Use a staged plan because the contract has review risks.",
            "evidence_refs": [evidence],
            "recommended_ladder": [
                {
                    "name": "Sample fee",
                    "purpose": "Verify payment intent.",
                    "amount": {"amount": "500.00", "currency": "USD"},
                    "invoice_currency": "USD",
                    "unlock_condition": "Human approves the plan.",
                }
            ],
            "requested_tools": [
                {
                    "tool_name": "create_invoice",
                    "arguments": {"milestone_sequence": 1},
                    "reason": "Create the first approved invoice.",
                }
            ],
            "warnings": ["Human approval is required."],
            "needs_human_approval": True,
            "approval_reason": "Financial action.",
            "confidence": 0.8,
        }
    )
    monkeypatch.setattr(
        "modules.trustloop.agent.llm_planner.is_llm_config_valid",
        lambda: True,
    )
    monkeypatch.setattr(
        "modules.trustloop.agent.llm_planner.get_llm_config",
        lambda: {
            "api_key": "test-key-1234567890",
            "api_url": "https://example.invalid/v1/chat/completions",
            "model_name": "test-model",
        },
    )
    planner = LLMPlanner(post=lambda *args, **kwargs: FakeResponse(payload))
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "LLM"
    assert proposal.decision == "REVIEW"
    assert proposal.needs_human_approval is True
    assert proposal.recommended_ladder[0].amount.format() == "USD 500.00"


def test_llm_planner_falls_back_on_fabricated_evidence(monkeypatch):
    run = _risk_ready_run()
    payload = _llm_payload(
        {
            "decision": "PROCEED",
            "rationale": "Proceed.",
            "evidence_refs": ["evidence not in the contract"],
            "recommended_ladder": [
                {
                    "name": "Sample fee",
                    "purpose": "Verify.",
                    "amount": {"amount": "500.00", "currency": "USD"},
                    "invoice_currency": "USD",
                    "unlock_condition": "Approval.",
                }
            ],
            "requested_tools": [],
            "warnings": [],
            "needs_human_approval": True,
            "approval_reason": "Financial action.",
            "confidence": 0.8,
        }
    )
    monkeypatch.setattr(
        "modules.trustloop.agent.llm_planner.is_llm_config_valid",
        lambda: True,
    )
    monkeypatch.setattr(
        "modules.trustloop.agent.llm_planner.get_llm_config",
        lambda: {
            "api_key": "test-key-1234567890",
            "api_url": "https://example.invalid/v1/chat/completions",
            "model_name": "test-model",
        },
    )
    planner = LLMPlanner(post=lambda *args, **kwargs: FakeResponse(payload))
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "RULE_BASED"
    assert any("deterministic fallback" in warning for warning in proposal.warnings)


def test_llm_planner_falls_back_without_config():
    run = _risk_ready_run()
    planner = LLMPlanner(post=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "RULE_BASED"
    assert any("not configured" in warning for warning in proposal.warnings)

