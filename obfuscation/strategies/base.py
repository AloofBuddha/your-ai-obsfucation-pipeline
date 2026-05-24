"""Obfuscation strategy ABC.

Adding a new strategy = new class implementing replace(), then register it in
obfuscation.strategies.__init__:make_strategy. Zero changes to vault, detection,
engine, or pipeline.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from detection.entity import Entity
from vault import SessionVault


class ObfuscationStrategy(ABC):
    """Replaces a detected entity with some safe-to-send string."""

    name: str  # short identifier, used by the env-var factory

    @abstractmethod
    async def replace(self, entity: Entity, vault: SessionVault) -> str:
        """Return the replacement string, registering it in the vault.

        Idempotency: calling replace() twice with the same entity (within the
        same session) must return the same string. The vault deduplicates via
        the HMAC dedupe_key, so implementations don't need their own cache.
        """
