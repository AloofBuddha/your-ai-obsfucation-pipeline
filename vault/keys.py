"""Session vault key (SVK) — random 32 bytes, in-memory only."""
from __future__ import annotations

import base64
import secrets


def generate_svk() -> bytes:
    """Random 32 bytes for HMAC + Fernet derivation."""
    return secrets.token_bytes(32)


def fernet_key_from_svk(svk: bytes) -> bytes:
    """Fernet requires a 32-byte URL-safe-base64-encoded key."""
    if len(svk) != 32:
        raise ValueError(f"SVK must be 32 bytes, got {len(svk)}")
    return base64.urlsafe_b64encode(svk)
