"""AuditEvent — schema-enforced purity (no PII field names, no nested metadata)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Action = Literal[
    "OBFUSCATE",
    "DEOBFUSCATE",
    "VAULT_CREATE",
    "VAULT_DESTROY",
    "LLM_CALL",
    "PIPELINE_RUN",
]

_FORBIDDEN_NAME = re.compile(r"value|original|plaintext", re.IGNORECASE)

Scalar = str | int | float | bool | None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(BaseModel):
    """One audit log entry. Never contains original entity values.

    PRD hard requirement: "Logging must never emit original values — token IDs only."
    Defense in depth:
      1. Schema field names are static and forbidden-token-free (verified by test).
      2. metadata dict keys validated at construct time.
      3. metadata values restricted to scalars (no nested dicts/lists that could
         smuggle structured PII).
    """

    timestamp: datetime = Field(default_factory=_utcnow)
    session_id: str
    action: Action
    entity_type: str | None = None
    token_id: str | None = None
    metadata: dict[str, Scalar] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def _metadata_safe(cls, value: dict[str, Scalar]) -> dict[str, Scalar]:
        for key in value:
            if _FORBIDDEN_NAME.search(key):
                raise ValueError(
                    f"metadata key {key!r} contains forbidden substring "
                    "(value/original/plaintext) — audit log must contain no PII"
                )
        return value
