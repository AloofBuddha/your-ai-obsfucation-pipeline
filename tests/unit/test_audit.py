"""Audit log tests — purity guarantees and async writes."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from audit import AuditEvent, JSONLAuditLog

FORBIDDEN = re.compile(r"value|original|plaintext", re.IGNORECASE)


def test_event_field_names_have_no_forbidden_tokens() -> None:
    """Defense in depth: schema field names themselves must not match the forbidden pattern."""
    for field_name in AuditEvent.model_fields:
        assert not FORBIDDEN.search(field_name), (
            f"Audit event field {field_name!r} matches forbidden pattern — "
            "could be mistaken for a PII-bearing field"
        )


def test_basic_event_constructs() -> None:
    e = AuditEvent(
        session_id="sess_abc",
        action="OBFUSCATE",
        entity_type="PHI_NAME",
        token_id="[PHI_NAME_k7a2mqpz]",
        metadata={"byte_count": 42, "recognizer": "PresidioNAME"},
    )
    assert e.session_id == "sess_abc"
    assert e.action == "OBFUSCATE"
    assert e.metadata["byte_count"] == 42


def test_metadata_rejects_forbidden_key_substring() -> None:
    """Caller cannot smuggle PII via a key like 'original_value'."""
    for forbidden_key in ["original_value", "plaintext_text", "field_VALUE", "Value"]:
        with pytest.raises(ValidationError):
            AuditEvent(
                session_id="s",
                action="OBFUSCATE",
                metadata={forbidden_key: "anything"},
            )


def test_metadata_rejects_nested_dict() -> None:
    """Pydantic's typed metadata field rejects nested containers."""
    with pytest.raises(ValidationError):
        AuditEvent(
            session_id="s",
            action="OBFUSCATE",
            metadata={"nested": {"hidden": "John"}},  # type: ignore[dict-item]
        )


def test_metadata_rejects_list() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            session_id="s",
            action="OBFUSCATE",
            metadata={"items": ["John", "Jane"]},  # type: ignore[dict-item]
        )


def test_metadata_allows_scalars() -> None:
    """str / int / float / bool / None all OK."""
    AuditEvent(
        session_id="s",
        action="OBFUSCATE",
        metadata={"s": "x", "i": 1, "f": 1.0, "b": True, "n": None},
    )


async def test_emit_writes_one_jsonl_per_event(tmp_path: Path) -> None:
    log = JSONLAuditLog(tmp_path / "audit.jsonl")
    e1 = AuditEvent(session_id="s", action="OBFUSCATE", entity_type="PHI_NAME", token_id="[PHI_NAME_a]")
    e2 = AuditEvent(session_id="s", action="LLM_CALL")
    await log.emit(e1)
    await log.emit(e2)

    text = (tmp_path / "audit.jsonl").read_text()
    lines = [ln for ln in text.splitlines() if ln]
    assert len(lines) == 2
    for ln in lines:
        parsed = json.loads(ln)
        assert "session_id" in parsed
        assert "action" in parsed


async def test_emit_concurrent_does_not_interleave(tmp_path: Path) -> None:
    """Lock prevents two writes from producing a corrupted line."""
    import asyncio

    log = JSONLAuditLog(tmp_path / "audit.jsonl")
    events = [
        AuditEvent(session_id="s", action="OBFUSCATE", token_id=f"[T_{i:04d}]")
        for i in range(50)
    ]
    await asyncio.gather(*(log.emit(e) for e in events))

    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    assert len(lines) == 50
    for ln in lines:
        # Every line must parse as JSON — no interleaving.
        json.loads(ln)
