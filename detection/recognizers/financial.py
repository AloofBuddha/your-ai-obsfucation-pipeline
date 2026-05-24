"""FIN_ACCOUNT_NUMBER (Luhn-validated) and FIN_TAX_ID."""
from __future__ import annotations

import re

from presidio_analyzer import (
    AnalysisExplanation,
    Pattern,
    PatternRecognizer,
    RecognizerResult,
)
from presidio_analyzer.nlp_engine import NlpArtifacts


def _luhn_check(digits: str) -> bool:
    """Standard Luhn checksum — used to filter out random digit sequences
    that happen to be 13-19 digits long but aren't real account numbers."""
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


class AccountNumberRecognizer(PatternRecognizer):
    """Account number — 13-19 digit sequence that passes Luhn."""

    _DIGIT_PATTERN = re.compile(r"\b\d[\d\s\-]{11,22}\d\b")

    def __init__(self) -> None:
        super().__init__(
            supported_entity="FIN_ACCOUNT_NUMBER",
            patterns=[
                Pattern(
                    name="digit_sequence",
                    regex=r"\b\d[\d\s\-]{11,22}\d\b",
                    score=0.3,  # Low — confirmed by Luhn check in analyze()
                ),
            ],
            context=["account", "card", "credit", "debit"],
        )

    def analyze(
        self,
        text: str,
        entities: list[str],
        nlp_artifacts: NlpArtifacts | None = None,
        regex_flags: int | None = None,
    ) -> list[RecognizerResult]:
        # Get base regex matches, then filter by Luhn validation.
        raw_results = super().analyze(text, entities, nlp_artifacts, regex_flags)
        validated: list[RecognizerResult] = []
        for r in raw_results:
            candidate = text[r.start : r.end]
            cleaned = re.sub(r"[\s\-]", "", candidate)
            if _luhn_check(cleaned):
                explanation = AnalysisExplanation(
                    recognizer="AccountNumberRecognizer",
                    pattern_name="digit_sequence+luhn",
                    pattern="luhn_validated",
                    original_score=r.score,
                    validation_result=True,
                )
                validated.append(
                    RecognizerResult(
                        entity_type="FIN_ACCOUNT_NUMBER",
                        start=r.start,
                        end=r.end,
                        score=0.95,
                        analysis_explanation=explanation,
                    )
                )
        return validated


class TaxIDRecognizer(PatternRecognizer):
    """EIN format (XX-XXXXXXX). SSN format is handled by Presidio's built-in
    US_SSN recognizer; we map that to PII_SSN.
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="FIN_TAX_ID",
            patterns=[
                Pattern(name="ein", regex=r"\b\d{2}-\d{7}\b", score=0.9),
            ],
            context=["ein", "tax", "employer id", "tax id"],
        )
