"""Detection — Presidio + custom recognizers for the PRD entity types."""
from detection.detector import Detector, PresidioDetector
from detection.entity import Entity
from detection.types import (
    DEFAULT_THRESHOLD,
    FIN_ACCOUNT_NUMBER,
    FIN_TAX_ID,
    LEGAL_PRIVILEGE,
    PHI_DIAGNOSIS,
    PHI_INSURANCE_ID,
    PHI_MEDICAL_LICENSE,
    PHI_MEDICATION,
    PHI_MRN,
    PII_ADDRESS,
    PII_DOB,
    PII_EMAIL,
    PII_NAME,
    PII_PHONE,
    PII_SSN,
    threshold_for,
)

__all__ = [
    "DEFAULT_THRESHOLD",
    "Detector",
    "Entity",
    "FIN_ACCOUNT_NUMBER",
    "FIN_TAX_ID",
    "LEGAL_PRIVILEGE",
    "PHI_DIAGNOSIS",
    "PHI_INSURANCE_ID",
    "PHI_MEDICAL_LICENSE",
    "PHI_MEDICATION",
    "PHI_MRN",
    "PII_ADDRESS",
    "PII_DOB",
    "PII_EMAIL",
    "PII_NAME",
    "PII_PHONE",
    "PII_SSN",
    "PresidioDetector",
    "threshold_for",
]
