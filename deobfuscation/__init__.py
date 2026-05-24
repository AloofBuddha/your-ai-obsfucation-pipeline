"""Deobfuscation — restore the LLM response to user-facing form."""
from deobfuscation.restorer import (
    UNRESOLVED_SENTINEL,
    Deobfuscator,
    TokenLeakError,
)

__all__ = ["UNRESOLVED_SENTINEL", "Deobfuscator", "TokenLeakError"]
