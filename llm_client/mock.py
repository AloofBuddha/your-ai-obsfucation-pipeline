"""MockLLMClient — for tests and offline demos. No network calls."""
from __future__ import annotations

import re

from llm_client.base import LLMClient


class EchoLLMClient(LLMClient):
    """Returns a templated response containing all tokens from the user message.

    Useful for end-to-end pipeline tests: we know exactly which tokens will
    appear in the 'LLM response' (the same ones we sent), so we can verify the
    deobfuscation pass restores them correctly.
    """

    _TOKEN_RE = re.compile(r"\[[A-Z_]+_[a-z2-7]{8}\]")
    _REDACTED_RE = re.compile(r"\[REDACTED_[A-Z_]+\]")

    def __init__(self, template: str | None = None) -> None:
        self._template = template

    async def generate(self, *, system: str, user: str) -> str:  # noqa: ARG002
        if self._template:
            return self._template.format(user=user)
        tokens = self._TOKEN_RE.findall(user) + self._REDACTED_RE.findall(user)
        if tokens:
            # Tokenization mode — stitch tokens into a paragraph that exercises
            # possessive ("X's record") and multi-entity ("X and Y") forms.
            if len(tokens) == 1:
                return f"Regarding {tokens[0]}: I have reviewed the document."
            return (
                f"Regarding {tokens[0]}'s record, I noticed mentions of "
                + ", ".join(tokens[1:])
                + f". Summary: {tokens[0]} appears central to the document."
            )
        # No tokens — likely pseudonymization mode (surrogates are plain strings).
        # Echo the user message back so all surrogates appear in the response and
        # can be restored. Keeps the mock useful in pseudonymization tests.
        return f"Based on the input you provided: {user}"


class CannedLLMClient(LLMClient):
    """Returns a fixed string regardless of input. For tests that need
    deterministic LLM output unrelated to tokens."""

    def __init__(self, response: str) -> None:
        self._response = response

    async def generate(self, *, system: str, user: str) -> str:  # noqa: ARG002
        return self._response
