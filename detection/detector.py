"""Async Presidio wrapper — runs detection in a thread to keep the event loop free."""
from __future__ import annotations

import asyncio
from typing import Protocol

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from detection.entity import Entity
from detection.recognizers import all_custom_recognizers
from detection.types import PRESIDIO_TO_LOCAL


class Detector(Protocol):
    async def detect(self, text: str) -> list[Entity]: ...


class PresidioDetector:
    """Presidio AnalyzerEngine wrapped for async use.

    Loading the engine is expensive (spaCy model warmup); keep one instance
    process-wide. Calls to `analyze` run in a thread via asyncio.to_thread.
    """

    def __init__(self, language: str = "en") -> None:
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(languages=[language])
        for rec in all_custom_recognizers():
            registry.add_recognizer(rec)
        self._engine = AnalyzerEngine(registry=registry)
        self._language = language

    async def detect(self, text: str) -> list[Entity]:
        results = await asyncio.to_thread(
            self._engine.analyze, text=text, language=self._language
        )
        # Dedupe by (start, end, type) — Presidio sometimes returns multiple
        # results for the same span from different recognizers.
        seen: set[tuple[int, int, str]] = set()
        entities: list[Entity] = []
        for r in results:
            local_type = _normalize_type(
                PRESIDIO_TO_LOCAL.get(r.entity_type, r.entity_type)
            )
            key = (r.start, r.end, local_type)
            if key in seen:
                continue
            seen.add(key)
            entities.append(
                Entity(
                    type=local_type,
                    text=text[r.start : r.end],
                    start=r.start,
                    end=r.end,
                    confidence=r.score,
                )
            )
        # Sort by start position; on ties, longest first (helps the obfuscation
        # engine resolve overlapping spans).
        entities.sort(key=lambda e: (e.start, -e.length))
        return entities


def _normalize_type(name: str) -> str:
    """Ensure the type has at least two _-separated uppercase segments so the
    deobfuscation regex can match the resulting token. Single-segment names
    (e.g. 'NRP' from Presidio, or anything from a custom recognizer that
    forgot the convention) get prefixed with 'PII_' as a safety bias.
    """
    if "_" in name:
        return name
    return f"PII_{name}"
