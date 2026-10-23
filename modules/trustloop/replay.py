"""Portable run bundles for replay and audit export."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from .audit import AuditEvent
from .models import DealRun


class RunBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run: DealRun
    events: list[AuditEvent]

