"""Self-contained Passport verification link tests."""

import pytest

from modules.trustloop.passport import verify_passport
from modules.trustloop.passport_link import (
    decode_passport_link,
    encode_passport_link,
    is_passport_link,
    normalise_link_input,
)
from modules.trustloop.service import build_demo_service, demo_deal_input


def _completed_run():
    service = build_demo_service()
    run = service.run_full_demo(demo_deal_input())
    run = service.get_run(run.run_id)
    return service, run


def test_link_round_trip_verifies_without_a_store():
    service, run = _completed_run()
    token = encode_passport_link(run.passport, service.get_audit_events(run.run_id))
    passport, events = decode_passport_link(token)

    result = verify_passport(passport, events)

    assert passport.passport_id == run.passport.passport_id
    assert len(events) == len(service.get_audit_events(run.run_id))
    assert result.checks["audit_chain_valid"] is True
    assert result.checks["head_hash_matches"] is True
    assert result.checks["approvals_match_audit"] is True
    assert result.checks["settlements_match_audit"] is True


def test_tampered_passport_fails_the_same_checks():
    service, run = _completed_run()
    token = encode_passport_link(run.passport, service.get_audit_events(run.run_id))
    passport, events = decode_passport_link(token)

    broken = passport.model_copy(update={"audit_head_hash": "0" * 64})
    result = verify_passport(broken, events)

    assert result.checks["head_hash_matches"] is False
    assert result.valid is False


def test_url_and_query_forms_are_accepted():
    service, run = _completed_run()
    token = encode_passport_link(run.passport, service.get_audit_events(run.run_id))

    assert is_passport_link(normalise_link_input(f"https://example.com/?verify={token}"))
    passport, _ = decode_passport_link(f"?verify={token}&x=1")
    assert passport.passport_id == run.passport.passport_id


def test_malformed_link_raises_value_error():
    with pytest.raises(ValueError):
        decode_passport_link("pl_not-a-real-payload")
    with pytest.raises(ValueError):
        decode_passport_link("TP-DEMO-0001")