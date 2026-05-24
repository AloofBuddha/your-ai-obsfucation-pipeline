"""Performance benchmarks matching PRD §"Performance Benchmarks".

Skipped by default unless explicitly selected — these tests vary across hosts
and CI/local. Run with: `uv run pytest -m perf`.
"""
from __future__ import annotations

import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio

from audit import JSONLAuditLog
from deobfuscation import Deobfuscator
from detection import PresidioDetector
from llm_client import CannedLLMClient
from obfuscation import ObfuscationEngine
from obfuscation.strategies import TokenizationStrategy
from pipeline import SessionManager
from store import FilesystemDocumentStore, UserKeyStore
from tests.fixtures.sources import medical_intake
from vault import SessionVault, VaultDB, generate_svk

pytestmark = pytest.mark.perf


def _make_2000_word_text() -> str:
    """Repeat the medical intake fixture until ~2000 words. Preserves all
    entity types per repetition (so we get meaningful obfuscation load)."""
    base = medical_intake.TEXT
    base_words = len(base.split())
    repeats = max(1, 2000 // base_words + 1)
    return ("\n\n--- continued ---\n\n").join([base] * repeats)


@pytest_asyncio.fixture
async def vault_db(tmp_path: Path) -> AsyncIterator[VaultDB]:
    db = VaultDB(tmp_path / "vault.db")
    await db.connect()
    yield db
    await db.close()


@pytest.fixture(scope="module")
def detector() -> PresidioDetector:
    return PresidioDetector()


@pytest_asyncio.fixture
async def session_vault(
    vault_db: VaultDB, tmp_path: Path
) -> AsyncIterator[SessionVault]:
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    svk = generate_svk()
    await vault_db.register_session("perf")
    vault = SessionVault("perf", svk, vault_db, audit)
    yield vault
    if vault.alive:
        await vault.destroy()


async def test_perf_obfuscation_alone_2000_words(
    detector: PresidioDetector, session_vault: SessionVault, tmp_path: Path
) -> None:
    text = _make_2000_word_text()
    audit = JSONLAuditLog(tmp_path / "a.jsonl")
    engine = ObfuscationEngine(detector, TokenizationStrategy(), session_vault, audit)

    t0 = time.perf_counter()
    await engine.obfuscate(text)
    elapsed = time.perf_counter() - t0

    assert elapsed < 2.0, f"Obfuscation took {elapsed:.2f}s, PRD budget is 2s"


async def test_perf_vault_lookup_under_5ms(
    session_vault: SessionVault,
) -> None:
    """1000-row vault; per-token lookup must be < 5ms on average."""
    # Pre-populate.
    tokens: list[str] = []
    for i in range(1000):
        token = await session_vault.store("PHI_NAME", f"Patient_{i}")
        tokens.append(token)

    t0 = time.perf_counter()
    for token in tokens:
        await session_vault.lookup(token)
    elapsed = time.perf_counter() - t0

    per_token_ms = (elapsed / len(tokens)) * 1000
    assert per_token_ms < 5.0, (
        f"Per-token lookup took {per_token_ms:.2f}ms, PRD budget is 5ms"
    )


async def test_perf_deobfuscation_500_tokens_under_500ms(
    session_vault: SessionVault, tmp_path: Path
) -> None:
    # Populate vault with 500 entities and build a synthetic response.
    tokens: list[str] = []
    for i in range(500):
        token = await session_vault.store("PHI_NAME", f"Patient_{i}")
        tokens.append(token)
    response = " ".join(f"{t} did something." for t in tokens)

    deob = Deobfuscator(JSONLAuditLog(tmp_path / "a.jsonl"))
    t0 = time.perf_counter()
    restored = await deob.restore(response, session_vault, "tokenize")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 500, f"Deobfuscation took {elapsed_ms:.0f}ms, PRD budget is 500ms"
    # And actually restored.
    assert "Patient_0" in restored


async def test_perf_full_pipeline_2000_words_under_15s(
    detector: PresidioDetector, tmp_path: Path
) -> None:
    """End-to-end pipeline timing — LLM is mocked so this measures only our
    own code's overhead. The PRD 15s budget allows for real LLM latency too;
    isolating it here lets us catch regressions in non-LLM stages."""
    vault_db = VaultDB(tmp_path / "vault.db")
    await vault_db.connect()
    audit = JSONLAuditLog(tmp_path / "audit.jsonl")
    keystore = UserKeyStore(tmp_path / "user_keys.json")
    docstore = FilesystemDocumentStore(tmp_path / "data", keystore)
    llm = CannedLLMClient("OK")
    mgr = SessionManager(vault_db, detector, docstore, llm, audit)
    await mgr.startup()

    pipeline = await mgr.start_session("perf_user", "tokenize")
    text = _make_2000_word_text()
    doc_id = await docstore.put(
        pipeline.user_id, content=text.encode(), filename="r.txt"
    )

    t0 = time.perf_counter()
    await pipeline.run(doc_id=doc_id, query="summary")
    elapsed = time.perf_counter() - t0

    await mgr.end_session(pipeline.session_id)
    await vault_db.close()

    assert elapsed < 15.0, f"Pipeline took {elapsed:.2f}s, PRD budget is 15s"
