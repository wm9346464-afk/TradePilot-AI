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


def test_llm_planner_falls_back_without_config(monkeypatch):
    monkeypatch.setattr(
        "modules.trustloop.agent.llm_planner.is_llm_config_valid",
        lambda: False,
    )
    run = _risk_ready_run()
    planner = LLMPlanner(post=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")))
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "RULE_BASED"
    assert any("not configured" in warning for warning in proposal.warnings)


def _llm_config_patch(monkeypatch):
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


def _proposal_payload(evidence_refs):
    return _llm_payload(
        {
            "decision": "REVIEW",
            "rationale": "Reformatted evidence should still count as contract evidence.",
            "evidence_refs": evidence_refs,
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
                },
                {
                    "tool_name": "send_invoice",
                    "arguments": {"milestone_sequence": 1},
                    "reason": "Send it after approval.",
                },
            ],
            "warnings": [],
            "needs_human_approval": True,
            "approval_reason": "Financial action.",
            "confidence": 0.8,
        }
    )


def test_llm_planner_accepts_reformatted_evidence(monkeypatch):
    """A re-spaced or re-punctuated quote is still the contract's own evidence."""

    run = _risk_ready_run()
    evidence = next(
        item.evidence_quote for item in run.risk.issues if item.evidence_quote
    )
    reformatted = f"  {evidence.replace('，', ',')}  "
    _llm_config_patch(monkeypatch)
    planner = LLMPlanner(post=lambda *args, **kwargs: FakeResponse(_proposal_payload([reformatted])))
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "LLM"
    assert proposal.evidence_refs == [evidence]


def test_llm_planner_keeps_matched_evidence_and_drops_invented(monkeypatch):
    run = _risk_ready_run()
    evidence = next(
        item.evidence_quote for item in run.risk.issues if item.evidence_quote
    )
    _llm_config_patch(monkeypatch)
    planner = LLMPlanner(
        post=lambda *args, **kwargs: FakeResponse(
            _proposal_payload([evidence, "the buyer promised to pay within 3 days"])
        )
    )
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "LLM"
    assert proposal.evidence_refs == [evidence]
    assert any("could not be matched" in warning for warning in proposal.warnings)


def test_llm_planner_keeps_three_stage_amount_envelope(monkeypatch):
    """A live model may not shrink the ladder or resize its milestones."""

    run = _risk_ready_run()
    evidence = next(
        item.evidence_quote for item in run.risk.issues if item.evidence_quote
    )
    payload = _llm_payload(
        {
            "decision": "REVIEW",
            "rationale": "Two stages are enough.",
            "evidence_refs": [evidence],
            "recommended_ladder": [
                {
                    "name": "Trial milestone",
                    "purpose": "Trial.",
                    "amount": {"amount": "5000.00", "currency": "USD"},
                    "invoice_currency": "USD",
                    "unlock_condition": "Approval.",
                },
                {
                    "name": "Deposit milestone",
                    "purpose": "Deposit.",
                    "amount": {"amount": "9000.00", "currency": "USD"},
                    "invoice_currency": "USD",
                    "unlock_condition": "Trial paid.",
                },
            ],
            "requested_tools": [],
            "warnings": [],
            "needs_human_approval": True,
            "approval_reason": "Financial action.",
            "confidence": 0.8,
        }
    )
    _llm_config_patch(monkeypatch)
    planner = LLMPlanner(post=lambda *args, **kwargs: FakeResponse(payload))
    proposal = planner.propose(
        run, invoice_currency="USD", sample_amount="500", trial_amount="5000", deposit_amount="9000"
    )

    assert proposal.planner_type == "LLM"
    assert [stage.amount.format() for stage in proposal.recommended_ladder] == [
        "USD 500.00",
        "USD 5,000.00",
        "USD 9,000.00",
    ]
    assert proposal.recommended_ladder[0].name == "Trial milestone"
    assert any("Policy envelope enforced" in warning for warning in proposal.warnings)


VISITOR_CONFIG = {
    "api_url": "https://visitor.example.invalid/v1/chat/completions",
    "model_name": "visitor-model",
    "api_key": "sk-visitor-placeholder-0123456789",
}


def test_visitor_config_drives_the_live_planner():
    """A supplied config is used without touching the deployment environment."""

    run = _risk_ready_run()
    evidence = next(
        item.evidence_quote for item in run.risk.issues if item.evidence_quote
    )
    calls = []

    def post(url, headers=None, json=None, timeout=None, **kwargs):
        calls.append((url, headers or {}))
        return FakeResponse(_proposal_payload([evidence]))

    planner = LLMPlanner(config=VISITOR_CONFIG, post=post)
    proposal = planner.propose(run, invoice_currency="USD")

    assert proposal.planner_type == "LLM"
    assert calls and calls[0][0] == VISITOR_CONFIG["api_url"]
    assert calls[0][1]["Authorization"].endswith(VISITOR_CONFIG["api_key"])


def test_visitor_config_must_be_https_and_long_enough():
    run = _risk_ready_run()

    def post(*args, **kwargs):
        raise AssertionError("network must not be called for an invalid config")

    plain_http = dict(VISITOR_CONFIG, api_url="http://visitor.example.invalid/v1")
    short_key = dict(VISITOR_CONFIG, api_key="too-short")

    for config in (plain_http, short_key):
        planner = LLMPlanner(config=config, post=post)
        proposal = planner.propose(run, invoice_currency="USD")
        assert proposal.planner_type == "RULE_BASED"
        assert any("not configured" in warning for warning in proposal.warnings)


def test_visitor_key_never_reaches_audit_passport_or_replay():
    """The visitor secret must stay in memory, out of every exported artifact."""

    from modules.trustloop.agent.executor import AgentToolExecutor
    from modules.trustloop.service import build_runtime_service

    service = build_runtime_service(paypal_backend="fake", use_llm=False)
    planner = LLMPlanner(config=VISITOR_CONFIG)
    service.agent_planner = planner

    deal = demo_deal_input()
    run = service.start_case(deal)
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    evidence = next(
        item.evidence_quote for item in run.risk.issues if item.evidence_quote
    )
    planner._post = lambda *args, **kwargs: FakeResponse(_proposal_payload([evidence]))

    run = service.propose_plan(run.run_id, invoice_currency="USD")
    assert run.agent_proposal.planner_type == "LLM"

    for _ in range(3):
        run = service.approve_plan(run.run_id)
        run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
        run = service.simulate_payment(run.run_id)
        run = service.advance_after_payment(run.run_id)

    assert run.state.value == "PASSPORT_ISSUED"
    artifacts = {
        "passport": json.dumps(run.passport.model_dump(mode="json"), ensure_ascii=False),
        "audit": json.dumps(
            [event.model_dump(mode="json") for event in service.get_audit_events(run.run_id)],
            ensure_ascii=False,
        ),
        "replay": json.dumps(service.export_run_bundle(run.run_id), ensure_ascii=False),
    }
    for name, blob in artifacts.items():
        assert VISITOR_CONFIG["api_key"] not in blob, f"api key leaked into {name}"
        assert "visitor.example.invalid" not in blob, f"endpoint leaked into {name}"
