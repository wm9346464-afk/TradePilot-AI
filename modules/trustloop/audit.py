"""Append-only audit events with a tamper-evident hash chain."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


GENESIS_HASH = "0" * 64


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: f"EVT-{uuid4().hex[:12].upper()}")
    run_id: str
    sequence: int = Field(ge=1)
    event_type: str
    actor_type: Literal["SYSTEM", "AGENT", "HUMAN", "PAYPAL", "FX_PROVIDER"]
    actor_id: str
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prev_hash: str
    event_hash: str


class AuditLog:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.events: list[AuditEvent] = []

    @property
    def head_hash(self) -> str:
        return self.events[-1].event_hash if self.events else GENESIS_HASH

    def append(
        self,
        event_type: str,
        actor_type: Literal["SYSTEM", "AGENT", "HUMAN", "PAYPAL", "FX_PROVIDER"],
        actor_id: str,
        payload: dict | None = None,
    ) -> AuditEvent:
        sequence = len(self.events) + 1
        prev_hash = self.head_hash
        event = AuditEvent(
            run_id=self.run_id,
            sequence=sequence,
            event_type=event_type,
            actor_type=actor_type,
            actor_id=actor_id,
            payload=payload or {},
            prev_hash=prev_hash,
            event_hash="pending",
        )
        body = event.model_dump(mode="json")
        body.pop("event_hash")
        event_hash = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
        event = event.model_copy(update={"event_hash": event_hash})
        self.events.append(event)
        return event

    def verify_chain(self) -> bool:
        previous = GENESIS_HASH
        for expected_sequence, event in enumerate(self.events, start=1):
            if event.sequence != expected_sequence or event.prev_hash != previous:
                return False
            body = event.model_dump(mode="json")
            body.pop("event_hash")
            expected_hash = hashlib.sha256(
                _canonical_json(body).encode("utf-8")
            ).hexdigest()
            if event.event_hash != expected_hash:
                return False
            previous = event.event_hash
        return True

