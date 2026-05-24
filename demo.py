"""End-to-end demo of the Secure Context Pipeline.

Usage:
    uv run python demo.py                          # uses medical_intake.txt fixture
    uv run python demo.py --fixture legal_memo     # one of: medical_intake, legal_memo, financial_statement
    uv run python demo.py --format pdf             # one of: txt, docx, pdf, png
    uv run python demo.py --strategy pseudonymize  # default: tokenize
    uv run python demo.py --offline                # use EchoLLMClient, no Anthropic call

Runs:
    1. Read + encrypt the fixture into a per-user document store.
    2. Decrypt, OCR/parse if needed.
    3. Detect PII/PHI entities (Presidio + custom recognizers).
    4. Obfuscate (tokenize or pseudonymize).
    5. Send the obfuscated prompt to the LLM.
    6. Restore tokens in the response.

Prints each stage so you can see the security guarantees in action — the
"Obfuscated payload" stage is what the LLM provider actually sees.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from audit import JSONLAuditLog
from detection import PresidioDetector
from llm_client import AnthropicLLMClient, EchoLLMClient, LLMClient, maybe_trace
from pipeline import SessionManager
from store import FilesystemDocumentStore, UserKeyStore
from tests.fixtures.build import OUTPUT_DIR, render_all
from vault import VaultDB

FIXTURES = ["medical_intake", "legal_memo", "financial_statement"]


def _separator(title: str, char: str = "─") -> str:
    bar = char * 78
    return f"\n{bar}\n{title}\n{bar}\n"


async def main(args: argparse.Namespace) -> None:
    load_dotenv()

    # Ensure fixtures exist on disk.
    rendered = OUTPUT_DIR / f"{args.fixture}.{args.format}"
    if not rendered.exists():
        print("Fixtures not built yet — rendering now...")
        render_all()

    fixture_bytes = rendered.read_bytes()
    fixture_filename = rendered.name

    # Build runtime singletons (kept local to avoid uvicorn/FastAPI overhead).
    base = Path(args.workdir)
    vault_db = VaultDB(base / "vault.db")
    await vault_db.connect()
    audit = JSONLAuditLog(base / "audit.jsonl")
    keystore = UserKeyStore(base / "user_keys.json")
    docstore = FilesystemDocumentStore(base / "data", keystore)

    print("Loading detection model (spaCy + Presidio)...")
    detector = PresidioDetector()

    using_real_llm = bool(not args.offline and os.getenv("ANTHROPIC_API_KEY"))
    if not using_real_llm:
        if not args.offline:
            print("ANTHROPIC_API_KEY not set; using EchoLLMClient instead.")
        llm: LLMClient = EchoLLMClient()
    else:
        llm = AnthropicLLMClient(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        )
    llm = maybe_trace(
        llm,
        enabled=os.getenv("LANGSMITH_TRACING", "").strip().lower()
        in {"1", "true", "yes", "on"},
        api_key=os.getenv("LANGSMITH_API_KEY", ""),
        project=os.getenv("LANGSMITH_PROJECT", "secure-context-pipeline"),
        endpoint=os.getenv(
            "LANGSMITH_ENDPOINT",
            "https://api.smith.langchain.com/",
        ),
    )

    manager = SessionManager(
        vault_db,
        detector,
        docstore,
        llm,
        audit,
        default_confidence_threshold=float(
            os.getenv("DETECTION_CONFIDENCE_THRESHOLD", "0.6")
        ),
    )
    await manager.startup()

    # Start a session, upload the fixture, run the pipeline.
    pipeline = await manager.start_session("demo_user", args.strategy)
    doc_id = await docstore.put(
        "demo_user", content=fixture_bytes, filename=fixture_filename
    )

    print(
        _separator(
            "Running pipeline — this calls the real LLM"
            if using_real_llm
            else "Running pipeline (offline / echo mock)"
        )
    )
    result = await pipeline.run(doc_id=doc_id, query=args.query)

    print(_separator("1. SOURCE DOCUMENT (decrypted, plaintext)"))
    print(result.document_text[:1200] + ("..." if len(result.document_text) > 1200 else ""))

    print(_separator("2. DETECTED ENTITIES"))
    by_type: dict[str, list[str]] = {}
    for e in result.detected_entities:
        by_type.setdefault(e.type, []).append(f"{e.text!r} ({e.confidence:.2f})")
    for t, items in sorted(by_type.items()):
        print(f"  {t}: {len(items)}")
        for it in items[:4]:
            print(f"    - {it}")
        if len(items) > 4:
            print(f"    ... and {len(items) - 4} more")

    print(_separator("3. OBFUSCATED PAYLOAD (this is what the LLM sees)"))
    print(result.obfuscated_prompt[:1500] + ("..." if len(result.obfuscated_prompt) > 1500 else ""))

    print(_separator("4. LLM RESPONSE (raw — still contains tokens/surrogates)"))
    print(result.llm_response_raw[:1500] + ("..." if len(result.llm_response_raw) > 1500 else ""))

    print(_separator("5. RESTORED RESPONSE (what the user sees)"))
    print(result.restored_response)

    # Cleanup
    await manager.end_session(pipeline.session_id)
    await vault_db.close()

    print(_separator("DONE"))
    print(f"Audit log: {audit.path}")
    print(f"Strategy:  {result.strategy_name}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the Secure Context Pipeline end-to-end.")
    p.add_argument(
        "--fixture",
        choices=FIXTURES,
        default="medical_intake",
        help="Which bundled fixture to process.",
    )
    p.add_argument(
        "--format",
        choices=["txt", "docx", "pdf", "png"],
        default="txt",
        help="Format to upload (forces OCR for png; pypdf for pdf).",
    )
    p.add_argument(
        "--strategy",
        choices=["tokenize", "pseudonymize"],
        default="tokenize",
    )
    p.add_argument(
        "--query",
        default="Summarize this document and flag anything that warrants follow-up.",
    )
    p.add_argument(
        "--offline",
        action="store_true",
        help="Use the echo mock instead of the real Anthropic API.",
    )
    p.add_argument(
        "--workdir",
        default=".demo",
        help="Where the demo writes its vault/audit/data (gitignored).",
    )
    return p.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
