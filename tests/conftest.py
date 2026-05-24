"""Shared test fixtures."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest_asyncio

from audit import JSONLAuditLog
from vault import SessionVault, VaultDB, generate_svk


@pytest_asyncio.fixture
async def vault_db(tmp_path: Path) -> AsyncIterator[VaultDB]:
    """A connected VaultDB scoped to one test, closed cleanly on teardown."""
    db = VaultDB(tmp_path / "vault.db")
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture
async def session_vault(
    vault_db: VaultDB, tmp_path: Path
) -> AsyncIterator[SessionVault]:
    """A ready-to-use SessionVault for the default session id 'sess_test'."""
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    svk = generate_svk()
    await vault_db.register_session("sess_test")
    vault = SessionVault("sess_test", svk, vault_db, audit)
    try:
        yield vault
    finally:
        if vault.alive:
            await vault.destroy()
