"""Crash-point and reopened-payment recovery tests."""

from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest

from modules.contract_checker import SAMPLE_CONTRACT
from modules.trustloop.enums import DealState
from modules.trustloop.models import PaymentResult
from modules.trustloop.policy import PolicyViolation
from modules.trustloop.service import build_runtime_service, demo_deal_input


APP_PATH = Path(__file__).resolve().parent.parent / "app_trustloop.py"


def _service(database):
    return build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )


def _awaiting_payment(database):
    service = _service(database)
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    run = service.approve_plan(run.run_id)
    run = service.create_invoice(run.run_id)
    return service, service.send_invoice(run.run_id)


def _configure_app(monkeypatch, database):
    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    monkeypatch.setenv("FX_PROVIDER", "fixture")


class PaidQueryGateway:
    backend_name = "FAKE"

    def __init__(self, *, amount, invoice_id):
        self.amount = amount
        self.invoice_id = invoice_id

    def get_invoice(self, invoice_id):
        return PaymentResult(
            success=True,
            backend="FAKE",
            mode="DEMO",
            invoice_id=invoice_id,
            invoice_number="PAID-AFTER-REOPEN",
            status="PAID",
            raw_status="PAID",
            amount=self.amount,
            transaction_id="TXN-AFTER-REOPEN",
        )


def test_reopened_pending_payment_is_not_reported_as_paid(tmp_path):
    database = tmp_path / "pending.db"
    _service_first, run = _awaiting_payment(database)
    reopened = _service(database)

    pending = reopened.refresh_payment(run.run_id)

    assert pending.state == DealState.AWAITING_PAYMENT
    assert pending.passport is None
    assert pending.plan.milestones[0].status.value != "PAID"


def test_external_payment_is_not_success_until_reopened_status_is_queried(tmp_path):
    database = tmp_path / "paid-before-refresh.db"
    _service_first, run = _awaiting_payment(database)
    reopened = _service(database)
    pending = reopened.get_run(run.run_id)
    invoice_id = pending.plan.milestones[0].invoice_id
    reopened.paypal_gateway = PaidQueryGateway(
        amount=pending.plan.milestones[0].amount,
        invoice_id=invoice_id,
    )

    assert pending.state == DealState.AWAITING_PAYMENT
    assert pending.passport is None
    assert pending.plan.milestones[0].status.value != "PAID"

    confirmed = reopened.refresh_payment(run.run_id)

    assert confirmed.state == DealState.PAYMENT_CONFIRMED
    assert confirmed.plan.milestones[0].status.value == "PAID"
    assert confirmed.passport is None


def test_paid_amount_mismatch_cannot_unlock_the_milestone(tmp_path):
    database = tmp_path / "amount-mismatch.db"
    _service_first, run = _awaiting_payment(database)
    reopened = _service(database)
    pending = reopened.get_run(run.run_id)
    invoice_id = pending.plan.milestones[0].invoice_id
    wrong_amount = pending.plan.milestones[0].amount.model_copy(
        update={"amount": "1.00"}
    )
    reopened.paypal_gateway = PaidQueryGateway(
        amount=wrong_amount,
        invoice_id=invoice_id,
    )

    with pytest.raises(PolicyViolation, match="does not match"):
        reopened.refresh_payment(run.run_id)

    unchanged = reopened.get_run(run.run_id)
    assert unchanged.state == DealState.AWAITING_PAYMENT
    assert unchanged.plan.milestones[0].status.value != "PAID"


def test_successful_invoice_response_without_id_is_rejected():
    class MissingInvoiceIdGateway:
        backend_name = "FAKE"

        def create_invoice(self, request):
            return PaymentResult(
                success=True,
                backend="FAKE",
                mode="DEMO",
                invoice_id=None,
                status="DRAFT",
                amount=request.amount,
            )

    service = build_runtime_service(paypal_backend="fake", use_llm=False)
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    run = service.approve_plan(run.run_id)
    service.paypal_gateway = MissingInvoiceIdGateway()

    with pytest.raises(PolicyViolation, match="no invoice ID"):
        service.create_invoice(run.run_id)


def test_invoice_creation_retry_reuses_the_same_idempotency_key():
    class FlakyGateway:
        backend_name = "FAKE"

        def __init__(self):
            self.keys = []

        def create_invoice(self, request):
            self.keys.append(request.idempotency_key)
            if len(self.keys) == 1:
                raise RuntimeError("temporary failure")
            return PaymentResult(
                success=True,
                backend="FAKE",
                mode="DEMO",
                invoice_id="FAKE-RETRY-INV",
                invoice_number="FAKE-RETRY-NO",
                status="DRAFT",
                amount=request.amount,
            )

    service = build_runtime_service(paypal_backend="fake", use_llm=False)
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    run = service.approve_plan(run.run_id)
    gateway = FlakyGateway()
    service.paypal_gateway = gateway

    with pytest.raises(RuntimeError, match="temporary failure"):
        service.create_invoice(run.run_id)
    created = service.create_invoice(run.run_id)

    assert created.state == DealState.INVOICE_CREATED
    assert len(gateway.keys) == 2
    assert gateway.keys[0] == gateway.keys[1]


def test_verified_payment_intermediate_states_can_resume(tmp_path):
    database = tmp_path / "confirmed.db"
    service, run = _awaiting_payment(database)
    invoice_id = run.plan.milestones[0].invoice_id
    service.paypal_gateway.simulate_payment(invoice_id)
    confirmed = service.refresh_payment(run.run_id)
    assert confirmed.state == DealState.PAYMENT_CONFIRMED

    reopened = _service(database)
    advanced = reopened.advance_after_payment(run.run_id)

    assert advanced.state == DealState.AWAITING_APPROVAL
    assert advanced.plan.milestones[0].status.value == "PAID"
    assert advanced.plan.milestones[1].status.value == "READY"


def test_milestone_completed_without_unlock_can_resume(tmp_path):
    database = tmp_path / "completed.db"
    service, run = _awaiting_payment(database)
    invoice_id = run.plan.milestones[0].invoice_id
    service.paypal_gateway.simulate_payment(invoice_id)
    service.refresh_payment(run.run_id)
    completed = service.complete_milestone(run.run_id)
    assert completed.state == DealState.MILESTONE_COMPLETED

    reopened = _service(database)
    with pytest.raises(PolicyViolation, match="All milestones must be PAID"):
        reopened.issue_passport(run.run_id)
    advanced = reopened.advance_after_payment(run.run_id)

    assert advanced.state == DealState.AWAITING_APPROVAL
    assert advanced.active_milestone_id == advanced.plan.milestones[1].milestone_id


def test_final_milestone_completed_without_passport_can_issue_it(tmp_path):
    database = tmp_path / "final-passport.db"
    service = _service(database)
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    for sequence in (1, 2):
        run = service.approve_plan(run.run_id)
        run = service.create_invoice(run.run_id)
        run = service.send_invoice(run.run_id)
        invoice_id = next(
            item.invoice_id
            for item in run.plan.milestones
            if item.sequence == sequence
        )
        service.paypal_gateway.simulate_payment(invoice_id)
        service.refresh_payment(run.run_id)
        run = service.complete_milestone(run.run_id)
        run = service.request_next_milestone(run.run_id)
    run = service.approve_plan(run.run_id)
    run = service.create_invoice(run.run_id)
    run = service.send_invoice(run.run_id)
    invoice_id = run.plan.milestones[2].invoice_id
    service.paypal_gateway.simulate_payment(invoice_id)
    service.refresh_payment(run.run_id)
    completed = service.complete_milestone(run.run_id)
    assert completed.state == DealState.MILESTONE_COMPLETED

    reopened = _service(database)
    issued = reopened.advance_after_payment(run.run_id)

    assert issued.state == DealState.PASSPORT_ISSUED
    assert issued.passport is not None


def test_reopened_fake_payment_can_be_simulated_from_the_ui(monkeypatch, tmp_path):
    database = tmp_path / "ui-payment.db"
    _service_first, run = _awaiting_payment(database)
    _configure_app(monkeypatch, database)

    at = AppTest.from_file(str(APP_PATH))
    at.query_params["run_id"] = run.run_id
    at.run(timeout=30)
    assert not at.exception
    assert not at.success
    assert any(
        metric.label == "Paid milestones" and metric.value == "0/3"
        for metric in at.metric
    )
    assert any(
        item.label == "Simulate demo payment" for item in at.button
    )
    assert not any(
        "Open PayPal payment page" in item.value for item in at.markdown
    )
    assert any("SENT" in item.value for item in at.markdown)
    assert not any("DRAFT" in item.value for item in at.markdown)

    next(
        item for item in at.button if item.label == "Simulate demo payment"
    ).click().run(timeout=30)

    assert not at.exception
    assert not at.error
    assert any(
        item.label == "Approve stage 2 & simulate PayPal" for item in at.button
    )
    assert any(
        metric.label == "Paid milestones" and metric.value == "1/3"
        for metric in at.metric
    )


def test_ui_recovers_payment_confirmed_and_milestone_completed(monkeypatch, tmp_path):
    for state in (DealState.PAYMENT_CONFIRMED, DealState.MILESTONE_COMPLETED):
        database = tmp_path / f"{state.value}.db"
        service, run = _awaiting_payment(database)
        invoice_id = run.plan.milestones[0].invoice_id
        service.paypal_gateway.simulate_payment(invoice_id)
        service.refresh_payment(run.run_id)
        if state == DealState.MILESTONE_COMPLETED:
            service.complete_milestone(run.run_id)
        _configure_app(monkeypatch, database)

        at = AppTest.from_file(str(APP_PATH))
        at.query_params["run_id"] = run.run_id
        at.run(timeout=30)
        assert any(
            item.label == "Finish verified payment progression" for item in at.button
        )
        next(
            item
            for item in at.button
            if item.label == "Finish verified payment progression"
        ).click().run(timeout=30)

        assert not at.exception
        assert not at.error
        assert any(
            item.label == "Approve stage 2 & simulate PayPal" for item in at.button
        )


def test_ui_recovers_invoice_creation_and_send_crash_points(monkeypatch, tmp_path):
    for state in (DealState.INVOICE_CREATING, DealState.INVOICE_CREATED):
        database = tmp_path / f"{state.value}.db"
        service = _service(database)
        run = service.start_case(demo_deal_input())
        run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
        run = service.propose_plan(run.run_id)
        run = service.approve_plan(run.run_id)
        if state == DealState.INVOICE_CREATED:
            service.create_invoice(run.run_id)
        _configure_app(monkeypatch, database)

        at = AppTest.from_file(str(APP_PATH))
        at.query_params["run_id"] = run.run_id
        at.run(timeout=30)
        assert any(
            item.label == "Resume approved stage" for item in at.button
        )
        next(
            item for item in at.button if item.label == "Resume approved stage"
        ).click().run(timeout=30)

        assert not at.exception
        assert not at.error
        assert any(
            item.label == "Approve stage 2 & simulate PayPal" for item in at.button
        )
        assert any(
            metric.label == "Paid milestones" and metric.value == "1/3"
            for metric in at.metric
        )
