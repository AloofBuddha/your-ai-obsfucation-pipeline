"""Optional LangSmith tracing wrapper."""
from __future__ import annotations

from llm_client.base import LLMClient


class TracedLLMClient:
    """Wraps another LLMClient and ships traces to LangSmith if available."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        api_key: str,
        project: str = "secure-context-pipeline",
        endpoint: str = "https://api.smith.langchain.com/",
    ) -> None:
        self._inner = inner
        self._project = project
        # Defer import so an unset env var leaves us with zero LangSmith deps.
        self._client = None
        if api_key:
            try:
                from langsmith import Client  # type: ignore[import-not-found]

                self._client = Client(api_key=api_key, api_url=endpoint)
            except ImportError:
                # Optional dep not installed; silently skip tracing.
                self._client = None

    async def generate(self, *, system: str, user: str) -> str:
        if self._client is None:
            return await self._inner.generate(system=system, user=user)
        # Emit a trace event around the call. LangSmith's async support varies
        # by SDK version; we keep this best-effort.
        run = self._client.create_run(
            project_name=self._project,
            name="llm_generate",
            run_type="llm",
            inputs={"system": system, "user": user},
        )
        try:
            output = await self._inner.generate(system=system, user=user)
        except Exception as e:
            self._client.update_run(run_id=run.id, error=str(e), end_time=None)
            raise
        self._client.update_run(run_id=run.id, outputs={"output": output})
        return output


def maybe_trace(
    client: LLMClient,
    *,
    enabled: bool = False,
    api_key: str = "",
    project: str = "secure-context-pipeline",
    endpoint: str = "https://api.smith.langchain.com/",
) -> LLMClient:
    """Helper used by the pipeline. Wraps `client` if tracing env is set."""
    if enabled and api_key:
        return TracedLLMClient(
            client,
            api_key=api_key,
            project=project,
            endpoint=endpoint,
        )
    return client
