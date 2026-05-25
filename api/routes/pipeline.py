"""Pipeline run endpoint."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import TypeAlias, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from api.schemas import RunPipelineRequest
from pipeline import Pipeline, PipelineResult, SessionNotFoundError
from vault import SessionExpiredError

router = APIRouter(prefix="/sessions", tags=["pipeline"])
SSEData: TypeAlias = dict[str, object]


@router.post("/{session_id}/pipeline", response_model=PipelineResult)
async def run_pipeline(
    session_id: str,
    body: RunPipelineRequest,
    request: Request,
) -> PipelineResult:
    try:
        pipeline = cast(
            Pipeline,
            request.app.state.app_state.manager.get(session_id),
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"}) from e

    try:
        return await pipeline.run(doc_id=body.doc_id, query=body.user_query)
    except SessionExpiredError as e:
        raise HTTPException(status_code=409, detail={"error": "session_expired"}) from e
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "document_not_found"}) from e


def _sse(event: str, data: SSEData) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


@router.post("/{session_id}/pipeline/stream")
async def stream_pipeline(
    session_id: str,
    body: RunPipelineRequest,
    request: Request,
) -> StreamingResponse:
    try:
        pipeline = cast(
            Pipeline,
            request.app.state.app_state.manager.get(session_id),
        )
    except SessionNotFoundError as e:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"}) from e

    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, SSEData]] = asyncio.Queue()

        async def progress(
            stage: str,
            status: str,
            metadata: dict[str, str | int | float | bool | None],
        ) -> None:
            await queue.put(
                (
                    "progress",
                    {
                        "stage": stage,
                        "status": status,
                        "metadata": metadata,
                    },
                )
            )

        async def run() -> None:
            try:
                result = await pipeline.run_with_progress(
                    doc_id=body.doc_id,
                    query=body.user_query,
                    progress=progress,
                )
                await queue.put(("result", result.model_dump(mode="json")))
            except SessionExpiredError:
                await queue.put(("error", {"error": "session_expired"}))
            except FileNotFoundError:
                await queue.put(("error", {"error": "document_not_found"}))
            except Exception as exc:
                await queue.put(("error", {"error": "pipeline_failed", "detail": str(exc)}))
            finally:
                await queue.put(("done", {}))

        task = asyncio.create_task(run())
        try:
            while True:
                event, data = await queue.get()
                if event == "done":
                    break
                yield _sse(event, data)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(events(), media_type="text/event-stream")
