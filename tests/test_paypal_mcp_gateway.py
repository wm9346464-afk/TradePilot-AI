"""Mocked tests for the optional PayPal MCP adapter."""

from modules.trustloop.gateways.paypal import CreateInvoiceRequest
from modules.trustloop.gateways.paypal_mcp import McpPayPalGateway
from modules.trustloop.money import money


class FakeMcpClient:
    def __init__(self):
        self.calls = []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "create_invoice":
            return {
                "success": True,
                "id": "MCP-INV-1",
                "invoice_number": "MCP-NO-1",
                "status": "DRAFT",
                "currency": "USD",
                "amount": {"value": "500.00", "currency_code": "USD"},
                "payment_url": "https://sandbox.paypal.com/invoice/MCP-INV-1",
            }
        if name == "send_invoice":
            return {"success": True, "status": "SENT"}
        if name == "get_invoice":
            return {
                "success": True,
                "status": "PAID",
                "currency": "USD",
                "amount": {"value": "500.00", "currency_code": "USD"},
                "transaction_id": "MCP-TXN-1",
            }
        raise AssertionError(name)


def test_mcp_gateway_maps_tool_results():
    client = FakeMcpClient()
    gateway = McpPayPalGateway(client)
    created = gateway.create_invoice(
        CreateInvoiceRequest(
            buyer_name="Buyer",
            buyer_email="buyer@example.com",
            amount=money("500", "USD"),
            idempotency_key="mcp-test-0001",
        )
    )
    sent = gateway.send_invoice("MCP-INV-1")
    paid = gateway.get_invoice("MCP-INV-1")

    assert created.invoice_id == "MCP-INV-1"
    assert created.amount.format() == "USD 500.00"
    assert sent.status == "SENT"
    assert paid.status == "PAID"
    assert [call[0] for call in client.calls] == [
        "create_invoice",
        "send_invoice",
        "get_invoice",
    ]

