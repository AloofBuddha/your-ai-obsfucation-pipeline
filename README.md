# Secure Context Pipeline

PII/PHI obfuscation for external LLM providers. Detects sensitive entities in
documents, replaces them with safe-to-send tokens or surrogates, calls the LLM,
and transparently restores the originals in the response — so the LLM provider
never sees raw PII but the user sees their data unchanged.

See **`PLAN.html`** for the full design rationale and **`PRD.md`** for the
source-of-truth requirements.

---

## Quick start

```bash
# 1. Set your Anthropic key in .env
cp .env.example .env
# edit .env to add ANTHROPIC_API_KEY=sk-ant-...

# 2. Install deps (uv pulls Python 3.11 + all packages)
uv sync
uv run python -m spacy download en_core_web_lg

# 3. Build the synthetic test fixtures
uv run python -m tests.fixtures.build

# 4. Run the CLI demo end-to-end on a bundled fixture
uv run python demo.py                       # medical intake, tokenization
uv run python demo.py --strategy pseudonymize
uv run python demo.py --fixture legal_memo --format pdf

# 5. Run the full test suite
uv run pytest                               # 99 tests, ~25s
uv run pytest -m perf                       # 4 perf benchmarks
```

### With the UI

```bash
# Terminal 1: the FastAPI backend
uv run uvicorn api.main:app --reload --port 8000

# Terminal 2: the React UI (Vite dev server)
cd ui && npm install && npm run dev
# open http://localhost:5173
```

Dev-mode UI (default) shows all four pipeline stages — source, detected entities,
obfuscated payload sent to the LLM, restored response. Add `?dev=false` for the
clean "what the user sees" view.

### With docker-compose

```bash
docker-compose up
# UI at http://localhost:5173, API at http://localhost:8000
```

System dependencies (Tesseract, Poppler) are baked into the API image.

---

## Threat model

Designed against six adversaries, in priority order. Each one is mapped to a
concrete defense and a CI-testable assertion.

| # | Adversary | Capability | Defense |
|---|---|---|---|
| **A1** | External LLM provider | Sees outbound payload, logs prompts | Zero raw PII in payload — only typed tokens or surrogates. Verified by `test_zero_pii_leakage_100_runs` (100 randomized fixtures). |
| **A2** | Network MITM | Captures TLS-decrypted traffic at egress | Same as A1 — the payload is already PII-free before TLS. |
| **A3** | Cross-session leakage | Session B receives a token derived from Session A's data | Per-session ephemeral vault key (SVK). Tokens are HMAC outputs of that key, not lookups in a global table. Different SVK → different token for same value. |
| **A4** | Vault snapshot theft | Attacker exfiltrates the vault DB file at rest | Rows encrypted with per-session Fernet key. SVK is in-memory only — never written to disk. Stolen DB ≡ unreadable ciphertext. |
| **A5** | Audit log inspection | Compliance auditor or attacker reads the audit log | Log contains tokens + types + timestamps only. Schema-enforced: pydantic validator rejects any field name containing `value`/`original`/`plaintext`, recursively, including inside `metadata` dicts. |
| **A6** | Re-identification via correlation | Adversary has obfuscated doc + LLM response + side knowledge | Partially mitigated; frequency/co-occurrence leakage documented as a known gap (see below). |

### Three hard guarantees (testable in CI)

1. **The outbound LLM payload contains no substring from the source document's
   detected entities.** Tested across all bundled fixtures and 100 randomized
   ones.
2. **If a session vault is destroyed, no token from that session can be reversed
   by any code path.** The SVK is wiped from memory; vault rows are deleted from
   SQLite; even if a backup of the DB leaks, no key exists to decrypt.
3. **The audit log, grep'd for any original entity value, returns zero matches.**
   Verified end-to-end after a full pipeline run.

---

## Cryptographic design

**Two keys, two lifetimes.** Deliberately minimal — matches the PRD's
encryption-at-rest + per-user isolation requirements without dragging in
production-grade machinery (KMS, key wrapping, KDF) that the demo doesn't need.

| Key | Scope | Lifetime | Storage |
|---|---|---|---|
| **User key** | One per user | Persistent | 32 random bytes, env var `USER_KEY_<user_id>` or auto-generated and persisted to `data/user_keys.json` (gitignored) |
| **Session vault key (SVK)** | Per session | Ephemeral, dies on `vault.destroy()` | 32 random bytes, generated at session start, in-memory only |

### Token construction

```
token   = "[{TYPE}_{SHORTID}]"          e.g.  [PHI_NAME_k7a2mqpz]
SHORTID = base32( HMAC-SHA256(SVK, TYPE || canonicalize(value)) )[:8].lower()
```

- **8 lowercased base32 chars = 40 bits.** Collision probability across 10k
  entities in a session is negligible.
- **Deterministic within session** (same SVK + same value → same token), so the
  same entity always maps to the same token within one document.
- **Non-deterministic across sessions** (different SVK → different token). This
  is the cryptographic basis for the PRD's "irreversible across sessions"
  requirement — not a policy, but a property: without the SVK, no token can be
  inverted.
- **One-way.** Even an adversary with both the SVK and a token must already
  guess the value to verify it (no offline reversal).

Vault rows store `Fernet(SVK).encrypt(value)` keyed by the token. SVK dies on
logout → row ciphertext is permanently unrecoverable.

A separate domain-separated HMAC (`compute_dedupe_key`) computes a stable
session-scoped key used for dedup — so storing the same entity twice returns
the same replacement without ever computing the Faker surrogate twice (matters
for pseudonymization).

---

## Entity detection — approach and justification

**Microsoft Presidio + custom recognizers**, wrapped in `asyncio.to_thread`.

Why Presidio:
- Ships with battle-tested recognizers for the PRD's required entity types:
  `PERSON` (→ PII_NAME), `US_SSN`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `DATE_TIME`
  (→ PII_DOB), `LOCATION` (→ PII_ADDRESS), `CREDIT_CARD`.
- Plugin architecture (`PatternRecognizer`) means a new entity type is one new
  file in `detection/recognizers/` plus one registration line — meeting the PRD
  extensibility NFR with zero engine code change.
- Accuracy is good enough for an MVP (~85-95% on standard PII formats) and the
  failure mode is over-detection (safer than under-detection for a redaction
  pipeline).

What's added on top:

| Entity | Approach |
|---|---|
| `PHI_DIAGNOSIS` | Curated dictionary of ~40 common conditions + ICD-10 code regex |
| `PHI_MEDICATION` | Dictionary of common drug names + dosage regex (`\d+\s?(mg|mL|mcg)`) |
| `PHI_MRN` | Regex `\bMRN[:\s#]+\d{6,10}\b` |
| `PHI_INSURANCE_ID` | Member-ID / policy patterns with context boost |
| `FIN_ACCOUNT_NUMBER` | 13-19 digit sequences validated by Luhn checksum |
| `FIN_TAX_ID` | EIN regex `\b\d{2}-\d{7}\b` + Presidio's SSN/ITIN |
| `LEGAL_PRIVILEGE` | Phrase matcher for "ATTORNEY-CLIENT PRIVILEGED", "WORK PRODUCT", Rule 408, etc. |
| `PII_ADDRESS` | Full US street suffix list (Faker-compatible) — supplements Presidio's LOCATION which is city/state-level |

**Per-entity confidence thresholds.** Presidio score calibration varies across
recognizer types — regex-based recognizers typically return 0.85+, NLP-based
PERSON returns 0.85 default but can drop to 0.5 on ambiguous tokens. The
thresholds in `detection/types.py:PER_TYPE_THRESHOLD` are tuned per type. Below
threshold → entity is degraded to an opaque vault token even if pseudonymization
is selected. The LLM still sees no raw value, and our side can restore the value
if the LLM repeats the token (PRD §"Graceful entity degradation").

**Tradeoff vs alternatives:**
- *spaCy alone:* faster but you build the regex layer yourself for SSN, phone,
  email, etc. More work for similar accuracy.
- *LLM-based detection:* highest accuracy on novel entity types but adds an
  extra network hop and routes the original (unredacted!) document through
  another LLM — which violates threat model A1 unless you self-host. Skipped
  for MVP.

---

## Tokenization vs pseudonymization

Two strategies, swappable via `OBFUSCATION_STRATEGY=tokenize|pseudonymize`.
Both implement the same `ObfuscationStrategy` ABC; both deduplicate by HMAC of
the value within a session (so the same entity always gets the same
replacement); both restore correctly through the deobfuscation engine.

**Comparison on two concrete entity types:**

### PII_NAME — "Sofia M. Reyes"

| | Tokenization | Pseudonymization |
|---|---|---|
| LLM sees | `[PII_NAME_k7a2mqpz]` | `Michael Torres` |
| Semantic info leaked | None — the type label is the only signal | Plausibility-shape (it's a person name, not a city) and statistical properties (length, gender bias of Faker) |
| LLM utility | Lower — the LLM treats the token as an opaque ID. Reasoning about pronouns and roles may degrade. | Higher — the LLM treats it as a real name and produces natural prose. |
| Restoration | Regex match → vault lookup. Trivial. | Substring match with possessive/plural-suffix tolerance, longest-surrogate-first. More moving parts. |
| Cross-session safety | Strong — different SVK → different token. | Strong — different Faker seed → different surrogate. |

### PHI_DIAGNOSIS — "Type 2 diabetes"

| | Tokenization | Pseudonymization |
|---|---|---|
| LLM sees | `[PHI_DIAGNOSIS_a3bcde2f]` | `[medical condition]` (placeholder — Faker has no medical-condition generator, and a randomly-substituted *real* diagnosis would risk the LLM giving medically-wrong advice) |
| LLM utility | The LLM knows *something* sensitive exists at this slot but can't reason about treatment, severity, comorbidity. | The LLM treats it as a generic placeholder — also can't reason about the specifics, but the structure of the prose is preserved. |
| Information leak | None. | None (placeholder is constant). |
| Recommendation | **Use tokenization for medical contexts.** Surrogates that "look like" diagnoses are dangerous; opaque tokens are honest about ignorance. |

**Rule of thumb:** tokenize for high-stakes structured fields (medical, legal,
financial IDs). Pseudonymize for low-stakes narrative fields (names, addresses,
generic descriptors) where preserving prose structure helps the LLM do useful
work.

---

## Architecture

```
                          UI (React + Vite)
                                ↓
                          api/  (FastAPI)
                                ↓
                       pipeline/  (orchestrator)
              ┌────────┬────────┬─────────┬──────────────┐
              ▼        ▼        ▼         ▼              ▼
           store/   detection/ obfuscation/ deobfuscation/ llm_client/
              │        │        │           │              │
              └────────┴──→ vault/  ←───────┘              │
                            │                              │
                            └─→ audit/  ←──────────────────┘
```

Module layering is strict. `audit/` depends on nothing; `vault/` depends on
`audit/`; `obfuscation/`/`deobfuscation/` depend on `vault/` + `audit/`;
`pipeline/` orchestrates them; `api/` exposes them. Adding a new entity type or
a new obfuscation strategy touches only the relevant leaf module.

---

## Test coverage

```
uv run pytest          # 99 functional tests, ~12s
uv run pytest -m perf  # 4 perf benchmarks, ~10s
```

PRD-required test scenarios all live in `tests/`:

| Test | Asserts |
|---|---|
| `test_happy_path` family | Each PRD entity type detected on synthetic text |
| `test_entity_below_threshold` | Sub-threshold → opaque vault token, original not in payload |
| `test_vault_miss_on_deobfuscation` | Foreign token → `[UNRESOLVED_TOKEN]`, audit event, no crash |
| `test_expired_session` | `pipeline.run()` after `vault.destroy()` → `SessionExpiredError` |
| `test_cross_session_isolation` | Two sessions, same value → different tokens; cross-lookup fails |
| `test_doc_encrypted_at_rest` | Raw bytes on disk contain no plaintext from input |
| `test_cross_user_decrypt_fails` | User B's key can't decrypt User A's doc |
| `test_outbound_payload_zero_pii` | Captured outbound LLM body contains no source-entity substrings |
| `test_audit_log_purity` | After full run, grep'd audit log has zero source-entity matches |
| `test_session_destroy_irreversible` | Post-destroy lookup → None; ciphertext gone |
| `test_zero_pii_leakage_100_runs` | 100 randomized fixtures, no leakage; planted == detected (catches vacuous passes) |
| `test_perf_*` | All four PRD perf budgets (15s pipeline, 2s obfuscation, 5ms vault, 500ms deob) |

---

## Known gaps

**In rough priority order — addressing each would be a non-trivial follow-up.**

1. **Co-reference resolution.** The LLM may produce indirect references the
   pipeline never tokenized — "the patient", "this individual", "she". These
   leak through unrestored. Mitigations: prompt engineering (current — system
   prompt asks the LLM to use placeholders verbatim); future, a second
   entity-linking pass.

2. **Frequency analysis on pseudonymized output.** An adversary with both the
   obfuscated doc and the LLM response can count surrogate occurrences and
   infer entity importance. Tokenization is unaffected. Future fix:
   differential-privacy noise on entity counts.

3. **Vault key in process memory.** The SVK lives in Python memory for the
   session duration. An attacker with memory-read access (e.g., a co-tenant on
   the host, a malicious dependency, a `/proc/<pid>/mem` reader) defeats the
   scheme. Production: HSM-resident or KMS-resident keys, with audit on every
   `decrypt` operation.

4. **Vault-lookup timing side-channel.** SQLite index hit/miss timings differ
   measurably; an attacker with API access could probe token existence. MVP
   doesn't mitigate; production would use constant-time lookup paths or rate
   limiting per session.

5. **Pseudonymization inflection edge cases.** The current regex handles
   trailing `'s` / `s` / punctuation, but the LLM may produce more exotic
   inflections ("the Torreses", "Torres'" without `s`, lowercased mid-sentence
   "torres", non-English plurals on European-name surrogates). Tokenization is
   not affected.

6. **Handwriting OCR.** Tesseract handles printed/typed text only. Scanned forms
   with handwritten fields are out of scope for the MVP. Production would
   layer Cloud Vision or a specialized model, though see threat model A1 —
   would need self-hosted to avoid sending the unredacted image to a third
   party.

7. **Multi-language detection.** Presidio default is English-only.

8. **Vault HA.** Single SQLite file, no replication. Production: managed
   Postgres with row-level encryption + KMS-wrapped session keys.

9. **PHI_DIAGNOSIS / PHI_MEDICATION dictionary is shallow.** ~40 conditions and
   ~50 drug names. A real deployment needs UMLS / SNOMED-CT / RxNorm
   integration. Sub-threshold matches degrade to opaque tokens (per the NFR),
   so the failure mode is reduced model utility, not leakage.

---

## What I'd build next with one extra day

1. **A coreference-aware second pass.** Run the pipeline output through a
   lightweight model (or just spaCy's coref) to flag pronouns/descriptors that
   refer to known tokens, and replace those too. Closes the biggest live-review
   weakness (PRD Q2).

2. **End-to-end encryption to the LLM provider.** Even though we send tokens,
   the prompt itself is sensitive metadata (e.g., "how many SSN tokens are in
   this document"). HTTPS already covers the wire, but a request-level envelope
   that the LLM provider can't introspect would close the metadata-leak gap.

3. **Real KMS integration for user keys** (AWS KMS or GCP KMS with a local
   stub). Even just wrapping the current per-user keys with a KMS master key
   would be a meaningful production-readiness step.

4. **Audit log signing.** Append-only is half the story; an attacker with disk
   access could remove inconvenient entries. Hash-chained or HMAC-signed
   entries would make tampering detectable.

5. **A `vault.stats` panel for the UI**, restricted to dev mode. Currently
   omitted because exposing counts publicly is a side channel (PLAN §M2), but
   dev-only it's useful for verifying the pipeline visually.

6. **Richer UI verification panels.** Side-by-side diff between the source
   document and what the LLM provider would have seen if obfuscation had been
   off — concrete reassurance for non-engineer stakeholders.

---

## Project layout

```
.
├── audit/              # Append-only event log (schema-enforced PII-free)
├── vault/              # Session-scoped encrypted token/value mapping
├── detection/          # Presidio + custom recognizers
├── obfuscation/        # Strategy pattern over the ABC
│   ├── strategies/     # tokenize, pseudonymize
│   └── engine/         # Detect → replace → splice
├── deobfuscation/      # Token / surrogate restoration
├── store/              # Encrypted at-rest document store + extractors
├── llm_client/         # Async Anthropic wrapper + mocks + LangSmith tracing
├── pipeline/           # End-to-end orchestrator + session manager
├── api/                # FastAPI HTTP layer
├── ui/                 # React + Vite + Tailwind frontend
├── tests/
│   ├── unit/           # 87 tests — module isolation, fast
│   ├── integration/    # 12 tests — full pipeline on fixtures
│   └── fixtures/       # Synthetic medical / legal / financial sources + build.py
├── demo.py             # CLI end-to-end demo
├── docker-compose.yml  # api + ui services
├── pyproject.toml
├── PLAN.html           # Design rationale (this is the "why")
├── PRD.md              # Requirements (source of truth)
└── SPRINT.html         # Build progress
```

---

*Built for the YourAI Senior Engineer take-home. Confidential — for review use
only.*
