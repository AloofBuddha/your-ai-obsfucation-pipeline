"""Restoration — turn the LLM's response back into user-facing text.

Two strategy-specific paths:

  Tokenization: tokens are bracketed [TYPE_xxxxxxxx] strings. Match via TOKEN_RE,
  look up in vault, replace. Tokens not in vault (e.g. session destroyed mid-flight)
  become [UNRESOLVED_TOKEN] with an audit event.

  Pseudonymization: replacements are Faker-generated strings like "Michael Torres".
  The LLM may inflect them ("Torres's", "Torreses"). For each known surrogate in the
  vault, find occurrences in the response (case-insensitive with possessive/plural
  suffix tolerance) and replace with the original. Longest surrogate first to
  prevent partial matches.

A final invariant: after restoration, no TOKEN_RE match should remain in the
output. We assert that and surface a hard error rather than silently leak.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from audit import AuditEvent, AuditLog
from vault import TOKEN_RE, SessionVault

UNRESOLVED_SENTINEL = "[UNRESOLVED_TOKEN]"


class TokenLeakError(RuntimeError):
    """Raised if a bracketed token survives the restoration pass. Indicates a
    bug or an inconsistent vault state; surfaced loudly rather than letting the
    token reach the user.
    """


class Deobfuscator:
    def __init__(self, audit: AuditLog) -> None:
        self._audit = audit

    async def restore(
        self,
        text: str,
        vault: SessionVault,
        strategy_name: str,
    ) -> str:
        if strategy_name == "tokenize":
            restored = await self._restore_tokens(text, vault)
        elif strategy_name == "pseudonymize":
            token_restored = await self._restore_tokens(text, vault)
            restored = await self._restore_pseudonyms(token_restored, vault)
        else:
            raise ValueError(f"Unknown strategy for restoration: {strategy_name!r}")

        # Post-condition: no bracketed [TYPE_xxxxxxxx] tokens may survive.
        # [REDACTED_*] and [UNRESOLVED_TOKEN] are allowed — they're explicit
        # markers, not data leaks.
        leftover = TOKEN_RE.findall(restored)
        if leftover:
            raise TokenLeakError(
                f"Restoration left tokens unresolved: {leftover[:5]}"
            )
        return restored

    async def _restore_tokens(self, text: str, vault: SessionVault) -> str:
        """Tokenization path. Tokens are unambiguous regex matches."""
        matches = list(TOKEN_RE.finditer(text))
        originals = await vault.lookup_many([m.group(0) for m in matches])
        events: list[AuditEvent] = []
        # Right-to-left so offsets stay valid.
        buf = text
        for m in reversed(matches):
            token = m.group(0)
            original = originals.get(token)
            if original is None:
                events.append(
                    AuditEvent(
                        session_id=vault.session_id,
                        action="DEOBFUSCATE",
                        token_id=token,
                        metadata={"resolved": False},
                    )
                )
                replacement = UNRESOLVED_SENTINEL
            else:
                events.append(
                    AuditEvent(
                        session_id=vault.session_id,
                        action="DEOBFUSCATE",
                        token_id=token,
                        metadata={"resolved": True},
                    )
                )
                replacement = original
            buf = buf[: m.start()] + replacement + buf[m.end() :]
        await self._emit_many(events)
        return buf

    async def _emit_many(self, events: Sequence[AuditEvent]) -> None:
        emit_many = getattr(self._audit, "emit_many", None)
        if emit_many is not None:
            await emit_many(events)
            return
        for event in events:
            await self._audit.emit(event)

    async def _restore_pseudonyms(self, text: str, vault: SessionVault) -> str:
        """Pseudonymization path. Surrogates may appear inflected — match with
        possessive/plural-suffix tolerance.

        Boundary handling: use lookaround for non-word chars rather than \b,
        because surrogates may end in non-word chars (e.g., "Jr.") where \b
        wouldn't fire.

        Inflection: capture the suffix (e.g. "'s") and preserve it on
        replacement so "Michael Torres's chart" -> "John Smith's chart".

        Longest-surrogate-first prevents "Michael" from matching inside
        "Michael Torres".
        """
        entries = await vault.all_replacements()
        # Skip token-format entries (defensive: in case a session somehow mixes strategies).
        entries = [(r, t) for (r, t) in entries if not TOKEN_RE.fullmatch(r)]
        entries.sort(key=lambda e: -len(e[0]))

        # spans: (start, end_of_match, replacement_text). Collected longest-first,
        # then overlaps are filtered.
        spans: list[tuple[int, int, str]] = []
        for surrogate, _type in entries:
            original = await vault.lookup(surrogate)
            if original is None:
                continue
            pattern = re.compile(
                r"(?<!\w)" + re.escape(surrogate) + r"(['’]s|s)?(?!\w)",
                re.IGNORECASE,
            )
            for m in pattern.finditer(text):
                # Skip if this span is contained in an already-collected one.
                if any(s <= m.start() and m.end() <= e for s, e, _ in spans):
                    continue
                suffix = m.group(1) or ""
                replacement_text = original + suffix
                spans.append((m.start(), m.end(), replacement_text))
                await self._audit.emit(
                    AuditEvent(
                        session_id=vault.session_id,
                        action="DEOBFUSCATE",
                        token_id=surrogate,
                        metadata={"resolved": True, "inflected": bool(suffix)},
                    )
                )

        spans.sort(key=lambda x: x[0], reverse=True)
        buf = text
        for start, end, replacement_text in spans:
            buf = buf[:start] + replacement_text + buf[end:]
        return buf
