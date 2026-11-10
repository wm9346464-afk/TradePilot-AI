"""Self-contained Passport verification links.

A production verifier normally looks the Passport up in its own trusted store.
That breaks as soon as the store is ephemeral (a free container, a restarted
process): the link outlives the row.

This module carries the Passport and its audit chain inside the link instead.
The verifier re-derives every hash and re-checks the issuer signature, so the
page still proves itself without any database — and it never has to trust the
server that handed the link over.
"""

from __future__ import annotations

import base64
import binascii
import json

from .audit import AuditEvent
from .models import TrustPassport

PREFIX = "pl_"
MAX_ENCODED_LENGTH = 400_000


def encode_passport_link(passport: TrustPassport, events: list[AuditEvent]) -> str:
    """Return a URL-safe token that carries the Passport and its audit chain."""
    payload = {
        "passport": passport.model_dump(mode="json"),
        "events": [event.model_dump(mode="json") for event in events],
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    return PREFIX + token


def is_passport_link(value: str) -> bool:
    return value.strip().startswith(PREFIX)


def normalise_link_input(value: str) -> str:
    """Accept a bare token, `?verify=<token>` or a full URL."""
    text = value.strip()
    if "verify=" in text:
        text = text.split("verify=", 1)[1]
        for separator in ("&", "#", " "):
            text = text.split(separator, 1)[0]
    return text.strip()


def decode_passport_link(value: str) -> tuple[TrustPassport, list[AuditEvent]]:
    """Parse a token back into the Passport and its events.

    Raises ValueError on anything malformed, so callers can render a clean
    "this link is not valid" message instead of a traceback.
    """
    text = normalise_link_input(value)
    if not is_passport_link(text):
        raise ValueError("not a passport link")
    body = text[len(PREFIX):]
    if len(body) > MAX_ENCODED_LENGTH:
        raise ValueError("payload too large")
    padding = "=" * (-len(body) % 4)
    try:
        raw = base64.urlsafe_b64decode(body + padding)
        payload = json.loads(raw.decode("utf-8"))
        passport = TrustPassport.model_validate(payload["passport"])
        events = [AuditEvent.model_validate(item) for item in payload["events"]]
    except (binascii.Error, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError("passport link is not readable") from error
    return passport, events
