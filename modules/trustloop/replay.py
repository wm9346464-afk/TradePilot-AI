"""Portable run bundles for replay and audit export."""

from __future__ import annotations

from datetime import datetime, timezone
import json

from pydantic import BaseModel, ConfigDict, Field

from .audit import AuditEvent
from .models import DealRun


MAX_REPLAY_BUNDLE_BYTES = 10 * 1024 * 1024


class RunBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    exported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run: DealRun
    events: list[AuditEvent]


def parse_run_bundle_bytes(data: bytes) -> dict:
    if len(data) > MAX_REPLAY_BUNDLE_BYTES:
        raise ValueError(
            f"Replay Bundle exceeds {MAX_REPLAY_BUNDLE_BYTES} bytes"
        )
    try:
        bundle = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Replay Bundle is not valid UTF-8 JSON") from exc
    if not isinstance(bundle, dict):
        raise ValueError("Replay Bundle root must be a JSON object")
    return bundle

