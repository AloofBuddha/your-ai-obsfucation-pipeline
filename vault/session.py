"""Session vault — token/value mapping for the lifetime of one session.

Lifecycle:
    1. start_session() generates a random SVK in-memory.
    2. .store() derives tokens via HMAC(SVK, ...) and encrypts values via Fernet(SVK).
    3. .destroy() wipes rows from SQLite and best-effort zeroes the SVK.

After destroy(), the Fernet key is gone — any leftover ciphertext anywhere on
disk is unrecoverable. This is the cryptographic basis for PRD's "irreversible
across sessions" requirement.
"""
from __future__ import annotations

from collections.abc import Callable

from cryptography.fernet import Fernet, InvalidToken

from audit import AuditEvent, AuditLog
from vault.keys import fernet_key_from_svk
from vault.storage import VaultDB
from vault.tokens import compute_dedupe_key, make_token

ReplacementFactory = Callable[[str, str], str]
"""Signature: (entity_type, value) -> replacement string."""


class SessionExpiredError(RuntimeError):
    """Raised when an operation is attempted on a destroyed session."""


class SessionVault:
    """A vault scoped to one session. Owns the SVK in-memory."""

    def __init__(
        self,
        session_id: str,
        svk: bytes,
        db: VaultDB,
        audit: AuditLog,
    ) -> None:
        self._session_id = session_id
        self._svk: bytearray | None = bytearray(svk)
        self._db = db
        self._audit = audit
        self._fernet: Fernet | None = Fernet(fernet_key_from_svk(svk))

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def alive(self) -> bool:
        return self._svk is not None and self._fernet is not None

    def _require_alive(self) -> tuple[bytes, Fernet]:
        if not self.alive:
            raise SessionExpiredError(
                f"Session {self._session_id!r} is destroyed; SVK is gone"
            )
        assert self._svk is not None and self._fernet is not None
        return bytes(self._svk), self._fernet

    async def store(
        self,
        entity_type: str,
        value: str,
        factory: ReplacementFactory | None = None,
    ) -> str:
        """Idempotent within session.

        First call with (entity_type, value): generates a replacement, encrypts
        the value, stores. Returns the replacement.

        Subsequent calls with same (entity_type, value): return the existing
        replacement (no factory call, no re-insert).

        factory(entity_type, value) -> replacement string. If None, defaults to
        HMAC-derived token like [PHI_NAME_xxxxxxxx]. Pseudonymization passes a
        Faker-based factory.
        """
        svk, fernet = self._require_alive()
        dedupe = compute_dedupe_key(svk, entity_type, value)

        existing = await self._db.find_by_dedupe(self._session_id, dedupe)
        if existing is not None:
            return existing

        replacement = (
            factory(entity_type, value)
            if factory is not None
            else make_token(svk, entity_type, value)
        )
        ciphertext = fernet.encrypt(value.encode("utf-8"))
        await self._db.insert_entry(
            self._session_id, dedupe, replacement, entity_type, ciphertext
        )
        await self._audit.emit(
            AuditEvent(
                session_id=self._session_id,
                action="OBFUSCATE",
                entity_type=entity_type,
                token_id=replacement,
            )
        )
        return replacement

    async def lookup(self, replacement: str) -> str | None:
        """Reverse the replacement → original mapping. Returns None on miss."""
        _, fernet = self._require_alive()
        ciphertext = await self._db.lookup(self._session_id, replacement)
        if ciphertext is None:
            return None
        try:
            return fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken:
            return None

    async def lookup_many(self, replacements: list[str]) -> dict[str, str]:
        """Reverse many replacements using one database round trip."""
        _, fernet = self._require_alive()
        ciphertexts = await self._db.lookup_many(self._session_id, replacements)
        originals: dict[str, str] = {}
        for replacement, ciphertext in ciphertexts.items():
            try:
                originals[replacement] = fernet.decrypt(ciphertext).decode("utf-8")
            except InvalidToken:
                continue
        return originals

    async def all_replacements(self) -> list[tuple[str, str]]:
        """Return [(replacement, entity_type), ...] for this session.

        Used by pseudonymization restoration which needs the full surrogate list.
        """
        self._require_alive()
        return await self._db.all_replacements(self._session_id)

    async def destroy(self) -> None:
        """Wipe rows + zero the SVK in-memory. Idempotent."""
        if not self.alive:
            return
        await self._db.end_session(self._session_id)
        await self._audit.emit(
            AuditEvent(session_id=self._session_id, action="VAULT_DESTROY")
        )
        assert self._svk is not None
        for i in range(len(self._svk)):
            self._svk[i] = 0
        self._svk = None
        self._fernet = None
