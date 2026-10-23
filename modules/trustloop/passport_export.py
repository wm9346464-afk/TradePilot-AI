"""Printable HTML export for a Trust Passport."""

from __future__ import annotations

import html

from .models import TrustPassport


def render_passport_html(passport: TrustPassport) -> str:
    risk_rows = "".join(
        f"<tr><td>{html.escape(item.severity.value)}</td>"
        f"<td>{html.escape(item.type.value)}</td>"
        f"<td>{html.escape(item.description)}</td></tr>"
        for item in passport.risk_summary.issues
    ) or "<tr><td colspan='3'>No issues recorded.</td></tr>"
    milestone_rows = "".join(
        f"<tr><td>{item.sequence}</td><td>{html.escape(item.name)}</td>"
        f"<td>{html.escape(item.amount.format())}</td>"
        f"<td>{html.escape(item.status.value)}</td></tr>"
        for item in passport.ladder
    )
    settlement_rows = "".join(
        f"<tr><td>{html.escape(item.invoice_number)}</td>"
        f"<td>{html.escape(item.amount.format())}</td>"
        f"<td>{html.escape(item.status)}</td>"
        f"<td>{html.escape(item.transaction_id or 'N/A')}</td></tr>"
        for item in passport.settlements
    )
    approval_rows = "".join(
        f"<tr><td>{html.escape(item.milestone_id)}</td>"
        f"<td>{html.escape(item.approved_amount.format())}</td>"
        f"<td>{html.escape(item.approved_by)}</td>"
        f"<td>{html.escape(item.approved_at.isoformat())}</td></tr>"
        for item in passport.approvals
    )
    agent_rows = "".join(
        f"<tr><td>{html.escape(item.action_type)}</td>"
        f"<td>{html.escape(item.actor)}</td>"
        f"<td>{html.escape(item.summary)}</td>"
        f"<td>{html.escape(', '.join(item.tool_names) or 'None')}</td></tr>"
        for item in passport.agent_actions
    ) or "<tr><td colspan='4'>No agent action evidence recorded.</td></tr>"
    fx_rows = "".join(
        f"<tr><td>{html.escape(item.base_currency)}/{html.escape(item.quote_currency)}</td>"
        f"<td>{html.escape(str(item.rate))}</td>"
        f"<td>{html.escape(item.source)}</td>"
        f"<td>{html.escape(item.mode)}</td></tr>"
        for item in passport.fx_snapshots
    ) or "<tr><td colspan='4'>No FX conversion required.</td></tr>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Trust Passport {html.escape(passport.passport_id)}</title>
<style>
body{{font-family:Arial,sans-serif;color:#111827;max-width:980px;margin:32px auto;padding:0 24px;line-height:1.45}}
h1,h2{{color:#003087}} table{{width:100%;border-collapse:collapse;margin:12px 0 24px}}
th,td{{border:1px solid #d9e2ec;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f0f6ff}} .meta{{background:#f7f9fa;padding:16px;border-radius:12px}}
.hash{{font-family:monospace;word-break:break-all;font-size:12px}} footer{{color:#667085;font-size:12px}}
@media print{{body{{margin:0;max-width:none}}}}
</style></head><body>
<h1>TradePilot Trust Passport</h1>
<div class="meta">
<p><strong>Passport ID:</strong> {html.escape(passport.passport_id)}</p>
<p><strong>Run ID:</strong> {html.escape(passport.run_id)}</p>
<p><strong>Deal ID:</strong> {html.escape(passport.deal_id)}</p>
<p><strong>Mode:</strong> {html.escape(passport.mode.value)}</p>
<p><strong>Issued at:</strong> {html.escape(passport.issued_at.isoformat())}</p>
</div>
<h2>Risk evidence</h2><table><tr><th>Severity</th><th>Type</th><th>Description</th></tr>{risk_rows}</table>
<h2>Trust Ladder</h2><table><tr><th>#</th><th>Milestone</th><th>Amount</th><th>Status</th></tr>{milestone_rows}</table>
<h2>Payments</h2><table><tr><th>Invoice</th><th>Amount</th><th>Status</th><th>Transaction</th></tr>{settlement_rows}</table>
<h2>Human approvals</h2><table><tr><th>Milestone</th><th>Amount</th><th>Approved by</th><th>Time</th></tr>{approval_rows}</table>
<h2>Agent decision evidence</h2><table><tr><th>Action</th><th>Actor</th><th>Summary</th><th>Requested tools</th></tr>{agent_rows}</table>
<h2>FX snapshots</h2><table><tr><th>Pair</th><th>Rate</th><th>Source</th><th>Mode</th></tr>{fx_rows}</table>
<h2>Audit head</h2><p class="hash">{html.escape(passport.audit_head_hash)}</p>
<h2>Issuer signature</h2><p><strong>Algorithm:</strong> {html.escape(passport.signature_algorithm or 'Not configured')}</p>
<p><strong>Key ID:</strong> {html.escape(passport.signing_key_id or 'N/A')}</p>
<p class="hash">{html.escape(passport.signature or 'Unsigned passport')}</p>
<footer>This document is an audit artifact. It is not a legal opinion, credit rating or payment guarantee.</footer>
</body></html>"""

