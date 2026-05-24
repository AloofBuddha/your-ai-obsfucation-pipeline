"""PHI_DIAGNOSIS — dictionary-based + ICD-10 code regex."""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

# Short curated list of common conditions. Not exhaustive — README documents
# this as a known limitation and the suggested next-step is a fuller dictionary
# (UMLS / SNOMED-CT) or LLM-based detection.
_DIAGNOSES = [
    "type 1 diabetes",
    "type 2 diabetes",
    "diabetes mellitus",
    "diabetes",
    "hypertension",
    "high blood pressure",
    "depression",
    "major depressive disorder",
    "anxiety",
    "generalized anxiety disorder",
    "asthma",
    "copd",
    "chronic obstructive pulmonary disease",
    "alzheimer's",
    "alzheimer's disease",
    "dementia",
    "cancer",
    "breast cancer",
    "lung cancer",
    "prostate cancer",
    "leukemia",
    "lymphoma",
    "hiv",
    "aids",
    "hepatitis",
    "hepatitis c",
    "stroke",
    "myocardial infarction",
    "heart attack",
    "congestive heart failure",
    "atrial fibrillation",
    "hyperlipidemia",
    "obesity",
    "osteoarthritis",
    "rheumatoid arthritis",
    "ptsd",
    "post-traumatic stress disorder",
    "bipolar disorder",
    "schizophrenia",
    "epilepsy",
    "migraine",
]

# ICD-10 code pattern: one letter, two digits, optional .digits suffix.
_ICD10_PATTERN = Pattern(
    name="icd10",
    regex=r"\b[A-Z]\d{2}(?:\.\d{1,3})?\b",
    score=0.6,  # Low: many false positives (e.g., S30 could be a code or a label)
)


class DiagnosisRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="PHI_DIAGNOSIS",
            deny_list=_DIAGNOSES,
            deny_list_score=0.85,
            patterns=[_ICD10_PATTERN],
        )
