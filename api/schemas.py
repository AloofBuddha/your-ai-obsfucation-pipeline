"""API request/response schemas — separate from internal models for clear boundaries."""
from __future__ import annotations

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    user_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    strategy: str = Field(default="tokenize")


class StartSessionResponse(BaseModel):
    session_id: str
    user_id: str
    strategy: str


class PutDocumentResponse(BaseModel):
    doc_id: str
    filename: str


class RunPipelineRequest(BaseModel):
    doc_id: str
    user_query: str


class AuditEntry(BaseModel):
    """The shape returned by GET /sessions/{id}/audit. Mirrors AuditEvent but
    re-typed at the API boundary so internal schema changes don't leak."""

    timestamp: str
    session_id: str
    action: str
    entity_type: str | None
    token_id: str | None
    metadata: dict[str, str | int | float | bool | None]
