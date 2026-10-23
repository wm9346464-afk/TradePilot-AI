"""Printable Trust Passport export tests."""

from modules.trustloop.passport_export import render_passport_html
from modules.trustloop.service import build_demo_service, demo_deal_input


def test_passport_html_contains_verified_evidence():
    service = build_demo_service()
    run = service.run_full_demo(demo_deal_input())
    document = render_passport_html(run.passport)

    assert "TradePilot Trust Passport" in document
    assert run.passport.passport_id in document
    assert run.passport.audit_head_hash in document
    assert "Payments" in document
    assert "Human approvals" in document
    assert "not a legal opinion" in document

