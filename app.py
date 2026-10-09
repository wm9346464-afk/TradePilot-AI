#!/usr/bin/env python3
"""
TradePilot AI - Commodity Trading New Customer Onboarding & Trust Building Agent
PayPal AI Hackathon Entry

Core Features:
1. Market Signals - Ferrous metals commodity market observation & spread analysis (demo mode)
2. Contract Review - AI intelligent contract checking (typos, clause completeness, data consistency, risk alerts)
3. PayPal Payment - Trust-building period small payments (sample fees, trial orders, deposits, cross-border service fees)
4. Customer Notifications - Full-trading-workflow auto notification generation

Tech Stack: Streamlit + Python + pandas + numpy + PayPal REST API + LLM API
"""

import sys
import html
import logging
import os
from pathlib import Path

# Ensure modules package can be imported
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np

# Import four core modules
from modules.market_signal import (
    get_all_signals,
    get_price_chart_data,
    get_provider_info,
)
from modules.contract_checker import check_contract, SAMPLE_CONTRACT, is_ai_configured
from modules.paypal_payment import (
    create_and_send_invoice,
    retry_send_invoice,
    simulate_payment_demo,
    check_payment_status,
    list_invoices_demo,
    clear_invoices_demo,
    format_amount,
    is_paypal_configured,
)
from modules.notification import generate_notification, generate_trade_workflow_notifications
from modules.config import get_llm_config_status, get_paypal_config_status
from modules.i18n import t
from modules.webhook_handler import get_webhook_handler
from modules.trust_score import calculate_trust_score, get_trust_level_color


logger = logging.getLogger(__name__)


def _t(key: str, **kwargs) -> str:
    """Get translated text using current session language."""
    lang = st.session_state.get("lang", "zh")
    text = t(key, lang)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text


# ============================================================
# Contract review shortcut callbacks
# ============================================================

def _load_sample_contract():
    '''Load the built-in sample contract for the review page.'''
    st.session_state['contract_text'] = SAMPLE_CONTRACT


def _clear_contract():
    '''Clear the contract input for the review page.'''
    st.session_state['contract_text'] = ''


# ============================================================
# Page Config
# ============================================================

st.set_page_config(
    page_title=_t("page_title"),
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=60, show_spinner=False)
def _cached_get_all_signals(lang: str = "zh"):
    """Cache remote/demo signals to avoid hitting remote API on every rerun."""
    return get_all_signals(lang=lang)

# Custom CSS styles - PayPal Design System
st.markdown("""
<style>
    /* ===== PayPal Color Palette ===== */
    :root {
        --pp-blue-dark: #003087;
        --pp-blue: #0070ba;
        --pp-blue-light: #009cde;
        --pp-blue-pale: #f0f6ff;
        --pp-bg: #f7f9fa;
        --pp-card: #ffffff;
        --pp-border: #e1e4e5;
        --pp-text: #0c0c0c;
        --pp-text-secondary: #6c7378;
        --pp-success: #009c48;
        --pp-warning: #f5a623;
        --pp-danger: #d9364c;
    }

    /* ===== Global ===== */
    .stApp {
        background: var(--pp-bg);
    }
    .main .block-container {
        padding-top: 2rem;
        max-width: 1100px;
    }
    h1, h2, h3 {
        color: var(--pp-text);
        font-weight: 700;
        letter-spacing: -0.01em;
    }

    /* ===== Sidebar ===== */
    section[data-testid="stSidebar"] {
        background: var(--pp-card);
        border-right: 1px solid var(--pp-border);
    }
    section[data-testid="stSidebar"] .stRadio label {
        padding: 0.6rem 0.75rem;
        border-radius: 10px;
        transition: background 0.15s;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        background: var(--pp-blue-pale);
    }
    /* Radio selected dot - PayPal blue instead of Streamlit red */
    section[data-testid="stSidebar"] [data-baseweb="radio"] div[aria-checked="true"] div {
        background-color: var(--pp-blue) !important;
    }
    section[data-testid="stSidebar"] [data-baseweb="radio"] div[aria-checked="true"] {
        border-color: var(--pp-blue) !important;
    }

    /* ===== Buttons - PayPal Style ===== */
    .stButton > button {
        background: var(--pp-blue);
        color: white;
        border: none;
        border-radius: 24px;
        padding: 0.55rem 1.5rem;
        font-weight: 600;
        font-size: 0.95rem;
        transition: all 0.15s ease;
        box-shadow: 0 1px 3px rgba(0,112,186,0.2);
    }
    .stButton > button:hover {
        background: var(--pp-blue-dark);
        box-shadow: 0 2px 8px rgba(0,48,135,0.3);
        transform: translateY(-1px);
    }
    .stButton > button:active {
        transform: translateY(0);
    }

    /* ===== Inputs ===== */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {
        border: 1px solid var(--pp-border);
        border-radius: 10px;
        padding: 0.6rem 0.75rem;
        transition: border-color 0.15s, box-shadow 0.15s;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: var(--pp-blue);
        box-shadow: 0 0 0 3px rgba(0,112,186,0.15);
    }

    /* ===== Cards / Metrics ===== */
    .metric-box {
        background: var(--pp-card);
        border: 1px solid var(--pp-border);
        border-radius: 14px;
        padding: 1.25rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.04);
        text-align: center;
        transition: box-shadow 0.2s;
    }
    .metric-box:hover {
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
    }
    .metric-box h3 {
        color: var(--pp-blue-dark);
        font-size: 1.4rem;
        margin-bottom: 0.25rem;
    }
    .metric-box p {
        color: var(--pp-text-secondary);
        font-size: 0.85rem;
        margin: 0;
    }

    /* ===== Workflow Steps ===== */
    .workflow-step {
        display: flex;
        align-items: center;
        padding: 0.9rem 1rem;
        background: var(--pp-card);
        border: 1px solid var(--pp-border);
        border-radius: 12px;
        margin-bottom: 0.6rem;
        transition: border-color 0.15s;
    }
    .workflow-step:hover {
        border-color: var(--pp-blue-light);
    }
    .step-number {
        background: var(--pp-blue);
        color: white;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        font-size: 0.85rem;
        margin-right: 1rem;
        flex-shrink: 0;
    }

    /* ===== Status Badges ===== */
    .mode-live {
        background: #e6f4ea;
        color: var(--pp-success);
        padding: 4px 14px;
        border-radius: 16px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .mode-demo {
        background: #fff4e0;
        color: #b8860b;
        padding: 4px 14px;
        border-radius: 16px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .signal-high { color: var(--pp-danger); font-weight: 600; }
    .signal-medium { color: var(--pp-warning); font-weight: 600; }
    .signal-low { color: var(--pp-success); font-weight: 600; }

    /* ===== Headers ===== */
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        color: var(--pp-blue-dark);
        margin-bottom: 0.3rem;
        letter-spacing: -0.02em;
    }
    .sub-header {
        font-size: 1.05rem;
        color: var(--pp-text-secondary);
        margin-bottom: 1.5rem;
        line-height: 1.5;
    }

    /* ===== DataFrames / Tables ===== */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid var(--pp-border);
    }

    /* ===== Tabs ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 0.5rem 1rem;
    }
    .stTabs [aria-selected="true"] {
        color: var(--pp-blue) !important;
    }

    /* ===== Expander ===== */
    .streamlit-expanderHeader {
        border-radius: 10px;
        font-weight: 600;
    }

    /* ===== Info/Warning/Error boxes ===== */
    .stAlert {
        border-radius: 12px;
        border: none;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Sidebar Navigation
# ============================================================

with st.sidebar:
    st.markdown(f"### {_t('sidebar.title')}")
    st.markdown(f"**{_t('sidebar.subtitle')}**")
    st.markdown("---")

    # Language switcher
    lang_choice = st.radio(
        _t("sidebar.lang_label"),
        ["zh", "en"],
        format_func=lambda x: _t(f"sidebar.lang_{x}"),
        index=0,
        key="lang_radio",
    )
    st.session_state["lang"] = lang_choice

    page = st.radio(
        _t("sidebar.nav_label"),
        [
            _t("sidebar.page_home"),
            _t("sidebar.page_onboarding"),
            _t("sidebar.page_market"),
            _t("sidebar.page_contract"),
            _t("sidebar.page_paypal"),
            _t("sidebar.page_notification"),
        ],
        index=0,
    )

    app_password = os.getenv("APP_PASSWORD", "")
    if app_password:
        entered_password = st.text_input(_t("sidebar.password_label"), type="password")
        if entered_password != app_password:
            st.warning(_t("sidebar.password_hint"))
            st.stop()

    st.markdown("---")
    st.markdown(f"### {_t('sidebar.system_status')}")

    paypal_status = get_paypal_config_status(lang=st.session_state.get("lang", "zh"))
    llm_status = get_llm_config_status(lang=st.session_state.get("lang", "zh"))
    paypal_class = "mode-live" if paypal_status["state"] == "usable" else "mode-demo"
    llm_class = "mode-live" if llm_status["state"] == "usable" else "mode-demo"
    st.markdown(
        f"{_t('sidebar.paypal_api')}: <span class='{paypal_class}'>{paypal_status['label']}</span>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f"{_t('sidebar.ai_review')}: <span class='{llm_class}'>{llm_status['label']}</span>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(f"### {_t('sidebar.about')}")
    st.markdown(_t("sidebar.about_line1"))
    st.markdown(_t("sidebar.about_line2"))


# ============================================================
# Page 1: Home / Project Overview
# ============================================================

if page == _t("sidebar.page_home"):
    st.markdown('<p class="main-header">TradePilot AI</p>', unsafe_allow_html=True)
    st.markdown(f'<p class="sub-header">{_t("home.subheader")}</p>', unsafe_allow_html=True)

    st.markdown(f"### {_t('home.problem_title')}")
    st.markdown(f"""
    {_t('home.problem_intro')}
    - {_t('home.problem_1')}
    - {_t('home.problem_2')}
    - {_t('home.problem_3')}
    - {_t('home.problem_4')}
    """)

    st.markdown(f"### {_t('home.solution_title')}")
    st.markdown(f"""
    {_t('home.solution_intro')}

    1. {_t('home.solution_1')}
    2. {_t('home.solution_2')}
    3. {_t('home.solution_3')}
    4. {_t('home.solution_4')}

    {_t('home.disclaimer')}
    """)

    st.markdown(f"### {_t('home.workflow_title')}")
    col1, col2 = st.columns([2, 1])
    with col1:
        steps = [
            (_t("home.workflow_step1_title"), _t("home.workflow_step1_desc")),
            (_t("home.workflow_step2_title"), _t("home.workflow_step2_desc")),
            (_t("home.workflow_step3_title"), _t("home.workflow_step3_desc")),
            (_t("home.workflow_step4_title"), _t("home.workflow_step4_desc")),
            (_t("home.workflow_step5_title"), _t("home.workflow_step5_desc")),
            (_t("home.workflow_step6_title"), _t("home.workflow_step6_desc")),
        ]
        for i, (title, desc) in enumerate(steps, 1):
            st.markdown(f"""
            <div class="workflow-step">
                <div class="step-number">{i}</div>
                <div>
                    <strong>{title}</strong><br/>
                    <span style="color: #666; font-size: 0.9rem;">{desc}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"#### {_t('home.core_data_title')}")
        st.markdown(f'<div class="metric-box"><h3>{_t("home.metric1_title")}</h3><p>{_t("home.metric1_desc")}</p></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-box"><h3>{_t("home.metric2_title")}</h3><p>{_t("home.metric2_desc")}</p></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="metric-box"><h3>{_t("home.metric3_title")}</h3><p>{_t("home.metric3_desc")}</p></div>', unsafe_allow_html=True)

    st.markdown(f"### {_t('home.tech_title')}")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"#### {_t('home.tech_market_title')}")
        st.markdown(_t("home.tech_market_desc"))
    with col2:
        st.markdown(f"#### {_t('home.tech_contract_title')}")
        st.markdown(_t("home.tech_contract_desc"))
    with col3:
        st.markdown(f"#### {_t('home.tech_paypal_title')}")
        st.markdown(_t("home.tech_paypal_desc"))
    with col4:
        st.markdown(f"#### {_t('home.tech_notification_title')}")
        st.markdown(_t("home.tech_notification_desc"))

    st.markdown("---")
    st.markdown(f"### {_t('home.start_title')}")
    st.markdown(_t("home.start_desc"))


# ============================================================
# Page: New Customer Onboarding Workflow
# ============================================================

elif page == _t("sidebar.page_onboarding"):
    st.markdown(f"<h1 class='main-header'>{_t('onboarding.title')}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-header'>{_t('onboarding.subtitle')}</p>", unsafe_allow_html=True)

    # Initialize onboarding state
    if "onboarding_step" not in st.session_state:
        st.session_state["onboarding_step"] = 0
    if "onboarding_data" not in st.session_state:
        st.session_state["onboarding_data"] = {}
    if "onboarding_contract_reviewed" not in st.session_state:
        st.session_state["onboarding_contract_reviewed"] = False
    if "onboarding_invoice_created" not in st.session_state:
        st.session_state["onboarding_invoice_created"] = False
    if "onboarding_paid" not in st.session_state:
        st.session_state["onboarding_paid"] = False
    if "onboarding_notifications_generated" not in st.session_state:
        st.session_state["onboarding_notifications_generated"] = False

    current_step = st.session_state["onboarding_step"]
    ob_data = st.session_state["onboarding_data"]
    lang = st.session_state.get("lang", "zh")

    # Step indicator
    steps = [_t("onboarding.step1"), _t("onboarding.step2"), _t("onboarding.step3"), _t("onboarding.step4")]
    cols = st.columns(4)
    for i, (col, step_name) in enumerate(zip(cols, steps)):
        with col:
            if i < current_step:
                st.markdown(f"<div style='text-align:center;'><div style='background:#009c48;color:white;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto;font-weight:bold;'>✓</div><div style='margin-top:8px;font-size:0.85rem;color:#009c48;font-weight:600;'>{step_name}</div></div>", unsafe_allow_html=True)
            elif i == current_step:
                st.markdown(f"<div style='text-align:center;'><div style='background:#0070ba;color:white;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto;font-weight:bold;'>{i+1}</div><div style='margin-top:8px;font-size:0.85rem;color:#0070ba;font-weight:600;'>{step_name}</div></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center;'><div style='background:#e1e4e5;color:#6c7378;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto;font-weight:bold;'>{i+1}</div><div style='margin-top:8px;font-size:0.85rem;color:#6c7378;'>{step_name}</div></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ===== Step 1: Customer Inquiry & Market Analysis =====
    if current_step == 0:
        st.markdown(f"### {_t('onboarding.step1_title')}")
        st.caption(_t("onboarding.step1_desc"))

        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input(_t("onboarding.customer_name"), value=ob_data.get("customer_name", ""), placeholder=_t("onboarding.customer_name_placeholder"))
            product = st.text_input(_t("onboarding.product"), value=ob_data.get("product", ""), placeholder=_t("onboarding.product_placeholder"))
        with col2:
            quantity = st.number_input(_t("onboarding.quantity"), min_value=0, value=ob_data.get("quantity", 100), step=10)

        # Show market signal
        st.markdown(f"#### {_t('onboarding.market_signal')}")
        signal_bundle = _cached_get_all_signals(lang=lang)
        signals = signal_bundle.get("signals", {})
        if signals:
            first_key = list(signals.keys())[0]
            sig = signals[first_key]
            conf = sig.get("confidence", "medium")
            conf_color = {"high": "#d9364c", "medium": "#f5a623", "low": "#009c48"}.get(conf, "#6c7378")
            st.markdown(f"""
            <div class='metric-box'>
                <h3 style='color:{conf_color};'>{sig.get('signal','N/A')}</h3>
                <p>{first_key} | {_t(f'market.conf_{conf}') if conf in ['high','medium','low'] else conf}</p>
            </div>
            """, unsafe_allow_html=True)

        # Pricing suggestion based on signal
        st.markdown(f"#### {_t('onboarding.pricing_suggestion')}")
        if signals:
            first_key = list(signals.keys())[0]
            sig = signals[first_key]
            signal_text = sig.get("signal", "").lower()
            if "多" in signal_text or "bull" in signal_text or "涨" in signal_text:
                suggestion = "当前行情偏多，建议尽快锁定价格，可适当提高报价" if lang == "zh" else "Market is bullish, recommend locking price soon, can slightly raise offer"
            elif "空" in signal_text or "bear" in signal_text or "跌" in signal_text:
                suggestion = "当前行情偏空，建议保守报价，预留降价空间" if lang == "zh" else "Market is bearish, recommend conservative pricing, reserve room for price cuts"
            else:
                suggestion = "当前行情震荡，建议按市场价报价，保持灵活" if lang == "zh" else "Market is range-bound, recommend market-price offer, stay flexible"
            st.info(suggestion)
        else:
            st.info("按市场价报价" if lang == "zh" else "Price at market rate")

        # Save data and next
        if st.button(_t("onboarding.next"), key="ob_next_1", type="primary"):
            ob_data["customer_name"] = customer_name
            ob_data["product"] = product
            ob_data["quantity"] = quantity
            st.session_state["onboarding_step"] = 1
            st.rerun()

    # ===== Step 2: Contract Review =====
    elif current_step == 1:
        st.markdown(f"### {_t('onboarding.step2_title')}")
        st.caption(_t("onboarding.step2_desc"))

        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button(_t("onboarding.use_sample_contract"), key="ob_sample"):
                st.session_state['ob_contract_text'] = SAMPLE_CONTRACT
        with col_btn2:
            if st.button(_t("onboarding.clear_contract"), key="ob_clear"):
                st.session_state['ob_contract_text'] = ''

        contract_text = st.text_area(
            _t("contract.input_label"),
            value=st.session_state.get('ob_contract_text', ''),
            height=200,
            placeholder=_t("onboarding.contract_placeholder"),
            key="ob_contract_input"
        )

        if st.button(_t("contract.review_button"), key="ob_review", type="primary"):
            if not contract_text.strip():
                st.warning(_t("contract.empty_warning"))
            else:
                with st.spinner(_t("contract.reviewing")):
                    result = check_contract(contract_text, use_ai=False, lang=lang)
                st.session_state["ob_contract_result"] = result
                st.session_state["onboarding_contract_reviewed"] = True

        if st.session_state.get("onboarding_contract_reviewed") and "ob_contract_result" in st.session_state:
            result = st.session_state["ob_contract_result"]
            st.markdown(f"#### {_t('onboarding.review_result')}")
            st.markdown(f"**{_t('contract.summary_label')}**: {result.get('summary', '')}")
            issues = result.get("issues", [])
            if issues:
                for issue in issues:
                    severity = issue.get("severity", "low")
                    sev_color = {"high": "#d9364c", "medium": "#f5a623", "low": "#009c48"}.get(severity, "#6c7378")
                    st.markdown(f"- <span style='color:{sev_color};font-weight:600;'>[{issue.get('type','')}]</span> {issue.get('description','')}", unsafe_allow_html=True)
            else:
                st.success(_t("contract.no_issues"))

        col_prev, col_next = st.columns([1, 4])
        with col_prev:
            if st.button(_t("onboarding.prev"), key="ob_prev_2"):
                st.session_state["onboarding_step"] = 0
                st.rerun()
        with col_next:
            if st.button(_t("onboarding.next"), key="ob_next_2", type="primary", disabled=not st.session_state.get("onboarding_contract_reviewed", False)):
                st.session_state["onboarding_step"] = 2
                st.rerun()

    # ===== Step 3: Sample Fee Payment =====
    elif current_step == 2:
        st.markdown(f"### {_t('onboarding.step3_title')}")
        st.caption(_t("onboarding.step3_desc"))

        col1, col2 = st.columns(2)
        with col1:
            sample_amount = st.number_input(_t("onboarding.sample_amount"), min_value=0.0, value=ob_data.get("sample_amount", 500.0), step=50.0)
            buyer_name = st.text_input(_t("onboarding.buyer_name"), value=ob_data.get("customer_name", ""))
        with col2:
            buyer_email = st.text_input(_t("onboarding.buyer_email"), value=ob_data.get("buyer_email", "buyer@example.com"))

        if st.button(_t("onboarding.create_invoice"), key="ob_create_invoice", type="primary"):
            with st.spinner(_t("paypal.creating")):
                invoice = create_and_send_invoice(
                    payment_type="sample_fee",
                    buyer_email=buyer_email,
                    buyer_name=buyer_name,
                    amount=sample_amount,
                    currency="USD",
                    contract_id=f"OB-{ob_data.get('customer_name','DEMO')[:10]}",
                    use_api=False,
                    lang=lang,
                )
            st.session_state["ob_invoice"] = invoice
            st.session_state["onboarding_invoice_created"] = True
            ob_data["sample_amount"] = sample_amount
            ob_data["buyer_email"] = buyer_email
            ob_data["buyer_name"] = buyer_name

        if st.session_state.get("onboarding_invoice_created") and "ob_invoice" in st.session_state:
            invoice = st.session_state["ob_invoice"]
            if invoice.get("success"):
                st.success(f"{_t('paypal.invoice_created')} #{invoice.get('invoice_number','')}")
                st.markdown(f"**{_t('paypal.amount')}**: {invoice.get('currency','USD')} {invoice.get('amount','')}")
                st.markdown(f"**{_t('paypal.status')}**: {invoice.get('status','')}")

                # Simulate payment button (demo)
                if not st.session_state.get("onboarding_paid"):
                    if st.button(_t("paypal.simulate_payment"), key="ob_sim_pay"):
                        pay_result = simulate_payment_demo(invoice["invoice_id"])
                        if pay_result.get("success"):
                            st.session_state["onboarding_paid"] = True
                            # Auto-trigger webhook handling
                            wh = get_webhook_handler()
                            wh_result = wh.simulate_invoice_paid_event(
                                invoice_id=invoice.get("invoice_id", "DEMO"),
                                amount=invoice.get("amount", 0),
                                currency=invoice.get("currency", "USD"),
                                invoice_number=invoice.get("invoice_number", "DEMO-001"),
                            )
                            st.session_state["ob_webhook_result"] = wh_result
                            st.success(_t("paypal.payment_success"))
                            st.rerun()
                else:
                    st.success(_t("paypal.payment_success"))
                    # Show webhook auto-triggered actions
                    if "ob_webhook_result" in st.session_state:
                        wh_result = st.session_state["ob_webhook_result"]
                        if wh_result.get("auto_triggered"):
                            st.info(_t("paypal.webhook_auto_triggered"))
                            for action in wh_result.get("actions", [])[1:]:  # skip first line (invoice paid)
                                st.markdown(f"- {action}")
            else:
                st.error(f"{_t('paypal.create_failed', error=invoice.get('error',''))}")

        col_prev, col_next = st.columns([1, 4])
        with col_prev:
            if st.button(_t("onboarding.prev"), key="ob_prev_3"):
                st.session_state["onboarding_step"] = 1
                st.rerun()
        with col_next:
            if st.button(_t("onboarding.next"), key="ob_next_3", type="primary", disabled=not st.session_state.get("onboarding_paid", False)):
                st.session_state["onboarding_step"] = 3
                st.rerun()

    # ===== Step 4: Shipping & Notifications =====
    elif current_step == 3:
        st.markdown(f"### {_t('onboarding.step4_title')}")
        st.caption(_t("onboarding.step4_desc"))

        if st.button(_t("onboarding.generate_notifications"), key="ob_gen_notif", type="primary"):
            with st.spinner(_t("notification.generating")):
                notifications = generate_trade_workflow_notifications(
                    customer_name=ob_data.get("customer_name", "Demo Customer"),
                    product=ob_data.get("product", "Iron Ore"),
                    quantity=ob_data.get("quantity", 100),
                    amount=ob_data.get("sample_amount", 500),
                    lang=lang,
                )
            st.session_state["ob_notifications"] = notifications
            st.session_state["onboarding_notifications_generated"] = True

        if st.session_state.get("onboarding_notifications_generated") and "ob_notifications" in st.session_state:
            notifications = st.session_state["ob_notifications"]
            st.success(f"{_t('notification.generated')} {len(notifications)}")
            for i, notif in enumerate(notifications):
                with st.expander(f"{notif.get('type','')} - {notif.get('title','')}"):
                    st.markdown(notif.get("content", ""))

        st.markdown("---")
        col_prev, col_finish = st.columns([1, 4])
        with col_prev:
            if st.button(_t("onboarding.prev"), key="ob_prev_4"):
                st.session_state["onboarding_step"] = 2
                st.rerun()
        with col_finish:
            if st.button(_t("onboarding.finish"), key="ob_finish", type="primary", disabled=not st.session_state.get("onboarding_notifications_generated", False)):
                st.session_state["onboarding_step"] = 4  # complete
                st.rerun()

    # ===== Complete Page =====
    elif current_step == 4:
        st.balloons()
        st.markdown(f"### {_t('onboarding.complete_title')}")
        st.success(_t("onboarding.complete_desc"))

        st.markdown(f"#### {_t('onboarding.summary')}")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(_t("onboarding.customer_name"), ob_data.get("customer_name", "-"))
        with col2:
            st.metric(_t("onboarding.product"), ob_data.get("product", "-"))
        with col3:
            st.metric(_t("onboarding.quantity"), f"{ob_data.get('quantity', 0)} t")

        col4, col5 = st.columns(2)
        with col4:
            st.metric(_t("onboarding.sample_amount"), f"${ob_data.get('sample_amount', 0)}")
        with col5:
            # Real trust score calculation
            contract_result = st.session_state.get("ob_contract_result", {})
            issues = contract_result.get("issues", [])
            high_risk_count = sum(1 for i in issues if i.get("severity") == "高")
            # Determine market volatility from signal
            market_vol = "medium"
            try:
                sig_bundle = _cached_get_all_signals(lang=lang)
                sigs = sig_bundle.get("signals", {})
                if sigs:
                    first_sig = list(sigs.values())[0]
                    conf = first_sig.get("confidence", "medium")
                    market_vol = {"high": "high", "medium": "medium", "low": "low"}.get(conf, "medium")
            except Exception:
                pass
            trust_result = calculate_trust_score(
                contract_issues_count=len(issues),
                contract_high_risk_count=high_risk_count,
                has_payment_history=st.session_state.get("onboarding_paid", False),
                payment_on_time_rate=1.0 if st.session_state.get("onboarding_paid") else 0.5,
                market_volatility=market_vol,
                company_name_provided=bool(ob_data.get("customer_name")),
                company_contact_provided=bool(ob_data.get("buyer_email")),
                transaction_amount=ob_data.get("sample_amount", 500),
                lang=lang,
            )
            trust_color = get_trust_level_color(trust_result.level)
            st.metric(_t("onboarding.trust_score"), f"{trust_result.total}/100")
            st.markdown(f"<div style='text-align:center;color:{trust_color};font-weight:600;'>{trust_result.level}信任 / {trust_result.level_en if lang=='en' else trust_result.level}</div>", unsafe_allow_html=True)

        # Trust score dimension breakdown
        st.markdown("---")
        st.markdown(f"#### {_t('onboarding.trust_score')} - {_t('onboarding.summary')}")
        dim_cols = st.columns(5)
        for i, (dim_key, dim_data) in enumerate(trust_result.dimensions.items()):
            with dim_cols[i]:
                pct = int(dim_data["score"] / dim_data["max"] * 100)
                st.markdown(f"<div style='text-align:center;'><div style='font-size:1.5rem;font-weight:bold;color:#0070ba;'>{dim_data['score']}/{dim_data['max']}</div><div style='font-size:0.8rem;color:#6c7378;'>{dim_data['label']}</div><div style='background:#e1e4e5;height:6px;border-radius:3px;margin-top:4px;'><div style='background:#0070ba;height:6px;border-radius:3px;width:{pct}%;'></div></div></div>", unsafe_allow_html=True)

        # Recommendations
        if trust_result.recommendations:
            st.markdown("---")
            st.markdown(f"#### {'交易建议' if lang == 'zh' else 'Recommendations'}")
            for rec in trust_result.recommendations:
                st.markdown(f"- {rec}")

        st.markdown("---")
        if st.button(_t("onboarding.restart"), key="ob_restart", type="primary"):
            for key in ["onboarding_step", "onboarding_data", "onboarding_contract_reviewed",
                        "onboarding_invoice_created", "onboarding_paid", "onboarding_notifications_generated",
                        "ob_contract_result", "ob_invoice", "ob_notifications", "ob_contract_text"]:
                st.session_state.pop(key, None)
            st.rerun()


# ============================================================
# Page 2: Market Signals Dashboard
# ============================================================

elif page == _t("sidebar.page_market"):
    st.title(_t("market.title"))
    st.markdown(_t("market.subtitle"))

    signal_bundle = _cached_get_all_signals(lang=st.session_state.get("lang", "zh"))
    signals = signal_bundle.get("signals", {})
    provider_info = get_provider_info(signal_bundle, lang=st.session_state.get("lang", "zh"))

    if signal_bundle.get("degraded"):
        st.warning(
            _t("market.degraded_warning")
            + f"{signal_bundle.get('fallback_reason', _t('common.unknown'))}"
        )
    elif provider_info.get("is_demo"):
        st.warning(_t("market.demo_warning"))

    st.caption(
        f"{_t('market.source_label')}{provider_info.get('signals_source', 'N/A')} | "
        f"{_t('market.chart_source_label')}{provider_info.get('chart_source', 'N/A')} | "
        f"{_t('market.as_of_label')}{provider_info.get('as_of', 'N/A')}"
    )

    # Data cutoff date hint
    try:
        data_path = PROJECT_ROOT / "data" / "demo_market_data.csv"
        df_check = pd.read_csv(data_path)
        last_date = df_check.iloc[-1, 0] if len(df_check) > 0 else _t("common.unknown")
        st.info(_t("market.data_date_info", date=last_date))
    except Exception as exc:
        logger.warning("Failed to read demo data cutoff date: %s", exc)
        st.info(_t("market.data_date_fallback", date=provider_info.get('as_of', _t('common.unknown'))))

    st.markdown(f"### {_t('market.overview_title')}")
    cols = st.columns(3)
    for i, (key, sig) in enumerate(signals.items()):
        with cols[i]:
            zh = html.escape(str(sig.get("zh", "")))
            direction = html.escape(str(sig.get("direction", "")))
            confidence = str(sig.get("confidence", _t("common.low")))
            confidence = confidence if confidence in {"高", "中", "低", "High", "Medium", "Low"} else _t("common.low")
            conf_class = {
                "高": "signal-high", "中": "signal-medium", "低": "signal-low",
                "High": "signal-high", "Medium": "signal-medium", "Low": "signal-low",
            }.get(confidence, "signal-low")
            probability = sig.get("probability", 0.0)
            probability = float(probability) if isinstance(probability, (int, float)) else 0.0
            z_value = sig.get("z")
            z_text = (
                f"{z_value:.2f}"
                if isinstance(z_value, (int, float)) and np.isfinite(z_value)
                else "N/A"
            )
            if sig.get("triggered"):
                st.markdown(f"""
                <div class="metric-box" style="border-top: 4px solid #d32f2f;">
                    <h3 style="color: #d32f2f;">{direction}</h3>
                    <p><strong>{zh}</strong></p>
                    <p class="{conf_class}">{_t('market.confidence_label')}{html.escape(confidence)}</p>
                    <p>{_t('market.probability_label')}{probability:.1%}</p>
                    <p>z-score: {z_text}</p>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-box" style="border-top: 4px solid #999;">
                    <h3 style="color: #999;">{direction}</h3>
                    <p><strong>{zh}</strong></p>
                    <p>{_t('market.confidence_label')}{html.escape(confidence)}</p>
                    <p>z-score: {z_text}</p>
                    <p style="font-size: 0.8rem; color: #999;">{_t('market.not_triggered')}</p>
                </div>
                """, unsafe_allow_html=True)

    st.markdown(f"### {_t('market.details_title')}")
    for key, sig in signals.items():
        with st.expander(f"{sig['zh']} - {sig['direction']} {_t('market.expand_hint')}", expanded=sig["triggered"]):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown(f"**{_t('market.signal_name')}**: {sig['zh']}")
                st.markdown(f"**{_t('market.current_status')}**: {sig['direction']}")
                st.markdown(f"**{_t('market.confidence')}**: {sig['confidence']}")
                st.markdown(f"**{_t('market.convergence_prob')}**: {sig['probability']:.1%}")
                z_val = sig.get('z')
                if isinstance(z_val, (int, float)) and np.isfinite(z_val):
                    st.markdown(f"**{_t('market.z_score')}**: {z_val:.2f}")
                else:
                    st.markdown(f"**{_t('market.z_score')}**: N/A")
                st.markdown(f"**{_t('market.signal_date')}**: {sig['date']}")
                current_spread = sig.get('current_spread')
                if isinstance(current_spread, (int, float)) and np.isfinite(current_spread):
                    st.markdown(f"**{_t('market.current_spread')}**: {current_spread:.0f}")
                roll_mean = sig.get('roll_mean')
                if isinstance(roll_mean, (int, float)) and np.isfinite(roll_mean):
                    st.markdown(f"**{_t('market.roll_mean')}**: {roll_mean:.0f}")
            with col2:
                st.markdown(f"**{_t('market.signal_explanation')}**:")
                reasons = sig.get("reasons") or []
                if isinstance(reasons, str):
                    reasons = [reasons]
                for reason in reasons:
                    st.markdown(f"- {reason}")

    st.markdown(f"### {_t('market.chart_title')}")
    chart_data = get_price_chart_data()
    df_chart = pd.DataFrame({
        _t("market.chart_date"): pd.to_datetime(chart_data["dates"]),
        _t("market.chart_cold_spot"): chart_data["cold_roll"],
        _t("market.chart_hc_futures"): chart_data["hc_futures"],
        _t("market.chart_rb_futures"): chart_data["rb_futures"],
        _t("market.chart_rb_spot"): chart_data["rb_spot"],
    })
    df_chart = df_chart.set_index(_t("market.chart_date"))
    st.line_chart(df_chart, use_container_width=True)
    st.caption(f"{_t('market.chart_data_source')}{provider_info.get('chart_source', 'N/A')}")

    with st.expander(_t("market.module_info_title")):
        st.markdown(_t("market.module_positioning"))
        st.markdown(_t("market.public_version"))
        st.markdown(_t("market.signal_types"))
        st.markdown(_t("market.architecture"))
        st.markdown(_t("market.important_notice"))


# ============================================================
# Page 3: AI Contract Review
# ============================================================

elif page == _t("sidebar.page_contract"):
    st.title(_t("contract.title"))
    st.markdown(_t("contract.subtitle"))

    if "contract_text" not in st.session_state:
        st.session_state["contract_text"] = ""
    if "contract_result" not in st.session_state:
        st.session_state["contract_result"] = None
    if "contract_processing" not in st.session_state:
        st.session_state["contract_processing"] = False

    st.warning(_t("contract.ai_warning"))

    col1, col2 = st.columns([3, 1])
    with col1:
        contract_text = st.text_area(
            _t("contract.textarea_label"),
            height=300,
            key="contract_text",
            placeholder=_t("contract.textarea_placeholder"),
            max_chars=20000,
        )
    with col2:
        st.markdown(_t("contract.quick_actions"))
        st.button(_t("contract.load_sample"), use_container_width=True, on_click=_load_sample_contract)
        st.button(_t("contract.clear"), use_container_width=True, on_click=_clear_contract)

        force_demo = st.checkbox(
            _t("contract.demo_mode"),
            value=False,
            help=_t("contract.demo_mode_help")
        )
        use_ai = st.checkbox(_t("contract.enable_ai"), value=False, help=_t("contract.enable_ai_help"))
        st.markdown("---")
        st.markdown(_t("contract.check_dimensions"))
        st.markdown(_t("contract.dim_typo"))
        st.markdown(_t("contract.dim_completeness"))
        st.markdown(_t("contract.dim_consistency"))
        st.markdown(_t("contract.dim_risk"))
        st.markdown(_t("contract.dim_compliance"))

    if st.button(
        _t("contract.start_review"),
        type="primary",
        use_container_width=True,
        disabled=st.session_state["contract_processing"],
    ):
        if not contract_text or not contract_text.strip():
            st.warning(_t("contract.empty_warning"))
        else:
            st.session_state["contract_processing"] = True
            st.session_state["pending_contract_text"] = contract_text
            st.session_state["pending_use_ai"] = use_ai
            st.session_state["pending_force_demo"] = force_demo
            st.session_state["contract_result"] = None
            st.rerun()

    if st.session_state["contract_processing"]:
        pending_text = st.session_state.get("pending_contract_text", "")
        with st.spinner(_t("contract.reviewing")):
            result = check_contract(
                pending_text,
                use_ai=st.session_state.get("pending_use_ai", False),
                force_demo=st.session_state.get("pending_force_demo", False),
                lang=st.session_state.get("lang", "zh"),
            )
        st.session_state["contract_result"] = result
        st.session_state["contract_processing"] = False
        st.rerun()

    result = st.session_state.get("contract_result")
    if result:
        st.markdown(_t("contract.result_title"))

        mode_code = result.get("mode_code", "RULE_ONLY")
        mode_label = result.get("mode_label", result.get("mode", ""))
        if mode_code == "AI_LIVE":
            st.markdown(f"{_t('contract.current_mode')}<span class='mode-live'>{html.escape(mode_label)}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"{_t('contract.current_mode')}<span class='mode-demo'>{html.escape(mode_label)}</span>", unsafe_allow_html=True)

        st.info(f"**{result['summary']}**")

        if result.get("ai_error"):
            st.warning(f"⚠️ {result['ai_error']}")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(_t("contract.total_issues"), result["total_issues"])
        with col2:
            st.metric(_t("contract.high_risk"), result["high_count"])
        with col3:
            st.metric(_t("contract.medium_risk"), result["medium_count"])
        with col4:
            st.metric(_t("contract.low_risk"), result["low_count"])

        st.markdown(_t("contract.issues_detail"))
        for i, issue in enumerate(result["issues"], 1):
            severity_color = {
                "高": "🔴 高风险", "中": "🟡 中风险", "低": "🟢 低风险",
                "High": "🔴 High", "Medium": "🟡 Medium", "Low": "🟢 Low",
            }.get(issue.get("severity", "低"), issue.get("severity", ""))
            with st.expander(
                f"{i}. {severity_color} | {issue['type']} | {str(issue['original'])[:30]}...",
                expanded=issue.get("severity") in ("高", "High"),
            ):
                st.markdown(f"**{_t('contract.issue_type')}**: {issue['type']}")
                st.markdown(f"**{_t('contract.severity')}**: {severity_color}")
                st.markdown(f"**{_t('contract.original_text')}**: {issue['original']}")
                st.markdown(f"**{_t('contract.suggestion')}**: {issue['suggestion']}")
                st.markdown(f"**{_t('contract.description')}**: {issue['description']}")

    st.markdown("---")
    st.caption(_t("contract.disclaimer"))


# ============================================================
# Page 4: PayPal Payment
# ============================================================

elif page == _t("sidebar.page_paypal"):
    st.title(_t("paypal.title"))
    st.markdown(_t("paypal.subtitle"))

    paypal_status = get_paypal_config_status(lang=st.session_state.get("lang", "zh"))
    if paypal_status["state"] == "usable":
        st.success(_t("paypal.config_usable"))
    elif paypal_status["state"] == "unverified":
        st.warning(_t("paypal.config_unverified"))
    else:
        st.warning(_t("paypal.config_demo"))

    with st.expander(_t("paypal.protection_title")):
        st.markdown(_t("paypal.protection_content"))

    # Market-linked payment strategy suggestion
    st.markdown(f"#### {_t('paypal.pricing_title')}")
    try:
        signal_bundle_pp = _cached_get_all_signals(lang=st.session_state.get("lang", "zh"))
        signals_pp = signal_bundle_pp.get("signals", {})
        if signals_pp:
            first_key_pp = list(signals_pp.keys())[0]
            sig_pp = signals_pp[first_key_pp]
            signal_text_pp = sig_pp.get("signal", "").lower()
            if "多" in signal_text_pp or "bull" in signal_text_pp or "涨" in signal_text_pp:
                st.info(_t("paypal.pricing_bull"))
            elif "空" in signal_text_pp or "bear" in signal_text_pp or "跌" in signal_text_pp:
                st.warning(_t("paypal.pricing_bear"))
            else:
                st.info(_t("paypal.pricing_neutral"))
        else:
            st.info(_t("paypal.pricing_neutral"))
    except Exception:
        st.info(_t("paypal.pricing_neutral"))

    st.markdown(_t("paypal.create_title"))
    col1, col2 = st.columns(2)
    with col1:
        payment_type = st.selectbox(
            _t("paypal.payment_type"),
            options=[
                ("sample_fee", _t("paypal.type_sample")),
                ("trial_order", _t("paypal.type_trial")),
                ("deposit", _t("paypal.type_deposit")),
                ("service_fee", _t("paypal.type_service")),
            ],
            format_func=lambda x: x[1],
        )
        buyer_name = st.text_input(_t("paypal.buyer_name"), value="Shanghai Construction Materials Co., Ltd.")
        buyer_email = st.text_input(_t("paypal.buyer_email"), value="buyer@example.com")
    with col2:
        amount = st.number_input(_t("paypal.amount"), min_value=0.01, value=150.00, step=10.0)
        currency = st.selectbox(
            _t("paypal.currency"),
            options=["USD", "CNY", "EUR"],
            index=0,
            help=_t("paypal.currency_help"),
        )
        contract_id = st.text_input(_t("paypal.contract_id"), value="GM20260915001")

    use_api = st.checkbox(
        _t("paypal.use_api"),
        value=is_paypal_configured(),
        disabled=not is_paypal_configured(),
        help=_t("paypal.use_api_help")
    )

    if "invoice_processing" not in st.session_state:
        st.session_state["invoice_processing"] = False
    if "last_invoice_result" not in st.session_state:
        st.session_state["last_invoice_result"] = None

    if st.button(
        _t("paypal.create_send"),
        type="primary",
        use_container_width=True,
        disabled=st.session_state["invoice_processing"],
    ):
        st.session_state["pending_invoice_args"] = {
            "payment_type": payment_type[0],
            "buyer_name": buyer_name,
            "buyer_email": buyer_email,
            "amount": amount,
            "currency": currency,
            "contract_id": contract_id,
            "use_api": use_api,
            "lang": st.session_state.get("lang", "zh"),
        }
        st.session_state["invoice_processing"] = True
        st.session_state["last_invoice_result"] = None
        st.rerun()

    if st.session_state["invoice_processing"]:
        invoice_args = st.session_state.get("pending_invoice_args", {})
        with st.spinner(_t("paypal.creating")):
            invoice_result = create_and_send_invoice(**invoice_args)
        st.session_state["last_invoice_result"] = invoice_result
        st.session_state["invoice_processing"] = False
        st.session_state["last_invoice_use_api"] = bool(invoice_args.get("use_api"))
        st.rerun()

    invoice = st.session_state.get("last_invoice_result")
    if invoice:
        if not invoice.get("success", True):
            invoice_id = invoice.get("invoice_id", "")
            if invoice.get("status") == "DRAFT" and invoice_id:
                st.warning(
                    _t("paypal.draft_created", id=invoice_id,
                       error=invoice.get('detail') or invoice.get('error', _t('common.unknown')))
                )
                st.session_state["last_invoice_id"] = invoice_id
                if st.button(_t("paypal.retry_send"), key="retry_send_invoice"):
                    retry_result = retry_send_invoice(
                        invoice_id,
                        use_api=st.session_state.get("last_invoice_use_api", True),
                        lang=st.session_state.get("lang", "zh"),
                    )
                    st.session_state["last_invoice_result"] = retry_result
                    st.rerun()
            else:
                st.error(_t("paypal.create_failed", error=invoice.get('error', _t('common.unknown'))))
            mode = invoice.get("mode", "")
            if mode:
                st.caption(f"{_t('paypal.mode_label')}{mode}")
        else:
            inv_mode = invoice.get("mode", "DEMO")
            if inv_mode == "LIVE_SANDBOX":
                st.success(_t("paypal.success_live"))
                st.markdown("<span class='mode-live'>LIVE SANDBOX</span>", unsafe_allow_html=True)
            else:
                st.success(_t("paypal.success_demo"))
                st.markdown("<span class='mode-demo'>DEMO MODE</span>", unsafe_allow_html=True)

            invoice_amount = invoice.get("total", invoice.get("amount", 0.0))
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{_t('paypal.invoice_number')}**: {invoice.get('invoice_number', 'N/A')}")
                st.markdown(f"**{_t('paypal.payment_type_label')}**: {invoice.get('payment_type_name', 'N/A')}")
                st.markdown(f"**{_t('paypal.amount')}**: {format_amount(invoice_amount, invoice.get('currency', ''))}")
                st.markdown(f"**{_t('paypal.status_label')}**: {invoice.get('status', 'N/A')}")
            with col2:
                st.markdown(f"**{_t('paypal.buyer_label')}**: {invoice.get('buyer_name', 'N/A')}")
                st.markdown(f"**{_t('paypal.email_label')}**: {invoice.get('buyer_email', 'N/A')}")
                st.markdown(f"**{_t('paypal.contract_label')}**: {invoice.get('contract_id', 'N/A')}")

            st.markdown(_t("paypal.payment_link"))
            payment_url = invoice.get("payment_url", "") or invoice.get("recipient_view_url", "")
            if payment_url and inv_mode == "LIVE_SANDBOX":
                st.markdown(f"[{payment_url}]({payment_url})")
            elif payment_url:
                st.code(payment_url, language=None)
                st.caption(_t("paypal.mock_link_note"))
            else:
                st.info(_t("paypal.link_pending"))

            if inv_mode == "LIVE_SANDBOX":
                st.info(_t("paypal.live_payment_hint"))
            else:
                st.info(_t("paypal.demo_payment_hint"))
            st.session_state["last_invoice_id"] = invoice.get("invoice_id", "")

    # Payment operations
    st.markdown("---")
    st.markdown(_t("paypal.payment_ops_title"))

    last_invoice_id = st.session_state.get("last_invoice_id", "")
    last_use_api = st.session_state.get("last_invoice_use_api", False)
    invoice_id_to_pay = st.text_input(_t("paypal.invoice_id_input"), value=last_invoice_id, help=_t("paypal.invoice_id_help"))

    col1, col2 = st.columns(2)
    with col1:
        if st.button(_t("paypal.refresh_status"), use_container_width=True):
            if not invoice_id_to_pay:
                st.warning(_t("paypal.no_invoice_warning"))
            else:
                with st.spinner(_t("paypal.checking_status")):
                    status = check_payment_status(invoice_id_to_pay, use_api=last_use_api, lang=st.session_state.get("lang", "zh"))
                if status.get("success", False):
                    st.success(_t("paypal.current_status", status=status.get('status', 'UNKNOWN')))
                    if status.get("status") == "PAID":
                        st.markdown(f"**{_t('paypal.paid_at')}**: {status.get('paid_at', 'N/A')}")
                        st.markdown(f"**{_t('paypal.transaction_id')}**: {status.get('transaction_id', 'N/A')}")
                else:
                    st.error(_t("paypal.query_failed", error=status.get('error', _t('common.unknown'))))

    with col2:
        if st.button(_t("paypal.simulate_payment"), use_container_width=True, disabled=last_use_api):
            if not invoice_id_to_pay:
                st.warning(_t("paypal.no_invoice_warning"))
            elif last_use_api:
                st.info(_t("paypal.live_payment_note"))
            else:
                with st.spinner(_t("paypal.processing_payment")):
                    result = simulate_payment_demo(invoice_id_to_pay)
                if result.get("success"):
                    st.success(_t("paypal.payment_success"))
                    st.markdown(f"**{_t('paypal.transaction_id')}**: {result['transaction_id']}")
                    st.markdown(f"**{_t('paypal.amount')}**: {format_amount(result.get('amount', 0), result.get('currency', ''))}")
                    st.markdown(f"**{_t('paypal.paid_at_label')}**: {result['paid_at']}")
                    st.markdown(_t("paypal.next_actions_title"))
                    for action in result["next_actions"]:
                        st.markdown(f"- {action}")
                else:
                    st.error(_t("paypal.payment_failed", error=result.get('error', _t('common.unknown'))))

    # Invoice list
    st.markdown("---")
    st.markdown(_t("paypal.invoice_list_title"))
    invoices = list_invoices_demo()
    if invoices:
        df_invoices = pd.DataFrame([{
            _t("paypal.col_invoice_number"): inv.get("invoice_number", ""),
            _t("paypal.col_type"): inv.get("payment_type_name", ""),
            _t("paypal.col_buyer"): inv.get("buyer_name", ""),
            _t("paypal.col_amount"): format_amount(inv.get('total', inv.get('amount', 0)), inv.get('currency', '')),
            _t("paypal.col_status"): inv.get("status", ""),
            _t("paypal.col_created_at"): str(inv.get("created_at", ""))[:19],
        } for inv in invoices])
        st.dataframe(df_invoices, use_container_width=True)
        if st.button(_t("paypal.clear_invoices"), use_container_width=False):
            clear_invoices_demo()
            st.session_state["last_invoice_result"] = None
            st.session_state["last_invoice_id"] = ""
            st.rerun()
    else:
        st.info(_t("paypal.no_invoices"))

    # Webhooks section
    st.markdown("---")
    st.markdown(f"### {_t('paypal.webhook_title')}")
    st.caption(_t("paypal.webhook_desc"))

    webhook_handler = get_webhook_handler()

    col_webhook1, col_webhook2 = st.columns([2, 1])
    with col_webhook1:
        with st.expander(_t("paypal.webhook_config_title")):
            st.markdown(_t("paypal.webhook_config_step1"))
            st.markdown(_t("paypal.webhook_config_step2"))
            st.markdown(_t("paypal.webhook_config_step3"))
            st.info("modules/webhook_handler.py 已实现完整的签名验证和事件处理逻辑，生产环境部署为HTTP端点即可。" if st.session_state.get("lang", "zh") == "zh" else "modules/webhook_handler.py implements full signature verification and event handling. Deploy as an HTTP endpoint in production.")

    with col_webhook2:
        if st.button(_t("paypal.webhook_simulate"), key="simulate_webhook", type="primary"):
            # Get latest invoice for demo
            invoices = list_invoices_demo()
            if invoices:
                latest = invoices[-1]
                result = webhook_handler.simulate_invoice_paid_event(
                    invoice_id=latest.get("invoice_id", "DEMO"),
                    amount=latest.get("total", latest.get("amount", 0)),
                    currency=latest.get("currency", "USD"),
                    invoice_number=latest.get("invoice_number", "DEMO-001"),
                )
                st.session_state["last_webhook_result"] = result
            else:
                result = webhook_handler.simulate_invoice_paid_event(
                    invoice_id="DEMO-INV-001",
                    amount=500.0,
                    currency="USD",
                    invoice_number="DEMO-001",
                )
                st.session_state["last_webhook_result"] = result

    if "last_webhook_result" in st.session_state:
        result = st.session_state["last_webhook_result"]
        if result.get("auto_triggered"):
            st.success(_t("paypal.webhook_auto_triggered"))
            st.markdown(f"**{_t('paypal.payment_status')}**: PAID")
            st.markdown(f"**{_t('paypal.amount')}**: {result.get('currency', 'USD')} {result.get('amount', '0')}")
            st.markdown("**Auto-triggered actions:**")
            for action in result.get("actions", []):
                st.markdown(f"- {action}")

    # Webhook event log
    st.markdown(f"#### {_t('paypal.webhook_event_log')}")
    event_log = webhook_handler.get_event_log()
    if event_log:
        df_events = pd.DataFrame(event_log)
        st.dataframe(df_events, use_container_width=True)
    else:
        st.info(_t("paypal.webhook_no_events"))


# ============================================================
# Page 5: Customer Notifications
# ============================================================

elif page == _t("sidebar.page_notification"):
    st.title(_t("notification.title"))
    st.markdown(_t("notification.subtitle"))
    st.warning(_t("notification.demo_warning"))
    st.caption(_t("notification.demo_caption"))

    mode = st.radio(
        _t("notification.mode_label"),
        [_t("notification.mode_single"), _t("notification.mode_workflow")],
        horizontal=True,
    )

    if mode == _t("notification.mode_single"):
        col1, col2 = st.columns(2)
        with col1:
            notification_type = st.selectbox(
                _t("notification.type_label"),
                options=[
                    ("market_alert", _t("notification.type_market")),
                    ("contract_ready", _t("notification.type_contract")),
                    ("payment_request", _t("notification.type_payment")),
                    ("payment_confirmed", _t("notification.type_confirmed")),
                    ("shipping_notice", _t("notification.type_shipping")),
                    ("delivery_confirmation", _t("notification.type_delivery")),
                    ("after_sales", _t("notification.type_after_sales")),
                ],
                format_func=lambda x: x[1],
            )
            customer_name = st.text_input(_t("notification.customer_name"), value="Shanghai Construction Materials Co., Ltd.")
            company_name = st.text_input(_t("notification.company_name"), value="TradePilot AI Trading Co., Ltd.")
        with col2:
            if notification_type[0] == "market_alert":
                product = st.text_input(_t("notification.product"), value="Ferrous metals commodities")
                signal_name = st.text_input(_t("notification.signal_name"), value="Cold-rolled vs Rebar spread")
                direction = st.text_input(_t("notification.signal_direction"), value="Converging")
                probability = st.number_input(_t("notification.probability"), value=60.0, min_value=0.0, max_value=100.0)
                confidence = st.text_input(_t("notification.confidence"), value=_t("common.high"))
                z_value = st.number_input("z-score", value=1.23)
                extra_vars = {
                    "product": product, "signal_name": signal_name,
                    "direction": direction, "probability": probability,
                    "confidence": confidence, "z_value": z_value,
                    "reasons": "Current spread deviates from historical mean, possibility of mean reversion (demo data).",
                    "date": "2026-10-05",
                }
            elif notification_type[0] == "contract_ready":
                contract_id = st.text_input(_t("notification.contract_id"), value="GM20260915001")
                total_issues = st.number_input(_t("notification.total_issues"), value=3)
                high_count = st.number_input(_t("notification.high_risk"), value=1)
                medium_count = st.number_input(_t("notification.medium_risk"), value=2)
                low_count = st.number_input(_t("notification.low_risk"), value=0)
                extra_vars = {
                    "contract_id": contract_id, "total_issues": int(total_issues),
                    "high_count": int(high_count), "medium_count": int(medium_count),
                    "low_count": int(low_count),
                    "issues_summary": "Main issues: missing quality acceptance clause (high risk), penalty ratio not specified (medium risk).",
                    "date": "2026-10-05",
                }
            elif notification_type[0] == "payment_request":
                payment_type_name = st.text_input(_t("notification.payment_type"), value="Small trial order payment")
                amount = st.number_input(_t("paypal.amount"), value=18250.00)
                currency = st.text_input(_t("notification.currency"), value="CNY")
                invoice_number = st.text_input(_t("notification.invoice_number"), value="TP-20261005-0001")
                contract_id = st.text_input(_t("notification.contract_id"), value="GM20260915001")
                payment_url = st.text_input(
                    _t("notification.payment_url"),
                    value="https://www.sandbox.paypal.com/invoice/payerView/details/INV-DEMO",
                )
                extra_vars = {
                    "payment_type_name": payment_type_name, "amount": amount,
                    "currency": currency, "invoice_number": invoice_number,
                    "contract_id": contract_id, "payment_url": payment_url,
                    "note": "First collaboration small trial order, using PayPal secure payment channel, traceable transaction.",
                    "date": "2026-10-05",
                }
            elif notification_type[0] == "payment_confirmed":
                amount = st.number_input(_t("paypal.amount"), value=18250.00)
                currency = st.text_input(_t("notification.currency"), value="CNY")
                invoice_number = st.text_input(_t("notification.invoice_number"), value="TP-20261005-0001")
                payment_type_name = st.text_input(_t("notification.payment_type"), value="Small trial order payment")
                transaction_id = st.text_input(_t("notification.transaction_id"), value="TXN-DEMO123456")
                paid_at = st.text_input(_t("notification.paid_at"), value="2026-10-05 16:30")
                extra_vars = {
                    "amount": amount, "currency": currency,
                    "invoice_number": invoice_number, "payment_type_name": payment_type_name,
                    "transaction_id": transaction_id, "paid_at": paid_at,
                    "next_actions": "1. Production will send payment confirmation notification\n2. Production will notify warehouse to prepare goods\n3. Production will update transaction record",
                    "date": "2026-10-05",
                }
            elif notification_type[0] == "shipping_notice":
                contract_id = st.text_input(_t("notification.contract_id"), value="GM20260915001")
                product_name = st.text_input(_t("notification.product_name"), value="Hot-rolled ribbed steel bar HRB400E Φ16mm")
                quantity = st.text_input(_t("notification.quantity"), value="50 tons")
                ship_date = st.text_input(_t("notification.ship_date"), value="2026-10-06")
                estimated_arrival = st.text_input(_t("notification.estimated_arrival"), value="2026-10-09")
                logistics_company = st.text_input(_t("notification.logistics_company"), value="SF Logistics")
                tracking_number = st.text_input(_t("notification.tracking_number"), value="SF1234567890")
                extra_vars = {
                    "contract_id": contract_id, "product_name": product_name,
                    "quantity": quantity, "ship_date": ship_date,
                    "estimated_arrival": estimated_arrival,
                    "logistics_company": logistics_company, "tracking_number": tracking_number,
                    "quality_objection_days": "7",
                    "date": "2026-10-06",
                }
            elif notification_type[0] == "delivery_confirmation":
                contract_id = st.text_input(_t("notification.contract_id"), value="GM20260915001")
                estimated_arrival = st.text_input(_t("notification.estimated_arrival_date"), value="2026-10-09")
                extra_vars = {
                    "contract_id": contract_id,
                    "estimated_arrival": estimated_arrival,
                    "quality_objection_days": "7",
                    "date": "2026-10-09",
                }
            else:
                contract_id = st.text_input(_t("notification.contract_id"), value="GM20260915001")
                product_name = st.text_input(_t("notification.product_name"), value="Hot-rolled ribbed steel bar HRB400E Φ16mm")
                quantity = st.text_input(_t("notification.quantity"), value="50 tons")
                amount = st.number_input(_t("paypal.amount"), value=18250.00)
                currency = st.text_input(_t("notification.currency"), value="CNY")
                completion_date = st.text_input(_t("notification.completion_date"), value="2026-10-16")
                extra_vars = {
                    "contract_id": contract_id, "product_name": product_name,
                    "quantity": quantity, "amount": amount, "currency": currency,
                    "completion_date": completion_date,
                    "date": "2026-10-16",
                }

        if st.button(_t("notification.generate"), type="primary", use_container_width=True):
            result = generate_notification(
                notification_type[0],
                lang=st.session_state.get("lang", "zh"),
                customer_name=customer_name,
                company_name=company_name,
                **extra_vars,
            )
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(_t("notification.generated"))
                st.markdown(f"**{_t('notification.subject_label')}**: {result['subject']}")
                st.markdown(f"**{_t('notification.body_label')}**:")
                st.text_area(_t("notification.content_label"), value=result["body"], height=400)

    else:
        st.markdown(_t("notification.workflow_title"))
        st.markdown(_t("notification.workflow_desc"))

        col1, col2 = st.columns(2)
        with col1:
            customer_name = st.text_input(_t("notification.customer_name"), value="Shanghai Construction Materials Co., Ltd.", key="wf_customer")
            contract_id = st.text_input(_t("notification.contract_id"), value="GM20260915001", key="wf_contract")
            product_name = st.text_input(_t("notification.product_name"), value="Hot-rolled ribbed steel bar HRB400E Φ16mm", key="wf_product")
        with col2:
            quantity = st.text_input(_t("notification.quantity"), value="50 tons (trial)", key="wf_quantity")
            amount = st.number_input(_t("paypal.amount"), value=18250.00, key="wf_amount")
            currency = st.text_input(_t("notification.currency"), value="CNY", key="wf_currency")
            company_name = st.text_input(_t("notification.company_name"), value="TradePilot AI Trading Co., Ltd.", key="wf_company")

        if st.button(_t("notification.generate_workflow"), type="primary", use_container_width=True):
            with st.spinner(_t("notification.generating")):
                notifications = generate_trade_workflow_notifications(
                    customer_name=customer_name,
                    contract_id=contract_id,
                    product_name=product_name,
                    quantity=quantity,
                    amount=amount,
                    currency=currency,
                    company_name=company_name,
                    lang=st.session_state.get("lang", "zh"),
                )

            st.success(_t("notification.workflow_success", count=len(notifications)))

            for i, notif in enumerate(notifications, 1):
                with st.expander(f"{_t('notification.notif_index', i=i)} {notif['type_name']} - {notif['subject'][:40]}...", expanded=(i == 1)):
                    st.markdown(f"**{_t('notification.subject_label')}**: {notif['subject']}")
                    st.markdown(f"**{_t('notification.body_label')}**:")
                    st.text_area(f"{_t('notification.content_label')}_{i}", value=notif["body"], height=300, key=f"notif_{i}")


# ============================================================
# Footer
# ============================================================

st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #999; font-size: 0.85rem;'>"
    f"{_t('footer.text')}"
    "</div>",
    unsafe_allow_html=True,
)
