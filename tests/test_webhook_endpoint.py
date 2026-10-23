"""Verified PayPal webhook processing and local HTTP endpoint tests."""

import json
import threading
import urllib.error
import urllib.request

from modules.contract_checker import SAMPLE_CONTRACT
from modules.trustloop.enums import DealState
from modules.trustloop.service import build_runtime_service, demo_deal_input
from modules.trustloop.webhook_events import process_verified_paypal_event
from webhook_server import build_server


def _awaiting_payment_run(tmp_path, *, name="webhook.db"):
    database = tmp_path / name
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id, invoice_currency="USD")
    run = service.approve_plan(run.run_id)
    run = service.create_invoice(run.run_id)
    run = service.send_invoice(run.run_id)
    invoice_id = run.plan.milestones[0].invoice_id
    assert invoice_id
    service.paypal_gateway.simulate_payment(invoice_id)
    return service, run, invoice_id


def _paid_event(invoice_id):
    return {
        "id": "WH-TEST-1",
        "event_type": "INVOICING.INVOICE.PAID",
        "resource_type": "invoice",
        "resource": {
            "id": invoice_id,
            "status": "PAID",
            "amount": {"currency_code": "USD", "value": "500.00"},
        },
    }


class FakeVerifier:
    def __init__(self, result=True):
        self.result = result
        self.calls = 0

    def verify_signature(self, headers, body):
        self.calls += 1
        return self.result


def test_verified_webhook_requeries_paypal_and_unlocks_next_stage(tmp_path):
    service, run, invoice_id = _awaiting_payment_run(tmp_path)

    result = process_verified_paypal_event(_paid_event(invoice_id), service)
    repeated = process_verified_paypal_event(_paid_event(invoice_id), service)
    current = service.get_run(run.run_id)

    assert result.status == "processed"
    assert result.processed is True
    assert current.state == DealState.AWAITING_APPROVAL
    assert current.plan.milestones[0].status.value == "PAID"
    assert current.plan.milestones[1].status.value == "READY"
    assert repeated.status == "already_processed"
    assert repeated.processed is False


def test_webhook_resumes_a_milestone_completed_before_unlock(tmp_path):
    service, run, invoice_id = _awaiting_payment_run(tmp_path, name="recover-webhook.db")
    service.paypal_gateway.simulate_payment(invoice_id)
    service.refresh_payment(run.run_id)
    service.complete_milestone(run.run_id)

    result = process_verified_paypal_event(_paid_event(invoice_id), service)
    current = service.get_run(run.run_id)

    assert result.status == "processed"
    assert result.processed is True
    assert current.state == DealState.AWAITING_APPROVAL
    assert current.plan.milestones[1].status.value == "READY"


def test_invoice_index_resumes_a_webhook_target_in_a_new_service(tmp_path):
    service, run, invoice_id = _awaiting_payment_run(tmp_path)
    resumed = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(service.store.path),
    )

    found = resumed.find_run_by_invoice(invoice_id)

    assert found is not None
    assert found.run_id == run.run_id


def test_http_endpoint_rejects_unverified_payload_without_advancing(tmp_path):
    service, run, invoice_id = _awaiting_payment_run(tmp_path, name="rejected.db")
    verifier = FakeVerifier(result=False)
    server = build_server(
        host="127.0.0.1",
        port=0,
        verifier=verifier,
        service_factory=lambda: service,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps(_paid_event(invoice_id)).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/paypal/webhook",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5):
            raise AssertionError("unverified webhook should have been rejected")
    except urllib.error.HTTPError as exc:
        assert exc.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert verifier.calls == 1
    assert service.get_run(run.run_id).state == DealState.AWAITING_PAYMENT


def test_http_endpoint_health_does_not_require_webhook_secrets():
    server = build_server(
        host="127.0.0.1",
        port=0,
        verifier=FakeVerifier(),
        service_factory=lambda: None,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{server.server_address[1]}/health",
            timeout=5,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "ok"
        assert payload["service"] == "tradepilot-trustloop-webhook"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_http_endpoint_returns_structured_error_when_service_init_fails():
    def fail_factory():
        raise RuntimeError("database unavailable")

    server = build_server(
        host="127.0.0.1",
        port=0,
        verifier=FakeVerifier(),
        service_factory=fail_factory,
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps(_paid_event("FAKE-INV-1")).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_address[1]}/paypal/webhook",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5):
            raise AssertionError("service initialization failure should return HTTP 500")
    except urllib.error.HTTPError as exc:
        assert exc.code == 500
        payload = json.loads(exc.read().decode("utf-8"))
        assert payload["error"] == "service_initialization_failed"
        assert payload["error_type"] == "RuntimeError"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
