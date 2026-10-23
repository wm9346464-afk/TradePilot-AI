# TradePilot AI — TrustLoop

> **An agentic trust workflow for first-time cross-border B2B trade.**

[![PayPal AI Hackathon 2026](https://img.shields.io/badge/PayPal%20AI%20Hackathon-2026-003087.svg)](https://paypalaihackathon.devpost.com/)
[![Python](https://img.shields.io/badge/Python-3.10--3.12-3776AB.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.54.0-FF4B4B.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

---

## The problem

First-time cross-border trade has a trust problem.

- Buyers want credit or a trial order.
- Sellers want certainty before shipping.
- A contract alone does not prove that either side will perform.
- Large bank transfers are slow and poorly suited to the first small commitment.

TradePilot turns trust into a sequence of verified actions rather than an unverifiable promise.

> **Today, trust is a promise. With TradePilot, trust becomes a sequence of verifiable payments.**

---

## What TrustLoop does

```text
Deal intake
→ Evidence-backed contract review
→ PayPal-aware currency validation
→ Agent proposes a Trust Ladder
→ Human approves each exact milestone
→ PayPal Sandbox invoice is created and sent
→ Payment is verified from PayPal status
→ Next milestone unlocks
→ Trust Passport is issued
```

The agent does not merely recommend an action. After explicit human approval, it creates and sends a real PayPal Sandbox invoice and advances only when PayPal reports `PAID`.

---

## Why this is agentic commerce

The system combines:

- **Agent reasoning:** a structured AgentProposal selects a risk-aware payment path.
- **Restricted tool use:** the agent may request only registered tools.
- **Human-in-the-loop control:** every financial milestone needs a human approval bound to an exact amount and currency.
- **PayPal execution:** invoices are created, sent, and queried through the PayPal REST API.
- **Verified progression:** no optimistic UI states; only `PAID` unlocks the next stage.
- **Auditable trust evidence:** approval, payment, FX, and agent decision events are packaged in a Trust Passport.

---

## Trust Ladder

The default demonstration uses three milestones:

1. **Sample fee** — verify payment capability and collaboration intent.
2. **Small trial order** — validate fulfilment and acceptance with limited exposure.
3. **Commodity deposit** — reduce unsecured exposure before a larger shipment or credit terms.

The next stage unlocks only after the current stage is verified as paid.

---

## Multi-currency by design

TradePilot distinguishes:

- contract currency;
- PayPal invoice currency;
- settlement currency;
- display currency.

Implemented controls include:

- `Decimal`-backed `Money`; floats are rejected;
- ISO currency validation;
- zero-decimal currencies such as JPY, HUF, and TWD;
- PayPal in-country-only handling for CNY, BRL, and MYR;
- timestamped FX snapshots with source and expiry;
- fixture rates for offline demos and HTTP reference rates for live use;
- explicit labeling when FX falls back to demo data.

The demo contract may be denominated in CNY while the PayPal milestone invoice is issued in USD. The conversion is recorded and never invented by the LLM.

> Actual PayPal settlement may differ because of PayPal conversion rates and fees.

---

## Architecture

```text
Streamlit Deal Room
        │
        ▼
TrustLoopService
├── DealStateMachine
├── RuleBasedPlanner / LLMPlanner
├── ToolRegistry
├── PolicyEngine
├── ContractReviewGateway
├── PayPalGateway
│   ├── FakePayPalGateway
│   └── PayPalRestGateway
├── FX providers
├── AuditLog
└── TrustPassport
```

See [docs/TRUSTLOOP_ARCHITECTURE.md](docs/TRUSTLOOP_ARCHITECTURE.md).

---

## Demo modes

| Mode | PayPal | LLM | Purpose |
|---|---|---|---|
| `fake` | Deterministic fake gateway | Optional | Offline demo and tests |
| `rest` | PayPal Sandbox REST | Optional | Real Sandbox invoice/payment flow |

The UI always displays the active mode.

---

## Quick start

### 1. Create a virtual environment

```powershell
cd C:\Users\17663\Doubao\chats\2026-10-05\new-chat-2\TradePilot-AI-Public
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 2. Configure environment variables

```powershell
Copy-Item .env.example .env
```

For the safe offline demo:

```env
TRUSTLOOP_PAYPAL_BACKEND=fake
TRUSTLOOP_USE_LLM=false
FX_PROVIDER=fixture
```

For the real PayPal Sandbox path:

```env
PAYPAL_CLIENT_ID=
PAYPAL_CLIENT_SECRET=
PAYPAL_MERCHANT_EMAIL=
PAYPAL_MERCHANT_NAME=TradePilot AI
PAYPAL_SANDBOX_BUYER_EMAIL=
TRUSTLOOP_PAYPAL_BACKEND=rest
TRUSTLOOP_USE_LLM=true
FX_PROVIDER=fixture
```

For live structured planning, also configure:

```env
LLM_API_KEY=
LLM_API_URL=https://api.deepseek.com/chat/completions
LLM_MODEL_NAME=deepseek-chat
```

Never commit `.env` or real credentials.

### 3. Run the Deal Room

```powershell
.\.venv\Scripts\python.exe -m streamlit run app_trustloop.py
```

The legacy multi-page application remains available with:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

---

## Sandbox verification

The following real PayPal Sandbox flow has been verified:

- OAuth token acquisition;
- invoice draft creation;
- invoice sending;
- payment by a Sandbox Personal account;
- status query returning `PAID`;
- amount, currency, and transaction ID extraction.

See [docs/SANDBOX_SETUP.md](docs/SANDBOX_SETUP.md) and `scripts/sandbox_smoke_test.py`.

The default smoke test does not create an invoice:

```powershell
.\.venv\Scripts\python.exe scripts\sandbox_smoke_test.py
```

Only the explicit flag creates a `$0.01` DRAFT invoice:

```powershell
.\.venv\Scripts\python.exe scripts\sandbox_smoke_test.py --create-invoice
```

---

## Security model

- PayPal secrets remain server-side.
- Automated tests never call real PayPal or LLM APIs.
- Financial tools require an approval record for the exact milestone amount and currency.
- The agent can request only registered tools.
- Contract text is treated as untrusted input.
- The LLM cannot change tool permissions, currency policy, or amount limits.
- Only verified PayPal `PAID` status advances the workflow.
- Demo, Replay, and Live Sandbox modes must be visibly separate.
- Trust Passport is an audit artifact, not a legal opinion, credit rating, or payment guarantee.

See [SECURITY.md](SECURITY.md).

---

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE="1"
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-tmp
```

Current status:

- 43 automated tests passing;
- Python compilation checks passing;
- Fake PayPal end-to-end workflow passing;
- structured LLM and deterministic fallback tests passing;
- real PayPal Sandbox create/send/payment/status verified manually.

---

## Project structure

```text
app.py                         Legacy multi-page app
app_trustloop.py               TrustLoop Deal Room
modules/trustloop/             Domain, state, agent, gateways, policy, audit
modules/contract_checker.py    Contract review and evidence checks
modules/paypal_payment.py      Existing PayPal REST implementation
modules/webhook_handler.py     Simulated webhook demo
docs/                          Architecture, sandbox, judge and demo guides
tests/                         Unit, integration and AppTest coverage
```

---

## Current limitations

- The public demo is not yet deployed to a permanent hosted URL.
- PayPal MCP adapter is not yet implemented; REST is the stable path.
- Buyer/seller agent negotiation is a planned enhancement.
- Persistent event storage and replay across process restarts are planned.
- Real webhook signature verification is not enabled; the legacy page is explicitly a simulation.
- Trust Passport supports JSON; PDF export and a public verification page are planned.
- The project is a Sandbox/Demo and does not move real money.

---

## Documentation

- [Architecture](docs/TRUSTLOOP_ARCHITECTURE.md)
- [Sandbox setup](docs/SANDBOX_SETUP.md)
- [Demo script](docs/DEMO_SCRIPT.md)
- [Judge guide](docs/JUDGE_GUIDE.md)
- [Implementation status](docs/IMPLEMENTATION_STATUS.md)
- [Security](SECURITY.md)

---

## License

Apache License 2.0. See [LICENSE](LICENSE).

---

## Contact

- GitHub: [wm9346464-afk](https://github.com/wm9346464-afk)
- Email: wm9346464-afk@users.noreply.github.com

