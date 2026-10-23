"""Printable Trust Passport export tests."""

from modules.trustloop.passport_export import render_passport_html
from modules.trustloop.enums import MilestoneStatus
from modules.trustloop.service import build_demo_service, demo_deal_input


def test_passport_html_contains_verified_evidence():
    service = build_demo_service()
    run = service.run_full_demo(demo_deal_input())
    document = render_passport_html(run.passport)

    assert "TradePilot Trust Passport" in document
    assert run.passport.passport_id in document
    assert run.passport.audit_head_hash in document
    assert "Payments" in document
    assert "Human approvals" in document
    assert "Agent decision evidence" in document
    assert "Issuer signature" in document
    assert "not a legal opinion" in document


def test_passport_contains_agent_and_negotiation_evidence():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    service.simulate_negotiation(run.run_id)
    while run.plan and any(
        item.status != MilestoneStatus.PAID for item in run.plan.milestones
    ):
        run = service.approve_plan(run.run_id)
        run = service.create_invoice(run.run_id)
        run = service.send_invoice(run.run_id)
        run = service.simulate_payment(run.run_id)
        run = service.complete_milestone(run.run_id)
        if any(
            item.status != MilestoneStatus.PAID for item in run.plan.milestones
        ):
            run = service.request_next_milestone(run.run_id)
    service.issue_passport(run.run_id)
    run = service.get_run(run.run_id)

    assert run.passport is not None
    action_types = [item.action_type for item in run.passport.agent_actions]
    assert "PLAN_PROPOSAL" in action_types
    assert "NEGOTIATION" in action_types

