"""Issuer signatures for portable Trust Passport artifacts."""

from __future__ import annotations

import hashlib
import hmac
import json

from .models import TrustPassport


SIGNATURE_EXCLUDED_FIELDS = {"signature_algorithm", "signing_key_id", "signature"}


def _canonical_payload(passport: TrustPassport) -> bytes:
    payload = passport.model_dump(
        mode="json",
        exclude=SIGNATURE_EXCLUDED_FIELDS,
    )
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def signing_key_id(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16].upper()


def sign_passport(passport: TrustPassport, secret: str) -> TrustPassport:
    if len(secret) < 32:
        raise ValueError("TRUSTLOOP_PASSPORT_SIGNING_KEY must be at least 32 characters")
    signature = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(passport),
        hashlib.sha256,
    ).hexdigest()
    return passport.model_copy(
        update={
            "signature_algorithm": "HMAC-SHA256",
            "signing_key_id": signing_key_id(secret),
            "signature": signature,
        }
    )


def verify_passport_signature(passport: TrustPassport, secret: str) -> bool:
    if passport.signature_algorithm != "HMAC-SHA256" or not passport.signature:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        _canonical_payload(passport),
        hashlib.sha256,
    ).hexdigest()
    return (
        passport.signing_key_id == signing_key_id(secret)
        and hmac.compare_digest(passport.signature, expected)
    )
