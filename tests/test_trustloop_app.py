"""Streamlit AppTest coverage for the v0 Deal Room."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from modules.trustloop.service import build_runtime_service, demo_deal_input


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


def test_public_passport_verification_uses_trusted_store(monkeypatch, tmp_path):
    database = tmp_path / "trustloop.db"
    service = build_runtime_service(
        paypal_backend="fake",
        use_llm=False,
        store_path=str(database),
    )
    completed = service.run_full_demo(demo_deal_input())
    assert completed.passport is not None

    monkeypatch.setenv("TRUSTLOOP_STORE_PATH", str(database))
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

