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
| `healthcare/referral_packet.txt` | PII, PHI | Clinical facts, MRNs, insurance IDs, medication and diagnosis context |
| `financial/tax_and_wire_packet.txt` | PII, FIN | Account numbers, tax IDs, payment rails, payer identity |
| `legal/privileged_strategy_memo.txt` | PII, LEGAL | Privilege markers, case strategy, named parties |
| `mixed/hr_accommodation_claim.txt` | PII, PHI, FIN, LEGAL | Cross-domain document with multiple policy choices in one payload |

## Notes

- Synthea is still a good upstream source for future healthcare fixtures, but
  this corpus keeps healthcare to one compact scenario so financial, legal, and
  generic PII receive equal coverage.
- Some planted values represent desired or aspirational coverage beyond the
  current strongest recognizers. The manifest marks every planted value so we
  can decide whether missed detection is acceptable, a known gap, or a bug.
- These examples are designed for text ingestion first. Rendered PDF/DOCX/PNG
  versions can be generated later if we want extractor-specific coverage.
