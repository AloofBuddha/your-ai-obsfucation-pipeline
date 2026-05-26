"""Run synthetic-corpus security/utility evals, optionally uploading to LangSmith.

The evals are deterministic by default: they use EchoLLMClient so security
scores do not depend on provider behavior. Pass `--llm anthropic` to measure
real model utility/token preservation with the configured Anthropic key.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from audit import JSONLAuditLog
from detection import PresidioDetector
from detection.entity import Entity
from llm_client import AnthropicLLMClient, EchoLLMClient, LLMClient
from pipeline import SessionManager
from store import FilesystemDocumentStore, UserKeyStore
from vault import TOKEN_RE, VaultDB

ROOT = Path(__file__).parents[1]
SYNTHETIC_ROOT = ROOT / "synthetic_data"
MANIFEST_PATH = SYNTHETIC_ROOT / "manifest.json"
DEFAULT_QUERY = "Summarize the document and flag any follow-up items."

Strategy = Literal["tokenize", "pseudonymize"]
LLMMode = Literal["echo", "anthropic"]


@dataclass(frozen=True)
class PlantedEntity:
    type: str
    value: str


@dataclass(frozen=True)
class EvalDocument:
    id: str
    path: str
    scenario: str
    planted_entities: list[PlantedEntity]


@dataclass(frozen=True)
class EvalScores:
    leakage_pass: bool
    detection_pass: bool
    restoration_pass: bool
    utility_pass: bool
    leaked_count: int
    missed_count: int
    unresolved_token_count: int
    detected_count: int
    detected_type_count: int
    obfuscated_prompt_chars: int
    restored_response_chars: int


@dataclass(frozen=True)
class EvalRecord:
    document_id: str
    scenario: str
    strategy: Strategy
    llm_mode: LLMMode
    scores: EvalScores
    missed_types: list[str]
    leaked_types: list[str]


def load_manifest() -> list[EvalDocument]:
    raw = json.loads(MANIFEST_PATH.read_text())
    docs: list[EvalDocument] = []
    for item in raw["documents"]:
        docs.append(
            EvalDocument(
                id=item["id"],
                path=item["path"],
                scenario=item["scenario"],
                planted_entities=[
                    PlantedEntity(type=entity["type"], value=entity["value"])
                    for entity in item["planted_entities"]
                ],
            )
        )
    return docs


def overlaps_expected_type(entity: Entity, planted: PlantedEntity) -> bool:
    if entity.type != planted.type:
        return False
    return planted.value in entity.text or entity.text in planted.value


def planted_types_not_detected(
    planted_entities: list[PlantedEntity],
    detected_entities: list[Entity],
) -> list[str]:
    return [
        planted.type
        for planted in planted_entities
        if not any(
            overlaps_expected_type(entity, planted)
            for entity in detected_entities
        )
    ]


def planted_types_leaked(planted_entities: list[PlantedEntity], text: str) -> list[str]:
    return [
        planted.type
        for planted in planted_entities
        if planted.value and planted.value in text
    ]


def assert_langsmith_payload_safe(payload: dict[str, Any], planted: list[PlantedEntity]) -> None:
    blob = json.dumps(payload, sort_keys=True)
    leaked = planted_types_leaked(planted, blob)
    if leaked:
        raise ValueError(
            "Refusing to upload LangSmith eval payload containing planted values "
            f"for types: {sorted(set(leaked))}"
        )


def make_llm(mode: LLMMode) -> LLMClient:
    if mode == "echo":
        return EchoLLMClient()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("--llm anthropic requires ANTHROPIC_API_KEY")
    return AnthropicLLMClient(
        api_key=api_key,
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
    )


async def run_one(
    *,
    document: EvalDocument,
    strategy: Strategy,
    llm_mode: LLMMode,
    tmp_dir: Path,
) -> EvalRecord:
    text = (SYNTHETIC_ROOT / document.path).read_text()
    detector = PresidioDetector()
    raw_detected_entities = await detector.detect(text)

    vault_db = VaultDB(tmp_dir / f"{document.id}-{strategy}.vault.db")
    await vault_db.connect()
    audit = JSONLAuditLog(tmp_dir / f"{document.id}-{strategy}.audit.jsonl")
    keystore = UserKeyStore(tmp_dir / f"{document.id}-{strategy}.keys.json")
    docstore = FilesystemDocumentStore(tmp_dir / f"{document.id}-{strategy}.data", keystore)
    manager = SessionManager(
        vault_db,
        detector,
        docstore,
        make_llm(llm_mode),
        audit,
    )
    await manager.startup()
    try:
        pipeline = await manager.start_session(f"eval_{document.id}", strategy)
        doc_id = await docstore.put(
            pipeline.user_id,
            content=text.encode(),
            filename=Path(document.path).name,
        )
        result = await pipeline.run(doc_id=doc_id, query=DEFAULT_QUERY)
    finally:
        for session_id in manager.active_session_ids():
            await manager.end_session(session_id)
        await vault_db.close()

    leaked_types = planted_types_leaked(document.planted_entities, result.obfuscated_prompt)
    missed_types = planted_types_not_detected(
        document.planted_entities,
        raw_detected_entities,
    )
    unresolved_tokens = TOKEN_RE.findall(result.restored_response)
    utility_pass = bool(result.restored_response.strip()) and len(result.restored_response) > 20
    scores = EvalScores(
        leakage_pass=len(leaked_types) == 0,
        detection_pass=len(missed_types) == 0,
        restoration_pass=len(unresolved_tokens) == 0,
        utility_pass=utility_pass,
        leaked_count=len(leaked_types),
        missed_count=len(missed_types),
        unresolved_token_count=len(unresolved_tokens),
        detected_count=len(raw_detected_entities),
        detected_type_count=len({entity.type for entity in raw_detected_entities}),
        obfuscated_prompt_chars=len(result.obfuscated_prompt),
        restored_response_chars=len(result.restored_response),
    )
    return EvalRecord(
        document_id=document.id,
        scenario=document.scenario,
        strategy=strategy,
        llm_mode=llm_mode,
        scores=scores,
        missed_types=sorted(set(missed_types)),
        leaked_types=sorted(set(leaked_types)),
    )


def upload_to_langsmith(records: list[EvalRecord], project: str) -> None:
    api_key = os.getenv("LANGSMITH_API_KEY", "")
    if not api_key:
        return
    try:
        from langsmith import Client  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "LANGSMITH_API_KEY is set but langsmith is not installed. "
            "Run `uv sync --extra tracing` first."
        ) from exc

    client = Client(
        api_key=api_key,
        api_url=os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com/"),
    )
    for record in records:
        inputs: dict[str, Any] = {
            "document_id": record.document_id,
            "scenario": record.scenario,
            "strategy": record.strategy,
            "llm_mode": record.llm_mode,
        }
        outputs: dict[str, Any] = {
            "scores": asdict(record.scores),
            "missed_types": record.missed_types,
            "leaked_types": record.leaked_types,
        }
        planted = next(
            doc.planted_entities
            for doc in load_manifest()
            if doc.id == record.document_id
        )
        assert_langsmith_payload_safe(inputs, planted)
        assert_langsmith_payload_safe(outputs, planted)
        run = client.create_run(
            project_name=project,
            name=f"synthetic_eval:{record.document_id}:{record.strategy}",
            run_type="chain",
            inputs=inputs,
            outputs=outputs,
        )
        for key, value in asdict(record.scores).items():
            if isinstance(value, bool):
                score = 1.0 if value else 0.0
            elif isinstance(value, (int, float)):
                score = float(value)
            else:
                continue
            client.create_feedback(run.id, key=key, score=score)


async def run_all(strategies: list[Strategy], llm_mode: LLMMode) -> list[EvalRecord]:
    docs = load_manifest()
    with tempfile.TemporaryDirectory(prefix="secure-context-evals-") as tmp:
        tmp_dir = Path(tmp)
        records: list[EvalRecord] = []
        for doc in docs:
            for strategy in strategies:
                records.append(
                    await run_one(
                        document=doc,
                        strategy=strategy,
                        llm_mode=llm_mode,
                        tmp_dir=tmp_dir,
                    )
                )
        return records


def print_summary(records: list[EvalRecord], report_path: Path) -> None:
    total = len(records)
    leakage_failures = sum(not record.scores.leakage_pass for record in records)
    detection_failures = sum(not record.scores.detection_pass for record in records)
    restoration_failures = sum(not record.scores.restoration_pass for record in records)
    utility_failures = sum(not record.scores.utility_pass for record in records)
    print(f"records={total}")
    print(f"leakage_failures={leakage_failures}")
    print(f"detection_failures={detection_failures}")
    print(f"restoration_failures={restoration_failures}")
    print(f"utility_failures={utility_failures}")
    print(f"report={report_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strategy",
        choices=["tokenize", "pseudonymize", "both"],
        default="both",
    )
    parser.add_argument("--llm", choices=["echo", "anthropic"], default="echo")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("data/evals/synthetic_eval_report.json"),
    )
    parser.add_argument(
        "--langsmith-project",
        default=os.getenv("LANGSMITH_PROJECT", "secure-context-pipeline-evals"),
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    strategies: list[Strategy] = (
        ["tokenize", "pseudonymize"]
        if args.strategy == "both"
        else [args.strategy]
    )
    records = await run_all(strategies, args.llm)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps([asdict(record) for record in records], indent=2))
    upload_to_langsmith(records, args.langsmith_project)
    print_summary(records, args.report)


if __name__ == "__main__":
    asyncio.run(main())
