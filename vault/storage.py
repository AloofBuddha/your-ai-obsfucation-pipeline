"""Vault SQLite backend — encrypted-row store, session-scoped.

Schema design:
  entries(session_id, dedupe_key, replacement, entity_type, ciphertext)
  - PRIMARY KEY (session_id, replacement) so lookup-by-replacement is indexed.
  - INDEX on (session_id, dedupe_key) so dedup checks are O(log n).
  - `replacement` is the string that appears in the obfuscated text (either an
    HMAC token like [PHI_NAME_xxx] for tokenization, or a Faker surrogate like
    "Michael Torres" for pseudonymization).
  - `dedupe_key` is HMAC(svk, entity_type+value) — lets us detect "have we
    already replaced this entity in this session?" without exposing the value.
"""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Self

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at REAL NOT NULL,
    alive INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS entries (
    session_id    TEXT NOT NULL,
    dedupe_key    TEXT NOT NULL,
    replacement   TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    ciphertext    BLOB NOT NULL,
    PRIMARY KEY (session_id, replacement)
);

CREATE INDEX IF NOT EXISTS idx_entries_session ON entries(session_id);
CREATE INDEX IF NOT EXISTS idx_entries_dedupe  ON entries(session_id, dedupe_key);
"""


class VaultDB:
    """Async wrapper around the vault SQLite file. WAL mode for concurrent reads.
    Single-instance only — HA out of scope.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    @property
    def path(self) -> Path:
        return self._path

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._conn is not None:
            return
        self._conn = await aiosqlite.connect(self._path)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("VaultDB not connected — call .connect() or use async with")
        return self._conn

    async def register_session(self, session_id: str) -> None:
        conn = self._require_conn()
        await conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, created_at, alive) "
            "VALUES (?, strftime('%s','now'), 1)",
            (session_id,),
        )
        await conn.commit()

    async def end_session(self, session_id: str) -> None:
        """Mark dead and wipe rows. Irreversible."""
        conn = self._require_conn()
        await conn.execute("DELETE FROM entries WHERE session_id = ?", (session_id,))
        await conn.execute(
            "UPDATE sessions SET alive = 0 WHERE session_id = ?", (session_id,)
        )
        await conn.commit()

    async def cleanup_orphans(self, active_sessions: Iterable[str]) -> int:
        """Wipe rows for sessions not in `active_sessions`. Returns count of
        sessions cleaned (rows are unreadable without their SVK anyway)."""
        conn = self._require_conn()
        active = set(active_sessions)
        cursor = await conn.execute("SELECT DISTINCT session_id FROM entries")
        all_session_ids = {row[0] for row in await cursor.fetchall()}
        orphan_ids = all_session_ids - active
        if not orphan_ids:
            return 0
        placeholders = ",".join("?" * len(orphan_ids))
        await conn.execute(
            f"DELETE FROM entries WHERE session_id IN ({placeholders})",
            tuple(orphan_ids),
        )
        await conn.execute(
            f"DELETE FROM sessions WHERE session_id IN ({placeholders})",
            tuple(orphan_ids),
        )
        await conn.commit()
        return len(orphan_ids)

    async def find_by_dedupe(
        self, session_id: str, dedupe_key: str
    ) -> str | None:
        """Return the existing `replacement` for (session, dedupe_key) if any."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT replacement FROM entries WHERE session_id = ? AND dedupe_key = ?",
            (session_id, dedupe_key),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def insert_entry(
        self,
        session_id: str,
        dedupe_key: str,
        replacement: str,
        entity_type: str,
        ciphertext: bytes,
    ) -> None:
        """Idempotent on (session_id, replacement). Callers should call
        find_by_dedupe() first to avoid generating new surrogates needlessly.
        """
        conn = self._require_conn()
        await conn.execute(
            "INSERT OR IGNORE INTO entries "
            "(session_id, dedupe_key, replacement, entity_type, ciphertext) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, dedupe_key, replacement, entity_type, ciphertext),
        )
        await conn.commit()

    async def lookup(self, session_id: str, replacement: str) -> bytes | None:
        """Return ciphertext for a given replacement string, or None."""
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT ciphertext FROM entries WHERE session_id = ? AND replacement = ?",
            (session_id, replacement),
        )
        row = await cursor.fetchone()
        return bytes(row[0]) if row else None

    async def lookup_many(
        self, session_id: str, replacements: Iterable[str]
    ) -> dict[str, bytes]:
        """Return ciphertexts for replacement strings in one indexed query."""
        replacements = tuple(dict.fromkeys(replacements))
        if not replacements:
            return {}
        conn = self._require_conn()
        placeholders = ",".join("?" * len(replacements))
        cursor = await conn.execute(
            "SELECT replacement, ciphertext FROM entries "
            f"WHERE session_id = ? AND replacement IN ({placeholders})",
            (session_id, *replacements),
        )
        return {row[0]: bytes(row[1]) for row in await cursor.fetchall()}

    async def all_replacements(
        self, session_id: str
    ) -> list[tuple[str, str]]:
        """Return [(replacement, entity_type), ...] for a session.

        Used by the pseudonymization de-obfuscation pass which needs the full
        list of surrogates to scan the LLM response for. Does NOT return
        ciphertext.
        """
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT replacement, entity_type FROM entries WHERE session_id = ?",
            (session_id,),
        )
        return [(row[0], row[1]) for row in await cursor.fetchall()]

    async def is_session_alive(self, session_id: str) -> bool:
        conn = self._require_conn()
        cursor = await conn.execute(
            "SELECT alive FROM sessions WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return bool(row and row[0] == 1)
