"""SQLite persistence and cross-service resume tests."""

import copy
import threading
import time

import pytest

from modules.trustloop.audit import AuditEvent
from modules.trustloop.enums import DealState
from modules.trustloop.gateways.fake_paypal import FakePayPalGateway
from modules.trustloop.policy import PolicyViolation
from modules.trustloop.service import build_runtime_service, demo_deal_input
from modules.trustloop.store import SQLiteRunStore, StoreConflict


def _service(store_path):
    return build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(store_path),
    )


def test_completed_run_resumes_from_sqlite_in_a_new_service(tmp_path):
    database = tmp_path / "trustloop.db"
    first = _service(database)
    completed = first.run_full_demo(demo_deal_input())

    second = _service(database)
    resumed = second.get_run(completed.run_id)

    assert resumed.state == DealState.PASSPORT_ISSUED
    assert resumed.passport is not None
    assert second.verify_audit_chain(resumed.run_id) is True
    assert second.verify_trust_passport(resumed.run_id).valid is True

    by_passport = second.find_run_by_passport(resumed.passport.passport_id)
    assert by_passport is not None
    assert by_passport.run_id == resumed.run_id


def test_negotiation_result_is_persisted(tmp_path):
    database = tmp_path / "trustloop.db"
    first = _service(database)
    run = first.start_case(demo_deal_input())
    run = first.review_contract(run.run_id, __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT)
    run = first.propose_plan(run.run_id, invoice_currency="USD")
    result = first.simulate_negotiation(run.run_id)

    second = _service(database)
    restored = second.get_negotiation(run.run_id)

    assert restored is not None
    assert restored.agreed is result.agreed
    assert restored.summary == result.summary
    assert second.verify_audit_chain(run.run_id) is True


def test_audit_store_refuses_different_content_at_existing_sequence(tmp_path):
    store = SQLiteRunStore(tmp_path / "trustloop.db")
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store=store,
    )
    run = service.start_case(demo_deal_input())
    original = store.load_audit_events(run.run_id)[0]
    conflicting = AuditEvent.model_validate(
        {
            **original.model_dump(mode="json"),
            "actor_id": "TamperedActor",
            "event_hash": "f" * 64,
        }
    )

    with pytest.raises(StoreConflict):
        store.append_audit_event(conflicting)


def test_sqlite_connections_close_so_the_database_can_be_removed(tmp_path):
    database = tmp_path / "removable.db"
    store = SQLiteRunStore(database)
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store=store,
    )
    run = service.start_case(demo_deal_input())
    assert store.load_run(run.run_id) is not None

    database.unlink()

    assert database.exists() is False


def test_operation_lock_is_owned_and_released_atomically(tmp_path):
    store = SQLiteRunStore(tmp_path / "locks.db")

    assert store.acquire_operation_lock("run:create", "owner-1", 300) is True
    assert store.acquire_operation_lock("run:create", "owner-2", 300) is False
    store.release_operation_lock("run:create", "owner-1")
    assert store.acquire_operation_lock("run:create", "owner-2", 300) is True


def test_duplicate_create_invoice_is_blocked_before_external_call(tmp_path):
    class SlowGateway(FakePayPalGateway):
        def __init__(self):
            super().__init__()
            self.started = threading.Event()
            self.calls = 0

        def create_invoice(self, request):
            self.calls += 1
            self.started.set()
            time.sleep(0.2)
            return super().create_invoice(request)

    database = tmp_path / "duplicate-create.db"
    seed = _service(database)
    run = seed.start_case(demo_deal_input())
    run = seed.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = seed.propose_plan(run.run_id)
    seed.approve_plan(run.run_id)

    first = _service(database)
    second = _service(database)
    first_gateway = SlowGateway()
    second_gateway = SlowGateway()
    first.paypal_gateway = first_gateway
    second.paypal_gateway = second_gateway
    errors = []

    def create_once():
        try:
            first.create_invoice(run.run_id)
        except Exception as exc:  # pragma: no cover - failure assertion below
            errors.append(exc)

    thread = threading.Thread(target=create_once)
    thread.start()
    assert first_gateway.started.wait(timeout=2)

    with pytest.raises(PolicyViolation, match="already in progress"):
        second.create_invoice(run.run_id)

    thread.join(timeout=5)
    assert errors == []
    assert first_gateway.calls == 1
    assert second_gateway.calls == 0
    persisted = _service(database).get_run(run.run_id)
    assert persisted.state == DealState.INVOICE_CREATED


def test_fake_paypal_invoice_state_is_rehydrated_after_restart(tmp_path):
    database = tmp_path / "fake-resume.db"
    first = _service(database)
    run = first.start_case(demo_deal_input())
    run = first.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = first.propose_plan(run.run_id)
    run = first.approve_plan(run.run_id)
    run = first.create_invoice(run.run_id)
    invoice_id = run.plan.milestones[0].invoice_id
    assert invoice_id

    second = _service(database)
    resumed = second.get_run(run.run_id)
    resumed = second.send_invoice(resumed.run_id)
    resumed = second.simulate_payment(resumed.run_id)
    resumed = second.complete_milestone(resumed.run_id)

    assert resumed.plan.milestones[0].invoice_id == invoice_id
    assert resumed.plan.milestones[0].status.value == "PAID"


def test_stale_session_cannot_overwrite_a_newer_payment_state(tmp_path):
    database = tmp_path / "stale-session.db"
    seed = _service(database)
    run = seed.start_case(demo_deal_input())
    run = seed.review_contract(
        run.run_id,
        __import__("modules.contract_checker", fromlist=["SAMPLE_CONTRACT"]).SAMPLE_CONTRACT,
    )
    run = seed.propose_plan(run.run_id)
    run = seed.approve_plan(run.run_id)
    run = seed.create_invoice(run.run_id)
    run = seed.send_invoice(run.run_id)

    first = _service(database)
    stale = _service(database)
    first_run = first.get_run(run.run_id)
    stale.get_run(run.run_id)
    first.paypal_gateway.simulate_payment(first_run.plan.milestones[0].invoice_id)
    first.refresh_payment(run.run_id)
    first.advance_after_payment(run.run_id)

    with pytest.raises(StoreConflict):
        stale.refresh_payment(run.run_id)

    latest = stale.reload_run(run.run_id)
    assert latest.state == DealState.AWAITING_APPROVAL
    assert latest.plan.milestones[0].status.value == "PAID"
    persisted = _service(database).get_run(run.run_id)
    assert persisted.state == DealState.AWAITING_APPROVAL


def test_replay_bundle_is_read_only_and_cannot_overwrite_live_store(tmp_path):
    database = tmp_path / "replay-safe.db"
    service = _service(database)
    run = service.run_full_demo(demo_deal_input())
    bundle = service.export_run_bundle(run.run_id)
    tampered_bundle = copy.deepcopy(bundle)
    tampered_bundle["run"]["deal"]["product_name"] = "TAMPERED REPLAY PRODUCT"

    replay_service = _service(database)
    replay_service.restore_run_bundle(tampered_bundle)

    persisted = _service(database).get_run(run.run_id)
    assert persisted.deal.product_name == "HRB400E rebar"
