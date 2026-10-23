# TrustLoop Architecture

## Product flow

```text
Deal intake
→ Contract review with evidence
→ Currency validation
→ Agent proposal / Trust Ladder
→ Human approval for each stage
→ PayPal invoice creation and sending
→ Payment verification
→ Milestone completion and next-stage unlock
→ Trust Passport
```

## Layers

```text
Streamlit Deal Room
        ↓
TrustLoopService
├── DealStateMachine
├── RuleBasedPlanner / LLMPlanner
├── ToolRegistry
├── PolicyEngine
├── ContractReviewGateway
├── PayPalGateway (FAKE / REST / future MCP)
├── FX provider
├── AuditLog
└── TrustPassport
```

## Non-negotiable safety boundaries

- Financial actions require a milestone-specific human approval.
- The agent may request only registered tools.
- Amounts are `Decimal`-backed `Money` objects; floats are rejected.
- Cross-currency invoices require a timestamped FX snapshot.
- PayPal REST is the stable backend; MCP is a future switchable adapter.
- Demo, Replay and Live Sandbox modes must be visibly distinct.
- Only PayPal `PAID` status can unlock the next milestone.
- Trust Passport is an audit artifact, not a legal opinion, credit rating or payment guarantee.

## Current implementation status

Implemented:

- Domain models and state machine.
- Multi-currency policy including CNY in-country restrictions and zero-decimal currencies.
- Fixture and HTTP reference FX providers.
- Fake PayPal gateway with idempotency.
- PayPal REST adapter with mocked tests.
- Live PayPal Sandbox invoice creation, sending, buyer payment and PAID status verification.
- Structured AgentProposal and restricted tool registry.
- Deterministic planner and structured LLM planner with fallback.
- Three-stage Trust Ladder with explicit human approvals.
- Audit hash chain and Trust Passport.
- Deal Room with Fake and REST paths.

Requires final external delivery:

- Streamlit Cloud/Render deployment.
- Final three-minute video.
- Optional MCP adapter verification.

