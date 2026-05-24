"""Synthetic medical intake form. Plants every PHI/PII type we recognize."""
from __future__ import annotations

NAME = "medical_intake"

TEXT = """\
SOUTH LAMAR FAMILY MEDICINE — PATIENT INTAKE FORM

Date: 03/14/2026
Patient Name: Sofia M. Reyes
DOB: 06/12/1992
Address: 1234 South Lamar Blvd, Apt 26B, Austin, TX 78704
Email: sofia.reyes@example.com
Phone: (512) 555-0142
Occupation: Software engineer
MRN: 4581723
Insurance: Member ID: BCBSTX8472301, Group: ABC123456

CHIEF CONCERN
Annual physical. Patient reports occasional fatigue, requests update on chronic conditions.

PROBLEM LIST
- Type 2 diabetes (diagnosed 2018, controlled)
- Mild depression (diagnosed 2021, improving)
- Hyperlipidemia

CURRENT MEDICATIONS
- Metformin 500 mg, twice daily
- Sertraline 50 mg, once daily
- Atorvastatin 10 mg, once at bedtime

ALLERGIES
- Penicillin (rash)
- Sulfa drugs (urticaria)

FAMILY HISTORY
Father: Type 2 diabetes, hypertension. Mother: breast cancer.

PHYSICIAN ACKNOWLEDGMENT
Reviewed and signed by Dr. James Whitaker, MD on 03/14/2026.
"""

# Tokens we expect the detector to find (used by tests to verify coverage).
PLANTED_ENTITIES: list[tuple[str, str]] = [
    ("PII_NAME", "Sofia M. Reyes"),
    ("PII_NAME", "James Whitaker"),
    ("PII_DOB", "06/12/1992"),
    ("PII_ADDRESS", "1234 South Lamar Blvd"),
    ("PII_EMAIL", "sofia.reyes@example.com"),
    ("PII_PHONE", "(512) 555-0142"),
    ("PHI_MRN", "MRN: 4581723"),
    ("PHI_INSURANCE_ID", "Member ID: BCBSTX8472301"),
    ("PHI_DIAGNOSIS", "Type 2 diabetes"),
    ("PHI_DIAGNOSIS", "depression"),
    ("PHI_DIAGNOSIS", "hyperlipidemia"),
    ("PHI_MEDICATION", "Metformin 500 mg"),
    ("PHI_MEDICATION", "Sertraline 50 mg"),
    ("PHI_MEDICATION", "Atorvastatin 10 mg"),
]
