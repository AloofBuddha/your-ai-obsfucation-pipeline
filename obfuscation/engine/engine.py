"""ObfuscationEngine — detect → apply strategy → splice into original text.

Span resolution: when Presidio reports nested/overlapping entities (e.g.
'John Smith' and 'John' as two PERSON spans), the engine keeps the
longest-confidence outermost span and drops nested ones.

Replacement is applied right-to-left so earlier offsets stay valid as later
spans grow or shrink.

Confidence threshold: per-entity-type default (see detection.types). Below
threshold -> use an opaque vault token instead of the configured strategy. This
implements PRD "graceful entity degradation" without throwing away our local
ability to restore values the LLM repeats.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from audit import AuditEvent, AuditLog
from detection import DEFAULT_THRESHOLD, Detector, Entity, threshold_for
from obfuscation.strategies.base import ObfuscationStrategy
from vault import SessionVault


@dataclass(frozen=True)
class ObfuscationResult:
    obfuscated_text: str
    entities: list[Entity]  # all detected (kept after overlap-resolution)
    replacements: dict[int, str]  # entity index -> the string that replaced it


DetectedCallback = Callable[[list[Entity]], Awaitable[None]]


def _resolve_overlaps(entities: list[Entity]) -> list[Entity]:
    """Drop entities whose span is fully contained in another. When two spans
    partially overlap (not nested), keep the higher-confidence one; on ties,
    keep the longer one."""
    if not entities:
        return []
    # Sort by start asc, then length desc — longest at each start position first.
    sorted_es = sorted(entities, key=lambda e: (e.start, -e.length))
    kept: list[Entity] = []
    for e in sorted_es:
        conflict = False
        for k in kept:
            # Fully contained in a kept entity? Drop the inner one.
            if e.start >= k.start and e.end <= k.end:
                conflict = True
                break
            # Kept entity fully inside this one? Replace.
            if k.start >= e.start and k.end <= e.end:
                kept.remove(k)
                continue
            # Partial overlap — keep the higher confidence; on tie, longer; on
            # tie, the one already kept (stable).
            if not (e.end <= k.start or e.start >= k.end):
                if e.confidence > k.confidence or (
                    e.confidence == k.confidence and e.length > k.length
                ):
                    kept.remove(k)
                else:
                    conflict = True
                    break
        if not conflict:
            kept.append(e)
    # Return in span order (start asc).
    kept.sort(key=lambda e: e.start)
    return kept

class ObfuscationEngine:
    def __init__(
        self,
        detector: Detector,
        strategy: ObfuscationStrategy,
        vault: SessionVault,
        audit: AuditLog,
        default_confidence_threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        self._detector = detector
        self._strategy = strategy
        self._vault = vault
        self._audit = audit
        self._default_confidence_threshold = default_confidence_threshold

    async def obfuscate(
        self,
        text: str,
        on_detected: DetectedCallback | None = None,
    ) -> ObfuscationResult:
        raw = await self._detector.detect(text)
        entities = _resolve_overlaps(raw)
        if on_detected is not None:
            await on_detected(entities)

        # Compute replacements left-to-right (sequential to preserve order in
        # vault/audit) but apply them right-to-left so offsets stay valid.
        replacements: dict[int, str] = {}
        for idx, entity in enumerate(entities):
            if entity.confidence < threshold_for(
                entity.type,
                default_threshold=self._default_confidence_threshold,
            ):
                # The LLM still gets a fully opaque token, but we keep a vault
                # mapping so the user-facing response can be restored locally.
                replacements[idx] = await self._vault.store(entity.type, entity.text)
                await self._audit.emit(
                    AuditEvent(
                        session_id=self._vault.session_id,
                        action="OBFUSCATE",
                        entity_type=entity.type,
                        token_id=replacements[idx],
                        metadata={
                            "confidence": float(entity.confidence),
                            "redacted_below_threshold": True,
                        },
                    )
                )
            else:
                replacements[idx] = await self._strategy.replace(entity, self._vault)

        # Splice right-to-left.
        buf = text
        for idx in sorted(replacements, reverse=True):
            entity = entities[idx]
            replacement = replacements[idx]
            buf = buf[: entity.start] + replacement + buf[entity.end :]

        return ObfuscationResult(
            obfuscated_text=buf,
            entities=entities,
            replacements=replacements,
        )
