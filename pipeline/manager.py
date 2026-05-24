"""SessionManager — process-wide registry of active Pipelines."""
from __future__ import annotations

from uuid import uuid4

from audit import AuditEvent, AuditLog
from detection import DEFAULT_THRESHOLD, Detector
from llm_client import LLMClient
from obfuscation.strategies import make_strategy
from pipeline.orchestrator import Pipeline
from store import DocumentStore
from vault import SessionVault, VaultDB, generate_svk


class SessionNotFoundError(KeyError):
    """Raised on operations against an unknown / ended session."""


class SessionManager:
    """Owns the per-process map of active sessions. On startup, sweeps orphan
    rows from the vault DB (rows from sessions that died with a previous process)
    since their SVKs are gone and the ciphertexts are unreadable."""

    def __init__(
        self,
        vault_db: VaultDB,
        detector: Detector,
        store: DocumentStore,
        llm: LLMClient,
        audit: AuditLog,
        default_confidence_threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._vault_db = vault_db
        self._detector = detector
        self._store = store
        self._llm = llm
        self._audit = audit
        self._default_confidence_threshold = default_confidence_threshold
        self._active: dict[str, Pipeline] = {}

    async def startup(self) -> None:
        """Call once at process start. Sweeps orphans."""
        await self._vault_db.cleanup_orphans(active_sessions=[])

    async def start_session(
        self,
        user_id: str,
        strategy_name: str,
    ) -> Pipeline:
        session_id = uuid4().hex
        svk = generate_svk()
        await self._vault_db.register_session(session_id)
        vault = SessionVault(session_id, svk, self._vault_db, self._audit)
        strategy = make_strategy(strategy_name)
        pipeline = Pipeline(
            session_id=session_id,
            user_id=user_id,
            strategy=strategy,
            vault=vault,
            detector=self._detector,
            store=self._store,
            llm=self._llm,
            audit=self._audit,
            default_confidence_threshold=self._default_confidence_threshold,
        )
        self._active[session_id] = pipeline
        await self._audit.emit(
            AuditEvent(
                session_id=session_id,
                action="VAULT_CREATE",
                metadata={"strategy": strategy_name},
            )
        )
        return pipeline

    def get(self, session_id: str) -> Pipeline:
        try:
            return self._active[session_id]
        except KeyError as e:
            raise SessionNotFoundError(session_id) from e

    async def end_session(self, session_id: str) -> None:
        if session_id not in self._active:
            raise SessionNotFoundError(session_id)
        pipeline = self._active.pop(session_id)
        await pipeline.end()

    def active_session_ids(self) -> list[str]:
        return list(self._active.keys())
