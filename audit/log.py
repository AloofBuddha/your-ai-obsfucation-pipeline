"""Async JSONL audit log writer."""
from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

import aiofiles

from audit.event import AuditEvent


class AuditLog(Protocol):
    async def emit(self, event: AuditEvent) -> None: ...


class JSONLAuditLog:
    """Append-only JSONL writer. One event per line.

    A process-wide lock serializes writes so concurrent emits don't interleave
    half-lines. The lock is fine for single-instance MVP; production would use
    a queue + background flusher.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    @property
    def path(self) -> Path:
        return self._path

    async def emit(self, event: AuditEvent) -> None:
        line = event.model_dump_json() + "\n"
        async with (
            self._lock,
            aiofiles.open(self._path, mode="a", encoding="utf-8") as f,
        ):
            await f.write(line)

    async def emit_many(self, events: Sequence[AuditEvent]) -> None:
        if not events:
            return
        lines = "".join(event.model_dump_json() + "\n" for event in events)
        async with (
            self._lock,
            aiofiles.open(self._path, mode="a", encoding="utf-8") as f,
        ):
            await f.write(lines)
