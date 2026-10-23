# PayPal Sandbox Setup

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
FX_PROVIDER=fixture
```

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

