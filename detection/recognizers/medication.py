"""PHI_MEDICATION — dictionary of drug names + dosage regex."""
from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer

_MEDICATIONS = [
    # Diabetes
    "metformin", "insulin", "glipizide", "januvia",
    # Cardiovascular / lipids
    "atorvastatin", "lipitor", "simvastatin", "lisinopril", "amlodipine",
    "metoprolol", "losartan", "hydrochlorothiazide", "warfarin", "clopidogrel",
    # Pain / NSAIDs
    "ibuprofen", "naproxen", "aspirin", "acetaminophen", "tylenol",
    "oxycodone", "hydrocodone", "tramadol", "morphine",
    # Antidepressants / anxiolytics
    "sertraline", "zoloft", "fluoxetine", "prozac", "escitalopram", "lexapro",
    "citalopram", "venlafaxine", "duloxetine", "bupropion", "wellbutrin",
    "alprazolam", "xanax", "lorazepam", "ativan", "clonazepam",
    # Antibiotics
    "amoxicillin", "azithromycin", "ciprofloxacin", "doxycycline",
    # Respiratory
    "albuterol", "fluticasone", "montelukast", "singulair",
    # Thyroid / hormones
    "levothyroxine", "synthroid",
    # GI
    "omeprazole", "prilosec", "pantoprazole", "ranitidine",
]

# Dosage marker — used as a context boost. Common forms:
#   "10 mg", "500mg", "2.5 mL", "100 mcg"
_DOSAGE_PATTERN = Pattern(
    name="dosage",
    regex=r"\b\d+(?:\.\d+)?\s?(?:mg|ml|mcg|g|iu|units?)\b",
    score=0.4,  # Low on its own — meaningful only near a drug name
)


class MedicationRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="PHI_MEDICATION",
            deny_list=_MEDICATIONS,
            deny_list_score=0.85,
            patterns=[_DOSAGE_PATTERN],
            context=["medication", "rx", "prescribed", "dose", "tablet"],
        )
