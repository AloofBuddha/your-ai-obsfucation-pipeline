# Synthetic Data Corpus

Small, hand-authored synthetic documents for exercising obfuscation coverage
across the PRD's main sensitive-data families.

These files are not real records. Values are intentionally planted so demos,
manual QA, and future regression tests can identify which entity categories a
document is meant to cover.

Use `manifest.json` as the source of truth for:

- scenario category
- file path
- entity families covered
- planted values expected to be sensitive
- notes about why the use case is distinct for obfuscation

## Corpus Shape

| Scenario | Primary categories | Purpose |
| --- | --- | --- |
| `identity/customer_support_incident.txt` | PII | Generic personal data, URLs, IPs, government IDs |
| `identity/adversarial_identifier_packet.txt` | PII | Free-form support ticket with account-recovery identifiers |
| `healthcare/referral_packet.txt` | PII, PHI | Clinical facts, MRNs, insurance IDs, medication and diagnosis context |
| `healthcare/provider_email_thread.txt` | PII, PHI | PHI embedded in provider correspondence |
| `healthcare/noisy_ocr_intake.txt` | PII, PHI | OCR-like extracted form text with uppercase labels |
| `financial/tax_and_wire_packet.txt` | PII, FIN | Account numbers, tax IDs, payment rails, payer identity |
| `financial/tax_intake_table.txt` | PII, FIN | Pipe-delimited form/table layout with tax and account IDs |
| `legal/privileged_strategy_memo.txt` | PII, LEGAL | Privilege markers, case strategy, named parties |
| `legal/long_privileged_brief_excerpt.txt` | PII, FIN, LEGAL | Longer narrative legal text with repeated privileged references |
| `mixed/hr_accommodation_claim.txt` | PII, PHI, FIN, LEGAL | Cross-domain document with multiple policy choices in one payload |

## Notes

- Synthea is still a good upstream source for future healthcare fixtures, but
  this corpus keeps healthcare to one compact scenario so financial, legal, and
  generic PII receive equal coverage.
- Some planted values represent desired or aspirational coverage beyond the
  current strongest recognizers. The manifest marks every planted value so we
  can decide whether missed detection is acceptable, a known gap, or a bug.
- These examples are designed for text ingestion first. Rendered PDF/DOCX/PNG
  variants remain useful follow-up coverage for extractor-specific behavior and
  raw OCR quality.
