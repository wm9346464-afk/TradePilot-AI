"""Streamlit AppTest coverage for the v0 Deal Room."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules.trustloop.service import build_runtime_service, demo_deal_input
from modules.contract_checker import SAMPLE_CONTRACT


APP_PATH = Path(__file__).resolve().parent.parent / "app_trustloop.py"


def test_trustloop_deal_room_runs_full_demo(monkeypatch):
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH)).run(timeout=30)
    assert not at.exception

    button = next(item for item in at.button if item.label == "Review deal & build ladder")
    button.click().run(timeout=30)

    assert not at.exception

    for stage in (1, 2, 3):
        approval = next(
            item for item in at.button if item.label.startswith(f"Approve stage {stage}")
        )
        approval.click().run(timeout=30)
        assert not at.exception

    assert any("Trust Passport" in item.value for item in at.markdown)
    assert any("PAID" in item.value for item in at.markdown)
    assert any(metric.label == "Invoice currency" and metric.value == "USD" for metric in at.metric)
    assert not any(
        item.label == "Simulate Buyer / Seller negotiation" for item in at.button
    )
    download_labels = {
        item.proto.label for item in at.get("download_button")
    }
    assert download_labels == {
        "Download Trust Passport JSON",
        "Download Printable Passport HTML",
        "Download Replay Bundle JSON",
    }
    assert any(
        "Set TRUSTLOOP_STORE_PATH" in item.value for item in at.caption
    )

    next(
        item for item in at.button if item.label == "Reset current demo"
    ).click().run(timeout=30)
    assert not at.exception
    assert not at.metric
    assert any(
        item.label == "Review deal & build ladder" for item in at.button
    )


def test_trustloop_access_password_gate(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "sandbox-demo-pass")
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")

    at = AppTest.from_file(str(APP_PATH)).run(timeout=30)
    assert not at.exception
    assert not any(item.label == "Review deal & build ladder" for item in at.button)

    password = next(item for item in at.text_input if item.label == "Access password")
    password.set_value("sandbox-demo-pass").run(timeout=30)

    assert not at.exception
    assert any(item.label == "Review deal & build ladder" for item in at.button)


def test_trustloop_ui_can_build_a_eur_settlement_plan(monkeypatch):
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH)).run(timeout=30)
    assert not at.exception

    currency = next(
        item for item in at.selectbox if item.label == "PayPal settlement currency"
    )
    currency.set_value("EUR").run(timeout=30)
    next(
        item for item in at.button if item.label == "Review deal & build ladder"
    ).click().run(timeout=30)

    assert not at.exception
    assert any(
        metric.label == "Invoice currency" and metric.value == "EUR"
        for metric in at.metric
    )


def test_trustloop_ui_switches_to_chinese(monkeypatch):
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH)).run(timeout=30)
    language = next(item for item in at.radio if item.label == "Language / 语言")
    language.set_value("zh").run(timeout=30)

    assert not at.exception
    assert any(item.label == "审查交易并生成信任阶梯" for item in at.button)
    assert any(item.label == "PayPal 结算币种" for item in at.selectbox)


def test_resume_approved_stage_works_after_fake_gateway_restart(monkeypatch, tmp_path):
    database = tmp_path / "resume-stage.db"
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    run = service.approve_plan(run.run_id)
    run = service.create_invoice(run.run_id)

    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH))
    at.query_params["run_id"] = run.run_id
    at.run(timeout=30)
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


def test_refresh_payment_status_handles_pending_then_paid(monkeypatch, tmp_path):
    database = tmp_path / "refresh-payment.db"
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    run = service.approve_plan(run.run_id)
    run = service.create_invoice(run.run_id)
    run = service.send_invoice(run.run_id)

    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH))
    at.query_params["run_id"] = run.run_id
    at.run(timeout=30)

    next(
        item for item in at.button if item.label == "Refresh PayPal payment status"
    ).click().run(timeout=30)
    assert not at.exception
    assert not at.error
    assert any(
        metric.label == "Paid milestones" and metric.value == "0/3"
        for metric in at.metric
    )

    loaded_service = at.session_state["trustloop_service"]
    loaded_run = at.session_state["trustloop_run"]
    invoice_id = loaded_run.plan.milestones[0].invoice_id
    loaded_service.paypal_gateway.simulate_payment(invoice_id)
    next(
        item for item in at.button if item.label == "Refresh PayPal payment status"
    ).click().run(timeout=30)

    assert not at.exception
    assert not at.error
    assert any(
        item.label == "Approve stage 2 & simulate PayPal" for item in at.button
    )


def test_resumed_run_displays_persisted_negotiation(monkeypatch, tmp_path):
    database = tmp_path / "negotiation-resume.db"
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )
    run = service.start_case(demo_deal_input())
    run = service.review_contract(run.run_id, SAMPLE_CONTRACT)
    run = service.propose_plan(run.run_id)
    service.simulate_negotiation(run.run_id)

    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH))
    at.query_params["run_id"] = run.run_id
    at.run(timeout=30)

    assert not at.exception
    assert any("Negotiation result:" in item.value for item in at.markdown)
    assert any(
        "Buyer / Seller negotiation turns" in item.label for item in at.expander
    )


def test_switching_runs_does_not_reuse_previous_negotiation(monkeypatch, tmp_path):
    database = tmp_path / "switch-runs.db"
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )
    first = service.start_case(demo_deal_input())
    first = service.review_contract(first.run_id, SAMPLE_CONTRACT)
    first = service.propose_plan(first.run_id)
    service.simulate_negotiation(first.run_id)
    second = service.start_case(demo_deal_input())
    second = service.review_contract(second.run_id, SAMPLE_CONTRACT)
    second = service.propose_plan(second.run_id)

    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH))
    at.query_params["run_id"] = first.run_id
    at.run(timeout=30)
    assert any("Negotiation result:" in item.value for item in at.markdown)

    saved_run = next(
        item for item in at.text_input if item.label == "Open saved run by ID"
    )
    saved_run.set_value(second.run_id).run(timeout=30)
    next(
        item for item in at.button if item.label == "Resume saved run"
    ).click().run(timeout=30)

    assert not at.exception
    assert not any("Negotiation result:" in item.value for item in at.markdown)


def test_public_passport_verification_uses_trusted_store(monkeypatch, tmp_path):
    database = tmp_path / "trustloop.db"
    signing_key = "test-passport-signing-key-32-chars-minimum"
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
        passport_signing_key=signing_key,
    )
    completed = service.run_full_demo(demo_deal_input())
    assert completed.passport is not None

    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_PASSPORT_SIGNING_KEY", signing_key)
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH)).run(timeout=30)
    assert not at.exception

    passport_input = next(
        item for item in at.text_input if item.label == "Verify Passport ID"
    )
    passport_input.set_value(completed.passport.passport_id).run(timeout=30)
    verification_button = next(
        item for item in at.button if item.label == "Open public verification"
    )
    verification_button.click().run(timeout=30)

    assert not at.exception
    assert any("VALID" in item.value for item in at.success)
    assert any(
        metric.label == "Paid milestones" and metric.value == "3"
        for metric in at.metric
    )


def test_public_verification_missing_passport_keeps_a_way_back(monkeypatch, tmp_path):
    database = tmp_path / "missing-passport.db"
    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH))
    at.query_params["verify"] = "TP-NOT-FOUND"
    at.run(timeout=30)

    assert any(
        "Passport not found" in item.value for item in at.error
    )
    assert any(
        item.label == "Open the Deal Room" for item in at.button
    )


def test_public_verification_store_failure_is_handled(monkeypatch, tmp_path):
    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(tmp_path))
    monkeypatch.setenv("TRUSTLOOP_USE_LLM", "false")
    monkeypatch.setenv("TRUSTLOOP_PAYPAL_BACKEND", "fake")
    at = AppTest.from_file(str(APP_PATH))
    at.query_params["verify"] = "TP-ANY"
    at.run(timeout=30)

    assert not at.exception
    assert any(
        "trusted store could not be opened" in item.value for item in at.error
    )
    assert any(
        item.label == "Open the Deal Room" for item in at.button
    )

