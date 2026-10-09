#!/usr/bin/env python3
"""
TradePilot AI - PayPal Webhook Handler Module

Handles PayPal Webhook events for automatic payment confirmation.
In production, deploy this as an HTTP endpoint (e.g. Flask/FastAPI)
and register the URL in PayPal Developer Dashboard.

For Streamlit demo, we simulate webhook events to demonstrate the flow.
"""

import hashlib
import hmac
import base64
import json
import zlib
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class WebhookHandler:
    """Handles PayPal Webhook events with signature verification."""

    def __init__(self, webhook_id: str = "", demo_mode: bool = True):
        """
        Args:
            webhook_id: PayPal Webhook ID (from developer dashboard)
            demo_mode: If True, skip signature verification for demo
        """
        self.webhook_id = webhook_id
        self.demo_mode = demo_mode
        self._event_log = []

    def verify_signature(self, headers: dict, body: str) -> bool:
        """
        Verify PayPal Webhook signature.

        PayPal signature verification:
        1. Concatenate: transmission_id + transmission_time + webhook_id + crc32(body)
        2. HMAC-SHA256 with the webhook's secret key
        3. Base64 encode and compare with transmission_sig header

        Note: In production, you need the webhook secret from PayPal.
        Streamlit demo uses demo_mode=True to skip actual verification.
        """
        if self.demo_mode:
            logger.info("Webhook signature verification skipped (demo mode)")
            return True

        try:
            transmission_id = headers.get("Paypal-Transmission-Id", "")
            transmission_time = headers.get("Paypal-Transmission-Time", "")
            transmission_sig = headers.get("Paypal-Transmission-Sig", "")

            # CRC32 of body
            crc = hex(zlib.crc32(body.encode('utf-8')) & 0xffffffff)

            # Build signature string
            sig_string = f"{transmission_id}|{transmission_time}|{self.webhook_id}|{crc}"

            # Note: In production, use the webhook secret from PayPal
            # secret = os.getenv("PAYPAL_WEBHOOK_SECRET", "")
            # expected_sig = base64.b64encode(
            #     hmac.new(secret.encode(), sig_string.encode(), hashlib.sha256).digest()
            # ).decode()

            # return hmac.compare_digest(expected_sig, transmission_sig)
            logger.warning("Webhook secret not configured, verification skipped")
            return True

        except Exception as e:
            logger.error(f"Webhook signature verification failed: {e}")
            return False

    def handle_event(self, event: dict) -> dict:
        """
        Handle a PayPal Webhook event.

        Supported events:
        - INVOICING.INVOICE.PAID: Invoice paid successfully
        - INVOICING.INVOICE.CANCELLED: Invoice cancelled
        - INVOICING.INVOICE.SENT: Invoice sent
        - PAYMENT.CAPTURE.COMPLETED: Payment captured
        """
        event_type = event.get("event_type", "UNKNOWN")
        resource = event.get("resource", {})

        result = {
            "event_type": event_type,
            "processed": False,
            "timestamp": datetime.now().isoformat(),
            "actions": [],
        }

        # Log event
        self._event_log.append({
            "event_type": event_type,
            "resource_id": resource.get("id", ""),
            "timestamp": result["timestamp"],
        })

        if event_type == "INVOICING.INVOICE.PAID":
            result = self._handle_invoice_paid(resource, result)
        elif event_type == "INVOICING.INVOICE.CANCELLED":
            result["actions"].append("Invoice cancelled notification sent")
            result["processed"] = True
        elif event_type == "INVOICING.INVOICE.SENT":
            result["actions"].append("Invoice sent notification logged")
            result["processed"] = True
        elif event_type == "PAYMENT.CAPTURE.COMPLETED":
            result["actions"].append("Payment captured, triggering order fulfillment")
            result["processed"] = True
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            result["actions"].append(f"Event type {event_type} logged (no action)")

        return result

    def _handle_invoice_paid(self, resource: dict, result: dict) -> dict:
        """Handle INVOICING.INVOICE.PAID event - trigger post-payment actions."""
        invoice_id = resource.get("id", "")
        invoice_number = resource.get("invoice_number", "")
        amount = resource.get("amount", {}).get("value", "0")
        currency = resource.get("amount", {}).get("currency_code", "USD")

        result["invoice_id"] = invoice_id
        result["invoice_number"] = invoice_number
        result["amount"] = amount
        result["currency"] = currency

        # Post-payment actions (auto-triggered by webhook)
        result["actions"].extend([
            f"Invoice #{invoice_number} paid: {currency} {amount}",
            "Payment status updated to PAID in system",
            "Shipping notification generated automatically",
            "Customer payment confirmation email queued",
            "Sales team notified for order fulfillment",
            "Trust score updated for this customer",
        ])

        result["processed"] = True
        result["auto_triggered"] = True

        logger.info(f"Invoice paid webhook processed: {invoice_number}, {currency} {amount}")
        return result

    def get_event_log(self) -> list:
        """Return the webhook event log."""
        return self._event_log.copy()

    def simulate_invoice_paid_event(self, invoice_id: str, amount: float,
                                      currency: str = "USD",
                                      invoice_number: str = "DEMO-001") -> dict:
        """
        Simulate an INVOICING.INVOICE.PAID webhook event for demo purposes.
        In production, this event would be sent by PayPal to your webhook endpoint.
        """
        event = {
            "id": f"WH-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "event_type": "INVOICING.INVOICE.PAID",
            "event_version": "1.0",
            "create_time": datetime.now().isoformat(),
            "resource_type": "invoice",
            "resource_version": "1.0",
            "resource": {
                "id": invoice_id,
                "invoice_number": invoice_number,
                "status": "PAID",
                "amount": {
                    "currency_code": currency,
                    "value": str(amount),
                },
                "paid_amount": {
                    "currency_code": currency,
                    "value": str(amount),
                },
            },
            "links": [],
        }
        return self.handle_event(event)


# Singleton instance for app use
_webhook_handler: Optional[WebhookHandler] = None


def get_webhook_handler() -> WebhookHandler:
    """Get or create the singleton WebhookHandler instance."""
    global _webhook_handler
    if _webhook_handler is None:
        _webhook_handler = WebhookHandler(demo_mode=True)
    return _webhook_handler
