"""Issuer signature and tamper-detection tests for Trust Passports."""

from modules.trustloop.passport import verify_passport
from modules.trustloop.passport_signature import verify_passport_signature
from modules.trustloop.service import build_demo_service, demo_deal_input


SIGNING_KEY = "test-passport-signing-key-32-chars-minimum"


def test_signed_passport_verifies_and_detects_tampering():
    service = build_demo_service()
    service.passport_signing_key = SIGNING_KEY
    run = service.run_full_demo(demo_deal_input())

    assert run.passport is not None
    assert run.passport.signature_algorithm == "HMAC-SHA256"
    assert verify_passport_signature(run.passport, SIGNING_KEY) is True
    result = service.verify_trust_passport(run.run_id)
    assert result.valid is True
    assert result.checks["issuer_signature_valid"] is True

    tampered = run.passport.model_copy(
        update={"contract_hash": "0" * 64}
    )
    assert verify_passport_signature(tampered, SIGNING_KEY) is False
    tampered_result = verify_passport(
        tampered,
        service.get_audit_events(run.run_id),
        signing_key=SIGNING_KEY,
    )
    assert tampered_result.valid is False
    assert tampered_result.checks["issuer_signature_valid"] is False


def test_passport_signature_rejects_the_wrong_issuer_key():
    service = build_demo_service()
    service.passport_signing_key = SIGNING_KEY
    run = service.run_full_demo(demo_deal_input())

    assert run.passport is not None
    assert verify_passport_signature(
        run.passport,
        "different-signing-key-with-32-characters",
    ) is False
