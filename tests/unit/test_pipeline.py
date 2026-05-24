"""Pipeline tests — end-to-end with mocked detector + LLM + store."""
from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from audit import JSONLAuditLog
from detection.entity import Entity
from llm_client import EchoLLMClient
from pipeline import SessionManager, SessionNotFoundError
from store import FilesystemDocumentStore, UserKeyStore
from vault import SessionExpiredError, VaultDB


class FakeDetector:
    """Returns canned entities matching the document text we'll feed in."""

    def __init__(self) -> None:
        self._table: dict[str, list[Entity]] = {}

    def preload(self, text: str, entities: list[Entity]) -> None:
        self._table[text] = entities

    async def detect(self, text: str) -> list[Entity]:
        return list(self._table.get(text, []))


@pytest.fixture
async def manager(tmp_path: Path):
    vault_db = VaultDB(tmp_path / "vault.db")
    await vault_db.connect()
    keystore = UserKeyStore(tmp_path / "user_keys.json")
    docstore = FilesystemDocumentStore(tmp_path / "data", keystore)
    detector = FakeDetector()
    llm = EchoLLMClient()
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    mgr = SessionManager(vault_db, detector, docstore, llm, audit)
    await mgr.startup()
    yield mgr, detector, docstore
    # Teardown — destroy any leftover sessions, close DB.
    for sid in mgr.active_session_ids():
        try:
            await mgr.end_session(sid)
        except SessionNotFoundError:
            pass
    await vault_db.close()


async def test_session_lifecycle(manager) -> None:
    mgr, _, _ = manager
    pipeline = await mgr.start_session("alice", "tokenize")
    assert pipeline.session_id in mgr.active_session_ids()
    assert pipeline.strategy_name == "tokenize"

    await mgr.end_session(pipeline.session_id)
    assert pipeline.session_id not in mgr.active_session_ids()


async def test_session_not_found_after_end(manager) -> None:
    mgr, _, _ = manager
    pipeline = await mgr.start_session("alice", "tokenize")
    sid = pipeline.session_id
    await mgr.end_session(sid)
    with pytest.raises(SessionNotFoundError):
        mgr.get(sid)


async def test_pipeline_run_end_to_end_tokenize(manager) -> None:
    mgr, detector, docstore = manager
    pipeline = await mgr.start_session("alice", "tokenize")

    doc_text = "Patient John Smith has hypertension."
    doc_id = await docstore.put("alice", content=doc_text.encode(), filename="r.txt")
    cast(FakeDetector, detector).preload(
        doc_text,
        [
            Entity(type="PII_NAME", text="John Smith", start=8, end=18, confidence=0.95),
            Entity(type="PHI_DIAGNOSIS", text="hypertension", start=23, end=35, confidence=0.9),
        ],
    )
    # Empty entity list for the query — query has no PII.
    cast(FakeDetector, detector).preload("Summarize the document.", [])

    result = await pipeline.run(doc_id=doc_id, query="Summarize the document.")

    # Obfuscated text has tokens, not the originals.
    assert "John Smith" not in result.obfuscated_document
    assert "hypertension" not in result.obfuscated_document
    assert "John Smith" not in result.obfuscated_prompt
    assert "hypertension" not in result.obfuscated_prompt

    # Restored response has the originals back.
    assert "John Smith" in result.restored_response
    assert "hypertension" in result.restored_response

    # No raw tokens leak to the user.
    from vault import TOKEN_RE
    assert TOKEN_RE.search(result.restored_response) is None


async def test_pipeline_session_expired_after_end(manager) -> None:
    mgr, detector, docstore = manager
    pipeline = await mgr.start_session("alice", "tokenize")
    doc_id = await docstore.put("alice", content=b"hello", filename="r.txt")
    cast(FakeDetector, detector).preload("hello", [])
    cast(FakeDetector, detector).preload("q", [])

    # End the session, then attempting to run must raise.
    await mgr.end_session(pipeline.session_id)
    with pytest.raises(SessionExpiredError):
        await pipeline.run(doc_id=doc_id, query="q")


async def test_pipeline_pseudonymize_strategy(manager) -> None:
    mgr, detector, docstore = manager
    pipeline = await mgr.start_session("alice", "pseudonymize")

    doc_text = "Patient John Smith reports symptoms."
    doc_id = await docstore.put("alice", content=doc_text.encode(), filename="r.txt")
    cast(FakeDetector, detector).preload(
        doc_text,
        [Entity(type="PII_NAME", text="John Smith", start=8, end=18, confidence=0.95)],
    )
    cast(FakeDetector, detector).preload("What is going on?", [])

    result = await pipeline.run(doc_id=doc_id, query="What is going on?")

    # Obfuscated text should not contain the original; surrogate should be present.
    assert "John Smith" not in result.obfuscated_document
    # Restored response has the original back.
    assert "John Smith" in result.restored_response
