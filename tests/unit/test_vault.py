"""Vault tests — token derivation properties + session isolation + irreversibility."""
from __future__ import annotations

from pathlib import Path

import pytest

from audit import JSONLAuditLog
from vault import (
    TOKEN_RE,
    SessionExpiredError,
    SessionVault,
    VaultDB,
    canonicalize,
    generate_svk,
    make_token,
)

# ---------------------------------------------------------------- token derivation

def test_canonicalize_strips_and_lowers() -> None:
    assert canonicalize("John ") == canonicalize("JOHN") == canonicalize("john")


def test_token_deterministic_within_session() -> None:
    svk = generate_svk()
    t1 = make_token(svk, "PHI_NAME", "John Smith")
    t2 = make_token(svk, "PHI_NAME", "John Smith")
    assert t1 == t2


def test_token_nondeterministic_across_sessions() -> None:
    """Same value + different SVK -> different tokens. This is the cryptographic
    basis for 'irreversible across sessions' — PRD critical constraint."""
    svk_a = generate_svk()
    svk_b = generate_svk()
    t_a = make_token(svk_a, "PHI_NAME", "John Smith")
    t_b = make_token(svk_b, "PHI_NAME", "John Smith")
    assert t_a != t_b


def test_token_matches_regex() -> None:
    svk = generate_svk()
    for entity_type in [
        "PHI_NAME",
        "PHI_DIAGNOSIS",
        "PHI_INSURANCE_ID",  # three segments
        "FIN_ACCOUNT_NUMBER",  # three segments
        "LEGAL_PRIVILEGE",
        "PII_SSN",
    ]:
        token = make_token(svk, entity_type, "some value")
        assert TOKEN_RE.fullmatch(token), f"Token {token!r} doesn't match TOKEN_RE"


def test_token_handles_unicode() -> None:
    """NFKC normalization should make visually-equivalent strings hash the same."""
    svk = generate_svk()
    # U+00E9 (é precomposed) vs U+0065 U+0301 (e + combining acute)
    t1 = make_token(svk, "PHI_NAME", "Beyoncé")
    t2 = make_token(svk, "PHI_NAME", "Beyoncé")
    assert t1 == t2


def test_token_different_types_get_different_tokens() -> None:
    """Same value, different entity type -> different tokens. Prevents
    a name and a city with the same string from colliding."""
    svk = generate_svk()
    t_name = make_token(svk, "PHI_NAME", "Sydney")
    t_addr = make_token(svk, "PII_ADDRESS", "Sydney")
    assert t_name != t_addr


# ---------------------------------------------------------------- vault lifecycle

async def test_store_and_lookup_roundtrip(session_vault: SessionVault) -> None:
    token = await session_vault.store("PHI_NAME", "John Smith")
    assert TOKEN_RE.fullmatch(token)
    assert await session_vault.lookup(token) == "John Smith"


async def test_store_idempotent_same_value(session_vault: SessionVault) -> None:
    """PRD: same entity in same session maps to the same token."""
    t1 = await session_vault.store("PHI_NAME", "John Smith")
    t2 = await session_vault.store("PHI_NAME", "John Smith")
    assert t1 == t2


async def test_lookup_miss_returns_none(session_vault: SessionVault) -> None:
    assert await session_vault.lookup("[PHI_NAME_aaaaaaaa]") is None


async def test_destroy_clears_rows_and_blocks_further_ops(
    session_vault: SessionVault,
) -> None:
    token = await session_vault.store("PHI_NAME", "John Smith")
    assert await session_vault.lookup(token) == "John Smith"
    await session_vault.destroy()

    with pytest.raises(SessionExpiredError):
        await session_vault.store("PHI_NAME", "Anyone")
    with pytest.raises(SessionExpiredError):
        await session_vault.lookup(token)
    assert not session_vault.alive


async def test_destroy_is_idempotent(session_vault: SessionVault) -> None:
    await session_vault.destroy()
    await session_vault.destroy()  # should not raise


async def test_session_destroy_irreversible_even_with_db_intact(
    vault_db: VaultDB, tmp_path: Path
) -> None:
    """The vault is destroyed; the DB file persists. A new session with a
    different SVK cannot decrypt the (deleted) rows. Even if the rows leaked
    via backup, decryption is impossible."""
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")

    # Session A: store, then destroy.
    svk_a = generate_svk()
    await vault_db.register_session("A")
    vault_a = SessionVault("A", svk_a, vault_db, audit)
    token_a = await vault_a.store("PHI_NAME", "John Smith")
    await vault_a.destroy()

    # New session B with a different SVK cannot lookup A's token.
    svk_b = generate_svk()
    await vault_db.register_session("B")
    vault_b = SessionVault("B", svk_b, vault_db, audit)
    assert await vault_b.lookup(token_a) is None


async def test_cross_session_isolation_same_value_same_user(
    vault_db: VaultDB, tmp_path: Path
) -> None:
    """PRD: 'concurrent session isolation' — two sessions, same input -> different tokens."""
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    await vault_db.register_session("A")
    await vault_db.register_session("B")
    svk_a, svk_b = generate_svk(), generate_svk()
    vault_a = SessionVault("A", svk_a, vault_db, audit)
    vault_b = SessionVault("B", svk_b, vault_db, audit)

    token_a = await vault_a.store("PHI_NAME", "John Smith")
    token_b = await vault_b.store("PHI_NAME", "John Smith")
    assert token_a != token_b
    assert await vault_a.lookup(token_b) is None
    assert await vault_b.lookup(token_a) is None


async def test_orphan_cleanup(vault_db: VaultDB, tmp_path: Path) -> None:
    """If the API crashes between sessions, rows persist on disk but their SVK
    is gone (in-memory only) — so they're unreadable. Cleanup wipes them on
    startup."""
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    await vault_db.register_session("dead")
    svk = generate_svk()
    vault = SessionVault("dead", svk, vault_db, audit)
    await vault.store("PHI_NAME", "John")
    # Don't destroy — simulate a crash.

    deleted = await vault_db.cleanup_orphans(active_sessions=[])
    assert deleted == 1
    assert await vault_db.lookup("dead", "any-token") is None


async def test_db_isolation_no_value_leak_in_audit(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    """The audit log emitted during vault.store() must not contain the value."""
    secret_value = "PATIENT_NAME_NEVER_LEAK_12345"
    await session_vault.store("PHI_NAME", secret_value)

    audit_text = (tmp_path / "audit.jsonl").read_text()
    assert secret_value not in audit_text
