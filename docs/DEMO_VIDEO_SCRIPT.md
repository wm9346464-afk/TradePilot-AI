# Demo video script — 2:50, English narration

Rules: under 3 minutes, must show the project actually running, public YouTube upload.
Record the **hosted demo** (https://tradepilot-trustloop.streamlit.app) in an incognito window,
English UI, no bookmarks bar, no sidebar clutter, no API keys visible, browser zoom 100%.

Narration: read the lines in **>** blocks. Record them padded with 200 ms silence and send me the audio,
or generate TTS and I will time it.

---

## Shot 0 · 0:00–0:12 — Hook (hero, no clicks)

Screen: Deal Room hero, badges visible, cursor still.

> First-time cross-border trade runs on trust nobody can verify. The buyer wants credit. The seller
> wants certainty. A contract proves that both sides agreed — it does not prove that either will pay.

On-screen text (lower third): `Trust is a promise. What if it were a sequence of verified payments?`

## Shot 1 · 0:12–0:30 — The case, then run the agent

Action: click **Review deal & build ladder**. While the spinner shows:

> Five hundred tonnes of rebar, one point eight million CNY, thirty days of credit, and no payment
> history between these two companies.

Screen after load: Trust Ladder band with three stages, metrics row.

> The agent rejects unsecured credit and proposes a ladder instead: a sample fee, a small trial order,
> and a deposit — each one unlocking only after the one before it is verified as paid.

## Shot 2 · 0:30–0:58 — Evidence, not vibes

Action: scroll to **Deal & risk evidence**; open two of the `HIGH` cards slowly.

> Every finding links back to a quoted line of the contract. No liquidated damages clause. No delivery
> schedule. No dispute resolution. Each risk is evidence, and the evidence is what travels into the
> final Passport.

Action: move to **Agent plan**, point at `Agent decision: REVIEW · LLM · confidence`.

> The planner is a live model — DeepSeek, or any OpenAI-compatible endpoint a visitor brings — but it
> only chooses the reasoning and the wording. The number of stages and the amounts are fixed by
> deployment policy, and the tools it may request are a closed list.

## Shot 3 · 0:58–1:16 — Currency control

Action: point at **Currency & FX** card: `CNY 1,825,000.00 → USD`, rate, source, observed timestamp.

> The contract is in CNY. Cross-border CNY is restricted on this PayPal path, so the agent proposes a
> supported invoice currency and records a timestamped FX snapshot with its source. The model is never
> allowed to invent a rate, and the conversion is never hidden.

## Shot 4 · 1:16–1:38 — Human approval, then PayPal acts

Action: click **Approve stage 1 & simulate PayPal** (or the real Sandbox button if recording REST mode).

> Here is the line this whole project is built around. The agent can propose; it cannot pay. A human
> approves one exact amount and currency, and only then does the agent request invoice creation and
> sending, inside that approved envelope.

Screen: stage 1 flips to `PAID`, stage 2 becomes `READY`.

> The next stage unlocks because PayPal reported PAID — not because a click happened.

## Shot 5 · 1:38–2:00 — Evidence console (AG Grid)

Action: scroll to **Evidence console**. Let the exposure bar land, then sort the milestone grid by
Amount, type `TP-DEMO` in the quick filter, then clear it and press **Export CSV** (briefly show the
download starting, then cancel).

> Two AG Grid tables hold the whole run. Milestones joined to their approvals, their PayPal invoices and
> their settlement transaction ids — sortable, filterable, exportable. And the audit chain itself, with
> the hash of every event, so an edit anywhere in the history stops verifying.

## Shot 6 · 2:00–2:26 — Trust Passport and public verification

Action: scroll back to the Passport card; click **Download Trust Passport JSON**, show it for a second;
then in the sidebar paste the Passport id into **Verify Passport ID** and click **Open public
verification**.

Screen: green `VALID: the stored Passport and complete audit chain agree.`

> Every approval, settlement, FX snapshot and agent decision becomes a portable Trust Passport. Its
> integrity check covers the entire audit chain, and a configured issuer signs it, so an edited JSON
> file does not validate. This is what a counterparty — or a bank, or an inspection agent — can check
> without trusting us.

## Shot 7 · 2:26–2:50 — Close

Action: back to the Trust Ladder, all three stages `PAID`, Passport issued.

> PayPal moves the money, but that is not what makes this agentic commerce. The agent runs the trust
> formation: it reads the contract, chooses a risk posture, sizes the commitment, and stops at every
> financial boundary for a human to approve.
>
> We are not automating checkout. We are automating the formation of trust.

On-screen end card (static, 5 s):
`TradePilot AI — TrustLoop` · `tradepilot-trustloop.streamlit.app` · `github.com/wm9346464-afk/TradePilot-AI`

---

## Recording checklist

- [ ] Incognito window, no extensions, no bookmarks bar, zoom 100%
- [ ] Language switch left on **English**
- [ ] Fresh run (Reset current demo first) so the ladder starts at 0/3
- [ ] Cursor visible but calm: one action per sentence, no hunting
- [ ] Never show the sidebar API-key field contents
- [ ] Export 1920×1080, 30 fps; keep the final cut under 2:55
- [ ] Upload to YouTube as **Public** (not unlisted — judges must be able to open it without a link request)
- [ ] Paste the URL into the Devpost form and into `docs/DEVPOST_SUBMISSION.md`
