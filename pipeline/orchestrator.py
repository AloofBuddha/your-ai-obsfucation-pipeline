"""Pipeline orchestrator — one instance per session."""
from __future__ import annotations

from audit import AuditEvent, AuditLog
from deobfuscation import Deobfuscator
from detection import DEFAULT_THRESHOLD, Detector
from llm_client import LLMClient
from obfuscation import ObfuscationEngine
from obfuscation.strategies.base import ObfuscationStrategy
from pipeline.result import PipelineResult
from store import DocumentStore
from vault import SessionExpiredError, SessionVault


def _build_user_message(obfuscated_query: str, obfuscated_doc: str) -> str:
    return f"{obfuscated_query}\n\n--- DOCUMENT ---\n{obfuscated_doc}"


class Pipeline:
    """Session-scoped. Holds the vault + strategy + engine, exposes run()."""

    def __init__(
        self,
        session_id: str,
        user_id: str,
        strategy: ObfuscationStrategy,
        vault: SessionVault,
        detector: Detector,
        store: DocumentStore,
        llm: LLMClient,
        audit: AuditLog,
        default_confidence_threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._session_id = session_id
        self._user_id = user_id
        self._strategy = strategy
        self._vault = vault
        self._detector = detector
        self._store = store
        self._llm = llm
        self._audit = audit
        self._engine = ObfuscationEngine(
            detector,
            strategy,
            vault,
            audit,
            default_confidence_threshold=default_confidence_threshold,
        )
        self._deobfuscator = Deobfuscator(audit)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def user_id(self) -> str:
        return self._user_id

    @property
    def strategy_name(self) -> str:
        return self._strategy.name

    @property
    def vault(self) -> SessionVault:
        return self._vault

    async def run(self, *, doc_id: str, query: str) -> PipelineResult:
        """Full pipeline: load -> obfuscate -> LLM -> restore.

        Fails fast if the session has been destroyed, regardless of whether
        any entities are present (a vault.store call would also raise, but
        only if obfuscation actually touches the vault — defense in depth).
        """
        if not self._vault.alive:
            raise SessionExpiredError(
                f"Pipeline session {self._session_id!r} is destroyed"
            )
        document_text = await self._store.get_text(self._user_id, doc_id)

        doc_result = await self._engine.obfuscate(document_text)
        query_result = await self._engine.obfuscate(query)
        user_message = _build_user_message(
            query_result.obfuscated_text, doc_result.obfuscated_text
        )

        await self._audit.emit(
            AuditEvent(
                session_id=self._session_id,
                action="LLM_CALL",
                metadata={
                    "prompt_char_count": len(user_message),
                    "strategy": self.strategy_name,
                },
            )
        )
        llm_response = await self._llm.generate(system="", user=user_message)
        restored = await self._deobfuscator.restore(
            llm_response, self._vault, self.strategy_name
        )

        await self._audit.emit(
            AuditEvent(
                session_id=self._session_id,
                action="PIPELINE_RUN",
                metadata={"document_id": doc_id},
            )
        )

        return PipelineResult(
            user_query=query,
            obfuscated_query=query_result.obfuscated_text,
            document_text=document_text,
            detected_entities=doc_result.entities,
            obfuscated_document=doc_result.obfuscated_text,
            obfuscated_prompt=user_message,
            llm_response_raw=llm_response,
            restored_response=restored,
            strategy_name=self.strategy_name,
        )

    async def end(self) -> None:
        await self._vault.destroy()
