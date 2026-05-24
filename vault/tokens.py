"""Token derivation — HMAC-SHA256 keyed by the per-session SVK.

The token grammar deliberately matches the deobfuscation regex (see TOKEN_RE).
Cryptographic properties:
  - Deterministic within a session: same (svk, type, value) -> same token.
  - Non-deterministic across sessions: different SVKs produce unrelated tokens.
  - One-way: a token without the SVK reveals nothing about the value.

The same HMAC primitive is also used to compute a *dedupe key* (different
namespace) so the vault can deduplicate by (entity_type, value) regardless of
which obfuscation strategy is in use.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import unicodedata

# Matches [PHI_NAME_k7a2mqpz], [PHI_INSURANCE_ID_p3hxk5n7], [LEGAL_PRIVILEGE_a4bcde5f].
# - One-or-more uppercase _-separated segments before the shortid.
# - 8 lowercased base32 chars (alphabet a-z 2-7, RFC 4648).
TOKEN_RE = re.compile(r"\[[A-Z]+(?:_[A-Z]+)+_[a-z2-7]{8}\]")

_SHORTID_BYTES = 5  # 5 bytes -> 8 base32 chars exactly, no padding.


def canonicalize(value: str) -> str:
    """Normalize value before HMAC so trivial variants ('John', 'john ', 'JOHN')
    map to the same token. Documented behavior — collapses meaningless variation
    while preserving the semantic identity of the entity.
    """
    return unicodedata.normalize("NFKC", value).strip().lower()


def _hmac_short(svk: bytes, namespace: bytes, payload: bytes) -> str:
    """Domain-separated HMAC → 8-char lowercased base32."""
    digest = hmac.new(svk, namespace + b"\x00" + payload, hashlib.sha256).digest()
    return base64.b32encode(digest[:_SHORTID_BYTES]).decode("ascii").lower()


def derive_short_id(svk: bytes, entity_type: str, value: str) -> str:
    payload = f"{entity_type}\x00{canonicalize(value)}".encode()
    return _hmac_short(svk, b"token", payload)


def make_token(svk: bytes, entity_type: str, value: str) -> str:
    short = derive_short_id(svk, entity_type, value)
    return f"[{entity_type}_{short}]"


def compute_dedupe_key(svk: bytes, entity_type: str, value: str) -> str:
    """Stable per-session key used by the vault to deduplicate by (type, value).

    Domain-separated from the token derivation so vault rows and tokens stay
    distinguishable in the schema. Without the SVK, the dedupe key reveals
    nothing about the value.
    """
    payload = f"{entity_type}\x00{canonicalize(value)}".encode()
    digest = hmac.new(svk, b"dedupe\x00" + payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:16]).decode("ascii").rstrip("=")
