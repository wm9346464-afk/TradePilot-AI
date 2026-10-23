"""SQLite persistence and cross-service resume tests."""

import pytest

from modules.trustloop.audit import AuditEvent
from modules.trustloop.enums import DealState
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
