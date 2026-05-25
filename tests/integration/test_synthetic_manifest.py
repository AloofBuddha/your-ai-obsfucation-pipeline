"""Synthetic corpus regression tests backed by synthetic_data/manifest.json."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio

from audit import JSONLAuditLog
from detection import PresidioDetector
from detection.entity import Entity
from llm_client import CannedLLMClient
from pipeline import SessionManager
from store import FilesystemDocumentStore, UserKeyStore
from vault import VaultDB

ROOT = Path(__file__).parents[2]
SYNTHETIC_ROOT = ROOT / "synthetic_data"
MANIFEST_PATH = SYNTHETIC_ROOT / "manifest.json"


def _manifest_documents() -> list[dict[str, Any]]:
    return json.loads(MANIFEST_PATH.read_text())["documents"]


def _overlaps_expected_type(entity: Entity, value: str, expected_type: str) -> bool:
    if entity.type != expected_type:
        return False
    return value in entity.text or entity.text in value


@pytest.fixture(scope="module")
def detector() -> PresidioDetector:
    return PresidioDetector()


@pytest_asyncio.fixture
async def manager(
    tmp_path: Path,
    detector: PresidioDetector,
) -> AsyncIterator[tuple[SessionManager, FilesystemDocumentStore]]:
    vault_db = VaultDB(tmp_path / "vault.db")
    await vault_db.connect()
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    keystore = UserKeyStore(tmp_path / "user_keys.json")
    docstore = FilesystemDocumentStore(tmp_path / "data", keystore)
    mgr = SessionManager(
        vault_db,
        detector,
        docstore,
        CannedLLMClient("OK"),
        audit,
    )
    await mgr.startup()
    try:
        yield mgr, docstore
    finally:
        for sid in mgr.active_session_ids():
            await mgr.end_session(sid)
        await vault_db.close()


@pytest.mark.integration
@pytest.mark.parametrize("document", _manifest_documents(), ids=lambda d: d["id"])
async def test_manifest_planted_entities_are_detected_with_expected_type(
    detector: PresidioDetector,
    document: dict[str, Any],
) -> None:
    text = (SYNTHETIC_ROOT / document["path"]).read_text()
    entities = await detector.detect(text)

    missed: list[str] = []
    for planted in document["planted_entities"]:
        expected_type = planted["type"]
        value = planted["value"]
        if not any(
            _overlaps_expected_type(entity, value, expected_type)
            for entity in entities
        ):
            overlaps = [
                f"{entity.type}:{entity.text!r}"
                for entity in entities
                if value in entity.text or entity.text in value
            ]
            missed.append(f"{expected_type}:{value!r} overlaps={overlaps}")

    assert not missed, "\n".join(missed)


@pytest.mark.integration
@pytest.mark.parametrize("document", _manifest_documents(), ids=lambda d: d["id"])
async def test_manifest_planted_entities_do_not_reach_llm_payload(
    manager: tuple[SessionManager, FilesystemDocumentStore],
    document: dict[str, Any],
) -> None:
    mgr, docstore = manager
    text = (SYNTHETIC_ROOT / document["path"]).read_text()
    pipeline = await mgr.start_session(f"manifest_{document['id']}", "tokenize")
    doc_id = await docstore.put(
        pipeline.user_id,
        content=text.encode(),
        filename=Path(document["path"]).name,
    )
    result = await pipeline.run(doc_id=doc_id, query="Summarize.")

    leaked = [
        f"{planted['type']}:{planted['value']!r}"
        for planted in document["planted_entities"]
        if planted["value"] in result.obfuscated_prompt
    ]

    assert not leaked, "\n".join(leaked)
