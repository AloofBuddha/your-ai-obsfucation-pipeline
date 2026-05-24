"""App-state container — wires up all the singletons the API depends on."""
from __future__ import annotations

from dataclasses import dataclass

from api.config import Settings
from audit import AuditLog, JSONLAuditLog
from detection import PresidioDetector
from llm_client import AnthropicLLMClient, EchoLLMClient, LLMClient, maybe_trace
from pipeline import SessionManager
from store import FilesystemDocumentStore, UserKeyStore
from vault import VaultDB


@dataclass
class AppState:
    settings: Settings
    vault_db: VaultDB
    detector: PresidioDetector
    keystore: UserKeyStore
    docstore: FilesystemDocumentStore
    llm: LLMClient
    audit: AuditLog
    manager: SessionManager


async def build_state(settings: Settings) -> AppState:
    """Instantiate singletons. Engine startup (spaCy load) is the slow part."""
    vault_db = VaultDB(settings.vault_db_path)
    await vault_db.connect()

    audit = JSONLAuditLog(settings.audit_path)
    keystore = UserKeyStore(settings.user_keys_path)
    docstore = FilesystemDocumentStore(settings.data_dir, keystore)
    detector = PresidioDetector()

    if settings.anthropic_api_key:
        llm: LLMClient = AnthropicLLMClient(
            api_key=settings.anthropic_api_key, model=settings.anthropic_model
        )
    else:
        # Fall back to echo mock so the API still boots in CI / tests.
        llm = EchoLLMClient()
    llm = maybe_trace(
        llm,
        enabled=settings.langsmith_tracing,
        api_key=settings.langsmith_api_key,
        project=settings.langsmith_project,
        endpoint=settings.langsmith_endpoint,
    )

    manager = SessionManager(
        vault_db,
        detector,
        docstore,
        llm,
        audit,
        default_confidence_threshold=settings.detection_confidence_threshold,
    )
    await manager.startup()

    return AppState(
        settings=settings,
        vault_db=vault_db,
        detector=detector,
        keystore=keystore,
        docstore=docstore,
        llm=llm,
        audit=audit,
        manager=manager,
    )
