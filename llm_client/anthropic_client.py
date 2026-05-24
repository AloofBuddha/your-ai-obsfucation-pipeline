"""Async Anthropic wrapper."""
from __future__ import annotations

from anthropic import AsyncAnthropic

DEFAULT_SYSTEM_PROMPT = """\
You are an assistant operating inside a secure pipeline. The user's text \
contains bracketed identifiers like [PHI_NAME_xxxxxxxx], [PII_SSN_yyyyyyyy], \
or [REDACTED_PHI_DIAGNOSIS]. These are placeholders for sensitive information \
that has been removed for privacy. Rules:

1. Preserve these placeholders verbatim — do not paraphrase, translate, or \
expand them.
2. When you reference an entity, use its placeholder. Example: instead of \
"the patient", write "[PHI_NAME_k7a2mqpz]".
3. Do not attempt to guess or invent values for the placeholders.
4. Otherwise behave normally and follow the user's instructions."""


class AnthropicLLMClient:
    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2048,
        default_system: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._default_system = default_system

    @property
    def model(self) -> str:
        return self._model

    async def generate(self, *, system: str, user: str) -> str:
        # If caller passes empty system, use the default — keeps the security
        # contract in place by default.
        effective_system = system or self._default_system
        message = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=effective_system,
            messages=[{"role": "user", "content": user}],
        )
        # message.content is a list of content blocks; pick the text ones.
        parts: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        return "".join(parts)
