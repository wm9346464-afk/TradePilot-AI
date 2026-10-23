"""SQLite persistence for resumable TrustLoop runs and audit evidence."""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from .agent.negotiation import NegotiationResult
from .audit import AuditEvent
from .models import DealRun


class StoreConflict(RuntimeError):
    """Raised when an append-only record would be overwritten."""


class RunStore(Protocol):
    def save_run(self, run: DealRun) -> None:
        ...

    def save_checkpoint(self, run: DealRun, events: list[AuditEvent]) -> None:
        ...

    def load_run(self, run_id: str) -> DealRun | None:
        ...

    def append_audit_event(self, event: AuditEvent) -> None:
        ...

    def replace_audit_events(self, run_id: str, events: list[AuditEvent]) -> None:
        ...

    def load_audit_events(self, run_id: str) -> list[AuditEvent]:
        ...

    def save_negotiation(self, run_id: str, result: NegotiationResult) -> None:
        ...

    def load_negotiation(self, run_id: str) -> NegotiationResult | None:
        ...

    def find_run_by_passport(self, passport_id: str) -> DealRun | None:
        ...

    def find_run_by_invoice(self, invoice_id: str) -> DealRun | None:
        ...

    def acquire_operation_lock(self, lock_key: str, owner: str, ttl_seconds: int) -> bool:
        ...

    def release_operation_lock(self, lock_key: str, owner: str) -> None:
        ...

    def list_recent_runs(self, *, limit: int = 10) -> list[DealRun]:
        ...


class SQLiteRunStore:
    """Small append-only store intended for a single deployed application writer."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout = 5000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    passport_id TEXT,
                    state TEXT NOT NULL,
                    run_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_runs_passport
                    ON runs(passport_id) WHERE passport_id IS NOT NULL;
                CREATE INDEX IF NOT EXISTS idx_runs_updated
                    ON runs(updated_at DESC);
                CREATE TABLE IF NOT EXISTS audit_events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS negotiations (
                    run_id TEXT PRIMARY KEY,
                    result_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS invoice_index (
                    run_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    PRIMARY KEY (run_id, invoice_id)
                );
                CREATE INDEX IF NOT EXISTS idx_invoice_index_invoice
                    ON invoice_index(invoice_id);
                CREATE TABLE IF NOT EXISTS operation_locks (
                    lock_key TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    expires_at REAL NOT NULL
                );
                """
            )

    @staticmethod
    def _write_run(connection: sqlite3.Connection, run: DealRun) -> None:
        passport_id = run.passport.passport_id if run.passport else None
        connection.execute(
            """
            INSERT INTO runs(run_id, passport_id, state, run_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(run_id) DO UPDATE SET
                passport_id = excluded.passport_id,
                state = excluded.state,
                run_json = excluded.run_json,
                updated_at = excluded.updated_at
            """,
            (
                run.run_id,
                passport_id,
                run.state.value,
                run.model_dump_json(),
                run.updated_at.isoformat(),
            ),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO invoice_index(run_id, invoice_id) VALUES (?, ?)",
            [
                (run.run_id, invoice.invoice_id)
                for invoice in run.invoices
                if invoice.invoice_id
            ],
        )

    def save_run(self, run: DealRun) -> None:
        with self._connect() as connection:
            self._write_run(connection, run)

    def save_checkpoint(self, run: DealRun, events: list[AuditEvent]) -> None:
        """Atomically persist the run snapshot and its complete audit chain."""
        with self._connect() as connection:
            self._write_run(connection, run)
            for event in events:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO audit_events(run_id, sequence, event_json)
                    VALUES (?, ?, ?)
                    """,
                    (event.run_id, event.sequence, event.model_dump_json()),
                )
                if cursor.rowcount == 1:
                    continue
                row = connection.execute(
                    """
                    SELECT event_json FROM audit_events
                    WHERE run_id = ? AND sequence = ?
                    """,
                    (event.run_id, event.sequence),
                ).fetchone()
                if row is None or row["event_json"] != event.model_dump_json():
                    raise StoreConflict(
                        f"Audit sequence {event.sequence} already exists with different content"
                    )

    def load_run(self, run_id: str) -> DealRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_json FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return DealRun.model_validate_json(row["run_json"]) if row else None

    def append_audit_event(self, event: AuditEvent) -> None:
        event_json = event.model_dump_json()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO audit_events(run_id, sequence, event_json) VALUES (?, ?, ?)",
                (event.run_id, event.sequence, event_json),
            )
            if cursor.rowcount == 1:
                return
            row = connection.execute(
                "SELECT event_json FROM audit_events WHERE run_id = ? AND sequence = ?",
                (event.run_id, event.sequence),
            ).fetchone()
        if row is None or row["event_json"] != event_json:
            raise StoreConflict(
                f"Audit sequence {event.sequence} already exists with different content"
            )

    def replace_audit_events(self, run_id: str, events: list[AuditEvent]) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM audit_events WHERE run_id = ?", (run_id,))
            connection.executemany(
                "INSERT INTO audit_events(run_id, sequence, event_json) VALUES (?, ?, ?)",
                [
                    (event.run_id, event.sequence, event.model_dump_json())
                    for event in events
                ],
            )

    def load_audit_events(self, run_id: str) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT event_json FROM audit_events WHERE run_id = ? ORDER BY sequence",
                (run_id,),
            ).fetchall()
        return [AuditEvent.model_validate_json(row["event_json"]) for row in rows]

    def save_negotiation(self, run_id: str, result: NegotiationResult) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO negotiations(run_id, result_json, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(run_id) DO UPDATE SET
                    result_json = excluded.result_json,
                    updated_at = excluded.updated_at
                """,
                (run_id, result.model_dump_json()),
            )

    def load_negotiation(self, run_id: str) -> NegotiationResult | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT result_json FROM negotiations WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return NegotiationResult.model_validate_json(row["result_json"]) if row else None

    def find_run_by_passport(self, passport_id: str) -> DealRun | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT run_json FROM runs WHERE passport_id = ?",
                (passport_id,),
            ).fetchone()
        return DealRun.model_validate_json(row["run_json"]) if row else None

    def find_run_by_invoice(self, invoice_id: str) -> DealRun | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT runs.run_json FROM invoice_index
                JOIN runs ON runs.run_id = invoice_index.run_id
                WHERE invoice_index.invoice_id = ?
                LIMIT 1
                """,
                (invoice_id,),
            ).fetchone()
        return DealRun.model_validate_json(row["run_json"]) if row else None

    def acquire_operation_lock(self, lock_key: str, owner: str, ttl_seconds: int) -> bool:
        now = time.time()
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM operation_locks WHERE expires_at <= ?",
                (now,),
            )
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO operation_locks(lock_key, owner, expires_at)
                VALUES (?, ?, ?)
                """,
                (lock_key, owner, now + max(1, ttl_seconds)),
            )
            return cursor.rowcount == 1

    def release_operation_lock(self, lock_key: str, owner: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM operation_locks WHERE lock_key = ? AND owner = ?",
                (lock_key, owner),
            )

    def list_recent_runs(self, *, limit: int = 10) -> list[DealRun]:
        safe_limit = max(1, min(int(limit), 50))
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_json FROM runs ORDER BY updated_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
        return [DealRun.model_validate_json(row["run_json"]) for row in rows]
