"""TrustLoop v0 domain, currency and end-to-end tests."""

from decimal import Decimal

import pytest

from modules.trustloop.currency import CurrencyPolicy
from modules.trustloop.enums import DealState, MilestoneStatus
from modules.trustloop.gateways.paypal import CreateInvoiceRequest
from modules.trustloop.gateways.fake_paypal import FakePayPalGateway
from modules.trustloop.fx import FixtureFxRateProvider, HttpFxRateProvider
from modules.trustloop.money import money
from modules.trustloop.service import build_demo_service, demo_deal_input
from modules.trustloop.state_machine import DealStateMachine, InvalidStateTransition


def test_money_uses_currency_specific_precision():
    usd = money("1234.567", "USD")
    jpy = money("1234.567", "JPY")

    assert usd.amount == Decimal("1234.57")
    assert jpy.amount == Decimal("1235")
    assert usd.to_paypal_string() == "1234.57"
    assert jpy.to_paypal_string() == "1235"

    with pytest.raises(ValueError, match="float"):
        money(1.5, "USD")


def test_currency_policy_rejects_cross_border_cny():
    policy = CurrencyPolicy(fallback_currency="USD")
    decision = policy.validate_invoice_currency(
        "CNY",
        merchant_supported={"USD", "EUR", "CNY"},
        seller_country="CN",
        buyer_country="SG",
    )

    assert decision.status == "IN_COUNTRY_ONLY"
    assert decision.invoice_currency == "USD"
    assert decision.allowed is False


def test_state_machine_rejects_skipped_steps():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())

    with pytest.raises(InvalidStateTransition):
        DealStateMachine().transition(run, "APPROVED")


def test_fake_gateway_is_idempotent_and_simulates_payment():
    gateway = FakePayPalGateway()
    request = CreateInvoiceRequest(
        buyer_name="Buyer",
        buyer_email="buyer@example.com",
        amount=money("500", "USD"),
        idempotency_key="same-key-0001",
    )
    first = gateway.create_invoice(request)
    second = gateway.create_invoice(request)

    assert first.invoice_id == second.invoice_id
    assert first.status == "DRAFT"

    sent = gateway.send_invoice(first.invoice_id)
    paid = gateway.simulate_payment(first.invoice_id)
    paid_again = gateway.simulate_payment(first.invoice_id)

    assert sent.status == "SENT"
    assert paid.status == "PAID"
    assert paid.transaction_id == paid_again.transaction_id


def test_full_demo_flow_creates_audited_passport():
    service = build_demo_service()
    run = service.run_full_demo(demo_deal_input())

    assert run.state == DealState.PASSPORT_ISSUED
    assert run.risk is not None
    assert run.agent_proposal is not None
    assert run.agent_proposal.needs_human_approval is True
    assert run.plan is not None
    assert run.passport is not None
    assert run.passport.settlements
    assert run.passport.settlements[0].status == "PAID"
    assert len(run.passport.settlements) == 3
    assert run.plan.settlement_plan.invoice_currency == "USD"
    assert run.plan.settlement_plan.fx_snapshot is not None
    assert run.plan.settlement_plan.fx_snapshot.mode == "DEMO_FIXTURE"
    assert all(item.status == MilestoneStatus.PAID for item in run.plan.milestones)
    assert service.verify_audit_chain(run.run_id) is True
    assert len(service.get_audit_events(run.run_id)) >= 8


class FakeFxResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_http_fx_provider_records_reference_snapshot():
    provider = HttpFxRateProvider(
        get=lambda *args, **kwargs: FakeFxResponse(
            {"date": "2026-10-22", "rates": {"CNY": 6.6743}}
        )
    )
    snapshot = provider.get_rate("USD", "CNY")

    assert snapshot.mode == "LIVE"
    assert snapshot.source == "Frankfurter reference rate"
    assert snapshot.rate == Decimal("6.6743")
    assert snapshot.observed_at.date().isoformat() == "2026-10-22"


def test_http_fx_provider_falls_back_on_failure():
    def fail(*args, **kwargs):
        raise RuntimeError("network down")

    provider = HttpFxRateProvider(
        fallback=FixtureFxRateProvider(),
        get=fail,
    )
    snapshot = provider.get_rate("USD", "CNY")

    assert snapshot.mode == "DEMO_FIXTURE"
    assert "fallback" in snapshot.source.lower()


def test_refresh_payment_advances_only_when_paypal_reports_paid():
    service = build_demo_service()
    run = service.start_case(demo_deal_input())
    run = service.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    run = service.approve_plan(run.run_id)
    run = service.create_invoice(run.run_id)
    run = service.send_invoice(run.run_id)
    milestone = service._find_milestone(run, None)

    pending = service.refresh_payment(run.run_id)
    assert pending.state == DealState.AWAITING_PAYMENT
    assert milestone.status == MilestoneStatus.AWAITING_PAYMENT

    service.paypal_gateway.simulate_payment(milestone.invoice_id)
    paid = service.refresh_payment(run.run_id)

    assert paid.state == DealState.PAYMENT_CONFIRMED
    assert milestone.status == MilestoneStatus.PAID
    assert milestone.payment_id is not None

