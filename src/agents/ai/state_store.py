"""Opt-in SQL state store for the On-Prem Day-2 stores (roadmap item ④).

The approval and incident stores ship as append-only JSONL files — perfect for
the single-writer offline posture, and the reason the Helm chart pins
``replicas: 1``. This module is the productionization seam: the same
append-only, latest-row-per-key semantics on a SQL backend, so multiple
replicas can share state through PostgreSQL instead of a RWO volume.

Design mirrors the repo's other opt-in seams:

  - **Off by default.** ``PLATFORM_STATE_DSN`` unset → JSONL, byte-for-byte
    unchanged. Set it to a PostgreSQL DSN and the stores route here.
  - **Injected backend.** The store takes a DB-API ``connect`` factory plus its
    parameter placeholder, so unit tests drive it with stdlib ``sqlite3`` fully
    offline; live runs use ``psycopg2`` against a real PostgreSQL.
  - **Append-only.** Rows are never updated or deleted; readers reduce to the
    latest row per key — exactly the JSONL lifecycle, so approval resolution
    stays "append a new row with the same id".
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable

# One table holds every kind of record (APPROVAL / INCIDENT), keyed for
# latest-wins reduction. ``id`` preserves append order within equal timestamps.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS platform_state (
    id {autoincrement},
    kind TEXT NOT NULL,
    key TEXT NOT NULL,
    record TEXT NOT NULL
)
"""
_INDEX = "CREATE INDEX IF NOT EXISTS platform_state_kind_key ON platform_state (kind, key)"


class SQLStateStore:
    """Append-only row store over any DB-API connection factory."""

    def __init__(
        self,
        connect: Callable[[], Any],
        *,
        placeholder: str = "%s",
        autoincrement: str = "BIGSERIAL PRIMARY KEY",
    ) -> None:
        self._connect = connect
        self._ph = placeholder
        self._autoincrement = autoincrement
        self._initialised = False

    def _conn(self) -> Any:
        conn = self._connect()
        if not self._initialised:
            with conn:
                cur = conn.cursor()
                cur.execute(_SCHEMA.format(autoincrement=self._autoincrement))
                cur.execute(_INDEX)
            self._initialised = True
        return conn

    def append(self, kind: str, key: str, record: dict[str, Any]) -> None:
        conn = self._conn()
        try:
            with conn:
                conn.cursor().execute(
                    f"INSERT INTO platform_state (kind, key, record) "
                    f"VALUES ({self._ph}, {self._ph}, {self._ph})",
                    (kind, key, json.dumps(record, default=str)),
                )
        finally:
            conn.close()

    def rows(self, kind: str) -> list[dict[str, Any]]:
        """Every appended row for ``kind`` in append order (callers reduce
        latest-per-key themselves, same as the JSONL readers)."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                f"SELECT record FROM platform_state WHERE kind = {self._ph} ORDER BY id",
                (kind,),
            )
            out: list[dict[str, Any]] = []
            for (raw,) in cur.fetchall():
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
            return out
        finally:
            conn.close()


def from_dsn(dsn: str) -> SQLStateStore:
    """Build a store for a DSN. ``postgresql://`` uses psycopg2; ``sqlite://<path>``
    (tests/dev) uses stdlib sqlite3."""
    if dsn.startswith("sqlite://"):
        import sqlite3

        path = dsn[len("sqlite://") :]
        return SQLStateStore(
            lambda: sqlite3.connect(path),
            placeholder="?",
            autoincrement="INTEGER PRIMARY KEY AUTOINCREMENT",
        )
    import psycopg2  # optional extra: pip install .[state]

    return SQLStateStore(lambda: psycopg2.connect(dsn))


def configured_store() -> SQLStateStore | None:
    """The env-selected store, or ``None`` to stay on JSONL (the default)."""
    dsn = os.getenv("PLATFORM_STATE_DSN", "").strip()
    return from_dsn(dsn) if dsn else None


__all__ = ["SQLStateStore", "configured_store", "from_dsn"]
