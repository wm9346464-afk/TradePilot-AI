"""Payment and contract gateways for TrustLoop."""

from .fake_paypal import FakePayPalGateway
from .factory import build_paypal_gateway
from .paypal import CreateInvoiceRequest, PayPalGateway, PayPalGatewayError
from .paypal_rest import PayPalRestGateway
from .paypal_mcp import McpPayPalGateway

__all__ = [
    "CreateInvoiceRequest",
    "FakePayPalGateway",
    "PayPalGateway",
    "PayPalGatewayError",
    "PayPalRestGateway",
    "McpPayPalGateway",
    "build_paypal_gateway",
]

