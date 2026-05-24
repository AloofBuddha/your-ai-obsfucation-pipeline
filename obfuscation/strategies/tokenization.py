"""Tokenization — replace with [TYPE_HASH] opaque tokens.

This is the most secure strategy. Tokens are meaningless without the vault, so
the LLM provider sees zero information about the original entity. Trade-off:
the LLM can't reason about the entity in any semantic way (a token isn't a
plausible name to the model).
"""
from __future__ import annotations

from detection.entity import Entity
from obfuscation.strategies.base import ObfuscationStrategy
from vault import SessionVault


class TokenizationStrategy(ObfuscationStrategy):
    """Default vault behavior: no factory means HMAC-derived [TYPE_xxxxxxxx]."""

    name = "tokenize"

    async def replace(self, entity: Entity, vault: SessionVault) -> str:
        return await vault.store(entity.type, entity.text)
