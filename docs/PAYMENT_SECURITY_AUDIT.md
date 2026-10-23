# Payment Security Audit

Audit date: 2026-10-23

Scope: TrustLoop payment path, legacy PayPal page, PayPal REST/MCP adapters,
Webhook endpoint, Passport verification, Replay import and local persistence.

## External guidance used

- [Stripe idempotent requests](https://docs.stripe.com/api/idempotent_requests):
  retries with a stable idempotency key are intended to avoid creating a second
  object or performing the same operation twice after connection failures.
- [OWASP Automated Threats to Web Applications](https://owasp.org/www-project-automated-threats-to-web-applications/):
  valid application functionality can be abused through excessive and automated
  requests, so server-side limits and state checks are required.
- [PayPal Invoicing API](https://developer.paypal.com/docs/api/invoicing/v2/):
  TrustLoop delegates card/payment collection to PayPal-hosted invoice flows.

Historical online-payment incidents repeatedly fall into these patterns:

1. Checkout-page script compromise and card-data skimming.
2. Duplicate operations caused by double clicks, retries, timeouts or uncertain
   responses.
3. Forged or replayed payment notifications.
4. Missing server-side authorization or trusting browser-supplied amounts.
5. Over-retention of buyer PII and sensitive gateway responses.
6. Automated abuse of otherwise valid payment endpoints.
7. Stored/reflected content injection in evidence and review screens.

## Controls implemented in TradePilot

| Risk pattern | Current control | Evidence |
|---|---|---|
| Card-data theft/skimming | The application never asks for PAN, CVV or card credentials; payment happens on PayPal | `app_trustloop.py`, PayPal invoice gateways |
| Double click on approve/create | Per-run SQLite operation lock acquired before approval/create | `service.py`, `store.py`, `test_persistence.py` |
| Double click on send | Stable invoice-scoped `PayPal-Request-Id` plus per-run operation lock | `paypal_rest.py`, `service.py` |
| Retry after timeout | Deterministic create/send idempotency keys reused after failure | `service.py`, `paypal_payment.py`, `test_recovery.py` |
| MCP write succeeds but response is lost | Automatic MCP-to-REST write fallback is disabled by default | `paypal_mcp.py`, `test_paypal_mcp_gateway.py` |
| Browser supplies arbitrary amount | Server-side approval binds milestone ID, amount and currency | `policy.py`, `service.py` |
| PayPal reports wrong amount/currency | PAID result must equal the approved milestone | `service.py`, `test_recovery.py` |
| Webhook forgery | Official PayPal signature verification before processing | `webhook_handler.py`, `webhook_server.py` |
| Webhook replay/retry | Authoritative PayPal re-query and idempotent state progression | `webhook_events.py`, `test_webhook_endpoint.py` |
| Stale tab overwrites new state | Audit-chain conflict rolls back the stale write and UI reloads latest run | `store.py`, `service.py`, `test_persistence.py` |
| Aborted payment falsely succeeds | Only `PAID` creates payment confirmation; pending/reopened states remain unpaid | `service.py`, `test_recovery.py` |
| Replay overwrites live state | Replay import is memory-only and read-only | `service.py`, `test_persistence.py` |
| Malicious payment link | Only HTTPS `paypal.com` hosts are rendered | `security.py`, `test_security.py` |
| Plain-HTTP API keys | LLM/Signal endpoints require HTTPS except loopback development | `config.py`, `test_security.py` |
| Excessive file upload | Replay Bundles are limited to 10 MB and must be a JSON object | `replay.py`, `test_trustloop_v0.py` |
| Stored XSS from LLM/contract text | Dynamically rendered HTML is escaped | `app.py`, `app_trustloop.py`, `passport_export.py` |
| Sensitive raw gateway response retained | Gateway responses are reduced to payment evidence fields | `paypal_rest.py`, `paypal_mcp.py` |
| Public REST interface without auth | Live payment backends require `APP_PASSWORD` | `app_trustloop.py`, `test_trustloop_app.py` |
| Guessable public Passport IDs | New Passport IDs use full 128-bit UUID4 entropy | `models.py`, `test_passport_export.py` |

## Duplicate-payment conclusion

For this application, the user does not press a button that directly charges a
card. The flow creates and sends a PayPal invoice; the buyer pays on PayPal.
Double clicking the TradePilot action therefore risks duplicate invoices or
duplicate email sends, not an automatic repeated card charge by our code.

Defense layers are:

1. UI/state machine rejects the same operation from a progressed state.
2. A per-run operation lock prevents concurrent local execution.
3. The create request reuses `{run_id}:{milestone_id}:invoice` as its PayPal
   request ID.
4. The send request reuses `trustloop-send-{invoice_id}`.
5. MCP financial writes no longer silently fall back to REST.
6. PayPal's provider-side idempotency remains the final external guarantee.

## Residual risks and honest limits

- PayPal controls the idempotency retention period and provider-side behavior;
  the local code cannot prove provider internals beyond official API contracts.
- `APP_PASSWORD` is a demo access gate, not a production identity system with
  roles, MFA or per-user permissions.
- Session rate limits can be bypassed by creating a new browser session. This is
  acceptable for a Fake PayPal public demo, not for a production payment portal.
- SQLite stores buyer/deal fields needed to resume Sandbox workflows; it is not
  encrypted at rest by this project.
- PayPal MCP is implemented behind an injected adapter but has not been verified
  against a live official MCP transport.
- A final real PayPal REST UI test that closes the browser before and after
  payment is still required before production use.
