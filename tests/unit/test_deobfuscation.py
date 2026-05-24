"""Deobfuscation tests — both strategies, vault miss, inflection, leak detection."""
from __future__ import annotations

from pathlib import Path

import pytest

from audit import JSONLAuditLog
from deobfuscation import UNRESOLVED_SENTINEL, Deobfuscator, TokenLeakError
from obfuscation.strategies import PseudonymizationStrategy, TokenizationStrategy
from vault import SessionVault

# ---------------------------------------------------------------- tokenization restoration

async def test_restore_single_token(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    strat = TokenizationStrategy()
    from detection.entity import Entity

    token = await strat.replace(
        Entity(type="PHI_NAME", text="John Smith", start=0, end=10, confidence=0.95),
        session_vault,
    )
    text = f"The patient {token} has a follow-up appointment."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "tokenize")
    assert restored == "The patient John Smith has a follow-up appointment."


async def test_restore_multiple_tokens_idempotent_per_value(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    from detection.entity import Entity

    strat = TokenizationStrategy()
    t_name = await strat.replace(
        Entity(type="PHI_NAME", text="Jane Doe", start=0, end=8, confidence=0.95),
        session_vault,
    )
    t_diag = await strat.replace(
        Entity(type="PHI_DIAGNOSIS", text="hypertension", start=0, end=12, confidence=0.9),
        session_vault,
    )
    text = f"{t_name} has {t_diag}. {t_name}'s last visit was Tuesday."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "tokenize")
    assert restored == "Jane Doe has hypertension. Jane Doe's last visit was Tuesday."


async def test_restore_vault_miss_uses_sentinel(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    """Tokens not in vault (e.g. from a destroyed session) get the sentinel."""
    text = "Reference to [PHI_NAME_aaaaaaaa] from another session."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "tokenize")
    assert UNRESOLVED_SENTINEL in restored
    assert "[PHI_NAME_aaaaaaaa]" not in restored


async def test_restore_raises_on_token_leak(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    """Defensive post-condition: a successfully-matched token that doesn't get
    replaced should not silently leak. Here we monkey-patch the regex to skip
    replacement, simulating a bug — Deobfuscator must raise."""
    text = "[PHI_NAME_aaaaaaaa]"
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))

    # Cause the restore path to leave a token in place: feed text that
    # bypasses the regex pass via a no-op stub.
    async def _restore_noop(text: str, vault: SessionVault) -> str:
        return text  # leaves the token

    deob._restore_tokens = _restore_noop  # type: ignore[method-assign]
    with pytest.raises(TokenLeakError):
        await deob.restore(text, session_vault, "tokenize")


async def test_restore_handles_possessive_around_token(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    from detection.entity import Entity

    strat = TokenizationStrategy()
    token = await strat.replace(
        Entity(type="PHI_NAME", text="Sofia Reyes", start=0, end=11, confidence=0.95),
        session_vault,
    )
    text = f"{token}'s chart shows nothing unusual."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "tokenize")
    assert restored == "Sofia Reyes's chart shows nothing unusual."


# ---------------------------------------------------------------- pseudonymization restoration

async def test_pseudonym_restore_plain(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    from detection.entity import Entity

    strat = PseudonymizationStrategy()
    surrogate = await strat.replace(
        Entity(type="PII_NAME", text="John Smith", start=0, end=10, confidence=0.95),
        session_vault,
    )
    text = f"{surrogate} is the new patient."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "pseudonymize")
    assert "John Smith" in restored
    assert surrogate not in restored


async def test_pseudonym_restore_possessive(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    from detection.entity import Entity

    strat = PseudonymizationStrategy()
    surrogate = await strat.replace(
        Entity(type="PII_NAME", text="Jane Doe", start=0, end=8, confidence=0.95),
        session_vault,
    )
    # LLM might write "{surrogate}'s chart" — the possessive 's appears after.
    text = f"{surrogate}'s chart was reviewed."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "pseudonymize")
    assert "Jane Doe's" in restored


async def test_pseudonym_restore_longest_first(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    """Two surrogates where one is a substring of another. The longer must win."""

    # Force specific surrogates via direct vault.store so we control the names.
    await session_vault.store(
        "PII_NAME", "John Smith", factory=lambda _t, _v: "Michael Torres Jr."
    )
    await session_vault.store(
        "PII_NAME", "Michael Lee", factory=lambda _t, _v: "Michael Torres"
    )

    text = "Michael Torres Jr. spoke about Michael Torres."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "pseudonymize")
    # "Michael Torres Jr." -> "John Smith"
    # "Michael Torres" (standalone) -> "Michael Lee"
    assert "John Smith" in restored
    assert "Michael Lee" in restored
    assert "Torres" not in restored


async def test_pseudonym_restore_also_restores_token_fallbacks(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    """Low-confidence entities degrade to opaque tokens even in pseudonym mode."""
    from detection.entity import Entity

    token_strat = TokenizationStrategy()
    token = await token_strat.replace(
        Entity(type="PHI_MEDICATION", text="50 mg", start=0, end=5, confidence=0.4),
        session_vault,
    )

    text = f"Medication dose: {token}."
    deob = Deobfuscator(JSONLAuditLog(tmp_path / "audit.jsonl"))
    restored = await deob.restore(text, session_vault, "pseudonymize")

    assert restored == "Medication dose: 50 mg."
