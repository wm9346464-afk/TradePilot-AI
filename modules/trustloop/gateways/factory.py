"""Select a payment backend without changing the TrustLoop service."""

from __future__ import annotations

import os

from .fake_paypal import FakePayPalGateway
from .paypal_rest import PayPalRestGateway


def build_paypal_gateway(backend: str | None = None):
    selected = str(backend or os.getenv("PAYPAL_BACKEND", "rest")).strip().lower()
    if selected in {"fake", "demo"}:
        return FakePayPalGateway()
    if selected in {"rest", "sandbox", "live_sandbox"}:
        return PayPalRestGateway()
    raise ValueError(f"Unsupported PAYPAL_BACKEND: {selected}")

