"""Pseudonymization — replace with realistic surrogates (Faker) per entity type.

The LLM sees plausible names/addresses/etc., which preserves utility for tasks
that rely on grammatical structure (summarization, narrative generation). The
trade-off: an adversary with both the obfuscated doc and the response can do
frequency-based correlation. See README known gaps.

Cross-session: each session gets a fresh Faker — same original maps to a
*different* surrogate in a different session, matching the irreversibility
property.
"""
from __future__ import annotations

from collections.abc import Callable

from faker import Faker

from detection.entity import Entity
from detection.types import (
    FIN_ACCOUNT_NUMBER,
    FIN_TAX_ID,
    LEGAL_PRIVILEGE,
    PHI_DIAGNOSIS,
    PHI_INSURANCE_ID,
    PHI_MEDICATION,
    PHI_MRN,
    PII_ADDRESS,
    PII_DOB,
    PII_EMAIL,
    PII_NAME,
    PII_PHONE,
    PII_SSN,
)
from obfuscation.strategies.base import ObfuscationStrategy
from vault import SessionVault


class PseudonymizationStrategy(ObfuscationStrategy):
    name = "pseudonymize"

    def __init__(self) -> None:
        # Use a fresh Faker so this session's surrogates are independent of any
        # other session's. We don't seed — non-determinism across sessions is a
        # security property, not a bug.
        self._faker = Faker()
        self._generators: dict[str, Callable[[str, str], str]] = {
            PII_NAME: lambda _t, _v: self._faker.name(),
            PII_SSN: lambda _t, _v: self._faker.ssn(),
            PII_PHONE: lambda _t, _v: self._faker.phone_number(),
            PII_EMAIL: lambda _t, _v: self._faker.email(),
            PII_DOB: lambda _t, _v: self._faker.date_of_birth().isoformat(),
            PII_ADDRESS: lambda _t, _v: self._faker.street_address(),
            PHI_DIAGNOSIS: lambda _t, _v: self._unique_placeholder("medical condition"),
            PHI_MEDICATION: lambda _t, _v: self._unique_placeholder("prescribed medication"),
            PHI_MRN: lambda _t, _v: f"MRN{self._faker.numerify('#######')}",
            PHI_INSURANCE_ID: lambda _t, _v: f"Member ID: {self._faker.bothify('?#######').upper()}",
            FIN_ACCOUNT_NUMBER: lambda _t, _v: self._faker.credit_card_number(),
            FIN_TAX_ID: lambda _t, _v: self._faker.ein(),
            LEGAL_PRIVILEGE: lambda _t, _v: self._unique_placeholder("confidential marker"),
        }

    def _unique_placeholder(self, label: str) -> str:
        """Stable via vault dedupe per original, unique across distinct originals."""
        return f"[{label} {self._faker.unique.bothify('????-####').lower()}]"

    async def replace(self, entity: Entity, vault: SessionVault) -> str:
        generator = self._generators.get(entity.type)
        if generator is None:
            # Unknown entity type: fall back to a typed placeholder so we never
            # emit raw text. The factory is per-call so each unknown entity
            # gets a stable surrogate via the vault's dedup.
            def generator(t: str, _v: str) -> str:  # noqa: E731
                return self._unique_placeholder(f"redacted {t.lower()}")
        return await vault.store(entity.type, entity.text, factory=generator)
