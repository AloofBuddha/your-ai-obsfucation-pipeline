"""API contract tests — sessions, document upload, pipeline run, audit."""
from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

from api.config import Settings
from api.main import create_app


@pytest_asyncio.fixture
async def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    # Settings that route all state to tmp_path.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")  # forces EchoLLMClient
    settings = Settings(
        DATA_DIR=str(tmp_path / "data"),
        AUDIT_PATH=str(tmp_path / "audit.jsonl"),
        VAULT_DB_PATH=str(tmp_path / "vault.db"),
        USER_KEYS_PATH=str(tmp_path / "user_keys.json"),
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        # Manually drive lifespan since ASGITransport doesn't.
        async with app.router.lifespan_context(app):
            yield ac


async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_cors_allows_127_0_0_1_dev_origin(client: httpx.AsyncClient) -> None:
    r = await client.options(
        "/sessions",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


async def test_full_session_flow(client: httpx.AsyncClient) -> None:
    # Start session.
    r = await client.post(
        "/sessions", json={"user_id": "alice", "strategy": "tokenize"}
    )
    assert r.status_code == 201
    session_id = r.json()["session_id"]

    # Upload document.
    files = {"file": ("intake.txt", b"Patient Sofia Reyes has Type 2 diabetes.", "text/plain")}
    r = await client.post(f"/sessions/{session_id}/documents", files=files)
    assert r.status_code == 201
    doc_id = r.json()["doc_id"]

    # Run pipeline.
    r = await client.post(
        f"/sessions/{session_id}/pipeline",
        json={"doc_id": doc_id, "user_query": "Summarize."},
    )
    assert r.status_code == 200
    body = r.json()
    # Outbound prompt has no PII.
    assert "Sofia Reyes" not in body["obfuscated_prompt"]
    assert "Type 2 diabetes" not in body["obfuscated_prompt"]
    # Restored response has the original entities back (echo LLM ensures this).
    assert "Sofia Reyes" in body["restored_response"]

    # Audit query — has events for this session, no plaintext.
    r = await client.get(f"/sessions/{session_id}/audit")
    assert r.status_code == 200
    events = r.json()
    assert len(events) > 0
    audit_blob = str(events)
    assert "Sofia Reyes" not in audit_blob
    assert "Type 2 diabetes" not in audit_blob

    # End session — subsequent operations 404.
    r = await client.delete(f"/sessions/{session_id}")
    assert r.status_code == 204
    r = await client.post(
        f"/sessions/{session_id}/pipeline",
        json={"doc_id": doc_id, "user_query": "again"},
    )
    assert r.status_code == 404


async def test_unknown_strategy_rejected(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/sessions", json={"user_id": "alice", "strategy": "rot13"}
    )
    assert r.status_code == 400
    body = r.json()
    assert body["detail"]["error"] == "unknown_strategy"
    assert "tokenize" in body["detail"]["available"]


async def test_omitted_strategy_uses_configured_default(tmp_path: Path) -> None:
    settings = Settings(
        ANTHROPIC_API_KEY="",
        OBFUSCATION_STRATEGY="pseudonymize",
        DATA_DIR=str(tmp_path / "data"),
        AUDIT_PATH=str(tmp_path / "audit.jsonl"),
        VAULT_DB_PATH=str(tmp_path / "vault.db"),
        USER_KEYS_PATH=str(tmp_path / "user_keys.json"),
    )
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async with app.router.lifespan_context(app):
            r = await ac.post("/sessions", json={"user_id": "alice"})

    assert r.status_code == 201
    assert r.json()["strategy"] == "pseudonymize"


async def test_path_like_user_id_rejected(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/sessions", json={"user_id": "../outside", "strategy": "tokenize"}
    )
    assert r.status_code == 422


async def test_end_unknown_session_404(client: httpx.AsyncClient) -> None:
    r = await client.delete("/sessions/does-not-exist")
    assert r.status_code == 404


async def test_upload_to_unknown_session_404(client: httpx.AsyncClient) -> None:
    files = {"file": ("a.txt", b"x", "text/plain")}
    r = await client.post("/sessions/missing/documents", files=files)
    assert r.status_code == 404
