"""Streamlit integration tests.

When Streamlit is installed, AppTest exercises all five pages. In minimal
environments without Streamlit, source compilation checks still run.
"""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app.py"

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - exercised when Streamlit is absent
    AppTest = None


def test_app_source_compiles_and_declares_five_pages():
    source = APP_PATH.read_text(encoding="utf-8")
    compile(source, str(APP_PATH), "exec")
    for page in (
        "🏠 首页 / 项目介绍",
        "📈 行情信号看板",
        "📝 AI合同审查",
        "💳 PayPal结算",
        "📧 客户通知",
    ):
        assert page in source


def _find_button(app, label):
    for button in app.button:
        if button.label == label:
            return button
    raise AssertionError(f"button not found: {label}")


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_all_five_pages_open_without_exception():
    at = AppTest.from_file(str(APP_PATH)).run()
    for page in (
        "🏠 首页 / 项目介绍",
        "📈 行情信号看板",
        "📝 AI合同审查",
        "💳 PayPal结算",
        "📧 客户通知",
    ):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_contract_page_loads_sample_and_reviews():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.sidebar.radio[0].set_value("📝 AI合同审查").run()
    _find_button(at, "📄 加载示例合同").click().run()
    _find_button(at, "🔍 开始审查").click().run()
    assert not at.exception
    assert any("审查结果" in item.value for item in at.markdown)


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_paypal_demo_page_creates_invoice_and_clears():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.sidebar.radio[0].set_value("💳 PayPal结算").run()
    _find_button(at, "💰 创建并发送发票").click().run()
    assert not at.exception
    assert any("发票创建成功" in item.value for item in at.success)

    refresh = _find_button(at, "🔄 刷新付款状态")
    refresh.click().run()
    assert not at.exception

    clear = _find_button(at, "🗑️ 清空当前会话发票")
    clear.click().run()
    assert not at.exception


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_notification_page_generates_one_notification():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.sidebar.radio[0].set_value("📧 客户通知").run()
    _find_button(at, "📧 生成通知").click().run()
    assert not at.exception
    assert any("演示文案" in item.value for item in at.text_area)
