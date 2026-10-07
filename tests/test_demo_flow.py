"""Demo-mode regression tests. These tests must not call real external APIs."""

import json
import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import modules.config as config_module
import modules.paypal_payment as paypal_payment
from modules.config import (
    get_llm_config_status,
    get_paypal_config_status,
    get_signal_config_status,
    is_placeholder,
)
from modules.contract_checker import (
    SAMPLE_CONTRACT,
    _cn_number_to_decimal,
    _extract_declared_amount,
    ai_deep_check,
    basic_text_check,
    check_contract,
    demo_check_result,
    validate_issue,
)
from modules.notification import generate_trade_workflow_notifications
from modules.paypal_payment import (
    _extract_payment_info,
    check_payment_status,
    clear_invoices_demo,
    create_and_send_invoice,
    get_invoice_demo,
    list_invoices_demo,
    retry_send_invoice,
    simulate_payment_demo,
)
from modules.signal_provider import DemoSignalProvider, RemoteSignalProvider
from scripts.generate_demo_data import CHINA_HOLIDAYS, generate_demo_data


PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWN_HOLIDAYS = {
    date(2024, 1, 1),
    date(2024, 10, 1),
    date(2025, 1, 1),
    date(2025, 10, 1),
}


def test_demo_market_data_is_reproducible_and_holiday_safe():
    first = generate_demo_data()
    second = generate_demo_data()

    assert len(first) == 374
    assert first.equals(second)
    assert first.iloc[0]["date"] == "2024-06-03"
    assert first.iloc[-1]["date"] == "2025-12-12"
    assert all(date.fromisoformat(value).weekday() < 5 for value in first["date"])
    assert not any(date.fromisoformat(value) in CHINA_HOLIDAYS for value in first["date"])
    assert not any(date.fromisoformat(value) in KNOWN_HOLIDAYS for value in first["date"])
    assert not any(value.startswith("2026-") for value in first["date"])


def test_env_example_copy_keeps_all_modules_in_demo_mode(tmp_path, monkeypatch):
    shutil.copyfile(PROJECT_ROOT / ".env.example", tmp_path / ".env")
    for name in (
        "PAYPAL_CLIENT_ID",
        "PAYPAL_CLIENT_SECRET",
        "PAYPAL_MERCHANT_EMAIL",
        "LLM_API_KEY",
        "SIGNAL_API_URL",
        "SIGNAL_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config_module, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config_module, "_ENV_LOADED", False)
    config_module.load_config()

    assert is_placeholder("your_paypal_client_id_here")
    assert is_placeholder("your_llm_api_key_here")
    assert is_placeholder("https://your-service.example.com/api")
    assert get_paypal_config_status()["state"] == "not_configured"
    assert get_llm_config_status()["state"] == "not_configured"
    assert get_signal_config_status()["state"] == "not_configured"

    monkeypatch.setenv("PAYPAL_CLIENT_ID", "your_paypal_client_id_here")
    monkeypatch.setenv("PAYPAL_CLIENT_SECRET", "your_paypal_client_secret_here")
    monkeypatch.setenv("PAYPAL_MERCHANT_EMAIL", "buyer@example.com")
    monkeypatch.setenv("LLM_API_KEY", "your_llm_api_key_here")
    assert get_paypal_config_status()["state"] == "not_configured"
    assert get_llm_config_status()["state"] == "not_configured"


def test_demo_signal_provider_returns_structured_bundle_and_chart():
    provider = DemoSignalProvider()
    bundle = provider.get_all_signals()
    chart = provider.get_price_chart_data()

    assert set(bundle) >= {"source", "degraded", "error_code", "signals", "as_of"}
    assert len(bundle["signals"]) == 3
    assert bundle["degraded"] is False
    assert len(chart["dates"]) == 180
    assert set(chart) == {
        "dates",
        "cold_roll",
        "hc_futures",
        "rb_futures",
        "rb_spot",
    }


def test_remote_signal_payload_requires_complete_three_signal_schema():
    provider = RemoteSignalProvider(api_url="http://example.invalid")
    valid = {
        key: {
            "direction": "观望",
            "triggered": "false",
            "probability": "80",
            "reasons": "one reason",
        }
        for key in ("cold_fut_rb", "cold_fut_hc", "rb_basis")
    }
    normalized = provider._normalize_remote_signals(valid)

    assert normalized["cold_fut_rb"]["triggered"] is False
    assert normalized["cold_fut_rb"]["probability"] == 0.8
    assert normalized["cold_fut_rb"]["reasons"] == ["one reason"]

    with pytest.raises(ValueError, match="INVALID_REMOTE_PAYLOAD"):
        provider._normalize_remote_signals({})
    missing_signal = dict(valid)
    missing_signal.pop("rb_basis")
    with pytest.raises(ValueError, match="INVALID_REMOTE_PAYLOAD"):
        provider._normalize_remote_signals(missing_signal)
    missing_field = json.loads(json.dumps(valid))
    missing_field["rb_basis"].pop("probability")
    with pytest.raises(ValueError, match="INVALID_REMOTE_PAYLOAD"):
        provider._normalize_remote_signals(missing_field)
    wrong_type = json.loads(json.dumps(valid))
    wrong_type["cold_fut_hc"]["triggered"] = "maybe"
    with pytest.raises(ValueError, match="INVALID_REMOTE_PAYLOAD"):
        provider._normalize_remote_signals(wrong_type)


def test_remote_invalid_response_is_explicitly_degraded_without_shared_state(monkeypatch):
    provider = RemoteSignalProvider(api_url="http://example.invalid")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {}

    monkeypatch.setattr(
        "modules.signal_provider.requests.get",
        lambda *args, **kwargs: FakeResponse(),
    )
    bundle = provider.get_all_signals()

    assert bundle["degraded"] is True
    assert bundle["error_code"] == "INVALID_REMOTE_PAYLOAD"
    assert bundle["fallback_reason"] == "远程响应格式无效"
    assert provider.fallback_reason == ""
    assert len(bundle["signals"]) == 3


def test_demo_contract_fixture_matches_sample_and_deduplicates():
    for issue in demo_check_result():
        assert issue["original"] in SAMPLE_CONTRACT

    result = check_contract(SAMPLE_CONTRACT, use_ai=False, force_demo=True)
    combined_text = " ".join(
        f"{issue.get('type', '')} {issue.get('original', '')} {issue.get('description', '')}"
        for issue in result["issues"]
    )

    assert result["mode_code"] == "DEMO_FIXTURE"
    assert "金额大写缺失" not in combined_text
    assert "订金" not in combined_text
    assert result["total_issues"] == len(result["issues"])


def test_contract_length_and_schema_validation():
    too_long = check_contract("x" * 20001, use_ai=False)
    assert too_long["mode_code"] == "INPUT_TOO_LONG"

    invalid = {
        "type": "unknown_type",
        "severity": "高",
        "original": "x",
        "suggestion": "y",
        "description": "z",
    }
    assert validate_issue(invalid) is False
    assert validate_issue(
        {
            "type": "文字错误",
            "severity": "高",
            "original": "x",
            "suggestion": "y",
            "description": "z",
        }
    )


def test_chinese_amount_parser_handles_jiao_fen_and_missing_uppercase():
    assert _cn_number_to_decimal("壹佰元伍角") == Decimal("100.5")
    assert _cn_number_to_decimal("叁拾元伍角贰分") == Decimal("30.52")
    parsed = _extract_declared_amount("100.50元（大写：壹佰元伍角）")
    assert parsed is not None
    assert parsed[0] == Decimal("100.50")
    assert parsed[1] == Decimal("100.5")

    no_mismatch = basic_text_check("100.50元（大写：壹佰元伍角）")
    assert not any(issue["type"] == "数据一致性" for issue in no_mismatch)

    missing_uppercase = basic_text_check("人民币1000元")
    assert any(issue["original"] == "金额仅有阿拉伯数字" for issue in missing_uppercase)

    valid_uppercase = basic_text_check("1000元（大写：壹仟元整）")
    assert not any(issue["original"] == "金额仅有阿拉伯数字" for issue in valid_uppercase)
    assert not any(issue["type"] == "数据一致性" for issue in valid_uppercase)


def test_ai_evidence_quote_must_exist_in_contract(monkeypatch):
    contract_text = "合同编号：GM-001。双方签定本合同，未约定质量标准。"
    raw_issues = [
        {
            "type": "文字错误",
            "severity": "中",
            "original": "签定",
            "suggestion": "签订",
            "description": "错别字",
            "evidence_quote": "签定",
        },
        {
            "type": "条款完整性",
            "severity": "高",
            "original": "缺少质量标准",
            "suggestion": "补充质量标准",
            "description": "合同没有质量标准",
            "evidence_quote": "不存在的证据",
        },
    ]

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {"message": {"content": json.dumps(raw_issues, ensure_ascii=False)}}
                ]
            }

    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setenv("LLM_API_KEY", "test-key-1234567890")
    monkeypatch.setattr("modules.contract_checker.requests.post", fake_post)
    result = ai_deep_check(contract_text)

    assert result["success"] is True
    assert len(result["issues"]) == 1
    assert result["issues"][0]["evidence_quote"] == "签定"
    assert result["filtered_count"] == 1
    assert captured["payload"]["messages"][0]["role"] == "system"
    assert "---CONTRACT START---" in captured["payload"]["messages"][1]["content"]


def test_paypal_extracts_official_and_legacy_payment_shapes():
    paid_at, transaction_id, paid_amount = _extract_payment_info(
        {
            "payments": {
                "transactions": [
                    {
                        "payment_id": "PAY-123",
                        "payment_date": "2026-10-07T10:00:00Z",
                    }
                ],
                "paid_amount": {"value": "100.50"},
            }
        }
    )
    assert paid_at == "2026-10-07T10:00:00Z"
    assert transaction_id == "PAY-123"
    assert paid_amount == "100.50"

    legacy = _extract_payment_info(
        {
            "payments": [
                {
                    "date": "2025-01-01T00:00:00Z",
                    "transaction_id": "TXN-OLD",
                    "amount": {"value": "30.52"},
                }
            ]
        }
    )
    assert legacy == ("2025-01-01T00:00:00Z", "TXN-OLD", "30.52")


def test_paypal_demo_flow_is_session_scoped_and_capped():
    clear_invoices_demo()
    invoice = create_and_send_invoice(
        payment_type="sample_fee",
        buyer_name="Demo Buyer",
        buyer_email="buyer@example.com",
        amount=150.0,
        currency="USD",
        contract_id="DEMO-001",
        use_api=False,
    )
    assert invoice["success"] is True
    assert invoice["contract_id"] == "DEMO-001"

    payment = simulate_payment_demo(invoice["invoice_id"])
    assert payment["status"] == "PAID"
    status = check_payment_status(invoice["invoice_id"], use_api=False)
    assert status["status"] == "PAID"

    for index in range(12):
        create_and_send_invoice(
            payment_type="service_fee",
            buyer_name=f"Buyer {index}",
            buyer_email=f"buyer{index}@example.com",
            amount=1.0 + index,
            currency="USD",
            use_api=False,
        )
    assert len(list_invoices_demo()) == 10
    clear_invoices_demo()
    assert list_invoices_demo() == []


def test_paypal_create_success_send_failure_keeps_draft_for_retry(monkeypatch):
    clear_invoices_demo()
    fake_invoice = {
        "success": True,
        "mode": "LIVE_SANDBOX",
        "invoice_id": "INV-TEST-DRAFT",
        "invoice_number": "INV-NO-1",
        "status": "DRAFT",
        "total": 10.0,
        "currency": "USD",
        "buyer_email": "buyer@example.com",
        "buyer_name": "Buyer",
        "contract_id": "C-1",
        "payment_type": "sample_fee",
    }
    monkeypatch.setattr(paypal_payment, "is_paypal_configured", lambda: True)
    monkeypatch.setattr(paypal_payment, "create_invoice_api", lambda *args, **kwargs: dict(fake_invoice))
    monkeypatch.setattr(
        paypal_payment,
        "send_invoice_api",
        lambda invoice_id: {"success": False, "error": "HTTP 500"},
    )

    result = create_and_send_invoice(
        payment_type="sample_fee",
        buyer_name="Buyer",
        buyer_email="buyer@example.com",
        amount=10.0,
        currency="USD",
        contract_id="C-1",
        use_api=True,
    )
    assert result["success"] is False
    assert result["invoice_id"] == "INV-TEST-DRAFT"
    assert result["status"] == "DRAFT"
    assert result["retryable"] is True
    assert get_invoice_demo("INV-TEST-DRAFT")["status"] == "DRAFT"

    monkeypatch.setattr(paypal_payment, "send_invoice_api", lambda invoice_id: {"success": True})
    retry = retry_send_invoice("INV-TEST-DRAFT", use_api=True)
    assert retry["invoice_id"] == "INV-TEST-DRAFT"
    assert retry["status"] == "SENT"
    assert get_invoice_demo("INV-TEST-DRAFT")["status"] == "SENT"


def test_paypal_api_without_config_does_not_call_network(monkeypatch):
    for name in ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_MERCHANT_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        paypal_payment.requests,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("network called")),
    )

    result = create_and_send_invoice(
        payment_type="sample_fee",
        buyer_name="Demo Buyer",
        buyer_email="buyer@example.com",
        amount=10.0,
        use_api=True,
    )
    assert result["success"] is False
    assert result["mode"] == "NOT_CONFIGURED"

    status = check_payment_status("missing-invoice", use_api=True)
    assert status["success"] is False
    assert status["status"] == "NOT_CONFIGURED"


def test_notification_workflow_has_only_demo_language():
    notifications = generate_trade_workflow_notifications(
        customer_name="Demo Customer",
        contract_id="DEMO-001",
        product_name="Demo Product",
        quantity="1 ton",
        amount=100.0,
        currency="USD",
    )
    assert len(notifications) == 7
    blacklist = ("已发送", "已收到", "已发出", "已完成", "已通过")
    for item in notifications:
        assert "【演示文案，未实际发生。】" in item["body"]
        assert not any(word in item["subject"] for word in blacklist)
        assert not any(word in item["body"] for word in blacklist)

    payment = next(item for item in notifications if item["type"] == "payment_request")
    shipping = next(item for item in notifications if item["type"] == "shipping_notice")
    assert "模拟链接" in payment["body"]
    assert "示例单号" in shipping["body"]
