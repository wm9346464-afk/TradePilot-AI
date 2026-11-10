# Devpost submission — TradePilot AI / TrustLoop

Copy-paste pack for <https://paypalaihackathon.devpost.com>. Deadline: **Nov 12, 2026, 12:00pm PT**
(= Nov 13, 04:00 Beijing). Field order follows the Devpost project form.

---

## 1. Basic fields

**Project name**

```
TradePilot AI — TrustLoop
```

**Elevator pitch / tagline** (max ~200 chars)

```
An agentic trust workflow for first-time cross-border B2B trade: the agent proposes a staged payment path, a human approves each exact amount, and PayPal-verified payments unlock the next milestone.
```

**Thumbnail / cover image**

Use `docs/images/evidence-console.png` or `docs/images/deal-room.png` (both 1156×~430).
If Devpost wants a 3:2 cover, upload `docs/images/deal-room.png`.

**Video demo URL**

`https://www.youtube.com/watch?v=XXXXXXXXXXX` ← replace after upload (must be public, under 3 min)

**Repository URL**

```
https://github.com/wm9346464-afk/TradePilot-AI
```

**Live demo URL ("Try it out" links)**

```
https://tradepilot-trustloop.streamlit.app
```

---

## 2. "Inspiration"

```
First-time cross-border trade runs on trust that nobody can verify. A buyer with no payment history asks for 30 or 60 days of credit. A seller is asked to ship half a million dollars of rebar to a stranger. A contract proves that both sides agreed; it does not prove that either side will perform. The usual answers are a letter of credit (slow, expensive, bank-heavy) or a full upfront wire (impossible for a first order).

PayPal already moves money for millions of businesses, but a first-time B2B counterparty is not going to wire USD 1.8M to a stranger either. What they will do is pay a small, exact, verifiable amount — and let the evidence of that payment buy the next step. That is the product: trust as a sequence of verified payments instead of a promise.
```

## 3. "What it does"

```
TrustLoop is a Deal Room for a first cross-border order.

1. Deal intake — buyer, product, quantity, contract value in CNY, requested credit days.
2. Evidence-backed contract review — every finding links back to a quoted line of the contract text (missing liquidated-damages clause, no delivery schedule, no dispute resolution, typo in the counterparty name).
3. Agent proposal — a live LLM (or the deterministic planner when no key is configured) returns a structured AgentProposal: decision (PROCEED / REVIEW / BLOCK), rationale, the evidence it used, and the requested tools.
4. Currency policy — the contract is in CNY; cross-border CNY is restricted for this PayPal path, so the agent converts to a supported invoice currency and records a timestamped FX snapshot with its source. The model is never allowed to invent a rate.
5. Human approval — the operator approves one milestone at an exact amount and currency. Nothing financial happens without that record.
6. PayPal execution — the agent then requests create_invoice and send_invoice, in that order, inside the approved envelope.
7. Verified progression — the workflow advances only when PayPal reports PAID, and the paid amount and currency must match the approval exactly. There is no optimistic UI state.
8. Trust Passport — approvals, settlements, FX snapshots, agent evidence and the audit hash chain are packaged into a portable Passport that a public verification page can validate (HMAC-SHA256 issuer signature when configured).
9. Evidence console — the same run projected into two AG Grid tables: milestones joined to approvals and PayPal invoices, and the audit hash chain itself. Sortable, filterable, exportable.

Three milestones by default: sample fee (USD 500) → small trial order (USD 5,000) → commodity deposit (USD 9,000). Each stage unlocks only after the previous one is verified as paid.
```

## 4. "How we built it"

```
Python 3.12 + Streamlit 1.54 for the Deal Room, with a domain layer that is independent of the UI.

- DealStateMachine with deterministic transitions, idempotency keys and SQLite checkpoints, so an interrupted payment can be resumed in a new browser session without ever assuming success.
- Append-only audit log: every event carries the hash of the previous event; the head hash is written into the Trust Passport, so an edited history stops verifying.
- Money is Decimal-backed; floats are rejected at the model boundary. JPY/HUF/TWD zero-decimal handling, and CNY/BRL/MYR in-country restrictions for the PayPal path.
- PayPal REST integration: OAuth, invoice draft, send, and status query. A real Sandbox invoice was created, sent, paid by a Sandbox personal account, and verified as PAID with amount, currency and transaction id extracted.
- Signed webhook endpoint that verifies the PayPal transmission signature and then re-queries PayPal before changing state, so a forged callback cannot move the workflow.
- Policy engine: a hard USD-equivalent ceiling per milestone, a restricted tool registry, and a check that an agent plan cannot escalate its own permissions. Contract text is treated as untrusted input, with a prompt-injection test matrix.
- Live planning: a structured JSON prompt to an OpenAI-compatible endpoint (DeepSeek in the demo), with a deterministic fallback. The planner's evidence references are canonicalised back to the verbatim contract quote, and the ladder is clamped to the deployment's three-stage amount envelope, so the model chooses the reasoning and the wording but never the sizes.
- Bring your own model: a visitor can paste any OpenAI-compatible endpoint and key in the sidebar. The override lives only in that browser session's planner instance — never in os.environ, never on disk, never in the audit log, the Passport or a replay bundle. A regression test completes a full run and asserts the key appears in none of those artefacts.
- AG Grid (through streamlit-aggrid) renders the evidence console from the run state, not from a parallel copy, so every number can be traced to the audit chain.
- 130 automated tests cover the state machine, crash-point recovery, concurrency conflicts, idempotency, currency rules, prompt injection, webhook verification, persistence and the evidence projections.
```

## 5. "Challenges we ran into"

```
The hardest part was refusing to fake progress. It is very easy to write a demo that shows "PAID" because the click happened. We ended up threading three things through the whole codebase: an approval record bound to an exact amount and currency, a payment status that only PayPal can set, and a hash chain that makes a retroactive edit visible. Every one of those turned into a recovery case (what happens if the process dies between invoice creation and sending?) that had to be tested rather than assumed.

The second one was agent safety. Giving an LLM the ability to create invoices is exactly where a demo becomes dangerous, so the planner may only request registered tools, may not exceed the approved envelope, and its evidence must exist in the contract review — we canonicalise reformatted quotes instead of trusting them, and reject invented ones.
```

## 6. "Accomplishments that we're proud of"

```
- A verified end-to-end PayPal Sandbox payment, not a simulation: invoice created, sent, paid, and confirmed as PAID with the transaction id in the evidence.
- A Trust Passport that a third party can verify: integrity check over the whole audit chain, plus an issuer signature so an edited JSON file stops validating.
- The agent never moves money: it proposes, and a human approves one exact amount.
- 130 tests, including crash-point recovery and a prompt-injection matrix, all green.
- A public demo that needs no setup, no login and no API key to complete the whole flow.
```

## 7. "What we learned"

```
Trust is not a score and it is not a document — it is a sequence of small, verifiable commitments. Once the workflow is framed that way, the design questions answer themselves: what is the smallest commitment that proves payment capability, what evidence unlocks the next step, and who is allowed to sign it off.
```

## 8. "What's next"

```
- A durable hosted verifier (persistent store) so a Passport link stays valid for years, plus a QR code on the printed Passport.
- Live PayPal MCP transport behind the existing injectable adapter, so the agent can query PayPal context directly.
- Risk-driven milestone sizing instead of configured amounts, still inside a hard ceiling.
- An issuer marketplace: carriers, inspection agents and banks co-signing the same Passport.
```

## 9. "Built With" (tags)

```
python, streamlit, paypal-rest-api, paypal-sandbox, paypal-webhooks, ag-grid, streamlit-aggrid, deepseek, llm, ai-agents, pydantic, sqlite, hmac, agentic-commerce
```

## 10. "Tools used and how" (required field)

```
PayPal Developer Platform (Sandbox) — the core of the product. OAuth token, invoicing API (create draft, send), invoice status query, and the webhook verification API. Every state transition in the workflow is gated on a PayPal status of PAID. A real Sandbox invoice was created, sent, paid and verified during development.

DeepSeek (OpenAI-compatible chat completions) — the agent planner. It receives the deal, the contract risk evidence and the allowed tool list, and returns a structured AgentProposal (decision, rationale, evidence references, requested tools, confidence). Used live in the demo, with a deterministic fallback so the workflow always completes.

AG Grid (via streamlit-aggrid) — the evidence console. Two grids (milestone evidence joined to approvals and invoices; the audit hash chain) with sorting, per-column filters, quick filter and CSV export. Community features only.

Streamlit — the Deal Room UI, hosted on Streamlit Community Cloud.
```

## 11. Prizes to select

Primary: **Best Use of Agentic Commerce**. Also select **Best Use of PayPal + AI**, **Best Demo Delivery**,
and the sponsor category **Best Use of AG Grid**.

## 12. Submission checklist

- [ ] Project created on Devpost, all fields above pasted
- [ ] Repo is public, licence visible in the About section (Apache-2.0 ✓)
- [ ] Live demo opens in an incognito window and completes the three stages
- [ ] Video uploaded to YouTube as **public**, under 3:00, link pasted
- [ ] Screenshots uploaded (deal-room.png, passport.png, evidence-console.png)
- [ ] Tools field filled
- [ ] Prizes selected (one grand/honourable + one sponsor is allowed)
- [ ] Submit **before Nov 12, 12:00pm PT** — do not leave it to the last hour
