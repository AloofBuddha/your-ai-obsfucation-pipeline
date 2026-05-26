"""Healthcare identifier recognizers — pattern-based PHI recognition."""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


class MRNRecognizer(PatternRecognizer):
    """Medical record number: typical formats are 'MRN: 1234567' or 'MRN# 1234567'."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="PHI_MRN",
            patterns=[
                Pattern(
                    name="mrn_labeled",
                    regex=r"\bMRN[:\s#]+\d{6,10}\b",
                    score=0.95,
                ),
                Pattern(
                    # Just "MRN" followed by digits with no whitespace works too
                    name="mrn_compact",
                    regex=r"\bMRN\d{6,10}\b",
                    score=0.9,
                ),
            ],
            context=["medical record", "patient id", "chart"],
        )


class InsuranceIDRecognizer(PatternRecognizer):
    """Insurance/policy ID. Common formats vary by insurer; we accept:
    - 'Member ID: XYZ1234567'
    - 'Insurance: Member ID: XYZ1234567'
    - 'Policy #: 123-45-6789' (note: collides with SSN format — accept that risk)
    - 'Group: ABC123456'
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="PHI_INSURANCE_ID",
            patterns=[
                Pattern(
                    name="member_id",
                    regex=(
                        r"\b(?:Member\s*ID|Insurance\s*:\s*Member\s*ID|"
                        r"Insurance\s*ID|Policy\s*(?:ID|#|No\.?)?|Group)"
                        r"[:\s#-]+[A-Z0-9][A-Z0-9-]{5,20}\b"
                    ),
                    score=0.85,
                ),
            ],
            context=["insurance", "policy", "member id", "plan", "subscriber"],
        )


class ProviderMedicalLicenseRecognizer(PatternRecognizer):
    """Provider medical license identifiers in referral packets and clinical notes.

    Presidio's built-in MEDICAL_LICENSE recognizer covers common US formats but
    misses compact local/provider examples such as "Provider license: HP223344".
    The label/context requirement keeps short alphanumeric IDs from turning into
    broad false positives.
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="PHI_MEDICAL_LICENSE",
            patterns=[
                Pattern(
                    name="medical_license_labeled",
                    regex=(
                        r"\b(?:Provider\s+license|Medical\s+license|"
                        r"Clinician\s+license|Physician\s+license|NPI)"
                        r"[:\s#-]+[A-Z]{1,4}\d{5,10}\b"
                    ),
                    score=0.9,
                ),
            ],
            context=["provider", "physician", "clinician", "license", "npi"],
        )
