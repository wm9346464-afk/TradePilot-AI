# PayPal Sandbox Setup

> Verification status: on 2026-10-23 a USD 1.00 Sandbox invoice was created,
> sent, paid by the Personal test account, and queried back as `PAID`.

1. Sign in to <https://developer.paypal.com/>.
2. Open `Dashboard → Apps & Credentials`.
3. Select `Sandbox`.
4. Create an app and copy `Client ID` and `Client Secret`.
5. Open `Sandbox → Accounts`.
6. Copy the verified email of a Business test account into `PAYPAL_MERCHANT_EMAIL`.
7. Use the Personal test account for the buyer payment demonstration.
8. Put values only in the local `.env` or deployment Secrets.

Recommended local values:

```env
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_MERCHANT_EMAIL=sb-xxxx@business.example.com
PAYPAL_MERCHANT_NAME=TradePilot AI
PAYPAL_SANDBOX_BUYER_EMAIL=sb-yyyy@personal.example.com
TRUSTLOOP_PAYPAL_BACKEND=rest
TRUSTLOOP_USE_LLM=true
FX_PROVIDER=fixture
```

For a fast end-to-end UI payment rehearsal, use three USD 1.00 milestones:

```env
MAX_INVOICE_AMOUNT_USD=10000
TRUSTLOOP_SAMPLE_AMOUNT=1
TRUSTLOOP_TRIAL_AMOUNT=1
TRUSTLOOP_DEPOSIT_AMOUNT=1
```

The sample, trial and deposit values are demo configuration, not a credit
recommendation. Every amount still requires a milestone-specific human approval.

## Safe smoke test

The default command only checks configuration and OAuth:

```powershell
cd C:\Users\17663\Doubao\chats\2026-10-05\new-chat-2\TradePilot-AI-Public
.\.venv\Scripts\python.exe scripts\sandbox_smoke_test.py
```

Only when you explicitly want to test invoice permission:

```powershell
.\.venv\Scripts\python.exe scripts\sandbox_smoke_test.py --create-invoice
```

That command creates a `$0.01 USD` DRAFT invoice and never sends it.

## Run TrustLoop with REST

```powershell
$env:TRUSTLOOP_PAYPAL_BACKEND="rest"
$env:FX_PROVIDER="fixture"
.\.venv\Scripts\python.exe -m streamlit run app_trustloop.py
```

Use `FX_PROVIDER=live` for Frankfurter reference rates when network access is available.

## Verified Webhook endpoint

`webhook_server.py` is a small independent HTTP service that verifies PayPal's
transmission signature before processing an invoice event. It never trusts the
amount or status in the webhook body; after verification it queries PayPal again
and advances only when the authoritative status is `PAID`.

Add these values to `.env`:

```env
PAYPAL_WEBHOOK_ID=WH-xxxxxxxxxxxxxxxx
TRUSTLOOP_STORE_PATH=data/trustloop.db
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8787
```

Start the endpoint:

```powershell
.\.venv\Scripts\python.exe webhook_server.py
```

Expose it behind HTTPS and register this exact URL in the PayPal developer
dashboard:

```text
https://your-domain.example/paypal/webhook
```

Subscribe to `INVOICING.INVOICE.PAID`. A local health check is available at
`http://127.0.0.1:8787/health`.

