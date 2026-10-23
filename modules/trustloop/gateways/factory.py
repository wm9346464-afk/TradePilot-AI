"""Select a payment backend without changing the TrustLoop service."""

from __future__ import annotations

import os

from .fake_paypal import FakePayPalGateway
from .paypal_rest import PayPalRestGateway
from .paypal_mcp import McpPayPalGateway


def build_paypal_gateway(backend: str | None = None, *, mcp_client=None):
    selected = str(backend or os.getenv("PAYPAL_BACKEND", "rest")).strip().lower()
    if selected in {"fake", "demo"}:
        return FakePayPalGateway()
    if selected in {"rest", "sandbox", "live_sandbox"}:
        return PayPalRestGateway()
    if selected == "mcp":
        if mcp_client is None:
            raise ValueError("PAYPAL_BACKEND=mcp requires an injected MCP client")
        return McpPayPalGateway(mcp_client, fallback=PayPalRestGateway())
    raise ValueError(f"Unsupported PAYPAL_BACKEND: {selected}")

