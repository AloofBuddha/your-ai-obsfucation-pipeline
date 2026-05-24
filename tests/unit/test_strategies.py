"""Obfuscation strategy tests — both implement the ABC, both dedupe-on-repeat."""
from __future__ import annotations

import pytest

from detection.entity import Entity
from obfuscation.strategies import (
    PseudonymizationStrategy,
    TokenizationStrategy,
    available_strategies,
    make_strategy,
)
from vault import TOKEN_RE, SessionVault


def _entity(type_: str, text: str) -> Entity:
    return Entity(type=type_, text=text, start=0, end=len(text), confidence=0.9)


def test_factory_returns_known_strategies() -> None:
    assert isinstance(make_strategy("tokenize"), TokenizationStrategy)
    assert isinstance(make_strategy("pseudonymize"), PseudonymizationStrategy)


def test_factory_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown obfuscation strategy"):
        make_strategy("rot13")


def test_available_strategies_lists_both() -> None:
    names = set(available_strategies())
    assert {"tokenize", "pseudonymize"}.issubset(names)


# ---------------------------------------------------------------- tokenization

async def test_tokenization_returns_typed_token(session_vault: SessionVault) -> None:
    strategy = TokenizationStrategy()
    replacement = await strategy.replace(_entity("PHI_NAME", "John Smith"), session_vault)
    assert TOKEN_RE.fullmatch(replacement)
    assert "PHI_NAME" in replacement


async def test_tokenization_idempotent(session_vault: SessionVault) -> None:
    strategy = TokenizationStrategy()
    t1 = await strategy.replace(_entity("PHI_NAME", "John Smith"), session_vault)
    t2 = await strategy.replace(_entity("PHI_NAME", "John Smith"), session_vault)
    assert t1 == t2


async def test_tokenization_lookup_recovers_original(
    session_vault: SessionVault,
) -> None:
    strategy = TokenizationStrategy()
    token = await strategy.replace(_entity("PHI_NAME", "John Smith"), session_vault)
    assert await session_vault.lookup(token) == "John Smith"


# ---------------------------------------------------------------- pseudonymization

async def test_pseudonymization_returns_realistic_name(
    session_vault: SessionVault,
) -> None:
    strategy = PseudonymizationStrategy()
    replacement = await strategy.replace(
        _entity("PII_NAME", "John Smith"), session_vault
    )
    # Should not be a bracketed token.
    assert not TOKEN_RE.match(replacement)
    # Should not be the original.
    assert replacement != "John Smith"
    # Should look name-shaped.
    assert " " in replacement


async def test_pseudonymization_idempotent_within_session(
    session_vault: SessionVault,
) -> None:
    """Vault dedup means same entity -> same surrogate, even across two
    PseudonymizationStrategy.replace() calls."""
    strategy = PseudonymizationStrategy()
    s1 = await strategy.replace(_entity("PII_NAME", "John Smith"), session_vault)
    s2 = await strategy.replace(_entity("PII_NAME", "John Smith"), session_vault)
    assert s1 == s2


async def test_pseudonymization_email_looks_email_shaped(
    session_vault: SessionVault,
) -> None:
    strategy = PseudonymizationStrategy()
    replacement = await strategy.replace(
        _entity("PII_EMAIL", "patient@example.com"), session_vault
    )
    assert "@" in replacement


async def test_pseudonymization_ssn_looks_ssn_shaped(
    session_vault: SessionVault,
) -> None:
    strategy = PseudonymizationStrategy()
    replacement = await strategy.replace(
        _entity("PII_SSN", "529-99-0001"), session_vault
    )
    # Faker's ssn() produces XXX-XX-XXXX shape.
    assert len(replacement.replace("-", "")) == 9


async def test_pseudonymization_diagnosis_is_placeholder(
    session_vault: SessionVault,
) -> None:
    """Faker doesn't have medical condition generators; we use a placeholder
    so the LLM gets grammatical structure without acting on a fake diagnosis."""
    strategy = PseudonymizationStrategy()
    replacement = await strategy.replace(
        _entity("PHI_DIAGNOSIS", "Type 2 diabetes"), session_vault
    )
    assert replacement.startswith("[medical condition ")
    assert replacement.endswith("]")


async def test_pseudonymization_placeholders_are_unique_and_restorable(
    session_vault: SessionVault,
) -> None:
    strategy = PseudonymizationStrategy()

    diabetes = await strategy.replace(
        _entity("PHI_DIAGNOSIS", "Type 2 diabetes"), session_vault
    )
    depression = await strategy.replace(
        _entity("PHI_DIAGNOSIS", "depression"), session_vault
    )

    assert diabetes != depression
    assert await session_vault.lookup(diabetes) == "Type 2 diabetes"
    assert await session_vault.lookup(depression) == "depression"


async def test_pseudonymization_unknown_type_falls_back(
    session_vault: SessionVault,
) -> None:
    strategy = PseudonymizationStrategy()
    replacement = await strategy.replace(
        _entity("WEIRD_NEW_TYPE", "secret payload"), session_vault
    )
    # Must not leak the original.
    assert "secret payload" not in replacement


async def test_pseudonymization_unknown_type_placeholders_are_unique(
    session_vault: SessionVault,
) -> None:
    strategy = PseudonymizationStrategy()

    first = await strategy.replace(_entity("PII_IP", "192.0.2.1"), session_vault)
    second = await strategy.replace(_entity("PII_IP", "198.51.100.2"), session_vault)

    assert first != second
    assert await session_vault.lookup(first) == "192.0.2.1"
    assert await session_vault.lookup(second) == "198.51.100.2"
