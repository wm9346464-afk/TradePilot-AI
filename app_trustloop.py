"""TradePilot TrustLoop - v0 deterministic Deal Room."""

from __future__ import annotations

import html
import json
import os
import sqlite3
from uuid import uuid4

import streamlit as st

from modules.config import (
    is_llm_config_dict_valid,
    is_llm_config_valid,
    load_config,
)
from modules.trustloop.service import build_runtime_service, demo_deal_input
from modules.trustloop.enums import DealState
from modules.trustloop.evidence import (
    EVENT_COLUMNS,
    MILESTONE_COLUMNS,
    event_rows,
    exposure_bar_html,
    exposure_summary,
    milestone_rows,
    to_frame,
)
from modules.trustloop.security import (
    InMemoryRateLimiter,
    RateLimitExceeded,
    is_safe_paypal_payment_url,
)
from modules.trustloop.agent.executor import AgentToolExecutor
from modules.trustloop.passport_export import render_passport_html
from modules.trustloop.replay import parse_run_bundle_bytes
from modules.trustloop.ui_i18n import ui_text


def _query_value(name: str) -> str:
    value = st.query_params.get(name)
    if isinstance(value, (list, tuple)):
        return str(value[0]).strip() if value else ""
    return str(value or "").strip()


_GRID_WIDTHS = {
    "stage": 70,
    "status": 116,
    "milestone": 200,
    "amount": 132,
    "approved": 132,
    "approved_by": 146,
    "invoice": 152,
    "transaction": 214,
    "unlock_condition": 260,
    "sequence": 70,
    "event_type": 216,
    "actor": 236,
    "detail": 320,
    "hash": 172,
    "at": 178,
}



def _render_evidence_grid(
    frame,
    columns,
    *,
    height: int,
    quick_filter: str = "",
    status_column: str | None = None,
) -> None:
    """Render one AG Grid table, degrading to a plain dataframe without the component."""

    try:
        from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
    except Exception:
        st.dataframe(frame, use_container_width=True, hide_index=True)
        return

    builder = GridOptionsBuilder.from_dataframe(frame)
    builder.configure_default_column(
        sortable=True, filter=True, resizable=True, headerClass="tp-grid-header"
    )
    builder.configure_grid_options(quickFilterText=quick_filter, suppressSizeToFit=False)
    for field, header in columns.items():
        options = {
            "header_name": header,
            "width": _GRID_WIDTHS.get(field, 168),
        }
        if status_column and field == status_column:
            options["cellStyle"] = {"fontWeight": "700"}
        elif field in {"stage", "sequence"}:
            options["pinned"] = "left"
        builder.configure_column(field, **options)

    AgGrid(
        frame,
        gridOptions=builder.build(),
        height=height,
        theme="streamlit",
        fit_columns_on_grid_load=False,
        update_mode=GridUpdateMode.NO_UPDATE,
        key=f"evidence-{status_column or 'grid'}-{len(frame)}",
    )


def _llm_runtime() -> tuple[bool, dict | None]:
    """A visitor key wins; otherwise the deployment's own configuration applies."""

    visitor_config = st.session_state.get("trustloop_llm_config")
    if visitor_config:
        return True, visitor_config
    env_enabled = os.getenv("TRUSTLOOP_USE_LLM", "true").strip().lower() != "false"
    return env_enabled, None


def _open_deal_room_button() -> None:
    if st.button("Open the Deal Room", use_container_width=True):
        st.query_params.clear()
        st.rerun()


def _render_public_verification(passport_id: str) -> None:
    st.markdown(
        """
<style>
.stApp { background: #f5f8fc; }
.block-container { max-width: 980px; padding-top: 3rem; }
.verify-hero { background: linear-gradient(135deg, #003087, #0070ba);
  color: white; border-radius: 18px; padding: 26px 30px; margin-bottom: 20px; }
.verify-hero h1 { color: white; margin: 0; }
</style>
<div class="verify-hero">
  <h1>Public Trust Passport Verification</h1>
  <p>Server-side verification of the stored run, approvals, paid settlements and audit hash chain.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    try:
        service = build_runtime_service(paypal_backend="fake", use_llm=False)
    except Exception:
        st.error("The public verifier is unavailable. Its trusted store could not be opened.")
        _open_deal_room_button()
        return
    if service.store is None:
        st.error(
            "Public verification is unavailable because TRUSTLOOP_STORE_PATH is not configured."
        )
        _open_deal_room_button()
        return
    try:
        run = service.find_run_by_passport(passport_id)
    except Exception:
        st.error("The stored Passport or audit chain could not be verified safely.")
        _open_deal_room_button()
        return
    if run is None or run.passport is None:
        st.error("Passport not found in this verifier's trusted store.")
        _open_deal_room_button()
        return

    try:
        verification = service.verify_trust_passport(run.run_id)
    except Exception:
        st.error("The stored Passport or audit chain could not be verified safely.")
        _open_deal_room_button()
        return
    passport = run.passport
    if verification.valid:
        st.success("VALID: the stored Passport and complete audit chain agree.")
    else:
        st.error(f"INVALID: {verification.message}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Risk decision", passport.risk_summary.decision.value)
    col2.metric("Paid milestones", len(passport.settlements))
    col3.metric("Human approvals", len(passport.approvals))
    col4.metric("Mode", passport.mode.value)
    st.caption(
        f"Passport {passport.passport_id} · run {passport.run_id} · issued "
        f"{passport.issued_at.isoformat()}"
    )

    st.markdown("### Verified payment evidence")
    for settlement in passport.settlements:
        st.markdown(
            f"**{html.escape(settlement.invoice_number or settlement.invoice_id)}** · "
            f"{settlement.amount.format()} · **{html.escape(settlement.status)}**"
        )
        st.caption(f"Transaction: {settlement.transaction_id or 'N/A'}")

    if run.agent_proposal:
        proposal = run.agent_proposal
        st.markdown("### Agent decision evidence")
        st.markdown(
            f"**Planner:** {html.escape(proposal.planner_type)} · "
            f"**Decision:** {html.escape(proposal.decision)} · "
            f"**Confidence:** {proposal.confidence}"
        )
        st.caption(
            "Requested tools: "
            + ", ".join(item.tool_name for item in proposal.requested_tools)
        )
    negotiation = service.get_negotiation(run.run_id)
    if negotiation:
        st.markdown("### Buyer / Seller negotiation")
        st.write(negotiation.summary)

    with st.expander("Verification checks"):
        st.json(verification.checks)
    st.download_button(
        "Download verified Passport JSON",
        data=json.dumps(passport.model_dump(mode="json"), indent=2, ensure_ascii=False),
        file_name=f"{passport.passport_id}.json",
        mime="application/json",
        use_container_width=True,
    )
    _open_deal_room_button()


def _load_linked_run(run_id: str):
    use_llm, llm_config = _llm_runtime()
    service = build_runtime_service(
        paypal_backend=os.getenv("TRUSTLOOP_PAYPAL_BACKEND", "fake"),
        use_llm=use_llm,
        llm_config=llm_config,
    )
    run = service.get_run(run_id)
    return service, run, service.get_audit_events(run_id)


def _complete_after_payment(service, run):
    return service.advance_after_payment(run.run_id)


def _plan_failure_message(exc: Exception, language: str = "en") -> str:
    """Explain a planning failure without leaking driver internals."""

    if isinstance(exc, sqlite3.OperationalError) or "unable to open database file" in str(exc):
        if language == "zh":
            return (
                "演示用的本地存储无法打开：把 TRUSTLOOP_STORE_PATH 指向可写路径，"
                "或留空改用内存演示。"
            )
        return (
            "The demo store could not be opened. Point TRUSTLOOP_STORE_PATH at a "
            "writable path, or leave it empty to run the in-memory demo."
        )
    if language == "zh":
        return f"信任阶梯未能生成：{type(exc).__name__}: {exc}"
    return f"The Trust Ladder could not be built: {type(exc).__name__}: {exc}"


def _render_stepper(milestones) -> str:
    """Render the trust ladder as a row of stage cards with explicit status."""

    cards = []
    for item in milestones:
        status = item.status.value
        card_class = {"PAID": "is-paid", "READY": "is-ready"}.get(status, "is-locked")
        status_class = {"PAID": "tp-paid", "READY": "tp-ready"}.get(status, "tp-locked")
        cards.append(
            f'<div class="tp-step {card_class}">'
            f'<div class="tp-step-head">'
            f'<span class="tp-step-name">{item.sequence}. {html.escape(item.name)}</span>'
            f'<span class="tp-status {status_class}">{html.escape(status)}</span>'
            f"</div>"
            f'<div class="tp-step-amount">{item.amount.format()}</div>'
            f'<div class="tp-step-meta">{html.escape(item.unlock_condition)}</div>'
            f"</div>"
        )
    return '<div class="tp-steps">' + "".join(cards) + "</div>"


st.set_page_config(
    page_title="TradePilot TrustLoop",
    page_icon="TP",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_config()
public_passport_id = _query_value("verify")
if public_passport_id:
    _render_public_verification(public_passport_id)
    st.stop()

if "trustloop_lang" not in st.session_state:
    st.session_state["trustloop_lang"] = "en"
with st.sidebar:
    st.radio(
        "Language / 语言",
        ["en", "zh"],
        key="trustloop_lang",
        format_func=lambda code: "English" if code == "en" else "中文",
        horizontal=True,
    )
language = st.session_state.get("trustloop_lang", "en")


def tx(key: str, **values) -> str:
    return ui_text(key, language, **values)


app_password = os.getenv("APP_PASSWORD", "")
if app_password and not st.session_state.get("trustloop_authenticated", False):
    st.markdown("### TradePilot TrustLoop")
    st.caption(tx("access_protected"))
    entered_password = st.text_input(tx("access_input"), type="password")
    if entered_password != app_password:
        st.info(tx("access_info"))
        st.stop()
    st.session_state["trustloop_authenticated"] = True

if (
    os.getenv("TRUSTLOOP_PAYPAL_BACKEND", "fake").strip().lower()
    not in {"fake", "demo"}
    and not app_password
):
    st.error(
        "Live payment backends require APP_PASSWORD when the app is exposed to other users."
    )
    st.stop()

if "trustloop_session_key" not in st.session_state:
    st.session_state["trustloop_session_key"] = uuid4().hex
if "trustloop_rate_limiter" not in st.session_state:
    st.session_state["trustloop_rate_limiter"] = {
        "llm": InMemoryRateLimiter(max_calls=10, window_seconds=3600),
        "financial": InMemoryRateLimiter(max_calls=12, window_seconds=3600),
        "status": InMemoryRateLimiter(max_calls=60, window_seconds=3600),
        "negotiation": InMemoryRateLimiter(max_calls=20, window_seconds=3600),
    }
rate_limiter = st.session_state["trustloop_rate_limiter"]

linked_run_id = _query_value("run_id")
if linked_run_id and "trustloop_run" not in st.session_state:
    try:
        linked_service, linked_run, linked_events = _load_linked_run(linked_run_id)
    except Exception as exc:
        st.warning(f"Saved run could not be resumed: {type(exc).__name__}: {exc}")
    else:
        st.session_state["trustloop_service"] = linked_service
        st.session_state["trustloop_run"] = linked_run
        st.session_state["trustloop_events"] = linked_events
        st.session_state.pop("trustloop_negotiation", None)
        st.session_state["trustloop_replay"] = False

with st.sidebar:
    st.markdown(f"### {tx('demo_controls')}")
    st.caption(tx("safe_controls"))
    if not os.getenv("TRUSTLOOP_STORE_PATH", "").strip():
        st.caption(tx("store_required"))
    if st.button(tx("reset"), use_container_width=True):
        for key in (
            "trustloop_service",
            "trustloop_run",
            "trustloop_events",
            "trustloop_negotiation",
            "trustloop_replay",
        ):
            st.session_state.pop(key, None)
        st.query_params.clear()
        st.rerun()
    saved_run_id = st.text_input(
        tx("saved_run"),
        placeholder=tx("saved_run_placeholder"),
        help=tx("saved_run_help"),
    )
    if st.button(tx("resume_run"), use_container_width=True):
        if not saved_run_id.strip():
            st.warning(tx("enter_run"))
        else:
            try:
                saved_service, saved_run, saved_events = _load_linked_run(saved_run_id.strip())
            except Exception as exc:
                st.error(f"Run could not be resumed: {type(exc).__name__}: {exc}")
            else:
                st.session_state["trustloop_service"] = saved_service
                st.session_state["trustloop_run"] = saved_run
                st.session_state["trustloop_events"] = saved_events
                st.session_state.pop("trustloop_negotiation", None)
                st.session_state["trustloop_replay"] = False
                st.query_params["run_id"] = saved_run.run_id
                st.rerun()
    passport_lookup_id = st.text_input(
        tx("passport_lookup"),
        placeholder=tx("passport_placeholder"),
        help=tx("passport_lookup_help"),
    )
    if st.button(tx("open_verify"), use_container_width=True):
        if passport_lookup_id.strip():
            st.query_params["verify"] = passport_lookup_id.strip()
            st.rerun()
        else:
            st.warning(tx("enter_passport"))
    uploaded_bundle = st.file_uploader(
        tx("replay_upload"),
        type=["json"],
        help=tx("replay_help"),
    )
    if uploaded_bundle and st.button(tx("open_replay"), use_container_width=True):
        try:
            bundle = parse_run_bundle_bytes(uploaded_bundle.getvalue())
            replay_service = build_runtime_service(paypal_backend="fake", use_llm=False)
            replay_run = replay_service.restore_run_bundle(bundle)
            if replay_run.state != DealState.PASSPORT_ISSUED:
                st.error(tx("replay_only"))
            else:
                st.session_state["trustloop_service"] = replay_service
                st.session_state["trustloop_run"] = replay_run
                st.session_state["trustloop_events"] = replay_service.get_audit_events(replay_run.run_id)
                st.session_state.pop("trustloop_negotiation", None)
                st.session_state["trustloop_replay"] = True
                st.rerun()
        except Exception as exc:
            st.error(f"Replay bundle rejected: {type(exc).__name__}: {exc}")
    st.markdown(f"### {tx('quick_start')}")
    st.markdown(tx("quick_start_steps"))
    st.markdown(f"### {tx('active_mode')}")
    visitor_llm = st.session_state.get("trustloop_llm_config")
    if visitor_llm:
        llm_mode_label = tx(
            "llm_source_visitor", model=visitor_llm.get("model_name", "")
        )
    elif is_llm_config_valid():
        llm_mode_label = tx("llm_source_env")
    else:
        llm_mode_label = tx("llm_source_off")
    st.caption(
        f"PayPal: {os.getenv('TRUSTLOOP_PAYPAL_BACKEND', 'fake')}\n"
        f"LLM: {llm_mode_label}\n"
        f"FX: {os.getenv('FX_PROVIDER', 'fixture')}"
    )

    with st.expander(tx("llm_panel_label"), expanded=False):
        st.caption(tx("llm_privacy"))
        visitor_url = st.text_input(
            tx("llm_api_url"),
            value="https://api.deepseek.com/chat/completions",
            key="trustloop_llm_url_input",
        )
        visitor_model = st.text_input(
            tx("llm_model"),
            value="deepseek-chat",
            key="trustloop_llm_model_input",
        )
        visitor_key = st.text_input(
            tx("llm_api_key"),
            type="password",
            key="trustloop_llm_key_input",
        )
        apply_col, clear_col = st.columns(2)
        if apply_col.button(tx("llm_apply"), use_container_width=True):
            candidate = {
                "api_url": visitor_url.strip(),
                "model_name": visitor_model.strip(),
                "api_key": visitor_key.strip(),
            }
            if is_llm_config_dict_valid(candidate):
                st.session_state["trustloop_llm_config"] = candidate
                st.success(tx("llm_applied"))
            else:
                st.error(tx("llm_invalid"))
        if clear_col.button(tx("llm_clear"), use_container_width=True):
            st.session_state.pop("trustloop_llm_config", None)
            st.session_state["trustloop_llm_key_input"] = ""
            st.info(tx("llm_cleared"))

st.markdown(
    """
<style>
    :root {
        --pp-blue: #0070ba;
        --pp-blue-dark: #003087;
        --pp-ink: #111827;
        --pp-muted: #667085;
        --pp-border: #d9e2ec;
        --pp-panel: #ffffff;
        --pp-bg: #f5f8fc;
        --pp-good: #087443;
        --pp-warn: #b54708;
        --pp-danger: #b42318;
    }
    .stApp { background: var(--pp-bg); }
    .block-container { max-width: 1380px; padding-top: 2rem; }
    .tp-hero {
        background: linear-gradient(135deg, #003087 0%, #0070ba 70%, #009cde 100%);
        color: white; border-radius: 20px; padding: 28px 32px; margin-bottom: 20px;
    }
    .tp-hero h1 { color: white; margin: 0 0 8px 0; font-size: 2.25rem; }
    .tp-hero p { color: #eaf4ff; max-width: 850px; margin: 0; line-height: 1.55; }
    .tp-badge {
        display: inline-block; border-radius: 999px; padding: 5px 11px;
        font-size: 0.78rem; font-weight: 700; margin-right: 6px;
    }
    .tp-live { background: #e8f5ee; color: var(--pp-good); }
    .tp-demo { background: #fff3e8; color: var(--pp-warn); }
    .tp-card {
        background: var(--pp-panel); border: 1px solid var(--pp-border);
        border-radius: 16px; padding: 18px 20px; margin-bottom: 14px;
        box-shadow: 0 5px 20px rgba(16, 24, 40, 0.04);
    }
    .tp-card h3 { color: var(--pp-blue-dark); margin-top: 0; }
    .tp-muted { color: var(--pp-muted); font-size: 0.9rem; }
    .tp-money { font-size: 1.55rem; font-weight: 800; color: var(--pp-blue-dark); }
    .tp-arrow { color: var(--pp-muted); font-size: 1.25rem; padding: 0 8px; }
    .tp-milestone {
        border: 1px solid var(--pp-border); border-radius: 14px;
        padding: 12px 14px; margin-bottom: 10px; background: white;
    }
    .tp-status { font-weight: 700; font-size: 0.82rem; }
    .tp-ready { color: var(--pp-blue); }
    .tp-paid { color: var(--pp-good); }
    .tp-locked { color: var(--pp-muted); }
    .tp-event {
        border-left: 3px solid var(--pp-blue); padding: 8px 12px;
        margin-left: 5px; background: #f8fbff;
    }
    .tp-section {
        color: var(--pp-blue-dark); font-size: 1.18rem; font-weight: 800;
        margin: 26px 0 10px 0; letter-spacing: 0.01em;
    }
    .tp-steps { display: flex; gap: 12px; margin: 4px 0 10px 0; }
    .tp-step {
        flex: 1 1 0; background: var(--pp-panel); border: 1px solid var(--pp-border);
        border-radius: 14px; padding: 14px 16px;
        box-shadow: 0 4px 16px rgba(16, 24, 40, 0.05);
    }
    .tp-step-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; }
    .tp-step-name { font-weight: 700; color: var(--pp-ink); font-size: 0.95rem; }
    .tp-step-amount { font-size: 1.2rem; font-weight: 800; color: var(--pp-blue-dark); margin-top: 8px; }
    .tp-step-meta { color: var(--pp-muted); font-size: 0.8rem; margin-top: 6px; line-height: 1.35; }
    .tp-step.is-paid { border-color: #b7dfc9; box-shadow: inset 0 3px 0 var(--pp-good), 0 4px 16px rgba(16, 24, 40, 0.05); }
    .tp-step.is-ready { border-color: #b9d8f2; box-shadow: inset 0 3px 0 var(--pp-blue), 0 4px 16px rgba(16, 24, 40, 0.05); }
    .tp-step.is-locked { opacity: 0.72; }
    .tp-exp-bar { display: flex; height: 14px; border-radius: 999px; overflow: hidden;
        background: #e8eef6; margin: 10px 0 8px 0; }
    .tp-exp-seg { display: block; height: 100%; }
    .tp-exp-settled { background: var(--pp-good); }
    .tp-exp-approved { background: var(--pp-blue); }
    .tp-exp-open { background: #cfd8e3; }
    .tp-exp-legend { display: flex; gap: 18px; font-size: 12px; color: var(--pp-muted);
        margin-bottom: 8px; flex-wrap: wrap; }
    .tp-exp-dot { display: inline-block; width: 9px; height: 9px; border-radius: 2px; margin-right: 6px; }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="tp-hero">
  <h1>TradePilot TrustLoop</h1>
  <p>""" + html.escape(tx("hero_subtitle")) + """</p>
</div>
""",
    unsafe_allow_html=True,
)

configured_backend = os.getenv("TRUSTLOOP_PAYPAL_BACKEND", "fake").strip().upper()
invoice_currency_options = ["USD", "EUR"]
existing_run_for_currency = st.session_state.get("trustloop_run")
if existing_run_for_currency and existing_run_for_currency.plan:
    st.session_state["trustloop_invoice_currency"] = (
        existing_run_for_currency.plan.settlement_plan.invoice_currency
    )
if "trustloop_invoice_currency" not in st.session_state:
    st.session_state["trustloop_invoice_currency"] = "USD"
backend_badge = (
    '<span class="tp-badge tp-live">PAYPAL SANDBOX / REST</span>'
    if configured_backend == "REST"
    else '<span class="tp-badge tp-demo">DEMO / FAKE PAYPAL</span>'
)
if st.session_state.get("trustloop_replay", False):
    backend_badge = '<span class="tp-badge tp-live">REPLAY / READ-ONLY</span>'
st.markdown(
    backend_badge
    + (
        '<span class="tp-badge tp-demo">CNY contract → '
        + st.session_state["trustloop_invoice_currency"]
        + " invoice</span>"
    )
    + f'<span class="tp-badge tp-demo">{html.escape(tx("human_badge"))}</span>',
    unsafe_allow_html=True,
)
if configured_backend == "REST":
    st.info(tx("rest_info"))
else:
    st.warning(tx("fake_warning"))

left, right = st.columns([4, 1])
with left:
    st.markdown(f"### {tx('main_heading')}")
    st.caption(tx("main_caption"))
    selected_invoice_currency = st.selectbox(
        tx("currency_label"),
        invoice_currency_options,
        key="trustloop_invoice_currency",
        help=tx("currency_help"),
    )
with right:
    run_demo = st.button(tx("review_button"), type="primary", use_container_width=True)

if run_demo:
    try:
        rate_limiter["llm"].check("review_and_plan")
    except RateLimitExceeded as exc:
        st.error(str(exc))
        st.stop()
    with st.spinner(tx("review_spinner")):
        try:
            use_llm, llm_config = _llm_runtime()
            service = build_runtime_service(
                paypal_backend=os.getenv("TRUSTLOOP_PAYPAL_BACKEND", "fake"),
                use_llm=use_llm,
                llm_config=llm_config,
            )
            run = service.start_case(demo_deal_input())
            from modules.contract_checker import SAMPLE_CONTRACT

            run = service.review_contract(run.run_id, SAMPLE_CONTRACT, use_ai=False)
            run = service.propose_plan(
                run.run_id,
                invoice_currency=selected_invoice_currency,
            )
        except Exception as exc:
            st.error(_plan_failure_message(exc, language))
            st.stop()
        events = service.get_audit_events(run.run_id)
        st.session_state["trustloop_service"] = service
        st.session_state["trustloop_run"] = run
        st.session_state["trustloop_events"] = events
        st.session_state.pop("trustloop_negotiation", None)
        st.session_state["trustloop_replay"] = False
        st.query_params["run_id"] = run.run_id

run = st.session_state.get("trustloop_run")
events = st.session_state.get("trustloop_events", [])

if not run:
    st.markdown(
        """
<div class="tp-card">
  <h3>{title}</h3>
  <p>{step1}</p>
  <p>{step2}</p>
  <p>{step3}</p>
  <p>{step4}</p>
  <p>{step5}</p>
</div>
""".format(
            title=html.escape(tx("what_title")),
            step1=html.escape(tx("what_1")),
            step2=html.escape(tx("what_2")),
            step3=html.escape(tx("what_3")),
            step4=html.escape(tx("what_4")),
            step5=html.escape(tx("what_5")),
        ),
        unsafe_allow_html=True,
    )
    st.stop()

service = st.session_state.get("trustloop_service")
backend_name = service.paypal_gateway.backend_name if service else "FAKE"

milestones = run.plan.milestones if run.plan else []
paid_count = sum(item.status.value == "PAID" for item in milestones)
st.markdown(f"### {tx('progress')}")
if milestones:
    st.markdown(_render_stepper(milestones), unsafe_allow_html=True)
st.caption(
    tx("progress_text", paid=paid_count, total=len(milestones))
    + (tx("passport_suffix") if run.passport else "")
)
if run.state == DealState.AWAITING_APPROVAL and run.active_milestone_id:
    next_action = tx("next_approval")
elif run.state in {DealState.INVOICE_CREATING, DealState.INVOICE_CREATED}:
    next_action = tx("next_resume")
elif run.state == DealState.AWAITING_PAYMENT:
    next_action = (
        tx("next_sandbox")
        if backend_name != "FAKE"
        else tx("next_fake")
    )
elif run.state in {DealState.PAYMENT_CONFIRMED, DealState.MILESTONE_COMPLETED}:
    next_action = tx("next_finalize")
elif run.state == DealState.PASSPORT_ISSUED:
    next_action = tx("next_complete")
else:
    next_action = tx("next_continue")
st.info(next_action)

if run.state == DealState.AWAITING_APPROVAL and run.plan and service:
    active = next(
        (
            item
            for item in run.plan.milestones
            if item.milestone_id == run.active_milestone_id
        ),
        None,
    )
    if active:
        st.markdown(
            f"""<div class="tp-card">
            <h3>{html.escape(tx('approval_title'))}</h3>
            <p><strong>{html.escape(tx('stage', sequence=active.sequence, name=active.name))}</strong></p>
            <p>{html.escape(tx('amount'))} <strong>{active.amount.format()}</strong></p>
            <p class="tp-muted">{html.escape(tx('approval_desc'))}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button(
            (
                tx("approve_fake", sequence=active.sequence)
                if backend_name == "FAKE"
                else tx("approve_rest", sequence=active.sequence)
            ),
            type="primary",
            use_container_width=True,
        ):
            try:
                rate_limiter["financial"].check("approve_stage")
                with st.spinner(tx("approval_spinner")):
                    run = service.approve_plan(run.run_id)
                    run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
                    if backend_name == "FAKE":
                        run = service.simulate_payment(run.run_id)
                        run = _complete_after_payment(service, run)
            except Exception as exc:
                st.error(tx("stage_error", error=f"{type(exc).__name__}: {exc}"))
                st.session_state["trustloop_run"] = service.reload_run(run.run_id)
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
            else:
                st.session_state["trustloop_run"] = run
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
                st.rerun()

if run.state in {
    DealState.PAYMENT_CONFIRMED,
    DealState.MILESTONE_COMPLETED,
} and service:
    st.warning(tx("next_finalize"))
    if st.button(tx("resume_progression"), type="primary", use_container_width=True):
        try:
            rate_limiter["status"].check("resume_progression")
            with st.spinner(tx("progression_spinner")):
                run = service.advance_after_payment(run.run_id)
        except Exception as exc:
            st.error(tx("progression_error", error=f"{type(exc).__name__}: {exc}"))
            st.session_state["trustloop_run"] = service.reload_run(run.run_id)
            st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
        else:
            st.session_state["trustloop_run"] = run
            st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
            st.rerun()

if run.state in {DealState.INVOICE_CREATING, DealState.INVOICE_CREATED} and service:
    st.warning(tx("resume_warning"))
    if st.button(tx("resume_button"), type="primary", use_container_width=True):
        try:
            rate_limiter["financial"].check("resume_stage")
            with st.spinner(tx("resume_spinner")):
                run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
                if backend_name == "FAKE":
                    run = service.simulate_payment(run.run_id)
                    run = _complete_after_payment(service, run)
        except Exception as exc:
            st.error(tx("resume_error", error=f"{type(exc).__name__}: {exc}"))
            st.session_state["trustloop_run"] = service.reload_run(run.run_id)
            st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
        else:
            st.session_state["trustloop_run"] = run
            st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
            st.rerun()

if run.state == DealState.AWAITING_PAYMENT and run.plan and service:
    active = next(
        (
            item
            for item in run.plan.milestones
            if item.milestone_id == run.active_milestone_id
        ),
        None,
    )
    current_invoice = next(
        (
            item
            for item in reversed(run.invoices)
            if active and item.invoice_id == active.invoice_id
        ),
        None,
    )
    if active:
        st.markdown(
            f"""<div class="tp-card">
            <h3>{html.escape(tx('invoice_sent'))}</h3>
            <p><strong>{html.escape(tx('stage', sequence=active.sequence, name=active.name))}</strong></p>
            <p>{html.escape(tx('amount'))} <strong>{active.amount.format()}</strong></p>
            <p class="tp-muted">{html.escape(tx('waiting_payment'))}</p>
            </div>""",
            unsafe_allow_html=True,
        )
        if (
            backend_name != "FAKE"
            and current_invoice
            and is_safe_paypal_payment_url(current_invoice.payment_url)
        ):
            st.markdown(f"[{tx('open_payment')}]({current_invoice.payment_url})")
        elif backend_name == "FAKE":
            st.caption(tx("demo_payment_link"))
        else:
            st.caption("The gateway returned no trusted PayPal payment URL.")
        if backend_name == "FAKE" and st.button(
            tx("simulate_demo_payment"),
            type="primary",
            use_container_width=True,
        ):
            try:
                rate_limiter["financial"].check("simulate_resumed_payment")
                with st.spinner(tx("simulating_demo_payment")):
                    run = service.simulate_payment(run.run_id)
                    run = service.advance_after_payment(run.run_id)
            except Exception as exc:
                st.error(tx("simulate_error", error=f"{type(exc).__name__}: {exc}"))
                st.session_state["trustloop_run"] = service.reload_run(run.run_id)
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
            else:
                st.session_state["trustloop_run"] = run
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
                st.rerun()
        if st.button(tx("refresh_payment"), type="primary", use_container_width=True):
            try:
                rate_limiter["status"].check("refresh_status")
                with st.spinner(tx("checking_payment")):
                    run = service.refresh_payment(run.run_id)
                    if run.state == DealState.PAYMENT_CONFIRMED:
                        run = _complete_after_payment(service, run)
            except Exception as exc:
                st.error(tx("status_error", error=f"{type(exc).__name__}: {exc}"))
                st.session_state["trustloop_run"] = service.reload_run(run.run_id)
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
            else:
                st.session_state["trustloop_run"] = run
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
                st.rerun()

passport = run.passport
fx = run.plan.settlement_plan.fx_snapshot if run.plan else None
paid_milestones = [
    item for item in (run.plan.milestones if run.plan else []) if item.status.value == "PAID"
]

summary_cols = st.columns(4)
summary_cols[0].metric(tx("contract_value"), run.deal.contract_value.format())
summary_cols[1].metric(
    tx("invoice_currency"),
    run.plan.settlement_plan.invoice_currency if run.plan else "N/A",
)
summary_cols[2].metric(tx("paid_milestones"), f"{len(paid_milestones)}/{len(run.plan.milestones) if run.plan else 0}")
summary_cols[3].metric(tx("passport"), passport.passport_id if passport else tx("pending"))

if run.plan and run.plan.milestones:
    st.markdown(
        f'<h3 class="tp-section">{html.escape(tx("trust_ladder"))}</h3>',
        unsafe_allow_html=True,
    )
    st.markdown(_render_stepper(run.plan.milestones), unsafe_allow_html=True)

left, center, right = st.columns([1.08, 1.12, 1.0], gap="large")

with left:
    st.markdown(
        f'<h3 class="tp-section">{html.escape(tx("deal_risk"))}</h3>',
        unsafe_allow_html=True,
    )
    st.markdown(f"**{tx('buyer')}** {html.escape(run.deal.buyer.name)}")
    st.markdown(f"**{tx('seller')}** {html.escape(run.deal.seller.name)}")
    st.markdown(f"**{tx('product')}** {html.escape(run.deal.product_name)}")
    st.markdown(f"**{tx('quantity')}** {run.deal.quantity} {html.escape(run.deal.quantity_unit)}")
    st.markdown(f"**{tx('credit')}** {run.deal.requested_credit_days}")
    st.markdown(
        f"**{tx('decision')}** {run.risk.decision.value if run.risk else 'N/A'} "
        f"({run.risk.high_count if run.risk else 0} high / "
        f"{run.risk.medium_count if run.risk else 0} medium)"
    )

    if run.risk:
        for issue in run.risk.issues[:6]:
            with st.expander(f"{issue.severity.value} · {issue.type.value}"):
                st.markdown(f"**{tx('issue')}** {html.escape(issue.description)}")
                st.markdown(f"**{tx('suggestion')}** {html.escape(issue.suggestion)}")
                if issue.evidence_quote:
                    st.code(issue.evidence_quote)

with center:
    st.markdown(
        f'<h3 class="tp-section">{html.escape(tx("agent_plan"))}</h3>',
        unsafe_allow_html=True,
    )
    st.markdown(f"**{tx('plan')}** {run.plan.plan_id if run.plan else 'N/A'}")
    st.markdown(f"**{tx('approval')}** {run.plan.approval_reason if run.plan else 'N/A'}")
    st.markdown(f"**{tx('rationale')}** {html.escape(run.plan.rationale if run.plan else '')}")
    if run.agent_proposal:
        st.markdown(
            f"**{tx('agent_decision')}** {run.agent_proposal.decision} · "
            f"{run.agent_proposal.planner_type} · "
            f"confidence {run.agent_proposal.confidence}"
        )
        requested_tools = ", ".join(
            item.tool_name for item in run.agent_proposal.requested_tools
        )
        st.markdown(f"**{tx('requested_tools')}** {html.escape(requested_tools)}")
        for warning in run.agent_proposal.warnings:
            st.warning(warning)
        with st.expander(tx("view_proposal")):
            st.json(run.agent_proposal.model_dump(mode="json"))
    if (
        service
        and run.plan
        and run.state not in {
            DealState.PASSPORT_ISSUED,
            DealState.FAILED,
            DealState.CANCELLED,
        }
    ):
        if st.button(tx("simulate_negotiation"), use_container_width=True):
            try:
                rate_limiter["negotiation"].check("simulate_negotiation")
                st.session_state["trustloop_negotiation"] = service.simulate_negotiation(run.run_id)
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
                st.rerun()
            except RateLimitExceeded as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(tx("negotiation_error", error=f"{type(exc).__name__}: {exc}"))
                st.session_state["trustloop_run"] = service.reload_run(run.run_id)
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
        negotiation = st.session_state.get("trustloop_negotiation")
        if negotiation is None and service:
            negotiation = service.get_negotiation(run.run_id)
        if negotiation:
            st.markdown(f"**{tx('negotiation_result')}** {negotiation.summary}")
            with st.expander(tx("negotiation_turns"), expanded=True):
                for turn in negotiation.turns:
                    st.markdown(
                        f"**Turn {turn.turn} · {turn.actor}**"
                        + (f" · {tx('accepted')}" if turn.accepted else "")
                    )
                    st.caption(turn.message)

with right:
    st.markdown(
        f'<h3 class="tp-section">{html.escape(tx("currency_fx"))}</h3>',
        unsafe_allow_html=True,
    )
    if run.plan:
        st.markdown(
            f"<span class='tp-money'>{run.deal.contract_value.format()}</span>"
            "<span class='tp-arrow'>→</span>"
            f"<span class='tp-money'>{run.plan.settlement_plan.invoice_currency}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<span class='tp-muted'>{html.escape(tx('invoice_used', currency=run.plan.settlement_plan.invoice_currency))}</span>",
            unsafe_allow_html=True,
        )
    if fx:
        st.markdown(f"**{tx('fx_source')}** {html.escape(fx.source)}")
        st.markdown(f"**{tx('fx_rate')}** 1 {fx.base_currency} = {fx.rate:.4f} {fx.quote_currency}")
        st.markdown(f"**{tx('fx_observed')}** {fx.observed_at.isoformat()}")
        st.caption(tx("fx_reference"))

    st.markdown(
        f'<h3 class="tp-section">{html.escape(tx("payment_evidence"))}</h3>',
        unsafe_allow_html=True,
    )
    payment_rows = []
    if passport and passport.settlements:
        payment_rows = [
            (item.invoice_number, item.amount, "PAID", item.transaction_id)
            for item in passport.settlements
        ]
    elif run.plan:
        for milestone in run.plan.milestones:
            invoice = next(
                (
                    item
                    for item in reversed(run.invoices)
                    if item.invoice_id == milestone.invoice_id
                ),
                None,
            )
            if invoice:
                payment_rows.append(
                    (
                        invoice.invoice_number or "Pending",
                        invoice.amount or milestone.amount,
                        invoice.status or milestone.status.value,
                        invoice.transaction_id,
                    )
                )
    if payment_rows:
        for invoice_number, amount, status, transaction_id in payment_rows:
            status_class = "tp-paid" if status == "PAID" else "tp-ready"
            st.markdown(
                f"**{html.escape(invoice_number)}** · {amount.format()} · "
                f"<span class='tp-status {status_class}'>{html.escape(status)}</span>",
                unsafe_allow_html=True,
            )
            st.caption(f"Transaction: {transaction_id or 'N/A'}")
    else:
        st.info(tx("no_payment"))

    if passport:
        if service and service.store:
            st.markdown(
                f"[{tx('public_verify')}](?verify={passport.passport_id})"
            )
        else:
            st.caption(tx("store_required"))
        verification = service.verify_trust_passport(run.run_id) if service else None
        if verification and verification.valid:
            st.success(tx("verified"))
        elif verification:
            st.error(verification.message)
        if verification:
            with st.expander(tx("verification_checks")):
                st.json(verification.checks)
        st.download_button(
            tx("download_json"),
            data=json.dumps(passport.model_dump(mode="json"), indent=2, ensure_ascii=False),
            file_name=f"{passport.passport_id}.json",
            mime="application/json",
            use_container_width=True,
        )
        st.download_button(
            tx("download_html"),
            data=render_passport_html(passport),
            file_name=f"{passport.passport_id}.html",
            mime="text/html",
            use_container_width=True,
        )
        if service:
            replay_bundle = service.export_run_bundle(run.run_id)
            st.download_button(
                tx("download_replay"),
                data=json.dumps(replay_bundle, indent=2, ensure_ascii=False),
                file_name=f"{run.run_id}-replay.json",
                mime="application/json",
                use_container_width=True,
            )

st.markdown("---")
st.markdown(f"### {tx('audit_timeline')}")
for event in events:
    st.markdown(
        f"""<div class="tp-event">
        <strong>{event.sequence}. {html.escape(event.event_type)}</strong>
        <span class="tp-muted"> · {html.escape(event.actor_type)} / {html.escape(event.actor_id)}</span><br/>
        <span class="tp-muted">{event.created_at.isoformat()} · {html.escape(event.event_hash[:16])}...</span>
        </div>""",
        unsafe_allow_html=True,
    )

st.markdown("---")
st.markdown(f"### {tx('evidence_console')}")
st.caption(tx("evidence_console_hint"))
_exposure = exposure_summary(run)
st.markdown(tx("console_exposure_caption"))
st.markdown(exposure_bar_html(_exposure), unsafe_allow_html=True)
_console_query = st.text_input(tx("console_filter"), key="trustloop_console_filter")

st.markdown(f"**{tx('console_milestones')}**")
_render_evidence_grid(
    to_frame(milestone_rows(run), MILESTONE_COLUMNS),
    MILESTONE_COLUMNS,
    height=182,
    quick_filter=_console_query,
    status_column="status",
)

st.markdown(f"**{tx('console_events')}**")
_render_evidence_grid(
    to_frame(event_rows(events), EVENT_COLUMNS),
    EVENT_COLUMNS,
    height=360,
    quick_filter=_console_query,
)

if run.approvals:
    with st.expander(tx("approval_records")):
        st.json([item.model_dump(mode="json") for item in run.approvals])

st.caption(
    tx("footer")
)

