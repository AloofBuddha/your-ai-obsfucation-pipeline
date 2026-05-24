# YourAI · Engineering Interview Challenge

**Title:** Secure Context Pipeline: PII Obfuscation for External LLM Providers
**Track:** Senior Engineer · Security / AI · Take-Home
**Time Allowed:** 8 – 10 Hours
**Format:** Take-Home / Async

> Design and build the system that lets users bring their most sensitive data into AI workflows — without ever exposing raw PII, PHI, or privileged content to an external model provider.

**Confidentiality:** This challenge describes a real engineering problem YourAI is actively solving. Do not share publicly or with third parties.

---

## Business Context

YourAI is building an AI productivity platform for professionals working with the most sensitive data that exists: medical records, legal case files, financial disclosures, personal health information. Users — physicians, attorneys, financial advisors, compliance officers — need AI assistance with this data, but cannot expose it to third-party model providers in raw form.

External LLM providers (OpenAI, Anthropic, others) are the inference backends. Contractual zero-retention guarantees are insufficient — we need a **technical guarantee**: raw PII / PHI / privileged content must never leave our infrastructure in a form a provider or intermediary can read or reconstruct.

Simultaneously, the obfuscated data must retain enough **semantic structure** for the model to reason correctly. When the response returns, references to obfuscated entities must be **transparently restored** before the user sees them.

---

## The Problem You Are Solving

| Data Type | Examples | Regulatory Scope |
|---|---|---|
| PII | Full name, SSN, DOB, address, email, phone | GDPR, CCPA, COPPA |
| PHI | Diagnoses, medications, MRN, insurance IDs, lab results | HIPAA (45 CFR Parts 160 & 164) |
| Legal Privilege | Case strategy, client identity, settlement terms, privileged memos | Attorney-Client Privilege, Work Product Doctrine |
| Financial PII | Account numbers, tax IDs, transaction history | GLBA, SOX, PCI-DSS |

Build the **Secure Context Pipeline** — the system layer that sits between YourAI's document store and the external LLM API. It handles the full round-trip: **detect → obfuscate → call LLM → restore**.

---

## System Architecture You Are Building

```
┌──────────────────────────────────────────────────────────────────┐
│ YOURAI INFRASTRUCTURE                                            │
│                                                                  │
│   [User Upload]                                                  │
│        │                                                         │
│        ▼                                                         │
│   [Secure Document Store] ─── Encrypted at rest, per-user vault  │
│        │                                                         │
│        ▼                                                         │
│   [PII / PHI Detector]    ─── NER + rule-based recognition       │
│        │                                                         │
│        ▼                                                         │
│   [Obfuscation Engine]    ─── Token map stored in Session Vault  │
│        │                                                         │
│        ▼                                                         │
│   [Obfuscated Context] ────────────────────────►  External LLM   │
│                                                        │         │
│   [LLM Response w/ tokens] ◄───────────────────────────┘         │
│        │                                                         │
│        ▼                                                         │
│   [De-obfuscation Engine] ─── Vault lookup + token replacement   │
│        │                                                         │
│        ▼                                                         │
│   [Restored Response]     ─── User sees original values          │
└──────────────────────────────────────────────────────────────────┘
```

---

## Core Requirements (Must Complete)

| # | Component | Requirement |
|---|---|---|
| 1 | **Secure Store** | Users upload documents (PDF, DOCX, TXT). Encrypted at rest with AES-256. Per-user data isolation. |
| 2 | **PII/PHI Detector** | Detect & classify entities across all four data types. Must identify at minimum: NAME, SSN, DOB, ADDRESS, EMAIL, PHONE, DIAGNOSIS, MEDICATION, MRN, INSURANCE_ID, ACCOUNT_NUMBER, TAX_ID, plus legal privilege markers. |
| 3 | **Obfuscation Engine** | Two strategies: (a) **Tokenization** — replace with typed tokens like `[PHI_NAME_a3f2]`, meaningless to the model alone; (b) **Pseudonymization** — replace with realistic surrogates (e.g. "John Smith" → "Michael Torres") consistent within a session. |
| 4 | **Session Vault** | Bidirectional token ↔ original mapping, scoped to a user session. Vault entries encrypted. Same entity in the same session maps to the same token. |
| 5 | **LLM Context Injector** | Assemble obfuscated document chunks into a context payload and call an external LLM API. Raw document content must never appear in the outbound payload. |
| 6 | **De-obfuscation Engine** | Parse LLM response, detect all token references (including paraphrased / grammatically inflected forms), replace via vault lookup. |
| 7 | **Audit Log** | Every obfuscation and de-obfuscation event logged with: timestamp, session ID, entity type, token (not original), action. **No original values, ever.** |

> **Critical Constraint:** Reversible *within* a session, **irreversible across sessions**. If a vault is destroyed, original values cannot be recovered from tokens alone. This is a security guarantee, not a bug.

---

## Non-Functional Requirements

- **Extensibility:** Adding a new entity type (e.g. `PASSPORT_NUMBER`) requires changes to detector config only — zero changes to obfuscation or vault logic.
- **Strategy swappability:** Tokenization and pseudonymization interchangeable via config — no business logic changes.
- **Zero PII in transit:** Network inspection of outbound LLM call must show no recognizable PII / PHI / privileged content.
- **Vault isolation:** Vault from Session A must be cryptographically inaccessible to Session B, even by the same user.
- **Graceful entity degradation:** If an entity type cannot be detected with sufficient confidence, it must be redacted entirely rather than passed through unmasked.
- **Async pipeline:** All I/O (storage reads, LLM calls, vault lookups) must be non-blocking.

---

## Technology Stack

| Category | Required / Accepted | Notes |
|---|---|---|
| Language | Python 3.10+ | `asyncio` required throughout |
| PII Detection | spaCy, Microsoft Presidio, AWS Comprehend, or LLM-based | Candidate must justify (accuracy vs. latency vs. cost) |
| Encryption | Python `cryptography` (Fernet / AES-GCM) | No rolling own crypto |
| LLM Provider | OpenAI or Anthropic API | Provided key or candidate's own |
| Secure Storage | SQLite + SQLCipher, PostgreSQL, or encrypted file store | Must support per-user key isolation |
| Testing | pytest + pytest-asyncio | Required |
| Dev Tools | Git, Docker, .env config | Docker strongly encouraged |
| Cloud (optional) | AWS KMS / GCP KMS mock, S3 / GCS for doc store | Local mocks acceptable — design must be cloud-compatible |

---

## Expected Deliverables

Private Git repository with the following structure:

```
/secure-context-pipeline
  /store         # Encrypted document upload + retrieval
  /detection     # PII / PHI / privilege entity detection
  /obfuscation
    /strategies  # Tokenization + pseudonymization implementations
    /engine      # Orchestrates detection → strategy selection → output
  /vault         # Session-scoped encrypted token ↔ original mapping
  /pipeline      # End-to-end: ingest → obfuscate → LLM call → restore
  /deobfuscation # Token detection + replacement in LLM responses
  /audit         # Compliance event logging
  /tests         # Unit + integration tests
docker-compose.yml
README.md
```

**README must include:** Threat model (what attacks does your design resist?), entity detection approach + justification, tokenization vs. pseudonymization comparison for ≥ 2 entity types, known gaps, what you'd build next with one extra day.

---

## Evaluation Rubric

| Dimension | Weight | What We Look For |
|---|---|---|
| Security Architecture | 30% | Vault design credible under adversarial review. Encryption applied correctly (not just present). Zero PII in transit verifiable. |
| Obfuscation Quality | 25% | Tokenization deterministic within session, non-deterministic across sessions. Pseudonymization preserves utility. |
| De-obfuscation Correctness | 20% | All token references restored, including grammatically inflected forms. No tokens leak to user output. |
| Code Quality | 15% | Typed interfaces. Pluggable strategies. Async I/O everywhere. Tests cover edge cases. |
| Critical Thinking | 10% | README shows awareness of inference attacks, vault-as-target, re-identification risk. |

---

## Success Criteria

### Functional Must-Haves

- ✓ Document with PII/PHI uploaded, stored encrypted, retrievable only with correct user key.
- ✓ All specified entity types detected with labeled spans before any LLM call.
- ✓ Outbound LLM payload contains zero instances of original PII/PHI — verifiable by inspection.
- ✓ LLM response tokens fully restored to original values in user-facing output.
- ✓ Session vault destroyed on logout; subsequent sessions cannot access prior vault mappings.
- ✓ Audit log captures all obfuscation events with no original values present.
- ✓ End-to-end pipeline runs successfully on the provided test fixture document.

### Performance Benchmarks

- Full pipeline (detect → obfuscate → LLM call → restore) for a 2,000-word document: **< 15 seconds**.
- Obfuscation engine alone (excluding LLM call) for a 2,000-word document: **< 2 seconds**.
- Vault lookup for token re-identification: **< 5ms per token**.
- De-obfuscation of a 500-token LLM response: **< 500ms**.
- Zero PII leakage verified across **100 automated test runs** on varied fixture documents.

### Code Quality Expectations

- All public interfaces fully type-annotated — entity detection, vault operations, obfuscation strategies.
- Obfuscation strategies implement a shared base class — adding a new strategy touches zero harness code.
- All secrets/keys via environment variables or `.env` — none hardcoded or committed.
- Tests cover: happy path, entity type not found, vault miss on de-obfuscation, expired session, concurrent session isolation.
- Async I/O for all LLM API calls, vault reads/writes, document store operations.
- **Logging must never emit original values** — token IDs only. Hard requirement.

---

## Live Review Discussion (45 min, post-submission)

Prepare to walk through code and discuss:

- **Q1.** Walk through a 50-page legal brief with 200 distinct PII entities. Where are the bottlenecks; how would you address them at scale?
- **Q2.** LLM response contains "the patient's condition." Your token for the diagnosis was `[PHI_DIAGNOSIS_x7a]`. How do you handle co-reference — indirect references the model made without using the token?
- **Q3.** Pseudonymization replaces "John Smith" with "Michael Torres" consistently within a session. An adversary has the obfuscated document and the LLM response. What can they infer; how does your design limit that?
- **Q4.** Session vault is a single point of failure and high-value target. Describe your threat model and production-grade controls.
- **Q5.** A HIPAA auditor asks you to prove no PHI was transmitted to the LLM provider in the past 30 days. What does your audit log give them; what gaps remain?
- **Q6.** Tokenization is deterministic within a session. Why is non-determinism across sessions a security *requirement*, not just a preference?

---

## Submission Instructions

1. Push to a private GitHub/GitLab repo, grant access to hiring team before deadline.
2. README must include working setup guide — reviewers run with `docker-compose up` or `pip install + python demo.py`.
3. Include demo script/notebook that runs the full pipeline end-to-end on a bundled test document.
4. Submit repo link via hiring portal before deadline. Late submissions not reviewed.
5. Do not open-source or publicly share this challenge, problem description, or solution.

*YourAI · Confidential — For Candidate Use Only · © 2026*
