"""LLMClient Protocol — minimal async generate() interface."""
from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    """The pipeline only needs one operation: send a system+user prompt, get text back.

    Implementations should treat the input as opaque text — the pipeline has
    already obfuscated all PII before reaching this layer.
    """

    async def generate(self, *, system: str, user: str) -> str: ...
