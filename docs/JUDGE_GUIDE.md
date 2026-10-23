# Judge Guide

## Fast path

1. Open `app_trustloop.py` via the hosted demo or run it locally.
2. Use the sidebar language switch if you prefer Chinese.
3. Choose USD or EUR and click `Review deal & build ladder`.
4. Inspect the contract evidence, Agent decision, negotiation and Trust Ladder.
5. Click `Approve stage 1`.
6. In Fake mode, the demo simulates the PayPal payment. In REST mode, open the PayPal link, pay with the Sandbox buyer, then click `Refresh PayPal payment status`.
7. Repeat for each stage.
8. Open or download the Trust Passport after the final stage.
9. Open the public verification page and confirm `VALID`.

## What to look for

- The Agent proposes a plan but cannot execute financial actions without human approval.
- Each approval is bound to an exact amount and currency.
- CNY contracts can be converted to a supported PayPal invoice currency with a timestamped FX snapshot.
- Payment progression is based on PayPal status, not an optimistic UI state.
- Webhook events are signature-verified and then re-queried before progression.
- Every important action appears in the audit timeline.

## Optional deeper checks

- Download the Passport JSON and confirm that it includes Agent evidence, settlement transaction IDs and an issuer signature where configured.
- Export the Replay Bundle, reset the demo, and open the bundle read-only.
- With `TRUSTLOOP_STORE_PATH` configured, resume the same run by ID in a new browser session.

## Safety

This is a Sandbox/Demo project. It does not move real money, does not provide legal advice and does not claim that PayPal buyer protection applies to B2B commodity transactions.

