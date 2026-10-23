# Judge Guide

## Fast path

1. Open `app_trustloop.py` via the hosted demo or run it locally.
2. Click `Review deal & build ladder`.
3. Inspect the contract evidence, Agent decision and Trust Ladder.
4. Click `Approve stage 1`.
5. In Fake mode, the demo simulates the PayPal payment. In REST mode, open the PayPal link, pay with the Sandbox buyer, then click `Refresh PayPal payment status`.
6. Repeat for each stage.
7. Open or download the Trust Passport after the final stage.

## What to look for

- The Agent proposes a plan but cannot execute financial actions without human approval.
- Each approval is bound to an exact amount and currency.
- CNY contracts can be converted to a supported PayPal invoice currency with a timestamped FX snapshot.
- Payment progression is based on PayPal status, not an optimistic UI state.
- Every important action appears in the audit timeline.

## Safety

This is a Sandbox/Demo project. It does not move real money, does not provide legal advice and does not claim that PayPal buyer protection applies to B2B commodity transactions.

