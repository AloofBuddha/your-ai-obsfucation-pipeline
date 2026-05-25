"""Custom Presidio recognizers. Adding a new entity type = add a file here,
add it to all_custom_recognizers(), done. Per PRD extensibility NFR."""
from __future__ import annotations

from presidio_analyzer import EntityRecognizer

from detection.recognizers.address import StreetAddressRecognizer
from detection.recognizers.diagnosis import DiagnosisRecognizer
from detection.recognizers.financial import AccountNumberRecognizer, TaxIDRecognizer
from detection.recognizers.healthcare_ids import (
    InsuranceIDRecognizer,
    MRNRecognizer,
    ProviderMedicalLicenseRecognizer,
)
from detection.recognizers.legal import LegalPrivilegeRecognizer
from detection.recognizers.medication import MedicationRecognizer


def all_custom_recognizers() -> list[EntityRecognizer]:
    """Instantiated fresh each call so registries don't share state across tests."""
    return [
        DiagnosisRecognizer(),
        MedicationRecognizer(),
        MRNRecognizer(),
        InsuranceIDRecognizer(),
        ProviderMedicalLicenseRecognizer(),
        AccountNumberRecognizer(),
        TaxIDRecognizer(),
        LegalPrivilegeRecognizer(),
        StreetAddressRecognizer(),
    ]


__all__ = ["all_custom_recognizers"]
