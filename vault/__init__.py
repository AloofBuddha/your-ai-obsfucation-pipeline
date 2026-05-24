"""Vault — session-scoped, encrypted token/value mapping."""
from vault.keys import fernet_key_from_svk, generate_svk
from vault.session import ReplacementFactory, SessionExpiredError, SessionVault
from vault.storage import VaultDB
from vault.tokens import (
    TOKEN_RE,
    canonicalize,
    compute_dedupe_key,
    derive_short_id,
    make_token,
)

__all__ = [
    "TOKEN_RE",
    "ReplacementFactory",
    "SessionExpiredError",
    "SessionVault",
    "VaultDB",
    "canonicalize",
    "compute_dedupe_key",
    "derive_short_id",
    "fernet_key_from_svk",
    "generate_svk",
    "make_token",
]
