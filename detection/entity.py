"""Detected entity — minimal model carrying span + type + confidence."""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class Entity(BaseModel):
    """One detected PII/PHI/etc. span.

    `text` is the literal substring at [start, end). Kept so callers can avoid
    re-slicing and so confidence/type stay attached to the value.
    """

    type: str
    text: str
    start: int
    end: int
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _spans_consistent(self) -> Entity:
        if self.end <= self.start:
            raise ValueError(f"end ({self.end}) must be > start ({self.start})")
        return self

    @property
    def length(self) -> int:
        return self.end - self.start
