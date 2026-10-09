"""Streamlit integration tests.

When Streamlit is installed, AppTest exercises all five pages. In minimal
environments without Streamlit, source compilation checks still run.
"""

import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "app.py"

# Add project root to path so we can import modules
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # pragma: no cover - exercised when Streamlit is absent
    AppTest = None

from modules.i18n import t, TRANSLATIONS


# Page keys for i18n lookup
PAGE_KEYS = [
    "sidebar.page_home",
    "sidebar.page_onboarding",
    "sidebar.page_market",
    "sidebar.page_contract",
    "sidebar.page_paypal",
    "sidebar.page_notification",
]


def test_app_source_compiles_and_declares_five_pages():
    source = APP_PATH.read_text(encoding="utf-8")
    compile(source, str(APP_PATH), "exec")
    # Verify i18n keys exist in translations for both languages
    for lang in ("zh", "en"):
        for key in PAGE_KEYS:
            assert key in TRANSLATIONS[lang], f"Missing i18n key {key} for lang {lang}"
    # Verify app.py imports i18n
    assert "from modules.i18n import t" in source
    assert "_t(" in source


def _find_button(app, label):
    for button in app.button:
        if button.label == label:
            return button
    raise AssertionError(f"button not found: {label}")


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_all_five_pages_open_without_exception():
    at = AppTest.from_file(str(APP_PATH)).run(timeout=15)
    # sidebar.radio[0] = language switcher, sidebar.radio[1] = page navigation
    for page_key in PAGE_KEYS:
        page_label = t(page_key, "zh")
        at.sidebar.radio[1].set_value(page_label).run(timeout=15)
        assert not at.exception, f"Exception on page: {page_label}"


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_language_switch_works():
    at = AppTest.from_file(str(APP_PATH)).run()
    # Switch to English
    at.sidebar.radio[0].set_value("en").run()
    assert not at.exception
    # Verify English page labels appear in navigation options
    assert t("sidebar.page_home", "en") in at.sidebar.radio[1].options
    # Switch back to Chinese
    at.sidebar.radio[0].set_value("zh").run()
    assert not at.exception


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_contract_page_loads_sample_and_reviews():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.sidebar.radio[1].set_value(t("sidebar.page_contract", "zh")).run()
    _find_button(at, t("contract.load_sample", "zh")).click().run()
    _find_button(at, t("contract.start_review", "zh")).click().run()
    assert not at.exception
    assert any(t("contract.result_title", "zh").lstrip("# ") in item.value for item in at.markdown)


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_paypal_demo_page_creates_invoice_and_clears():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.sidebar.radio[1].set_value(t("sidebar.page_paypal", "zh")).run()
    _find_button(at, t("paypal.create_send", "zh")).click().run()
    assert not at.exception
    assert any(t("paypal.success_demo", "zh") in item.value for item in at.success)

    refresh = _find_button(at, t("paypal.refresh_status", "zh"))
    refresh.click().run()
    assert not at.exception

    clear = _find_button(at, t("paypal.clear_invoices", "zh"))
    clear.click().run()
    assert not at.exception


@pytest.mark.skipif(AppTest is None, reason="streamlit is not installed")
def test_notification_page_generates_one_notification():
    at = AppTest.from_file(str(APP_PATH)).run()
    at.sidebar.radio[1].set_value(t("sidebar.page_notification", "zh")).run()
    _find_button(at, t("notification.generate", "zh")).click().run()
    assert not at.exception
    # Notification content should be generated
    assert len(at.text_area) > 0
