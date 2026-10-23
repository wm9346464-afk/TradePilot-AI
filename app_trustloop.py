"""TradePilot TrustLoop - v0 deterministic Deal Room."""

from __future__ import annotations

import html
import json
import os
from uuid import uuid4

import streamlit as st

from modules.config import load_config
from modules.trustloop.service import build_runtime_service, demo_deal_input
from modules.trustloop.enums import DealState
from modules.trustloop.security import InMemoryRateLimiter, RateLimitExceeded
from modules.trustloop.agent.executor import AgentToolExecutor


def _complete_after_payment(service, run):
    run = service.complete_milestone(run.run_id)
    if run.plan and any(
        item.status.value != "PAID" for item in run.plan.milestones
    ):
        run = service.request_next_milestone(run.run_id)
    else:
        service.issue_passport(run.run_id)
        run = service.get_run(run.run_id)
    return run


st.set_page_config(
    page_title="TradePilot TrustLoop",
    page_icon="TP",
    layout="wide",
    initial_sidebar_state="collapsed",
)

load_config()
app_password = os.getenv("APP_PASSWORD", "")
if app_password and not st.session_state.get("trustloop_authenticated", False):
    st.markdown("### TradePilot TrustLoop")
    st.caption("This demo is protected by an access password.")
    entered_password = st.text_input("Access password", type="password")
    if entered_password != app_password:
        st.info("Enter the demo access password to continue.")
        st.stop()
    st.session_state["trustloop_authenticated"] = True

if "trustloop_session_key" not in st.session_state:
    st.session_state["trustloop_session_key"] = uuid4().hex
if "trustloop_rate_limiter" not in st.session_state:
    st.session_state["trustloop_rate_limiter"] = {
        "llm": InMemoryRateLimiter(max_calls=10, window_seconds=3600),
        "financial": InMemoryRateLimiter(max_calls=12, window_seconds=3600),
        "status": InMemoryRateLimiter(max_calls=60, window_seconds=3600),
    }
rate_limiter = st.session_state["trustloop_rate_limiter"]

with st.sidebar:
    st.markdown("### Demo controls")
    st.caption("Safe demo controls; no real money is used.")
    if st.button("Reset current demo", use_container_width=True):
        for key in ("trustloop_service", "trustloop_run", "trustloop_events"):
            st.session_state.pop(key, None)
        st.rerun()
    st.markdown("### Judge quick start")
    st.markdown(
        "1. Review the deal\n"
        "2. Inspect risk evidence\n"
        "3. Approve one exact stage\n"
        "4. Verify PayPal payment\n"
        "5. Inspect the Trust Passport"
    )
    st.markdown("### Active mode")
    st.caption(
        f"PayPal: {os.getenv('TRUSTLOOP_PAYPAL_BACKEND', 'fake')}\n"
        f"LLM: {'on' if os.getenv('TRUSTLOOP_USE_LLM', 'true').lower() != 'false' else 'off'}\n"
        f"FX: {os.getenv('FX_PROVIDER', 'fixture')}"
    )

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
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="tp-hero">
  <h1>TradePilot TrustLoop</h1>
  <p>An agentic trust workflow for first-time cross-border trade: review the contract,
  build a staged payment path, issue a PayPal invoice, verify payment, and turn the evidence
  into a portable Trust Passport.</p>
</div>
""",
    unsafe_allow_html=True,
)

configured_backend = os.getenv("TRUSTLOOP_PAYPAL_BACKEND", "fake").strip().upper()
backend_badge = (
    '<span class="tp-badge tp-live">PAYPAL SANDBOX / REST</span>'
    if configured_backend == "REST"
    else '<span class="tp-badge tp-demo">DEMO / FAKE PAYPAL</span>'
)
st.markdown(
    backend_badge
    + '<span class="tp-badge tp-demo">CNY contract → USD invoice</span>'
    + '<span class="tp-badge tp-demo">HUMAN APPROVAL REQUIRED</span>',
    unsafe_allow_html=True,
)
if configured_backend == "REST":
    st.info(
        "PayPal REST Sandbox mode: invoices are created and sent through PayPal. "
        "The workflow advances only after PayPal reports PAID."
    )
else:
    st.warning(
        "This mode uses deterministic Demo data and a fake PayPal gateway. "
        "No real payment, no real customer data, and no production claim."
    )

left, right = st.columns([4, 1])
with left:
    st.markdown("### One verified payment. A new trust relationship.")
    st.caption(
        "Demo case: a first-time buyer requests 30-day credit for a CNY 1,825,000 rebar order. "
        "The agent proposes a staged trust ladder instead of unsecured credit."
    )
with right:
    run_demo = st.button("Review deal & build ladder", type="primary", use_container_width=True)

if run_demo:
    try:
        rate_limiter["llm"].check("review_and_plan")
    except RateLimitExceeded as exc:
        st.error(str(exc))
        st.stop()
    with st.spinner("Reviewing contract and building the trust ladder..."):
        service = build_runtime_service(
            paypal_backend=os.getenv("TRUSTLOOP_PAYPAL_BACKEND", "fake"),
            use_llm=os.getenv("TRUSTLOOP_USE_LLM", "true").strip().lower() != "false",
        )
        run = service.start_case(demo_deal_input())
        from modules.contract_checker import SAMPLE_CONTRACT

        run = service.review_contract(run.run_id, SAMPLE_CONTRACT, use_ai=False)
        run = service.propose_plan(run.run_id, invoice_currency="USD")
        events = service.get_audit_events(run.run_id)
        st.session_state["trustloop_service"] = service
        st.session_state["trustloop_run"] = run
        st.session_state["trustloop_events"] = events

run = st.session_state.get("trustloop_run")
events = st.session_state.get("trustloop_events", [])

if not run:
    st.markdown(
        """
<div class="tp-card">
  <h3>What will happen</h3>
  <p>1. The contract review finds evidence-backed risks.</p>
  <p>2. The agent converts a cross-border CNY contract into a USD PayPal milestone plan.</p>
  <p>3. A human approval record binds the exact amount and currency.</p>
  <p>4. The fake gateway returns a PayPal-like invoice and PAID event.</p>
  <p>5. The Trust Passport records the risk, payment, FX snapshot, approvals, and audit hash.</p>
</div>
""",
        unsafe_allow_html=True,
    )
    st.stop()

service = st.session_state.get("trustloop_service")
backend_name = service.paypal_gateway.backend_name if service else "FAKE"

milestones = run.plan.milestones if run.plan else []
paid_count = sum(item.status.value == "PAID" for item in milestones)
progress_value = 1.0 if run.passport else (paid_count / len(milestones) if milestones else 0.0)
st.markdown("### Deal progress")
st.progress(
    progress_value,
    text=f"{paid_count}/{len(milestones)} milestones paid"
    + (" · Trust Passport issued" if run.passport else ""),
)
if run.state == DealState.AWAITING_APPROVAL and run.active_milestone_id:
    next_action = (
        "Next: review the exact milestone amount, then record human approval."
    )
elif run.state in {DealState.INVOICE_CREATING, DealState.INVOICE_CREATED}:
    next_action = "Next: resume the approved PayPal stage."
elif run.state == DealState.AWAITING_PAYMENT:
    next_action = (
        "Next: complete the Sandbox payment, then refresh PayPal status."
        if backend_name != "FAKE"
        else "Next: simulate the demo payment."
    )
elif run.state == DealState.PASSPORT_ISSUED:
    next_action = "Demo complete: inspect or download the Trust Passport."
else:
    next_action = "Next: continue the current verified workflow step."
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
            <h3>Human approval required</h3>
            <p><strong>Stage {active.sequence}: {html.escape(active.name)}</strong></p>
            <p>Amount: <strong>{active.amount.format()}</strong></p>
            <p class="tp-muted">Approving this stage authorizes invoice creation and sending for this exact amount and currency.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        if st.button(
            (
                f"Approve stage {active.sequence} & simulate PayPal"
                if backend_name == "FAKE"
                else f"Approve stage {active.sequence} & create PayPal invoice"
            ),
            type="primary",
            use_container_width=True,
        ):
            try:
                rate_limiter["financial"].check("approve_stage")
                with st.spinner("Applying approval and creating the PayPal invoice..."):
                    run = service.approve_plan(run.run_id)
                    run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
                    if backend_name == "FAKE":
                        run = service.simulate_payment(run.run_id)
                        run = _complete_after_payment(service, run)
            except Exception as exc:
                st.error(f"PayPal stage action failed: {type(exc).__name__}: {exc}")
                st.session_state["trustloop_run"] = service.get_run(run.run_id)
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
            else:
                st.session_state["trustloop_run"] = run
                st.session_state["trustloop_events"] = service.get_audit_events(run.run_id)
                st.rerun()

if run.state in {DealState.INVOICE_CREATING, DealState.INVOICE_CREATED} and service:
    st.warning("The approved stage is incomplete. You can safely resume it without re-approving.")
    if st.button("Resume approved stage", type="primary", use_container_width=True):
        try:
            rate_limiter["financial"].check("resume_stage")
            with st.spinner("Resuming the approved PayPal stage..."):
                run = AgentToolExecutor(service).execute_stage_invoice_tools(run.run_id)
                if backend_name == "FAKE":
                    run = service.simulate_payment(run.run_id)
                    run = _complete_after_payment(service, run)
        except Exception as exc:
            st.error(f"Resume failed: {type(exc).__name__}: {exc}")
            st.session_state["trustloop_run"] = service.get_run(run.run_id)
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
            <h3>PayPal invoice sent</h3>
            <p><strong>Stage {active.sequence}: {html.escape(active.name)}</strong></p>
            <p>Amount: <strong>{active.amount.format()}</strong></p>
            <p class="tp-muted">Waiting for the buyer to approve payment in PayPal. The workflow will advance only after PayPal reports PAID.</p>
            </div>""",
            unsafe_allow_html=True,
        )
        if current_invoice and current_invoice.payment_url:
            st.markdown(f"[Open PayPal payment page]({current_invoice.payment_url})")
        if st.button("Refresh PayPal payment status", type="primary", use_container_width=True):
            try:
                rate_limiter["status"].check("refresh_status")
                with st.spinner("Checking PayPal invoice status..."):
                    run = service.refresh_payment(run.run_id)
                    if run.state == DealState.PAYMENT_CONFIRMED:
                        run = _complete_after_payment(service, run)
            except Exception as exc:
                st.error(f"Payment status check failed: {type(exc).__name__}: {exc}")
                st.session_state["trustloop_run"] = service.get_run(run.run_id)
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
summary_cols[0].metric("Contract value", run.deal.contract_value.format())
summary_cols[1].metric(
    "Invoice currency",
    run.plan.settlement_plan.invoice_currency if run.plan else "N/A",
)
summary_cols[2].metric("Paid milestones", f"{len(paid_milestones)}/{len(run.plan.milestones) if run.plan else 0}")
summary_cols[3].metric("Passport", passport.passport_id if passport else "Pending")

left, center, right = st.columns([1.08, 1.12, 1.0], gap="large")

with left:
    st.markdown('<div class="tp-card"><h3>Deal & risk evidence</h3>', unsafe_allow_html=True)
    st.markdown(f"**Buyer:** {html.escape(run.deal.buyer.name)}")
    st.markdown(f"**Seller:** {html.escape(run.deal.seller.name)}")
    st.markdown(f"**Product:** {html.escape(run.deal.product_name)}")
    st.markdown(f"**Quantity:** {run.deal.quantity} {html.escape(run.deal.quantity_unit)}")
    st.markdown(f"**Requested credit:** {run.deal.requested_credit_days} days")
    st.markdown(
        f"**Decision:** {run.risk.decision.value if run.risk else 'N/A'} "
        f"({run.risk.high_count if run.risk else 0} high / "
        f"{run.risk.medium_count if run.risk else 0} medium)"
    )
    st.markdown("</div>", unsafe_allow_html=True)

    if run.risk:
        for issue in run.risk.issues[:6]:
            with st.expander(f"{issue.severity.value} · {issue.type.value}"):
                st.markdown(f"**Issue:** {html.escape(issue.description)}")
                st.markdown(f"**Suggestion:** {html.escape(issue.suggestion)}")
                if issue.evidence_quote:
                    st.code(issue.evidence_quote)

with center:
    st.markdown('<div class="tp-card"><h3>Agent plan</h3>', unsafe_allow_html=True)
    st.markdown(f"**Plan:** {run.plan.plan_id if run.plan else 'N/A'}")
    st.markdown(f"**Approval:** {run.plan.approval_reason if run.plan else 'N/A'}")
    st.markdown(f"**Rationale:** {html.escape(run.plan.rationale if run.plan else '')}")
    if run.agent_proposal:
        st.markdown(
            f"**Agent decision:** {run.agent_proposal.decision} · "
            f"{run.agent_proposal.planner_type} · "
            f"confidence {run.agent_proposal.confidence}"
        )
        requested_tools = ", ".join(
            item.tool_name for item in run.agent_proposal.requested_tools
        )
        st.markdown(f"**Requested tools:** {html.escape(requested_tools)}")
        for warning in run.agent_proposal.warnings:
            st.warning(warning)
        with st.expander("View structured AgentProposal JSON"):
            st.json(run.agent_proposal.model_dump(mode="json"))
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="tp-card"><h3>Trust Ladder</h3>', unsafe_allow_html=True)
    for milestone in run.plan.milestones if run.plan else []:
        status_class = "tp-paid" if milestone.status.value == "PAID" else "tp-ready" if milestone.status.value == "READY" else "tp-locked"
        st.markdown(
            f"""<div class="tp-milestone">
            <strong>{milestone.sequence}. {html.escape(milestone.name)}</strong>
            <span style="float:right" class="tp-status {status_class}">{milestone.status.value}</span><br/>
            <span class="tp-muted">{html.escape(milestone.purpose)}</span><br/>
            <span class="tp-money">{milestone.amount.format()}</span>
            </div>""",
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="tp-card"><h3>Currency & FX</h3>', unsafe_allow_html=True)
    if run.plan:
        st.markdown(
            f"<span class='tp-money'>{run.deal.contract_value.format()}</span>"
            "<span class='tp-arrow'>→</span>"
            f"<span class='tp-money'>{run.plan.settlement_plan.invoice_currency}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<span class='tp-muted'>{html.escape(run.plan.settlement_plan.invoice_currency)} is used for the PayPal milestone invoice.</span>",
            unsafe_allow_html=True,
        )
    if fx:
        st.markdown(f"**FX source:** {html.escape(fx.source)}")
        st.markdown(f"**Rate:** 1 {fx.base_currency} = {fx.rate:.4f} {fx.quote_currency}")
        st.markdown(f"**Observed:** {fx.observed_at.isoformat()}")
        st.caption("Reference conversion only. Actual PayPal settlement may differ.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="tp-card"><h3>Payment evidence</h3>', unsafe_allow_html=True)
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
        st.info("No payment evidence yet.")
    st.markdown("</div>", unsafe_allow_html=True)

    if passport:
        verification = service.verify_trust_passport(run.run_id) if service else None
        if verification and verification.valid:
            st.success("Trust Passport integrity verified.")
        elif verification:
            st.error(verification.message)
        if verification:
            with st.expander("Passport verification checks"):
                st.json(verification.checks)
        st.download_button(
            "Download Trust Passport JSON",
            data=json.dumps(passport.model_dump(mode="json"), indent=2, ensure_ascii=False),
            file_name=f"{passport.passport_id}.json",
            mime="application/json",
            use_container_width=True,
        )
        if service:
            replay_bundle = service.export_run_bundle(run.run_id)
            st.download_button(
                "Download Replay Bundle JSON",
                data=json.dumps(replay_bundle, indent=2, ensure_ascii=False),
                file_name=f"{run.run_id}-replay.json",
                mime="application/json",
                use_container_width=True,
            )

st.markdown("---")
st.markdown("### Audit timeline")
for event in events:
    st.markdown(
        f"""<div class="tp-event">
        <strong>{event.sequence}. {html.escape(event.event_type)}</strong>
        <span class="tp-muted"> · {html.escape(event.actor_type)} / {html.escape(event.actor_id)}</span><br/>
        <span class="tp-muted">{event.created_at.isoformat()} · {html.escape(event.event_hash[:16])}...</span>
        </div>""",
        unsafe_allow_html=True,
    )

if run.approvals:
    with st.expander("Human approval records"):
        st.json([item.model_dump(mode="json") for item in run.approvals])

st.caption(
    "v0 Demo · Fake PayPal gateway · no real money · human approval required · "
    "Trust Passport is not a credit rating or legal opinion."
)

