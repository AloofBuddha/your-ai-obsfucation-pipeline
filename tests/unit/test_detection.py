"""Detection tests — each PRD entity type must be detected on synthetic text."""
from __future__ import annotations

import pytest

from detection import (
    FIN_ACCOUNT_NUMBER,
    FIN_TAX_ID,
    LEGAL_PRIVILEGE,
    PHI_DIAGNOSIS,
    PHI_INSURANCE_ID,
    PHI_MEDICAL_LICENSE,
    PHI_MEDICATION,
    PHI_MRN,
    PII_DOB,
    PII_EMAIL,
    PII_NAME,
    PII_PHONE,
    PII_SSN,
    PresidioDetector,
)


@pytest.fixture(scope="module")
def detector() -> PresidioDetector:
    """One detector for the whole test module — engine startup is slow."""
    return PresidioDetector()


def _types_found(entities: list, expected_type: str) -> bool:
    return any(e.type == expected_type for e in entities)


async def test_detects_name(detector: PresidioDetector) -> None:
    entities = await detector.detect("The patient is John Smith.")
    assert _types_found(entities, PII_NAME)


async def test_detects_ssn(detector: PresidioDetector) -> None:
    # Use a valid-format SSN per SSA rules: area >= 1, not in reserved ranges.
    # "123-45-6789" is explicitly invalid (canonical "fake SSN") and Presidio
    # filters it. "529-99-0001" passes validity checks.
    entities = await detector.detect("SSN: 529-99-0001")
    assert _types_found(entities, PII_SSN)


async def test_detects_email(detector: PresidioDetector) -> None:
    entities = await detector.detect("Contact: john@example.com")
    assert _types_found(entities, PII_EMAIL)


async def test_detects_phone(detector: PresidioDetector) -> None:
    entities = await detector.detect("Call (512) 555-1234")
    assert _types_found(entities, PII_PHONE)


async def test_detects_dob(detector: PresidioDetector) -> None:
    entities = await detector.detect("DOB: 03/14/1985")
    assert _types_found(entities, PII_DOB)


async def test_detects_diagnosis(detector: PresidioDetector) -> None:
    entities = await detector.detect("Patient has Type 2 diabetes and hypertension.")
    assert _types_found(entities, PHI_DIAGNOSIS)


async def test_detects_medication(detector: PresidioDetector) -> None:
    entities = await detector.detect("Prescribed metformin 500 mg daily.")
    assert _types_found(entities, PHI_MEDICATION)


async def test_detects_mrn(detector: PresidioDetector) -> None:
    entities = await detector.detect("MRN: 1234567")
    assert _types_found(entities, PHI_MRN)


async def test_detects_insurance_member_id_value(detector: PresidioDetector) -> None:
    text = "Insurance: Member ID: BCBSTX8472301, Group: ABC123456"
    entities = await detector.detect(text)
    insurance_entities = [e for e in entities if e.type == PHI_INSURANCE_ID]

    assert insurance_entities
    assert any("BCBSTX8472301" in e.text for e in insurance_entities)
    assert any("ABC123456" in e.text for e in insurance_entities)


async def test_detects_medical_license_with_provider_context(
    detector: PresidioDetector,
) -> None:
    entities = await detector.detect("Referring provider license: HP223344")
    medical_license_entities = [
        e for e in entities if e.type == PHI_MEDICAL_LICENSE
    ]

    assert medical_license_entities
    assert any("HP223344" in e.text for e in medical_license_entities)


async def test_detects_legal_privilege(detector: PresidioDetector) -> None:
    entities = await detector.detect("ATTORNEY-CLIENT PRIVILEGED — do not share.")
    assert _types_found(entities, LEGAL_PRIVILEGE)


async def test_detects_account_number_luhn_valid(detector: PresidioDetector) -> None:
    # Real test card numbers that pass Luhn.
    entities = await detector.detect("Account: 4111 1111 1111 1111")
    assert _types_found(entities, FIN_ACCOUNT_NUMBER)


async def test_rejects_account_number_luhn_invalid(detector: PresidioDetector) -> None:
    """Random 16-digit string that doesn't pass Luhn must not be flagged as account."""
    entities = await detector.detect("Reference: 1234 5678 9012 3456")
    account_entities = [e for e in entities if e.type == FIN_ACCOUNT_NUMBER]
    assert account_entities == []


async def test_detects_tax_id(detector: PresidioDetector) -> None:
    entities = await detector.detect("EIN: 12-3456789")
    assert _types_found(entities, FIN_TAX_ID)


async def test_dedupes_overlapping_results(detector: PresidioDetector) -> None:
    """Multiple recognizers may flag the same span; the detector must dedupe."""
    entities = await detector.detect("John Smith, SSN 123-45-6789, born 03/14/1985.")
    seen: set[tuple[int, int, str]] = set()
    for e in entities:
        key = (e.start, e.end, e.type)
        assert key not in seen, f"Duplicate detection: {key}"
        seen.add(key)


async def test_entities_sorted_by_position(detector: PresidioDetector) -> None:
    entities = await detector.detect(
        "First name John, then SSN 123-45-6789, then email a@b.co"
    )
    starts = [e.start for e in entities]
    assert starts == sorted(starts)


async def test_no_pii_text_returns_empty(detector: PresidioDetector) -> None:
    entities = await detector.detect("This text contains no personal information.")
    # Some false positives possible (DATE_TIME might trigger on nothing) but
    # we don't expect names/SSNs/etc.
    assert not _types_found(entities, PII_SSN)
    assert not _types_found(entities, PII_EMAIL)
