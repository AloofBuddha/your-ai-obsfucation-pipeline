"""LEGAL_PRIVILEGE — header-phrase markers commonly seen on privileged docs."""
from __future__ import annotations

from presidio_analyzer import PatternRecognizer

# Hand-curated phrases. PRD's "legal privilege markers" doesn't enumerate which;
# these are the most common forms in US legal practice.
_PRIVILEGE_PHRASES = [
    "attorney-client privileged",
    "attorney-client communication",
    "attorney client privilege",
    "attorney work product",
    "work product doctrine",
    "privileged and confidential",
    "privileged & confidential",
    "confidential — legal",
    "confidential - legal",
    "subject to attorney-client privilege",
    "covered by work product",
    "do not distribute — privileged",
    "settlement communication",
    "rule 408",  # FRE 408 protects settlement discussions
]


class LegalPrivilegeRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="LEGAL_PRIVILEGE",
            deny_list=_PRIVILEGE_PHRASES,
            deny_list_score=0.95,
        )
