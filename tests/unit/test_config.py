"""Configuration loading tests."""
from __future__ import annotations

from api.config import Settings


def test_langsmith_config_uses_current_env_names(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://example.langsmith.test/")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "trace-project")

    settings = Settings(_env_file=None)

    assert settings.langsmith_tracing is True
    assert settings.langsmith_endpoint == "https://example.langsmith.test/"
    assert settings.langsmith_api_key == "ls-key"
    assert settings.langsmith_project == "trace-project"


def test_legacy_langchain_env_names_are_ignored(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LANGCHAIN_API_KEY", "old-key")
    monkeypatch.setenv("LANGCHAIN_PROJECT", "old-project")
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)

    settings = Settings(_env_file=None)

    assert settings.langsmith_api_key == ""
    assert settings.langsmith_project == "secure-context-pipeline"
