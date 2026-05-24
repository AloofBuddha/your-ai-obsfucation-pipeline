"""PipelineResult — the four pipeline stages, returned to the API so the UI can
render the dev-mode panels."""
from __future__ import annotations

from pydantic import BaseModel

from detection.entity import Entity


class PipelineResult(BaseModel):
    """All intermediate stages of a pipeline run.

    Each stage is included so the UI's dev mode can show the security
    properties (no PII in panel 3, restored output in panel 4). None of these
    fields cross a trust boundary — they go API -> UI on the same host.
    """

    user_query: str
    obfuscated_query: str
    document_text: str
    detected_entities: list[Entity]
    obfuscated_document: str
    obfuscated_prompt: str          # full string sent to the LLM
    llm_response_raw: str            # response containing tokens/surrogates
    restored_response: str           # final user-facing text
    strategy_name: str
