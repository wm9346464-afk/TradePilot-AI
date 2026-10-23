# TradePilot TrustLoop Deployment

The safest public judge demo uses the deterministic Fake PayPal gateway and the
real configured LLM. Real PayPal REST execution remains available for a private
Sandbox rehearsal, but judges should not be asked to log in to a personal
Sandbox account.

## Required public demo configuration

Store these values in the hosting platform's Secrets UI, never in Git:

```env
TRUSTLOOP_PAYPAL_BACKEND=fake
TRUSTLOOP_USE_LLM=true
FX_PROVIDER=fixture
TRUSTLOOP_STORE_PATH=data/trustloop.db
TRUSTLOOP_PASSPORT_SIGNING_KEY=<at least 32 random characters>
APP_PASSWORD=<optional public-demo password>
LLM_API_KEY=<platform-managed secret>
LLM_API_URL=https://api.deepseek.com/chat/completions
LLM_MODEL_NAME=deepseek-chat
```

Generate a signing key locally:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not reuse a PayPal, LLM or personal password as the signing key.

## Streamlit Community Cloud

1. Push the reviewed `competition/trustloop` branch after explicit owner approval.
2. Create a Streamlit app from the public GitHub repository.
3. Set the branch to `competition/trustloop` and the main file to `app_trustloop.py`.
4. Select Python 3.12.
5. Paste the configuration above into App Settings → Secrets.
6. Deploy and run the smoke checklist below.

Streamlit Community Cloud storage may be ephemeral. Use this path for a stable
demo, but use a platform with a persistent disk when long-lived public Passport
verification is required.

## Render Web Service

Create a Python web service with:

```text
Build command: pip install -r requirements.txt
Start command: streamlit run app_trustloop.py --server.address 0.0.0.0 --server.port $PORT
```

Attach a persistent disk and set:

```env
TRUSTLOOP_STORE_PATH=/var/data/trustloop.db
```

The application can then resume runs by ID after process restarts and expose the
stored Passport verification view.

## Optional Webhook service

The Webhook endpoint is separate from Streamlit. It requires a public HTTPS URL,
persistent storage and a PayPal Webhook ID:

```env
PAYPAL_WEBHOOK_ID=WH-xxxxxxxxxxxxxxxx
TRUSTLOOP_STORE_PATH=/var/data/trustloop.db
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=8787
```

Start command:

```text
python webhook_server.py
```

Register `https://your-domain.example/paypal/webhook` in the PayPal developer
dashboard and subscribe to `INVOICING.INVOICE.PAID`. The process verifies the
PayPal transmission signature, then re-queries PayPal before changing state.

## Pre-submission smoke checklist

- The hero shows `DEMO / FAKE PAYPAL` and the correct LLM/FX mode.
- USD and EUR settlement plans both open.
- A complete three-stage fake flow reaches `PASSPORT_ISSUED`.
- The audit timeline grows and the Passport integrity check passes.
- A public verification link returns `VALID` for the issued Passport.
- Replay Bundle export/import works read-only.
- Saved run resume works when `TRUSTLOOP_STORE_PATH` is configured.
- No keys, `.env`, Sandbox passwords or real customer data appear in the video.
- The hosted link works in an incognito browser window.
