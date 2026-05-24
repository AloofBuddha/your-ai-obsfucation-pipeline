"""ObfuscationEngine tests — splice correctness + threshold redaction + overlap resolution."""
from __future__ import annotations

from audit import JSONLAuditLog
from detection.entity import Entity
from obfuscation import ObfuscationEngine
from obfuscation.engine.engine import _resolve_overlaps
from obfuscation.strategies import TokenizationStrategy
from vault import SessionVault


class FakeDetector:
    """Returns whatever entities you pass to .preload()."""

    def __init__(self, entities: list[Entity] | None = None) -> None:
        self._entities = entities or []

    def preload(self, entities: list[Entity]) -> None:
        self._entities = entities

    async def detect(self, text: str) -> list[Entity]:
        return list(self._entities)


# ---------------------------------------------------------------- overlap resolution

def _e(start: int, end: int, type_: str = "PII_NAME", conf: float = 0.9) -> Entity:
    # Real text would be sliced from a source; for unit tests, any non-empty
    # string of the right length works.
    return Entity(type=type_, text="x" * (end - start), start=start, end=end, confidence=conf)


def test_resolve_overlaps_keeps_outermost() -> None:
    inner = _e(5, 9)            # "John"
    outer = _e(5, 16)           # "John Smith Jr."
    assert _resolve_overlaps([inner, outer]) == [outer]


def test_resolve_overlaps_keeps_higher_confidence_on_partial() -> None:
    a = _e(0, 10, conf=0.6)
    b = _e(5, 15, conf=0.9)
    assert _resolve_overlaps([a, b]) == [b]


def test_resolve_overlaps_keeps_disjoint() -> None:
    a = _e(0, 5)
    b = _e(10, 15)
    assert _resolve_overlaps([a, b]) == [a, b]


def test_resolve_overlaps_empty() -> None:
    assert _resolve_overlaps([]) == []


# ---------------------------------------------------------------- engine end-to-end

async def test_obfuscate_replaces_single_entity(
    session_vault: SessionVault, tmp_path
) -> None:
    text = "The patient is John Smith."
    detector = FakeDetector([Entity(type="PII_NAME", text="John Smith", start=15, end=25, confidence=0.95)])
    engine = ObfuscationEngine(
        detector, TokenizationStrategy(), session_vault, JSONLAuditLog(tmp_path / "a.jsonl")
    )
    result = await engine.obfuscate(text)
    assert "John Smith" not in result.obfuscated_text
    assert "The patient is " in result.obfuscated_text
    assert "PII_NAME" in result.obfuscated_text  # token contains the type


async def test_obfuscate_redacts_below_threshold(
    session_vault: SessionVault, tmp_path
) -> None:
    """PRD graceful degradation — low-confidence -> opaque token, not raw text."""
    text = "Maybe John Smith?"
    detector = FakeDetector([Entity(type="PHI_DIAGNOSIS", text="John Smith", start=6, end=16, confidence=0.3)])
    engine = ObfuscationEngine(
        detector, TokenizationStrategy(), session_vault, JSONLAuditLog(tmp_path / "a.jsonl")
    )
    result = await engine.obfuscate(text)
    assert "John Smith" not in result.obfuscated_text
    assert "[PHI_DIAGNOSIS_" in result.obfuscated_text
    assert await session_vault.lookup(result.obfuscated_text.removeprefix("Maybe ").removesuffix("?")) == "John Smith"


async def test_obfuscate_uses_configured_default_threshold(
    session_vault: SessionVault, tmp_path
) -> None:
    text = "Custom: secret"
    detector = FakeDetector(
        [
            Entity(
                type="PII_CUSTOM",
                text="secret",
                start=8,
                end=14,
                confidence=0.7,
            )
        ]
    )
    engine = ObfuscationEngine(
        detector,
        TokenizationStrategy(),
        session_vault,
        JSONLAuditLog(tmp_path / "a.jsonl"),
        default_confidence_threshold=0.8,
    )

    result = await engine.obfuscate(text)

    assert "[PII_CUSTOM_" in result.obfuscated_text


async def test_obfuscate_multiple_entities_offsets_preserved(
    session_vault: SessionVault, tmp_path
) -> None:
    """Right-to-left splicing must not corrupt later spans even when replacements
    have different lengths than originals."""
    text = "John Smith called from Boston about Dr. Anna Lee."
    detector = FakeDetector([
        Entity(type="PII_NAME", text="John Smith", start=0, end=10, confidence=0.95),
        Entity(type="PII_ADDRESS", text="Boston", start=23, end=29, confidence=0.85),
        Entity(type="PII_NAME", text="Anna Lee", start=40, end=48, confidence=0.95),
    ])
    engine = ObfuscationEngine(
        detector, TokenizationStrategy(), session_vault, JSONLAuditLog(tmp_path / "a.jsonl")
    )
    result = await engine.obfuscate(text)

    # All originals gone.
    assert "John Smith" not in result.obfuscated_text
    assert "Boston" not in result.obfuscated_text
    assert "Anna Lee" not in result.obfuscated_text
    # Connecting text preserved.
    assert " called from " in result.obfuscated_text
    assert " about Dr. " in result.obfuscated_text


async def test_obfuscate_idempotent_same_value_same_token(
    session_vault: SessionVault, tmp_path
) -> None:
    """Same value appearing twice in a doc gets the same token."""
    text = "John Smith met John Smith at the office."
    detector = FakeDetector([
        Entity(type="PII_NAME", text="John Smith", start=0, end=10, confidence=0.95),
        Entity(type="PII_NAME", text="John Smith", start=15, end=25, confidence=0.95),
    ])
    engine = ObfuscationEngine(
        detector, TokenizationStrategy(), session_vault, JSONLAuditLog(tmp_path / "a.jsonl")
    )
    result = await engine.obfuscate(text)

    # The token appears twice, identical both times.
    tokens = [
        result.obfuscated_text[m.start() : m.end()]
        for m in __import__("re").finditer(r"\[[A-Z_]+_[a-z2-7]{8}\]", result.obfuscated_text)
    ]
    assert len(tokens) == 2
    assert tokens[0] == tokens[1]


async def test_obfuscate_emits_audit_event_per_entity(
    session_vault: SessionVault, tmp_path
) -> None:
    audit_path = tmp_path / "audit.jsonl"
    text = "John Smith and Jane Doe"
    detector = FakeDetector([
        Entity(type="PII_NAME", text="John Smith", start=0, end=10, confidence=0.95),
        Entity(type="PII_NAME", text="Jane Doe", start=15, end=23, confidence=0.95),
    ])
    engine = ObfuscationEngine(
        detector, TokenizationStrategy(), session_vault, JSONLAuditLog(audit_path)
    )
    await engine.obfuscate(text)

    lines = audit_path.read_text().splitlines()
    obfuscate_lines = [ln for ln in lines if '"OBFUSCATE"' in ln]
    assert len(obfuscate_lines) >= 2  # at least one per entity
    # No original text should appear anywhere.
    full = audit_path.read_text()
    assert "John Smith" not in full
    assert "Jane Doe" not in full


async def test_obfuscate_empty_text(session_vault: SessionVault, tmp_path) -> None:
    detector = FakeDetector([])
    engine = ObfuscationEngine(
        detector, TokenizationStrategy(), session_vault, JSONLAuditLog(tmp_path / "a.jsonl")
    )
    result = await engine.obfuscate("")
    assert result.obfuscated_text == ""
    assert result.entities == []
