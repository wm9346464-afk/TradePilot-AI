"""Safe PayPal Sandbox smoke test.

By default this script only checks configuration and OAuth token acquisition.
Pass --create-invoice to create a $0.01 USD DRAFT invoice. It never sends it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.config import get_paypal_config_status  # noqa: E402
from modules.paypal_payment import (  # noqa: E402
    create_invoice_api,
    get_paypal_access_token,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--create-invoice",
        action="store_true",
        help="Create a $0.01 USD DRAFT invoice after the token check",
    )
    parser.add_argument(
        "--buyer-email",
        default="buyer@example.com",
        help="Buyer email for the optional draft invoice",
    )
    args = parser.parse_args()

    status = get_paypal_config_status(lang="en")
    print(f"paypal_config_state={status['state']}")
    if status["state"] != "usable":
        print("PayPal Sandbox configuration is not usable; stopping.")
        return 1

    token = get_paypal_access_token()
    print(f"oauth_token_acquired={bool(token)}")
    if not token:
        print("OAuth failed; check Client ID/Secret and Sandbox account access.")
        return 1

    if not args.create_invoice:
        print("Token check passed. No invoice was created.")
        return 0

    result = create_invoice_api(
        buyer_email=args.buyer_email,
        buyer_name="TradePilot Sandbox Buyer",
        items=[
            {
                "name": "Sandbox permission check",
                "description": "Draft invoice for PayPal API permission verification",
                "quantity": "1",
                "unit_price": "0.01",
            }
        ],
        note="Sandbox permission check. Do not send.",
        currency="USD",
        contract_id="SANDBOX-SMOKE-TEST",
        payment_type="service_fee",
        idempotency_key="trustloop-sandbox-smoke-test-0001",
    )
    print(f"invoice_create_success={bool(result.get('success'))}")
    if result.get("success"):
        print(f"invoice_id={result.get('invoice_id')}")
        print(f"invoice_number={result.get('invoice_number')}")
        print(f"status={result.get('status')}")
        return 0
    print(f"error={result.get('error', 'unknown error')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

