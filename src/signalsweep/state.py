"""Pluggable job-state stores for the Taskmaster service.

The default in-memory store is convenient for ephemeral runs. SQLite provides
restart-safe local development without adding a dependency; the interface is
intentionally small so Firestore can replace it for Cloud Run later.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, Protocol


class JobStore(Protocol):
    """Minimal persistence contract used by the HTTP service."""

    def put(self, event_id: str, record: dict[str, Any]) -> None:
        ...

    def get(self, event_id: str) -> dict[str, Any] | None:
        ...

    def delete(self, event_id: str) -> None:
        ...


def _clone(record: dict[str, Any]) -> dict[str, Any]:
    """Keep callers from mutating the store's internal record."""

    return json.loads(json.dumps(record, ensure_ascii=False))


class InMemoryJobStore:
    """Thread-safe store for tests and short-lived local demos."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def put(self, event_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._records[event_id] = _clone(record)

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._records.get(event_id)
            return _clone(record) if record is not None else None

    def delete(self, event_id: str) -> None:
        with self._lock:
            self._records.pop(event_id, None)


class SQLiteJobStore:
    """Restart-safe local store backed by Python's standard sqlite3 module."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    event_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at REAL NOT NULL DEFAULT (unixepoch())
                )
                """
            )

    def put(self, event_id: str, record: dict[str, Any]) -> None:
        payload = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs(event_id, payload, updated_at)
                VALUES (?, ?, unixepoch())
                ON CONFLICT(event_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (event_id, payload),
            )

    def get(self, event_id: str) -> dict[str, Any] | None:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM jobs WHERE event_id = ?",
                (event_id,),
            ).fetchone()
        return json.loads(row[0]) if row else None

    def delete(self, event_id: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM jobs WHERE event_id = ?", (event_id,))


def create_job_store() -> JobStore:
    """Build the configured store without importing cloud SDKs."""

    backend = os.getenv("SIGNALSWEEP_STATE_BACKEND", "memory").strip().lower()
    if backend == "memory":
        return InMemoryJobStore()
    if backend == "sqlite":
        path = os.getenv("SIGNALSWEEP_STATE_PATH", ".artifacts/jobs.sqlite3")
        return SQLiteJobStore(path)
    raise ValueError("SIGNALSWEEP_STATE_BACKEND must be 'memory' or 'sqlite'.")
