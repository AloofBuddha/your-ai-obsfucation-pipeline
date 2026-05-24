"""Canonical entity type names + mapping from Presidio's built-in labels.

Type names match the grammar `CATEGORY[_SUBCATEGORY]_FIELD` where CATEGORY is
PII | PHI | FIN | LEGAL. The deobfuscation regex requires this shape.
"""
from __future__ import annotations

# PII (generic personal info)
PII_NAME = "PII_NAME"
PII_SSN = "PII_SSN"
PII_PHONE = "PII_PHONE"
PII_EMAIL = "PII_EMAIL"
PII_DOB = "PII_DOB"
PII_ADDRESS = "PII_ADDRESS"
PII_NRP = "PII_NRP"             # Nationality / religion / political affiliation
PII_DRIVER_LICENSE = "PII_DRIVER_LICENSE"
PII_PASSPORT = "PII_PASSPORT"
PII_IP = "PII_IP"
PII_URL = "PII_URL"

# PHI (health)
PHI_DIAGNOSIS = "PHI_DIAGNOSIS"
PHI_MEDICATION = "PHI_MEDICATION"
PHI_MRN = "PHI_MRN"
PHI_INSURANCE_ID = "PHI_INSURANCE_ID"
PHI_MEDICAL_LICENSE = "PHI_MEDICAL_LICENSE"

# Financial
FIN_ACCOUNT_NUMBER = "FIN_ACCOUNT_NUMBER"
FIN_TAX_ID = "FIN_TAX_ID"
FIN_IBAN = "FIN_IBAN"
FIN_CRYPTO = "FIN_CRYPTO"

# Legal
LEGAL_PRIVILEGE = "LEGAL_PRIVILEGE"


# Map Presidio's built-in entity labels to our canonical ones. Any Presidio
# label not in this map is passed through unchanged (and tagged as the type
# the obfuscation engine sees).
PRESIDIO_TO_LOCAL: dict[str, str] = {
    "PERSON": PII_NAME,
    "US_SSN": PII_SSN,
    # US_ITIN is the IRS tax ID for non-citizens; same XXX-XX-XXXX shape as SSN.
    # Presidio also falls back to US_ITIN when a number looks SSN-shaped but
    # fails SSA validity rules. Tag as FIN_TAX_ID — sensitive regardless.
    "US_ITIN": FIN_TAX_ID,
    "PHONE_NUMBER": PII_PHONE,
    "EMAIL_ADDRESS": PII_EMAIL,
    "DATE_TIME": PII_DOB,        # Over-detects general dates, accepted as safety bias.
    "LOCATION": PII_ADDRESS,     # Presidio LOCATION ~ city/state; full street via custom recognizer below.
    "CREDIT_CARD": FIN_ACCOUNT_NUMBER,
    "US_BANK_NUMBER": FIN_ACCOUNT_NUMBER,
    "NRP": PII_NRP,
    "US_DRIVER_LICENSE": PII_DRIVER_LICENSE,
    "US_PASSPORT": PII_PASSPORT,
    "IP_ADDRESS": PII_IP,
    "URL": PII_URL,
    "MEDICAL_LICENSE": PHI_MEDICAL_LICENSE,
    "IBAN_CODE": FIN_IBAN,
    "CRYPTO": FIN_CRYPTO,
}


# Per-type confidence thresholds. Below threshold -> entity is degraded to an
# opaque vault token even when pseudonymization is selected.
# Defaults chosen with awareness that Presidio score calibration varies across
# recognizers (regex-based -> typically 0.85+; NLP-based PERSON -> 0.85 default
# but can drop to 0.6 on ambiguous tokens).
DEFAULT_THRESHOLD = 0.6
PER_TYPE_THRESHOLD: dict[str, float] = {
    PII_NAME: 0.55,           # spaCy PERSON is noisy; accept slightly lower confidence
    PII_DOB: 0.5,             # DATE_TIME over-fires; accept low confidence (safety bias)
    PII_ADDRESS: 0.55,
    PHI_DIAGNOSIS: 0.7,
    PHI_MEDICATION: 0.7,
    LEGAL_PRIVILEGE: 0.9,     # Phrase match is high-confidence by construction
}


def threshold_for(
    entity_type: str,
    default_threshold: float = DEFAULT_THRESHOLD,
) -> float:
    return PER_TYPE_THRESHOLD.get(entity_type, default_threshold)
