"""LLM client tests — mock-based; real Anthropic calls are integration-only."""
from __future__ import annotations

from llm_client import CannedLLMClient, EchoLLMClient, TracedLLMClient, maybe_trace


async def test_echo_extracts_and_returns_tokens() -> None:
    client = EchoLLMClient()
    response = await client.generate(
        system="",
        user="Tell me about [PHI_NAME_k7a2mqpz] and [PHI_DIAGNOSIS_a3bcde2f].",
    )
    assert "[PHI_NAME_k7a2mqpz]" in response
    assert "[PHI_DIAGNOSIS_a3bcde2f]" in response


async def test_echo_includes_redacted_sentinels() -> None:
    client = EchoLLMClient()
    response = await client.generate(
        system="",
        user="What about [REDACTED_PHI_DIAGNOSIS]?",
    )
    assert "[REDACTED_PHI_DIAGNOSIS]" in response


async def test_echo_handles_no_tokens() -> None:
    client = EchoLLMClient()
    response = await client.generate(system="", user="Hello world.")
    # Should still return a non-empty string.
    assert response


async def test_canned_returns_fixed_string() -> None:
    client = CannedLLMClient("FIXED RESPONSE")
    assert await client.generate(system="x", user="y") == "FIXED RESPONSE"


def test_maybe_trace_requires_enabled_and_key() -> None:
    client = CannedLLMClient("ok")

    assert maybe_trace(client, enabled=False, api_key="key") is client
    assert maybe_trace(client, enabled=True, api_key="") is client


def test_maybe_trace_wraps_when_enabled_with_key() -> None:
    client = CannedLLMClient("ok")

    traced = maybe_trace(client, enabled=True, api_key="key")

    assert isinstance(traced, TracedLLMClient)
