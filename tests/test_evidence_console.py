"""Evidence console projections: milestone/event rows, exposure and frames."""

from modules.contract_checker import SAMPLE_CONTRACT
from modules.trustloop.agent.executor import AgentToolExecutor
from modules.trustloop.evidence import (
    EVENT_COLUMNS,
    MILESTONE_COLUMNS,
    event_rows,
    exposure_bar_html,
    exposure_summary,
    milestone_rows,
    to_frame,
)
from modules.trustloop.service import build_demo_service, demo_deal_input


def _planned_run():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    return service, run


def _completed_run():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    for _ in range(3):
        run = service.approve_plan(run.run_id)
        run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
        run = service.simulate_payment(run.run_id)
        run = service.advance_after_payment(run.run_id)
    return service, run


def test_milestone_rows_are_empty_before_a_plan_exists():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())

    assert milestone_rows(run) == []
    frame = to_frame(milestone_rows(run), MILESTONE_COLUMNS)
    assert list(frame.columns) == list(MILESTONE_COLUMNS)


def test_milestone_rows_join_approvals_and_invoices():
    service, run = _planned_run()
    rows = milestone_rows(run)

    assert [row["stage"] for row in rows] == [1, 2, 3]
    assert rows[0]["status"] == "READY"
    assert rows[0]["amount"] == "USD 500.00"
    assert rows[0]["approved"] == ""  # nothing approved yet
    assert rows[0]["approved_by"] == ""

    run = service.approve_plan(run.run_id)
    run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
    rows = milestone_rows(run)
    assert rows[0]["approved"] == "USD 500.00"
    assert rows[0]["approved_by"] == "Seller Operator"
    assert rows[0]["invoice"].startswith("TP-DEMO-")
    assert rows[0]["transaction"] == ""  # paid later, not at invoice time

    run = service.simulate_payment(run.run_id)
    rows = milestone_rows(run)
    assert rows[0]["transaction"].startswith("FAKE-TXN-")


def test_exposure_summary_tracks_settlement():
    service, run = _planned_run()
    exposure = exposure_summary(run)
    assert exposure["planned_label"] == "USD 14,500.00"
    assert exposure["settled_label"] == "USD 0.00"
    assert exposure["approved_label"] == "USD 0.00"
    assert exposure["outstanding_label"] == "USD 14,500.00"

    service, run = _completed_run()
    exposure = exposure_summary(run)
    assert exposure["settled_label"] == "USD 14,500.00"
    assert exposure["approved_label"] == "USD 14,500.00"
    assert exposure["outstanding_label"] == "USD 0.00"


def test_exposure_bar_covers_the_whole_width():
    service, run = _completed_run()
    html = exposure_bar_html(exposure_summary(run))
    assert "tp-exp-settled" in html and 'width:100.0%' in html

    service, run = _planned_run()
    html = exposure_bar_html(exposure_summary(run))
    assert "tp-exp-open" in html and "width:100.0%" in html


def test_event_rows_expose_the_hash_chain():
    service, run = _completed_run()
    events = service.get_audit_events(run.run_id)
    rows = event_rows(events)

    assert len(rows) == len(events)
    assert rows[0]["sequence"] == 1
    assert rows[0]["event_type"] == "CASE_CREATED"
    assert len(rows[0]["hash"]) == 16
    assert rows[0]["at"].endswith("Z")
    assert any(row["event_type"] == "PASSPORT_ISSUED" for row in rows)
    assert list(to_frame(rows, EVENT_COLUMNS).columns) == list(EVENT_COLUMNS)
