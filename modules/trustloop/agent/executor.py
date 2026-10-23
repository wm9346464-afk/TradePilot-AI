"""Execute validated agent tool requests through TrustLoopService."""

from __future__ import annotations

from ..enums import DealState


class AgentToolExecutionError(ValueError):
    pass


class AgentToolExecutor:
    def __init__(self, service) -> None:
        self.service = service

    def execute_stage_invoice_tools(self, run_id: str):
        run = self.service.get_run(run_id)
        if not run.agent_proposal:
            raise AgentToolExecutionError("Agent proposal is missing")

        tool_names = [item.tool_name for item in run.agent_proposal.requested_tools]
        if "create_invoice" not in tool_names:
            raise AgentToolExecutionError("Agent did not request create_invoice")
        if "send_invoice" not in tool_names:
            raise AgentToolExecutionError("Agent did not request send_invoice")
        if tool_names.index("create_invoice") > tool_names.index("send_invoice"):
            raise AgentToolExecutionError(
                "create_invoice must be requested before send_invoice"
            )

        if run.state == DealState.INVOICE_CREATING:
            run = self.service.create_invoice(run_id)
        elif run.state not in {DealState.INVOICE_CREATED, DealState.AWAITING_PAYMENT}:
            raise AgentToolExecutionError(
                f"Current state cannot execute invoice tools: {run.state.value}"
            )

        if run.state == DealState.INVOICE_CREATED:
            run = self.service.send_invoice(run_id)

        if run.state != DealState.AWAITING_PAYMENT:
            raise AgentToolExecutionError(
                f"Agent stage did not reach AWAITING_PAYMENT: {run.state.value}"
            )
        return run

